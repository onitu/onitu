import time
import socket
import threading
from ssl import SSLError
import StringIO

import boto

from onitu.api import Plug, DriverError, ServiceError

plug = Plug()

# Amazon S3 related global variables
S3Conn = None
# e.g. 'Sat, 03 May 2014 04:36:11 GMT'
TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S GMT'
# to deal with format changes
ALL_KEYS_TIMESTAMP_FMT = '%Y-%m-%dT%H:%M:%S.000Z'
# "Each part must be at least 5 MB in size, except the last part."
# http://docs.aws.amazon.com/AmazonS3/latest/API/mpUploadUploadPart.html
S3_MINIMUM_CHUNK_SIZE = 5 << 20


def get_conn():
    """Gets the connection with the Amazon S3 server.
    Raises an error if conn cannot be established"""
    global S3Conn

    S3Conn = boto.connect_s3(
        aws_access_key_id=plug.options["aws_access_key"],
        aws_secret_access_key=plug.options["aws_secret_key"])


def get_bucket(head=False):
    """Gets the S3 bucket the Onitu driver is watching.
    Raises an error if bucket cannot be fetched.
    If head = True, will just check for bucket existence (faster)."""
    global S3Conn

    bucket = None
    err = ""
    try:
        if not head:
            # Get bucket's contents
            bucket = S3Conn.get_bucket(plug.options["bucket"])
        else:
            # Just check bucket existence
            S3Conn.head_bucket(plug.options["bucket"])
    # invalid bucket name. Some non-standard names can work on the S3 web
    # console, but not with boto API (e.g. if it has uppercase chars).
    except boto.exception.BotoClientError as exc:
        err = "Invalid bucket name. "
    # Request problem
    except boto.exception.S3ResponseError as exc:
        if exc.status == 403:
            err = "Invalid credentials. "
        if exc.status == 404:
            err = "The bucket '{}' doesn't exist. ".format(
                plug.options["bucket"])
    finally:
        if err:
            err += "Please check your Amazon S3 account \
configuration. {}".format(str(exc))
            raise DriverError(err)
    return bucket


def root_prefixed_filename(filename):
    """Prefixes the given filename with Onitu's root."""
    if not filename.startswith(plug.options['root']):
        rp_filename = plug.options['root']
        if not rp_filename.endswith('/'):
            rp_filename += '/'
            rp_filename += filename
    else:
        rp_filename = filename
    return rp_filename


def get_file(filename):
    """Gets a file on the bucket (S3 calls them "keys").
    Prefixes the given filename with Onitu's root.
    Raises a ServiceError if file doesn't exist."""
    bucket = get_bucket()
    filename = root_prefixed_filename(filename)
    key = bucket.get_key(filename)  # find the file on S3
    if key is None:  # in most cases, the file should exist
        err = "{}: No such file".format(filename)
        raise ServiceError(err)
    return key


def get_file_timestamp(filename):
    """Returns the float timestamp based on the
    date format timestamp stored by Amazon.
    Prefixes the given filename with Onitu's root."""
    key = get_file(filename)
    # convert timestamp to timestruct...
    timestamp = time.strptime(key.last_modified, TIMESTAMP_FMT)
    # ...timestruct to float
    timestamp = time.mktime(timestamp)
    return timestamp


def get_multipart_upload(metadata):
    """Returns the multipart upload we have the ID of in metadata.
    As Amazon allows several multipart uploads at the same time
    for the same file, the ID is the only unique, reliable descriptor."""
    multipart_upload = None
    metadata_mp_id = None
    # Retrieve the stored multipart upload ID
    try:
        metadata_mp_id = metadata.extra["mp_id"]
    except KeyError:  # No multipart upload ID
        # Raise now is faster (doesn't go through all the MP uploads)
        raise DriverError("Unable to retrieve multipart upload ID")
    bucket = get_bucket()
    # Go through all the multipart uploads to find the one of this transfer
    for mp in bucket.list_multipart_uploads():
        if mp.id == metadata_mp_id:
            multipart_upload = mp
    # At this point it shouldn't be None in any case
    if multipart_upload is None:
        raise DriverError("Cannot find upload for file '{}'"
                          .format(root_prefixed_filename(metadata.filename)))
    return multipart_upload


@plug.handler()
def set_chunk_size(chunk_size):
    if chunk_size < S3_MINIMUM_CHUNK_SIZE:
        return S3_MINIMUM_CHUNK_SIZE
    else:
        return None


@plug.handler()
def get_chunk(metadata, offset, size):
    key = get_file(root_prefixed_filename(metadata.filename))
    # Using the REST API "Range" header.
    range_bytes = "bytes={}-{}".format(str(offset), str(offset + (size-1)))
    try:
        chunk = key.get_contents_as_string(headers={"Range": range_bytes})
    except SSLError as ssle:  # read timeout
        raise DriverError(str(ssle))
    return chunk


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    multipart_upload = get_multipart_upload(metadata)
    part_num = len(multipart_upload.get_all_parts()) + 1
    # Boto only allows to upload a part from a file.
    # With StringIO we can simulate a file pointer.
    upload_fp = StringIO.StringIO(chunk)
    multipart_upload.upload_part_from_file(fp=upload_fp,
                                           part_num=part_num)
    upload_fp.close()


@plug.handler()
def start_upload(metadata):
    bucket = get_bucket()
    filename = root_prefixed_filename(metadata.filename)
    key = bucket.get_key(filename)
    if not key:  # Create a new empty file if it doesn't exist yet
        key = boto.s3.key.Key(bucket)
        key.key = filename
        key.set_contents_from_string("")
    # Creating a new S3 multipart upload
    multipart_upload = bucket.initiate_multipart_upload(
        filename,
        headers={'Content-Type': 'application/octet-stream'})
    # Write the new multipart ID in metadata
    metadata.extra['mp_id'] = multipart_upload.id
    if metadata.extra.get('timestamp') is None:
        metadata.extra['timestamp'] = '0.0'
    metadata.write()


@plug.handler()
def end_upload(metadata):
    multipart_upload = get_multipart_upload(metadata)
    filename = root_prefixed_filename(metadata.filename)
    # Finish the upload on remote server before getting rid of the
    # multipart upload ID
    try:
        multipart_upload.complete_upload()
    # If the file is left empty (i.e. for tests),
    # boto raises this exception
    except boto.exception.S3ResponseError as exc:
        if metadata.size == 0:
            # don't pollute S3 server with a void MP upload
            multipart_upload.cancel_upload()
            # Explicitly set the file contents to "nothing"
            b = get_bucket()
            # The file may not exist yet
            key = b.get_key(filename) or b.new_key(filename)
            key.set_contents_from_string('')
        else:
            raise DriverError("S3 Error: {}".format(exc))
    # From here we're sure that's OK for Amazon
    new_timestamp = get_file_timestamp(metadata.filename)
    del metadata.extra['mp_id']  # erases the upload ID
    metadata.extra['timestamp'] = new_timestamp
    metadata.write()


@plug.handler()
def abort_upload(metadata):
    multipart_upload = get_multipart_upload(metadata)
    # Cancel the upload on remote server before getting rid of the
    # multipart upload ID
    multipart_upload.cancel_upload()
    # From here we're sure that's OK for Amazon
    del metadata.extra['mp_id']  # erases the upload ID
    metadata.write()


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
        bucket = get_bucket()
        if bucket:
            keys = bucket.list(prefix=plug.options['root'])
            # Getting the multipart uploads list once for all files
            # is WAY faster than re-getting it for each file
            multipart_uploads = bucket.get_all_multipart_uploads()
            for key in keys:
                # During an upload, files can appear on the S3 file system
                # before the transfer has been completed (but they shouldn't).
                # If there's currently an upload going on this file,
                # don't notify it.
                is_being_uploaded = False
                for mp in multipart_uploads:
                    if mp.key_name == key.name:
                        is_being_uploaded = True
                        break
                if is_being_uploaded:
                    continue  # Skip this file
                metadata = plug.get_metadata(key.name)
                onitu_ts = metadata.extra.get('timestamp', 0.0)
                remote_ts = time.mktime(
                    time.strptime(key.last_modified, ALL_KEYS_TIMESTAMP_FMT))
                if onitu_ts < remote_ts:  # Remote timestamp is more recent
                    metadata.size = key.size
                    metadata.extra['timestamp'] = remote_ts
                    plug.update_file(metadata)

    def run(self):
        while not self.stop.isSet():
            try:
                self.check_bucket()
            # if the bucket read operation times out
            except SSLError as ssle:
                plug.logger.warning("Couldn't poll S3 bucket '{}': {}"
                                    .format(plug.options["bucket"], str(ssle)))
                pass  # cannot do much about it
            # Happens when connection is reset by peer
            except socket.error as serr:
                plug.logger.warning("Network problem, trying to reconnect. \
{}".format(str(serr)))
                get_conn()
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    if plug.options["changes_timer"] < 0:
        raise DriverError(
            "The change timer option must be a positive integer")
    get_conn()  # connection to S3
    b = get_bucket()  # Checks that the given bucket exists
    root = b.get_key(plug.options['root'])
    # If no root: create it
    if root is None:
        # Amazon S3 doesn't make the difference between a directory
        # and an empty file
        root = b.new_key(plug.options['root'])
        root.set_contents_from_string('')
    else:
        if root.size != 0:
            raise DriverError(
                'The given root "{}" isn\'t a directory on the "{}" bucket. It\
 has to be an empty file.'.format(
                    plug.options['root'], plug.options['bucket']))
    check = CheckChanges(plug.options["changes_timer"])
    check.start()
    plug.listen()
