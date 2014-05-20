import time
import threading
from ssl import SSLError
# import StringIO (Not implemented yet)
import boto

from onitu.api import Plug, DriverError, ServiceError

plug = Plug()

S3Conn = None

# Not implemented yet
# multipart_upload = None
# part_num = 0

# e.g. 'Sat, 03 May 2014 04:36:11 GMT'
TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S GMT'
# to deal with format changes
ALL_KEYS_TIMESTAMP_FMT = '%Y-%m-%dT%H:%M:%S.000Z'


def get_conn():
    """Gets the connection with the Amazon S3 server.
    Raises an error if conn cannot be established"""
    global S3Conn

    err = ""
    try:  # S3 Connection
        S3Conn = boto.connect_s3(
            aws_access_key_id=plug.options["aws_access_key"],
            aws_secret_access_key=plug.options["aws_secret_key"])
    except boto.exception.S3ResponseError as exc:
        if exc.status == 403:
            err = "Invalid credentials. "
        elif exc.status == 404:
            err = "The bucket '" + plug.options["bucket"]
            + "' doesn't exist. "
        err += "Please check your Amazon S3 account \
configuration. " + str(exc)
        raise ServiceError(err)    
    

def get_bucket():
    """Gets the S3 bucket the Onitu driver is watching.
    Raises an error if bucket cannot be fetched"""
    global S3Conn

    bucket = S3Conn.get_bucket(plug.options["bucket"])
    if not bucket:
        raise ServiceError(plug.options["bucket"] + ": No such bucket")
    return bucket


@plug.handler()
def get_chunk(metadata, offset, size):
    bucket = get_bucket()
    key = bucket.get_key(metadata.filename)
    if not key:
        err = "Get chunk: " + metadata.filename + ": No such file"
        raise ServiceError(err)    
    range_bytes = 'bytes=' + str(offset) + "-" + str(offset + (size-1))
    chunk = key.get_contents_as_string(headers={'Range': range_bytes})
    return chunk


@plug.handler()
def start_upload(metadata):
    # (not implemented yet)
    # global part_num
    # global multipart_upload

    bucket = get_bucket()
    key = bucket.get_key(metadata.filename)  # find the key on S3 
    if not key:  # Create a new empty file if it doesn't exist yet
        key = boto.s3.key.Key(bucket)
        key.key = metadata.filename
        key.set_contents_from_string("")
        # Creating a new S3 multipart upload
        # (not implemented yet)
        # multipart_upload = bucket.initiate_multipart_upload(
        #   metadata.filename,
        #   headers={'Content-Type': 'application/octet-stream'})
        # metadata.revision currently is a string holding two informations:
        # timestamp of the file's last revision
        # and multipart upload ID, separated by a '\t'.
        # Here, as we start a multipart upload we update the id.
        # Useful to resume the upload in case of a crash.
        # try:
        #     info_list = metadata.revision.split('\t')
        # except AttributeError: # no revision data
        #     info_list = ['', '']
        # try:
        #     info_list[1] = str(multipart_upload.id)
        # except IndexError: # No multipart upload id stored right now
        #     print 'index error'
        #     info_list.append(str(multipart_upload.id))
        # except Exception as e:
        #     print e
        # metadata.write_revision('\t'.join(info_list))
        # part_num = 0


@plug.handler()
def end_upload(metadata):
    # (not implemented yet)
    #    global part_num
    #    global multipart_upload
    bucket = get_bucket()
    key = bucket.get_key(metadata.filename)  # find the key on S3
    if not key: # the file should exist at the end of the upload
        err = "End upload: " + metadata.filename + ": No such file"
        raise ServiceError(err)
    # convert timestamp to timestruct
    new_revision = time.strptime(key.last_modified, TIMESTAMP_FMT)
    # convert timestruct to float
    new_revision = time.mktime(new_revision)
    # convert float to string
    new_revision = str(new_revision)
    metadata.revision = new_revision
    metadata.write_revision()
#    metadata.write_revision(new_revision)
    # Not implemented yet
    # multipart_upload.complete_upload()


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    # (not implemented yet)
    #    global part_num
    #    global multipart_upload
    bucket = get_bucket()
    key = bucket.get_key(metadata.filename)  # find the key on S3
    if not key:
        err = "Upload chunk: " + metadata.filename + ": No such file"
        raise ServiceError(err)
    contents = list(key.get_contents_as_string())
    chunk_size = len(chunk)-1
    contents[offset:chunk_size] = list(chunk)
    key.set_contents_from_string(''.join(contents))
            # Multipart upload (not implemented yet)
            # Amazon S3 multipart upload only works from a file.
            # StringIO allows to simulate a file pointer.
            # upload_fp = StringIO.StringIO()
            # upload_fp.write(chunk)
            # multipart_upload.upload_part_from_file(fp=upload_fp,
            #                                        part_num=part_num)
            # upload_fp.close()
            # part_num += 1


@plug.handler()
def abort_upload(metadata):
    # Not Implemented yet
    # global multipart_upload
    # if multipart_upload:
    #      multipart_upload.cancel_upload()
    pass


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
            for key in keys:
                metadata = plug.get_metadata(key.name)
                try:
                    onitu_revision = float(metadata.revision)
                # float cast failed or metadata.revision is None,
                # possibly because that's a new file
                except (ValueError, TypeError):
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
            # SSLError can appear if the bucket read operation times out
            except SSLError as ssle:
                plug.logger.warning("Couldn't poll S3 bucket '{}': {}".format(
                                           plug.options["bucket"],
                                           str(ssle)))
                pass  # cannot do much about it
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    global S3Conn

    get_conn()  # connection to S3
    try:
        err = ""
        # Check that the given bucket exists
        S3Conn.head_bucket(plug.options["bucket"])
    # invalid bucket name. Some non-standard names can work on the S3 web
    # console, but not with boto API (e.g. if it has uppercase chars)
    except boto.exception.BotoClientError as exc:
        err = "Invalid bucket name, please check your Amazon S3 account \
configuration. " + str(exc)
        raise DriverError(err)
    except boto.exception.S3ResponseError as exc:
        if exc.status == 404:
            err = "The bucket '{}' doesn't exist. ".format(
                plug.options["bucket"])
    finally:
        if err:
            err += "Please check your Amazon S3 account \
configuration. {}".format(str(exc))
            raise DriverError(err)
    if plug.options["changes_timer"] < 0:
        raise DriverError(
            "The change timer option must be a positive integer")
    # If here, everything went fine
    check = CheckChanges(plug.options["changes_timer"])
    check.start()
    plug.listen()
