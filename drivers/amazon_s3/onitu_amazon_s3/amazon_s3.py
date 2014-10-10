import time
import socket
import threading
import sys
from ssl import SSLError
# Python 2/3 compatibility
if sys.version_info.major == 2:
    from StringIO import StringIO as IOStream
elif sys.version_info.major == 3:
    # In Py3k, chunks are passed as raw bytes. Hence we can't use StringIO
    from io import BytesIO as IOStream

import requests
import tinys3

from onitu.plug import Plug, DriverError, ServiceError
from onitu.escalator.client import EscalatorClosed

plug = Plug()

# Amazon S3 related global variables
S3Conn = None
# To deal with timestamp changes
TIMESTAMP_FMT = '%Y-%m-%dT%H:%M:%S.000Z'
# When using HEAD requests on objects, the timestamp format changes
# it is like e.g. 'Sat, 03 May 2014 04:36:11 GMT'
HEAD_TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S GMT'
# "Each part must be at least 5 MB in size, except the last part."
# http://docs.aws.amazon.com/AmazonS3/latest/API/mpUploadUploadPart.html
S3_MINIMUM_CHUNK_SIZE = 5 << 20
# The number of multipart upload objects we keep in cache
MAX_CACHE_SIZE = 100
# Key: Multipart Upload ID <-> Value: MultipartUpload object
cache = {}


def get_conn():
    """Gets the connection with the Amazon S3 server.
    Raises an error if conn cannot be established"""
    global S3Conn

    S3Conn = tinys3.Connection(plug.options['aws_access_key'],
                               plug.options['aws_secret_key'],
                               default_bucket=plug.options['bucket'], tls=True)
    # Check that the given bucket exists by doing a HEAD request
    try:
        S3Conn.head_bucket()
    except requests.HTTPError as httpe:
        err = "Cannot reach Onitu bucket {}".format(plug.options['bucket'])
        if httpe.response.status_code == 404:
            err += ": The bucket doesn't exist."
        if httpe.response.status_code == 403:
            err += ": Invalid credentials."
        err += " Please check your Amazon S3 configuration. - {}".format(httpe)
        raise DriverError(err)
    return S3Conn


def get_root():
    """Returns Onitu's root for S3. Removes the leading slash if any."""
    root = plug.options['root']
    if root.startswith('/'):  # S3 doesn't like leading slashes
        root = root[1:]
    return root


def root_prefixed_filename(filename):
    """Prefixes the given filename with Onitu's root."""
    root = get_root()
    if not filename.startswith(root):
        rp_filename = root
        if not rp_filename.endswith('/'):
            rp_filename += '/'
        rp_filename += filename
    else:
        rp_filename = filename
    return rp_filename


def get_file_timestamp(filename):
    """Returns the float timestamp based on the
    date format timestamp stored by Amazon.
    Prefixes the given filename with Onitu's root."""
    global S3Conn

    metadata = S3Conn.head_object(filename)
    timestamp = metadata.headers['last-modified']
    # convert timestamp to timestruct...
    timestamp = time.strptime(timestamp, HEAD_TIMESTAMP_FMT)
    # ...timestruct to float
    timestamp = time.mktime(timestamp)
    return timestamp


def add_to_cache(multipart_upload):
    """Caches a multipart upload. Checks that the cache isn't growing
    past MAX_CACHE_SIZE and that it isn't in the cache yet."""
    global cache

    if len(cache) < MAX_CACHE_SIZE:
        if multipart_upload.uploadId not in cache:
            cache[multipart_upload.uploadId] = multipart_upload


def remove_from_cache(multipart_upload):
    """Removes the given MultipartUpload from the cache, if in it."""
    global cache

    if multipart_upload.uploadId in cache:
        del cache[multipart_upload.uploadId]


def get_multipart_upload(metadata):
    """Returns the multipart upload we have the ID of in metadata.
    As Amazon allows several multipart uploads at the same time
    for the same file, the ID is the only unique, reliable descriptor."""
    global S3Conn
    global cache

    multipart_upload = None
    metadata_mp_id = None
    filename = root_prefixed_filename(metadata.filename)
    # Retrieve the stored multipart upload ID
    try:
        metadata_mp_id = metadata.extra['mp_id']
    except KeyError:  # No multipart upload ID
        # Raise now is faster (doesn't go through all the MP uploads)
        raise DriverError("Unable to retrieve multipart upload ID")
    if metadata_mp_id not in cache:
        # Try to only request multipart uploads of this file
        for mp in S3Conn.list_multipart_uploads(prefix=filename):
            # Go through all the multipart uploads
            # to find the one of this transfer
            if mp.uploadId == metadata_mp_id:
                multipart_upload = mp
                add_to_cache(mp)
                break
    else:
        multipart_upload = cache[metadata_mp_id]
    # At this point it shouldn't be None in any case
    if multipart_upload is None:
        raise DriverError("Cannot find upload for file '{}'"
                          .format(filename))
    return multipart_upload


@plug.handler()
def set_chunk_size(chunk_size):
    if chunk_size < S3_MINIMUM_CHUNK_SIZE:
        return S3_MINIMUM_CHUNK_SIZE
    else:
        return None


@plug.handler()
def get_chunk(metadata, offset, size):
    global S3Conn
    global plug

    plug.logger.debug("GET CHUNK {} {} {}".format(metadata.filename, offset,
                                                  size))
    filename = root_prefixed_filename(metadata.filename)
    plug.logger.debug("Downloading {} bytes from the {} key"
                      " on bucket {}".format(size, filename,
                                             plug.options['bucket']))
    # Using the REST API "Range" header.
    headers = {'Range': "bytes={}-{}".format(offset, offset + (size-1))}
    try:
        key = S3Conn.get(filename, headers=headers)
    except requests.HTTPError as httpe:
        err = "Cannot retrieve chunk from {} on bucket {}".format(
            filename, plug.options['bucket'])
        if httpe.response.status_code == 404:
            err += ": the file doesn't exist anymore."
        err += " - {}".format(httpe)
        raise ServiceError(err)
    chunk = key.content
    plug.logger.debug("Download of {} bytes from the {} key on bucket {}"
                      " is complete".format(size, filename,
                                            plug.options['bucket']))
    return chunk


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    multipart_upload = get_multipart_upload(metadata)
    part_num = multipart_upload.number_of_parts() + 1
    plug.logger.debug("Start upload chunk of {}".format(multipart_upload.key))
    plug.logger.debug("Uploading {} bytes at offset {}"
                      " in part {}".format(len(chunk),
                                           offset, part_num))
    # upload_part_from_file expects a file pointer object.
    # we can simulate a file pointer with StringIO or BytesIO.
    # IOStream = StringIO in Python 2, BytesIO in Python 3.
    upload_fp = IOStream(chunk)
    try:
        multipart_upload.upload_part_from_file(upload_fp, part_num)
    except requests.HTTPError as httpe:
        plug.logger.debug("Chunk uploaded: {}".format(chunk))
        plug.logger.debug(httpe.response.text)
        err = "Cannot upload part {} of {} multipart upload - {}"
        err = err.format(part_num, multipart_upload.key, httpe)
        raise ServiceError(err)
    plug.logger.debug("Chunk upload complete")
    add_to_cache(multipart_upload)
    upload_fp.close()


@plug.handler()
def start_upload(metadata):
    global S3Conn
    global plug

    filename = root_prefixed_filename(metadata.filename)
    plug.logger.debug("Starting upload of '{}' to '{}' on bucket {}"
                      .format(metadata.filename, filename,
                              plug.options['bucket']))

    # Create a new multipart upload for this file
    new_mp = S3Conn.initiate_multipart_upload(filename)
    # Write the new multipart ID in metadata
    metadata.extra['mp_id'] = new_mp.uploadId
    # New file ? Create a default timestamp
    if metadata.extra.get('timestamp') is None:
        plug.logger.debug("Creating a new timestamp"
                          " for {}".format(metadata.filename))
        metadata.extra['timestamp'] = 0.0
    metadata.write()
    # Store the Multipart upload id in cache
    add_to_cache(new_mp)
    plug.logger.debug("Storing upload ID {} for {}"
                      .format(new_mp.uploadId, filename))


@plug.handler()
def upload_file(metadata, data):
    global S3Conn
    global plug
    filename = root_prefixed_filename(metadata.filename)
    plug.logger.debug("Starting one-shot upload of '{}' to '{}' on bucket {}"
                      .format(metadata.filename, filename,
                              plug.options['bucket']))
    fp = IOStream(data)
    try:
        S3Conn.upload(filename, fp)
    except requests.HTTPError as httpe:
        err = "Upload on file {} failed - {}"
        err = err.format(filename, httpe)
        raise ServiceError(err)
    plug.logger.debug("Chunk upload complete")


@plug.handler()
def end_upload(metadata):
    global S3Conn

    multipart_upload = get_multipart_upload(metadata)
    filename = root_prefixed_filename(metadata.filename)
    # Finish the upload on remote server before getting rid of the
    # multipart upload ID
    try:
        multipart_upload.complete_upload()
    # If the file is left empty (i.e. for tests),
    # an exception is raised
    except requests.HTTPError as exc:
        if metadata.size == 0:
            # don't pollute S3 server with a void MP upload
            multipart_upload.cancel_upload()
            # Explicitly set this file contents to "nothing"
            fp = IOStream(b"")
            S3Conn.upload(filename, fp)
        else:
            # Delete the mp id from cache
            remove_from_cache(multipart_upload)
            raise DriverError("Error: {}".format(exc))
    # From here we're sure that's OK for Amazon
    new_timestamp = get_file_timestamp(filename)
    del metadata.extra['mp_id']  # erases the upload ID
    metadata.extra['timestamp'] = new_timestamp
    metadata.write()
    # Delete the mp id from cache
    remove_from_cache(multipart_upload)


@plug.handler()
def abort_upload(metadata):
    multipart_upload = get_multipart_upload(metadata)
    # Cancel the upload on remote server before getting rid of the
    # multipart upload ID
    multipart_upload.cancel_upload()
    # From here we're sure that's OK for Amazon
    del metadata.extra['mp_id']  # erases the upload ID
    metadata.write()
    # Delete the mp id from cache
    remove_from_cache(multipart_upload)


@plug.handler()
def move_file(old_metadata, new_metadata):
    global plug
    global S3Conn
    old_filename = root_prefixed_filename(old_metadata.filename)
    new_filename = root_prefixed_filename(new_metadata.filename)
    bucket = plug.options['bucket']
    plug.logger.debug("Moving file '{}' to '{}' on bucket '{}'"
                      .format(old_filename, new_filename, bucket))
    try:
        plug.logger.debug("Copying file '{}' to '{}' on bucket '{}'..."
                          .format(old_filename, new_filename, bucket))
        S3Conn.copy(old_filename, bucket, new_filename, bucket)
        plug.logger.debug("Copying file '{}' to '{}' on bucket '{}'..."
                          " - Done".format(old_filename, new_filename, bucket))
        plug.logger.debug("Deleting file '{}' on bucket '{}'..."
                          .format(old_filename, bucket))
        S3Conn.delete(old_filename)
        plug.logger.debug("Deleting file '{}' on bucket '{}'..."
                          " - Done".format(old_filename, bucket))
        # Update timestamp of new object
        # This permits to not detect a new update in the check changes thread
        # and thus avoids an useless transfer the other way around
        plug.logger.debug("Updating timestamp of {}".format(new_filename))
        timestamp = get_file_timestamp(new_filename)
        new_metadata.extra['timestamp'] = timestamp
        new_metadata.write()
    except requests.HTTPError as httpe:
        raise ServiceError("Network problem while moving file - {}"
                           .format(httpe))


@plug.handler()
def delete_file(metadata):
    global plug
    global S3Conn
    try:
        filename = root_prefixed_filename(metadata.filename)
        plug.logger.debug("Deleting {}"
                          "on bucket {}".format(filename,
                                                plug.options['bucket']))
        S3Conn.delete(filename)
    except requests.HTTPError as httpe:
        raise ServiceError(
            "Error deleting file {} on bucket {}: {}".format(
                filename, plug.options['bucket'], httpe
                )
            )


class CheckChanges(threading.Thread):
    """A class spawned in a thread to poll for changes on the S3 bucket.
    Amazon S3 hasn't any bucket watching system in its API, so the best
    we can do is periodically polling the bucket's contents and compare the
    timestamps."""

    def __init__(self, timer):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer

    def check_bucket(self):
        global S3Conn
        global plug

        plug.logger.debug("Checking bucket"
                          " {} for changes".format(plug.options['bucket']))
        # We're only interested in keys and uploads under Onitu's root
        root = get_root()
        # We add a trailing slash to only list files under root and not the
        # root itself
        if not root.endswith('/'):
            root += '/'
        # We need to unroll the generator to be able to check for folders
        keys = [key for key in S3Conn.list(prefix=root)]
        plug.logger.debug("Processing files under '{}'".format(root))
        # Getting multipart uploads once for all files under root
        # is WAY faster than re-getting them for each file
        multipart_uploads = S3Conn.get_all_multipart_uploads(prefix=root)
        keys_being_uploaded = [mp.key for mp in multipart_uploads]
        # We have to be extra careful because S3 will list filenames without
        # leading slash.
        if root.startswith('/'):
            root = root[1:]
        for key in keys:
            plug.logger.debug("Processing file '{}'".format(key['key']))
            # During an upload, files can appear on the S3 file system
            # before the transfer has been completed.
            # Skip if there's currently an upload going on
            if key in keys_being_uploaded:
                plug.logger.debug("Remote file '{}' is being uploaded"
                                  " - skipped".format(key['key']))
                continue
            # Amazon S3 has no concept of folder, they are just empty files to
            # it. But we must not notify them on Onitu or it transfers them as
            # regular files. If a file is empty, check if other files begin
            # by its name (meaning it contains them)
            if key['size'] == 0:
                prefix = key['key'] + '/'
                children = [child for child in keys
                            if child['key'].startswith(prefix)]
                if children:
                    plug.logger.debug("File '{}' is a folder on S3"
                                      " - skipped".format(key['key']))
                    continue
            # Strip the S3 root of the S3 filename for root coherence.
            rootless_key = key['key'][len(root):]
            metadata = plug.get_metadata(rootless_key)
            onitu_ts = metadata.extra.get('timestamp', 0.0)
            remote_ts = time.mktime(key['last_modified'].timetuple())
            if onitu_ts < remote_ts:  # Remote timestamp is more recent
                plug.logger.debug("Updating metadata"
                                  " of file {}".format(metadata.filename))
                metadata.size = int(key['size'])
                metadata.extra['timestamp'] = remote_ts
                plug.update_file(metadata)
        plug.logger.debug("Done checking bucket - next check in {} seconds"
                          .format(self.timer))

    def run(self):
        global plug

        while not self.stop.isSet():
            try:
                self.check_bucket()
            except requests.HTTPError as httpe:
                err = "Error while polling Onitu's S3 bucket"
                if httpe.response.status_code == 404:
                    err += ": The given bucket {} doesn't exist".format(
                        plug.options['bucket'])
                err += " - {}".format(httpe)
                plug.logger.error(err)
            except requests.ConnectionError as conne:
                err = "Failed to connect to Onitu's S3 bucket for polling"
                err += " - {}".format(conne)
                plug.logger.error(err)
            # if the bucket read operation times out
            except SSLError as ssle:
                plug.logger.warning("Couldn't poll S3 bucket '{}': {}"
                                    .format(plug.options['bucket'], ssle))
                pass  # cannot do much about it
            # Happens when connection is reset by peer
            except socket.error as serr:
                plug.logger.warning("Network problem, trying to reconnect. "
                                    "{}".format(serr))
                get_conn()
            except EscalatorClosed:
                # We are closing
                return
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    global S3Conn

    if plug.options['changes_timer'] < 0:
        raise DriverError(
            "The change timer option must be a positive integer")
    get_conn()  # connection to S3
    root = get_root()
    if root != '':
        # Check that the given root isn't a regular file
        try:
            root_key = S3Conn.get(root)
        except requests.HTTPError as httpe:
            if httpe.response.status_code == 404:
                # it's alright, root doesn't exist, no problem
                pass
            else:  # another error
                raise DriverError("Cannot fetch Onitu's root ({}) on"
                                  " bucket "
                                  "{}: {}".format(plug.options['root'],
                                                  plug.options['bucket'],
                                                  httpe))
        else:  # no error - root already exists
            # Amazon S3 has no concept of directories, they're just 0-size
            # files. So if root hasn't a size of 0, it is a regular file.
            if len(root_key.content) != 0:
                raise DriverError(
                    "Onitu's root ({}) is a regular file on the '{}' bucket. "
                    "It has to be an empty file.".format(
                        plug.options['root'], plug.options['bucket'])
                    )
    check = CheckChanges(plug.options['changes_timer'])
    check.daemon = True
    check.start()
    plug.listen()
