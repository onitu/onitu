import base64
import os
import requests
import hashlib
import threading
import time
import datetime

from onitu.plug import Plug, ServiceError
from onitu.escalator.client import EscalatorClosed

plug = Plug()
hubic = None

# 25Mo (To avoid lot of segmented files)
MIN_CHUNK_SIZE = 25000000
SEGMENTS_FOLDER = 'segmented_files/'


class Hubic:
    def __init__(self, client_id, client_secret, hubic_refresh_token, root):
        self.client_id = client_id
        self.client_secret = client_secret
        self.hubic_refresh_token = hubic_refresh_token
        self.hubic_token = "falsetoken"
        self.os_endpoint = None
        self.os_token = None
        self.root = root

        # Get openstacks credentials
        self._get_openstack_credentials()

        # Create the root folder if doesn't exist
        self.create_folders(self.root, True)

    # ############################ OPENSTACK ##################################

    def _os_renew_token(self, method, uri, data, headers, limit):
        self._get_openstack_credentials()
        return self.os_call(method, uri, data, headers, limit)

    def os_call(self, method, uri, data=None, headers={}, limit=3):

        req = getattr(requests, method.lower())
        headers['X-Auth-Token'] = self.os_token
        url = self.os_endpoint + '/' + uri

        result = req(url, headers=headers, data=data)
        if result.status_code == 403:
            if limit > 0:
                limit = limit - 1
                return self._os_renew_token(method, uri, data, headers, limit)
        else:
            result.raise_for_status()

        return result

    def _get_openstack_credentials(self):

        openstack_tokens = self._hubic_call('GET',
                                            'account/credentials').json()
        self.os_endpoint = openstack_tokens['endpoint']
        self.os_token = openstack_tokens['token']

    # ############################## HUBIC ####################################

    def _hubic_renew_token(self, method, uri, data, headers, limit):

        application_token = base64.b64encode(self.client_id + ":" +
                                             self.client_secret)
        url = "https://api.hubic.com/oauth/token/"
        response = requests.post(
            url,
            data={"grant_type": "refresh_token",
                  "refresh_token": self.hubic_refresh_token},
            headers={'Authorization': 'Basic ' + application_token}
            )

        self.hubic_token = response.json()["access_token"]
        return self._hubic_call(method, uri, data, headers, limit)

    def _hubic_call(self, method, uri, data=None, headers={}, limit=3):

        req = getattr(requests, method.lower())
        headers['Authorization'] = "Bearer " + self.hubic_token
        url = 'https://api.hubic.com/1.0/' + uri

        result = req(url, headers=headers, data=data)
        json = result.json()
        if (result.status_code == 401 and json['error'] == 'invalid_token'):
            if limit > 0:
                limit = limit - 1
                return self._hubic_renew_token(method, uri, data,
                                               headers, limit)
        else:
            result.raise_for_status()

        return result

    def get_path(self, filename):
        return str(os.path.join(self.root, filename))

    def get_object_details(self, path):
        """ Return a dict with: content-length, accept-ranges,
        last-modified, x-object-manifest, x-timestamp, etag,
        x-trans-id, date, content-type """

        try:
            res = self.os_call('head', 'default/' + path)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                "Cannot get object details on file '{}': {}".format(path, e)
                )
        return res.headers

    def create_folders(self, name, with_root=False):

        full_path = ''
        folders = name.split('/')
        for f in folders:
            full_path = os.path.join(full_path, f)
            if with_root is True:
                path = full_path
            else:
                path = self.get_path(full_path)

            try:
                return self.os_call(
                    'put', 'default/' + path, None,
                    {'Content-Type': 'application/directory'}
                    ).text.split('\n')
            except requests.exceptions.RequestException as e:
                raise ServiceError(
                    "Cannot create folder '{}': {}".format(path, e)
                    )

# ############################## WATCHER ######################################


class CheckChanges(threading.Thread):
    """A class spawned in a thread to poll for changes on the HUBIC bucket.
    HUBIC hasn't any bucket watching system in its API, so the best we can
    do is periodically polling the bucket's contents and compare the
    timestamps."""

    def __init__(self, root, timer):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer
        self.root = root

    def check_changes(self, path=''):
        """ Detects changes in the given folder and its subfolders and
        launches the download if needed"""

        global plug
        global hubic

        folder_content = self.list_folder(hubic.get_path(path))
        for f in folder_content:
            # to avoid dowload of segments folder content
            if (not f) or (f[:len(SEGMENTS_FOLDER)] == SEGMENTS_FOLDER):
                continue

            filename = f[len(self.root) + 1 if self.root else 0:]
            details = hubic.get_object_details(f)
            if details['content-type'] == 'application/directory':
                self.check_changes(filename)
            else:
                hubic_rev = time.mktime(
                    datetime.datetime.strptime(details['last-modified'],
                                               "%a, %d %b %Y %X %Z"
                                               ).timetuple())

                metadata = plug.get_metadata(filename)
                onitu_rev = metadata.extra.get('revision', 0.)

                if hubic_rev > onitu_rev:
                    metadata.size = int(
                        hubic.get_object_details(f)['content-length'])
                    metadata.extra['revision'] = hubic_rev
                    plug.update_file(metadata)

    def list_folder(self, path=''):
        global hubic

        full_path = ('default/?path=' + path) if path else 'default'
        try:
            res = hubic.os_call('get', full_path)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                "Cannot get folder details '{}': {}".format(full_path, e)
                )
        return res.text.split('\n')

    def run(self):
        while not self.stop.isSet():
            try:
                self.check_changes()
            except EscalatorClosed:
                # We are closing
                return
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()

# ############################# ONITU BASIC ###################################


@plug.handler()
def set_chunk_size(chunk_size):
    if chunk_size < MIN_CHUNK_SIZE:
        return MIN_CHUNK_SIZE
    else:
        return None


@plug.handler()
def move_file(old_metadata, new_metadata):
    global hubic

    old_filename = hubic.get_path(old_metadata.filename)
    new_filename = hubic.get_path(new_metadata.filename)

    hubic.create_folders(os.path.dirname(new_metadata.filename))

    headers = {'X-Copy-From': 'default/' + old_filename}

    try:
        hubic.os_call('put', 'default/' + new_filename, headers=headers)
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            "Cannot move file '{}' to '{}': {}".format(
                old_filename, new_filename, e
                )
            )

    delete_file(old_metadata)


@plug.handler()
def delete_file(metadata):
    global hubic

    multipart = ''
    # directory = no extra
    if ('chunked' in metadata.extra) and (metadata.extra['chunked'] is True):
        multipart = '?multipart-manifest=delete'
    try:
        hubic.os_call('delete', 'default/' + hubic.get_path(metadata.filename)
                      + multipart)
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            "Cannot delete file '{}': {}".format(metadata.filename, e)
            )


@plug.handler()
def start_upload(metadata):
    """Initialize a new upload.
    This handler is called when a new transfer is started."""

    global hubic

    hubic.create_folders(os.path.dirname(metadata.filename))

    manifest_link = hashlib.md5(hubic.get_path(metadata.filename) +
                                str(time.time()))

    metadata.extra['manifest'] = SEGMENTS_FOLDER + manifest_link.hexdigest()
    metadata.extra['chunked'] = False
    metadata.extra['chunk_size'] = None
    metadata.write()

    if metadata.size == 0:
        upload_file(metadata, None)


@plug.handler()
def upload_file(metadata, data):
    global hubic

    try:
        hubic.os_call(
            'put', 'default/' + hubic.get_path(metadata.filename), data
            )
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            "Cannot upload file '{}': {}".format(metadata.filename, e)
            )


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    """Write a chunk in a file at a given offset."""

    global hubic

    chunk_size = len(chunk)
    if metadata.extra['chunk_size'] is None:
        metadata.extra['chunk_size'] = chunk_size
    if metadata.size == chunk_size:
        upload_file(metadata, chunk)
    else:
        metadata.extra['chunked'] = True
        metadata.write()
        chunk_num = str((offset / metadata.extra['chunk_size']))
        try:
            hubic.os_call('put', 'default/' + metadata.extra['manifest'] +
                          '/' + chunk_num, data=chunk)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                "Cannot upload chunk number {} of file '{}': {}".format(
                    chunk_num, metadata.filename, e
                    )
                )


@plug.handler()
def end_upload(metadata):
    """Called when a transfer is over."""

    global hubic
    if metadata.extra['chunked'] is True:
        headers = {
            'X-Object-Manifest': 'default/'
            + metadata.extra['manifest']
            }

        try:
            hubic.os_call('put', 'default/' +
                          hubic.get_path(metadata.filename),
                          data=None, headers=headers)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                "Cannot end upload of file '{}': {}".format(
                    metadata.filename, e
                    )
                )

    details = hubic.get_object_details(hubic.get_path(metadata.filename))
    metadata.extra['revision'] = time.mktime(
        datetime.datetime.strptime(details['last-modified'],
                                   "%a, %d %b %Y %X %Z"
                                   ).timetuple())


@plug.handler()
def get_chunk(metadata, offset, size):
    """Return a chunk of a given size,
    starting at the given offset, from a file."""

    global hubic
    headers = {'Range': str(offset) + '-' + str(offset + size)}
    try:
        return hubic.os_call(
            'get', 'default/' + hubic.get_path(metadata.filename),
            headers=headers).content
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            "Cannot get chunk of file '{}' (offset {}): {}".format(
                metadata.filename, offset, e
                )
            )


# ############################## START #######################################


def start():
    global plug

    # Clean the root
    root = plug.options['root']
    if root.startswith('/'):
        root = root[1:]
    if root.endswith('/'):
        root = root[:-1]

    onitu_client_id = "api_hubic_yExkTKwof2zteYA8kQG4gYFmnmHVJoNl"
    onitu_client_secret = "CWN2NMOVwM4wjsg3RFRMmE6OpUNJhsADLaiduV"
    "49e7SpBsHDAKdtm5WeR5KEaDvc"

    global hubic
    hubic = Hubic(onitu_client_id, onitu_client_secret,
                  plug.options['refresh_token'], root)

    # Launch the changes detection
    check = CheckChanges(root, plug.options['changes_timer'])
    check.daemon = True
    check.start()

    plug.listen()
