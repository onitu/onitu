import time
import threading
# import StringIO
import boto
from onitu.api import Plug

plug = Plug()

S3Conn = None

# Not implemented yet
# multipart_upload = None
# part_num = 0

# e.g. 'Sat, 03 May 2014 04:36:11 GMT'
TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S GMT'
# to deal with format changes
ALL_KEYS_TIMESTAMP_FMT = '%Y-%m-%dT%H:%M:%S.000Z'


def get_bucket():
    """Helper function to get the Onitu S3 bucket,
    and log an error if it couldn't fetch it."""
    global S3Conn

    bucket = S3Conn.get_bucket(plug.options["bucket"])
    if not bucket:
        plug.logger.error(plug.options["bucket"] + ": No such bucket")
    return bucket


@plug.handler()
def get_chunk(metadata, offset, size):
    bucket = get_bucket()
    chunk = None
    if bucket:
        key = bucket.get_key(metadata.filename)
        if not key:
            plug.logger.error(
                "Get chunk: " + metadata.filename + ": No such file")
        else:
            range_bytes = 'bytes=' + str(offset) + "-" + str(offset + (size-1))
            chunk = key.get_contents_as_string(headers={'Range': range_bytes})
    return chunk


@plug.handler()
def start_upload(metadata):
    # (not implemented yet)
    # global part_num
    # global multipart_upload

    bucket = get_bucket()
    if bucket:
        key = bucket.get_key(metadata.filename)  # find the key on S3
        if not key:  # Create a new empty file
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
    if bucket:
        key = bucket.get_key(metadata.filename)  # find the key on S3
        if not key:
            plug.logger.error(
                "End upload: " + metadata.filename + ": No such file")
        else:
            # convert timestamp to timestruct
            new_revision = time.strptime(key.last_modified, TIMESTAMP_FMT)
            # convert timestruct to float
            new_revision = time.mktime(metadata.revision)
            # convert float to string
            new_revision = str(new_revision)
            metadata.write_revision(new_revision)
            # Not implemented yet
            # multipart_upload.complete_upload()


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    # (not implemented yet)
    #    global part_num
    #    global multipart_upload

    bucket = get_bucket()
    if bucket:
        key = bucket.get_key(metadata.filename)  # find the key on S3
        if not key:
            plug.logger.error(
                "Upload chunk: " + metadata.filename + ": No such file")
        else:
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
    pass
    # Not Implemented yet
    # global multipart_upload
    # if multipart_upload:
    #      multipart_upload.cancel_upload()


class CheckChanges(threading.Thread):

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
            self.check_bucket()
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start(*args, **kwargs):
    global S3Conn

    plug.initialize(*args, **kwargs)
    error_msg = ""
    changes_timer = 0
    try:  # S3 Connection
        S3Conn = boto.connect_s3(
            aws_access_key_id=plug.options["aws_access_key"],
            aws_secret_access_key=plug.options["aws_secret_key"])
        # Check that connection was successful and that the given bucket exists
        S3Conn.head_bucket(plug.options["bucket"])
        # check for positive values later ?
        changes_timer = int(plug.options["changes_timer"])
    except KeyError as notfound:
        error_msg = "You must provide the " + str(notfound)
        + " option in your setup.json."
    # int fail
    except ValueError:
        error_msg = "The changes_timer option must be an integer ("
        + plug.options['changes_timer'] + " isn't an integer)."
    # invalid bucket's name (upper-case characters, ...)
    except boto.exception.BotoClientError as exc:
        error_msg = "Invalid bucket name, please check your setup.json or \
your Amazon S3 account configuration. " + str(exc)
    # invalid credentials or invalid bucket
    except boto.exception.S3ResponseError as exc:
        if exc.status == 403:
            error_msg = "Invalid credentials. "
        elif exc.status == 404:
            error_msg = "The bucket '" + plug.options["bucket"]
            + "' doesn't exist. "
        error_msg += "Please check your setup.json or your Amazon S3 account \
configuration. " + str(exc)
    if error_msg is "":
        check = CheckChanges(changes_timer)
        check.start()
        plug.listen()
    else:
        plug.logger.error(error_msg)
