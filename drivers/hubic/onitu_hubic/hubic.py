import urllib
import base64
import os
import requests
import hashlib
import threading
import time
import datetime
import json

from onitu.plug import Plug, ServiceError, DriverError
from onitu.escalator.client import EscalatorClosed
from onitu.utils import b, u, n

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
        self.hubic_token = 'falsetoken'
        self.os_endpoint = None
        self.os_token = None
        self.root = root

        # Get openstacks credentials
        self._get_openstack_credentials()

    # ############################ OPENSTACK ##################################

    def os_call(self, method, uri, data=None, headers=None, limit=3):
        req = getattr(requests, method.lower())

        if not headers:
            headers = {}

        if 'X-Auth-Token' not in headers:
            headers['X-Auth-Token'] = self.os_token

        url = n(u'{}/{}'.format(self.os_endpoint, uri))

        for _ in range(limit):
            result = req(url, headers=headers, data=data)
            if result.status_code != 403:
                break
            self._get_openstack_credentials()

        result.raise_for_status()

        return result

    def _get_openstack_credentials(self):
        openstack_tokens = self._hubic_call('GET',
                                            'account/credentials').json()
        self.os_endpoint = openstack_tokens['endpoint']
        self.os_token = openstack_tokens['token']

    # ############################## HUBIC ####################################

    def _hubic_renew_token(self):
        application_token = base64.b64encode(b(self.client_id + ':' +
                                               self.client_secret))
        url = 'https://api.hubic.com/oauth/token/'
        response = requests.post(
            url,
            data={'grant_type': 'refresh_token',
                  'refresh_token': self.hubic_refresh_token},
            headers={'Authorization': 'Basic ' + n(application_token)}
        )

        if response.status_code != 200:
            raise DriverError(
                "Cannot connect to Hubic, your token might have expired"
            )

        self.hubic_token = response.json()['access_token']

    def _hubic_call(self, method, uri, data=None, headers={}, limit=3):
        for _ in range(limit):
            req = getattr(requests, method.lower())
            headers['Authorization'] = 'Bearer ' + self.hubic_token
            url = 'https://api.hubic.com/1.0/' + uri

            result = req(url, headers=headers, data=data)
            json = result.json()

            if result.status_code == 401 and json['error'] == 'invalid_token':
                self._hubic_renew_token()
            else:
                break

        result.raise_for_status()
        return result

    def get_path(self, filename):
        return u(os.path.join(self.root, filename))

    def get_object_details(self, path):
        """ Return a dict with: content-length, accept-ranges,
        last-modified, x-object-manifest, x-timestamp, etag,
        x-trans-id, date, content-type """
        try:
            plug.logger.debug("Getting info about file {}", path)
            res = self.os_call('head', 'default/' + path)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                u"Cannot get object details on file '{}': {}".format(path, e)
            )
        return res.headers


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

    def check_changes(self):
        """Detects changes in the given folder and its subfolders and
        launches the download if needed"""
        folder_content = self.list_folder(self.root)
        for f in folder_content:
            # to avoid dowload of segments folder content
            if (not f) or (f[:len(SEGMENTS_FOLDER)] == SEGMENTS_FOLDER):
                continue

            filename = f[len(self.root) + 1 if self.root else 0:]
            details = hubic.get_object_details(f)

            if details['content-type'] == 'application/directory':
                continue

            hubic_rev = time.mktime(
                datetime.datetime.strptime(details['last-modified'],
                                           '%a, %d %b %Y %X %Z'
                                           ).timetuple())

            metadata = plug.get_metadata(filename)
            onitu_rev = metadata.extra.get('revision', 0.)

            if hubic_rev > onitu_rev:
                metadata.size = int(
                    hubic.get_object_details(f)['content-length'])
                metadata.extra['revision'] = hubic_rev
                plug.update_file(metadata)

    def list_folder(self, path):
        try:
            plug.logger.debug("Listing files in directory {}", path)
            res = hubic.os_call('get', 'default/?prefix=' + path)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                u"Cannot get folder details '{}': {}".format(path, e)
            )
        files = tuple(e for e in res.text.split('\n') if e)
        plug.logger.debug("Found {} files in directory {}", len(files), path)
        return files

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
    old_filename = old_metadata.path
    new_filename = new_metadata.path

    headers = {'X-Copy-From': 'default/' + n(old_filename)}

    try:
        hubic.os_call('put', 'default/' + new_filename, headers=headers)
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            u"Cannot move file '{}' to '{}': {}".format(
                old_filename, new_filename, e
            )
        )

    delete_file(old_metadata)


@plug.handler()
def delete_file(metadata):
    multipart = ''
    # directory = no extra
    if ('chunked' in metadata.extra) and (metadata.extra['chunked'] is True):
        multipart = '?multipart-manifest=delete'
    try:
        hubic.os_call('delete', 'default/' + metadata.path
                      + multipart)
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            u"Cannot delete file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def start_upload(metadata):
    """Initialize a new upload.
    This handler is called when a new transfer is started."""
    manifest_link = hashlib.md5(b(metadata.path) + b(str(time.time())))

    metadata.extra['manifest'] = SEGMENTS_FOLDER + manifest_link.hexdigest()
    metadata.extra['chunked'] = False
    metadata.extra['chunk_size'] = None
    metadata.write()

    if metadata.size == 0:
        upload_file(metadata, None)


@plug.handler()
def upload_file(metadata, data):
    try:
        hubic.os_call('put', 'default/' + metadata.path, data)
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            u"Cannot upload file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    """Write a chunk in a file at a given offset."""
    chunk_size = len(chunk)
    if metadata.extra['chunk_size'] is None:
        metadata.extra['chunk_size'] = chunk_size
    if metadata.size == chunk_size:
        upload_file(metadata, chunk)
    else:
        metadata.extra['chunked'] = True
        metadata.write()
        chunk_num = u((offset / metadata.extra['chunk_size']))
        try:
            hubic.os_call('put', 'default/' + metadata.extra['manifest'] +
                          '/' + chunk_num, data=chunk)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                u"Cannot upload chunk number {} of file '{}': {}".format(
                    chunk_num, metadata.filename, e
                )
            )


@plug.handler()
def end_upload(metadata):
    """Called when a transfer is over."""
    if metadata.extra['chunked'] is True:
        headers = {
            'X-Object-Manifest': 'default/' + n(metadata.extra['manifest'])
        }

        try:
            hubic.os_call('put', 'default/' +
                          metadata.path,
                          data=None, headers=headers)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                u"Cannot end upload of file '{}': {}".format(
                    metadata.filename, e
                )
            )

    details = hubic.get_object_details(metadata.path)
    metadata.extra['revision'] = time.mktime(
        datetime.datetime.strptime(details['last-modified'],
                                   '%a, %d %b %Y %X %Z'
                                   ).timetuple())


@plug.handler()
def get_chunk(metadata, offset, size):
    """Return a chunk of a given size,
    starting at the given offset, from a file."""
    headers = {'Range': '{}-{}'.format(offset, offset + size)}
    try:
        return hubic.os_call(
            'get', u'default/' + metadata.path,
            headers=headers).content
    except requests.exceptions.RequestException as e:
        raise ServiceError(
            u"Cannot get chunk of file '{}' (offset {}): {}".format(
                metadata.filename, offset, e
            )
        )


@plug.handler()
def get_oauth_url(redirect_uri):
    return (
        "https://api.hubic.com/oauth/auth/?client_id={}&redirect_uri={}&scope="
        "usage.r,account.r,getAllLinks.r,credentials.r,activate.w,links.drw"
        "&response_type=code"
    ).format(hubic.client_id, urllib.quote_plus(redirect_uri))


@plug.handler()
def set_oauth_token(query_param):
    query_param = json.loads(query_param)

    code = query_param["code"]
    redirect_uri = query_param["redirect_uri"]

    application_token = base64.b64encode(
        "{}".format(hubic.client_id, hubic.client_secret)
    )
    url = "https://api.hubic.com/oauth/token/"

    response = requests.post(
        url,
        data={
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={
            'Authorization': 'Basic ' + application_token
        }
    )

    if response.status_code == 400:
        raise Exception('An invalid request was submitted')
    elif not response.ok:
        raise Exception('The provided email address and/or pass are incorrect')

    access_token = response.json()["refresh_token"]

    db = plug.entry_db
    db.put("access_token", access_token)
    start()

# ############################## START #######################################


def start():
    global plug, hubic

    db = plug.entry_db
    access_token = db.get("access_token", default=None)

    if access_token is None:
        access_token = plug.options['refresh_token']

    root = plug.root.strip('/')

    hubic = Hubic(
        plug.options['client_id'],
        plug.options['client_secret'],
        access_token,
        root
    )

    # Launch the changes detection
    check = CheckChanges(root, plug.options[u'changes_timer'])
    check.daemon = True
    check.start()

    plug.listen()
