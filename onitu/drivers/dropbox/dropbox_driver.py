import urllib3
import threading

import dropbox
from dropbox.session import DropboxSession
from dropbox.client import DropboxClient

from onitu.plug import Plug
from onitu.plug import DriverError, ServiceError

# Onitu has a unique set of App key and secret to identify it.
ONITU_APP_KEY = "6towoytqygvexx3"
ONITU_APP_SECRET = "90hsd4z4d8eu3pp"
ONITU_ACCESS_TYPE = "dropbox"  # full access to user's Dropbox (may change)
plug = Plug()
dropbox_client = None


def connect_client():
    """Helper function to connect to Dropbox via the API, using access token
    keys to authenticate Onitu."""
    global dropbox_client
    plug.logger.debug("Attempting Dropbox connection using Onitu credentials")
    sess = DropboxSession(ONITU_APP_KEY,
                          ONITU_APP_SECRET,
                          ONITU_ACCESS_TYPE)
    # Use the OAuth access token previously retrieved by the user and typed
    # into Onitu configuration.
    sess.set_token(plug.options['access_key'], plug.options['access_secret'])
    dropbox_client = DropboxClient(sess)
    plug.logger.debug("Dropbox connection with Onitu credentials successful")
    return dropbox_client


def root_prefixed_filename(filename):
    name = plug.options['root']
    if not name.endswith('/'):
        name += '/'
    name += filename
    return name


def remove_upload_id(metadata):
    up_id = metadata.extra.get('upload_id', None)
    if up_id is not None:
        plug.logger.debug("Removing upload ID '{}' from '{}' metadata"
                          .format(up_id, metadata.filename))
        del metadata.extra['upload_id']


@plug.handler()
def get_chunk(metadata, offset, size):
    filename = root_prefixed_filename(metadata.filename)
    plug.logger.debug("Getting chunk of size {} from file {}"
                      " from offset {} to {}"
                      .format(size, filename, offset, offset+(size-1)))
    # content_server = True is required to let us access to file contents,
    # not only metadata
    try:
        url, params, headers = dropbox_client.request("/files/dropbox/{}"
                                                      .format(filename),
                                                      method="GET",
                                                      content_server=True)
        # Using the 'Range' HTTP Header for offseting.
        headers['Range'] = "bytes={}-{}".format(offset, offset+(size-1))
        chunk = dropbox_client.rest_client.request("GET",
                                                   url,
                                                   headers=headers,
                                                   raw_response=True)
    except (dropbox.rest.ErrorResponse, dropbox.rest.RESTSocketError) as err:
        raise ServiceError("Cannot get chunk of '{}' - {}"
                           .format(filename, err))
    plug.logger.debug("Getting chunk of size {} from file {}"
                      " from offset {} to {} - Done"
                      .format(size, filename, offset, offset+(size-1)))
    return chunk.read()


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    filename = root_prefixed_filename(metadata.filename)
    # Get the upload id of this file. None = upload's first time
    up_id = metadata.extra.get('upload_id', None)
    plug.logger.debug("Uploading chunk of size {}"
                      " to file {} at offset {} - Upload ID: {}"
                      .format(len(chunk), filename, offset, up_id))
    # upload_chunk returns a tuple containing the offset and the upload ID of
    # this upload. The offset isn't very useful
    (_, up_id) = dropbox_client.upload_chunk(file_obj=chunk,
                                             length=len(chunk),
                                             offset=offset,
                                             upload_id=up_id)
    metadata.extra['upload_id'] = up_id
    metadata.write()
    plug.logger.debug("Storing upload ID {} in metadata".format(up_id))
    plug.logger.debug("Uploading chunk of size {}"
                      " to file {} at offset {} - Done"
                      .format(len(chunk), filename, offset))


@plug.handler()
def end_upload(metadata):
    filename = root_prefixed_filename(metadata.filename)
    plug.logger.debug("Ending upload of '{}'".format(filename))
    # Note the difference between dropbox_client (the global variable), and
    # dropbox.client, the access to the dropbox.client submodule
    path = "/commit_chunked_upload/{}/{}".format(
        dropbox_client.session.root,
        dropbox.client.format_path(filename)
        )
    up_id = metadata.extra.get('upload_id', None)
    # At this point we should have the upload ID.
    if up_id is None:
        # empty file. We must upload one.
        if metadata.size == 0:
            (_, upload_id) = dropbox_client.upload_chunk('', 0)
            up_id = upload_id
        else:
            raise DriverError("No upload ID for {}".format(filename))
    params = dict(overwrite=True, upload_id=up_id)
    try:
        url, params, headers = dropbox_client.request(path,
                                                      params,
                                                      content_server=True)
        resp = dropbox_client.rest_client.POST(url, params, headers)
    except (dropbox.rest.ErrorResponse, dropbox.rest.RESTSocketError) as err:
        raise ServiceError("Cannot commit chunked upload for '{}' - {}"
                           .format(filename, err))
    remove_upload_id(metadata)
    metadata.size = resp['bytes']
    metadata.extra['revision'] = resp['revision']
    metadata.write()
    plug.logger.debug("Storing revision {} for '{}'"
                      .format(resp['revision'], filename))
    plug.logger.debug("Ending upload of '{}' - Done".format(filename))


@plug.handler()
def abort_upload(metadata):
    remove_upload_id(metadata)
    metadata.write()


@plug.handler()
def move_file(old_metadata, new_metadata):
    old_filename = root_prefixed_filename(old_metadata.filename)
    new_filename = root_prefixed_filename(new_metadata.filename)
    plug.logger.debug("Moving '{}' to '{}'".format(old_filename, new_filename))
    try:
        new_db_metadata = dropbox_client.file_move(from_path=old_filename,
                                                   to_path=new_filename)
    except dropbox.rest.ErrorResponse as err:
        raise ServiceError("Cannot move file {} - {}"
                           .format(old_filename, err))
    # Update revision of new object
    # This permits to not detect a new update in the check changes thread
    # and thus avoids an useless transfer the other way around

    new_metadata.extra['revision'] = new_db_metadata['revision']
    new_metadata.write()
    plug.logger.debug("Storing revision '{}' for file '{}'"
                      .format(new_db_metadata['revision'], new_filename))

    plug.logger.debug("Moving '{}' to '{}' - Done"
                      .format(old_filename, new_filename))


@plug.handler()
def delete_file(metadata):
    filename = root_prefixed_filename(metadata.filename)
    plug.logger.debug("Deleting '{}'".format(filename))
    try:
        dropbox_client.file_delete(filename)
    except dropbox.rest.ErrorResponse as err:
        raise ServiceError("Cannot delete file {} - {}".format(filename, err))
    plug.logger.debug("Deleting '{}' - Done".format(filename))


class CheckChanges(threading.Thread):
    """A class spawned in a thread to poll for changes on the S3 bucket.
    Amazon S3 hasn't any bucket watching system in its API, so the best
    we can do is periodically polling the bucket's contents and compare the
    timestamps."""

    def __init__(self, timer):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer
        # Cursors are used for Dropbox deltas to know from which point it must
        # send changes. A cursor is returned at each delta request, and one
        # ought to send the previous cursor to receive only the changes that
        # have occurred since the last time.
        # Since there is no way to store it in database yet, Onitu starts with
        # an empty cursor, which means the first delta may be a little longer
        # than the subsequent ones.
        self.cursor = None

    def check_dropbox(self):
        plug.logger.debug("Checking dropbox for changes in '{}' folder"
                          .format(plug.options['root']))
        prefix = plug.options['root']
        # Dropbox lists filenames with a leading slash
        if not prefix.startswith('/'):
            prefix = '/' + prefix
        has_more = True
        while has_more:
            # Dropbox doesn't support trailing slashes
            if prefix.endswith('/'):
                prefix = prefix[:-1]
            changes = dropbox_client.delta(cursor=self.cursor,
                                           path_prefix=prefix)
            self.cursor = changes['cursor']
            plug.logger.debug("Processing {} entries"
                              .format(len(changes['entries'])))
            prefix += '/'  # put the trailing slash back
            # Entries are a list of couples (filename, metadatas).
            # However, the filename is case-insensitive. So we have to use the
            # 'path' field of the metadata containing the true, correct-case
            # filename.
            for (db_filename, db_metadata) in changes['entries']:
                # No metadata = deleted file.
                if db_metadata is None:
                    # Retrieve the metadata saved by Dropbox.
                    db_metadata = dropbox_client.metadata(db_filename)
                # Strip the S3 root in the S3 filename for root coherence.
                rootless_filename = db_metadata['path'][len(prefix):]
                plug.logger.debug("Getting metadata of file '{}'"
                                  .format(rootless_filename))
                # empty string = root; since Dropbox doesn't allow path
                # prefixes to be ended by trailing slashes, we can't take it
                # out of the delta and thus must ignore it
                if rootless_filename == '':
                    continue
                metadata = plug.get_metadata(rootless_filename)
                # If the file has been deleted
                if db_metadata.get('is_deleted', False) is True:
                    # If it was synchronized by Onitu, notify the Plug
                    if metadata is not None:
                        plug.logger.debug("Delete detected on Dropbox of "
                                          "file {}".format(metadata.filename))
                        plug.delete_file(metadata)
                    continue
                onitu_rev = metadata.extra.get('revision', -1)
                dropbox_rev = db_metadata['revision']
                if dropbox_rev > onitu_rev:  # Dropbox revision is more recent
                    plug.logger.debug("Updating metadata of file '{}'"
                                      .format(rootless_filename))
                    metadata.size = db_metadata['bytes']
                    metadata.extra['revision'] = db_metadata['revision']
                    plug.update_file(metadata)
            # 'has_more' is set when where Dropbox couldn't send all data
            # in one shot. It's a special case where we're allowed to
            # immediately do another delta with the same cursor to retrieve
            # the remaining data.
            has_more = changes['has_more']

    def run(self):
        while not self.stop.isSet():
            try:
                self.check_dropbox()
            except urllib3.exceptions.MaxRetryError as mre:
                plug.logger.error("Cannot poll changes on Dropbox - {}"
                                  .format(mre))
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start(*args, **kwargs):
    if plug.options['changes_timer'] < 0:
        raise DriverError(
            "The change timer option must be a positive integer")
    connect_client()
    # Start the watching-for-new-files thread
    check = CheckChanges(plug.options['changes_timer'])
    check.daemon = True
    check.start()
    plug.listen()
