import time
import socket
import threading
from ssl import SSLError
import StringIO

import boto

from onitu.api import Plug, DriverError, ServiceError, TryAgain

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


def get_file(filename):
    """Gets a file on the bucket (S3 calls them "keys").
    Raises a ServiceError if file doesn't exist."""
    bucket = get_bucket()
    key = bucket.get_key(filename)  # find the file on S3
    if key is None:  # in most cases, the file should exist
        err = "{}: No such file".format(filename)
        raise ServiceError(err)
    return key


def get_file_timestamp(filename):
    """Returns the float timestamp based on the
    date format timestamp stored by Amazon."""
    key = get_file(filename)
    # convert timestamp to timestruct...
    timestamp = time.strptime(key.last_modified, TIMESTAMP_FMT)
    # ...timestruct to float
    timestamp = time.mktime(timestamp)
    return timestamp


def get_multipart_upload(metadata):
    """Returns the multipart upload we have the ID of in revision.
    As Amazon allows several multipart uploads at the same time
    for the same file, the ID is the only reliable descriptor."""
    multipart_upload = None
    metadata_mp_id = None
    try:
        # Retrieve the stored multipart upload ID
        metadata_mp_id = metadata.revision.split('\t')[1]
    except IndexError:  # No multipart upload ID ?!
        raise DriverError("Unable to retrieve multipart upload ID")
    except AttributeError:  # No metadata at all
        start_upload(metadata)  # initiate the upload
    bucket = get_bucket()
    # Go through all the multipart uploads to find the one of this transfer
    for mp in bucket.list_multipart_uploads():
        if mp.id == metadata_mp_id:
            multipart_upload = mp
    # At this point it shouldn't be None in any case
    if multipart_upload is None:
        raise DriverError("Cannot find upload for file '{}'"
                          .format(metadata.filename))
    return multipart_upload


@plug.handler()
def set_chunk_size(chunk_size):
    if chunk_size < S3_MINIMUM_CHUNK_SIZE:
        return S3_MINIMUM_CHUNK_SIZE
    else:
        return None


@plug.handler()
def get_chunk(metadata, offset, size):
    key = get_file(metadata.filename)
    # Using the REST API "Range" header.
    range_bytes = "bytes={}-{}".format(str(offset), str(offset + (size-1)))
    try:
        chunk = key.get_contents_as_string(headers={"Range": range_bytes})
    except SSLError as ssle:  # read timeout
        raise TryAgain(str(ssle))
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
    key = bucket.get_key(metadata.filename)
    if not key:  # Create a new empty file if it doesn't exist yet
        key = boto.s3.key.Key(bucket)
        key.key = metadata.filename
        key.set_contents_from_string("")
    # Creating a new S3 multipart upload
    multipart_upload = bucket.initiate_multipart_upload(
        metadata.filename,
        headers={'Content-Type': 'application/octet-stream'})
    # Write the new multipart ID into the revision
    try:
        timestamp = metadata.revision.split('\t')[0]
    except AttributeError:  # no timestamp ?
        timestamp = '0.0'
    metadata.revision = '\t'.join([timestamp, multipart_upload.id])
    metadata.write_revision()


@plug.handler()
def end_upload(metadata):
    multipart_upload = get_multipart_upload(metadata)
    # Finish the upload on remote server before getting rid of the
    # multipart upload ID
    multipart_upload.complete_upload()
    # From here we're sure that's OK for Amazon
    new_timestamp = str(get_file_timestamp(metadata.filename))
    metadata.revision = new_timestamp  # erases the upload ID
    metadata.write_revision()


@plug.handler()
def abort_upload(metadata):
    multipart_upload = get_multipart_upload(metadata)
    # Cancel the upload on remote server before getting rid of the
    # multipart upload ID
    multipart_upload.cancel_upload()
    # From here we're sure that's OK for Amazon
    try:
        # erase the upload ID
        metadata.revision = metadata.revision.split('\t')[0]
    except AttributeError:  # no timestamp ?
        metadata.revision = '0.0'
    metadata.write_revision()


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
            keys = bucket.get_all_keys()
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
                try:
                    onitu_revision = float(metadata.revision.split('\t')[0])
                # if metadata.revision is None, which means it's a new file
                except AttributeError:
                    onitu_revision = 0.0
                remote_revision = time.mktime(
                    time.strptime(key.last_modified, ALL_KEYS_TIMESTAMP_FMT))
                if onitu_revision < remote_revision:
                    metadata.size = key.size
                    metadata.revision = remote_revision
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
    get_bucket(head=True)  # Check that the given bucket exists
    check = CheckChanges(plug.options["changes_timer"])
    check.start()
    plug.listen()
