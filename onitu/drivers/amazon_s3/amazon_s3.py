import time
import threading
import StringIO
import boto
from onitu.api import Plug

plug = Plug()

S3Conn = None

multipart_upload = None
part_num = 0

TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S GMT' # example: 'Sat, 03 May 2014 04:36:11 GMT'
ALL_KEYS_TIMESTAMP_FMT = '%Y-%m-%dT%H:%M:%S.000Z' # using the get_all_keys method, format changes!
# '%Y-%m-%dT%H:%M:%S %Z'


def get_bucket():
    """Helper function to get the Onitu S3 bucket, and log an error if it couldn't fetch it."""
    global S3Conn

    bucket = S3Conn.get_bucket(plug.options["bucket"])
    if not bucket:
        plug.logger.error(filename + ": No such bucket")
    return bucket

@plug.handler()
def get_chunk(metadata, offset, size):
    bucket = get_bucket()
    chunk = None
    if bucket:
        key = bucket.get_key(metadata.filename)
        if not key:
            plug.logger.error("Get chunk: " + metadata.filename + ": No such file")
        else:
            range_bytes = 'bytes=' + str(offset) + "-" + str(offset + (size-1))
            chunk = key.get_contents_as_string(headers={'Range' : range_bytes})
    return chunk


@plug.handler()
def start_upload(metadata):
    global part_num

    bucket = get_bucket()
    if bucket:
        key = bucket.get_key(metadata.filename) # find the key on S3
        if not key: # Create a new empty file
            key = boto.s3.key.Key(bucket)
            key.key = metadata.filename
            key.set_contents_from_string("")
        # Creating a new S3 multipart upload
        print 'New multipart upload for', metadata.filename
        multipart_upload = bucket.initiate_multipart_upload(metadata.filename, headers={'Content-Type': 'application/octet-stream'})
        part_num = 0

@plug.handler()
def end_upload(metadata):
    global part_num

    bucket = get_bucket()
    if bucket:
        key = bucket.get_key(metadata.filename) # find the key on S3
        if not key:
            plug.logger.error("End upload: " + filename + ": No such file")
        else:
            new_revision = time.strptime(key.last_modified, TIMESTAMP_FMT) # convert timestamp to timestruct
            new_revision = time.mktime(metadata.revision) # convert timestruct to float
            new_revision = str(new_revision) # convert float to string
            print 'New timestamp:', new_revision
            revision_update = metadata.revision.split('\t')
            revision_update[0] = new_revision
            print 'new revision:', '\t'.join(revision_update)
            metadata.write_revision('\t'.join(revision_update))
        multipart_upload.complete_upload()
        print 'end mp upload'
        part_num = 0

@plug.handler()
def upload_chunk(metadata, offset, chunk):
    global part_num

    bucket = get_bucket()
    if bucket:
        key = bucket.get_key(metadata.filename) # find the key on S3
        if not key:
            plug.logger.error("Upload chunk: " + metadata.filename + ": No such file")
        else:
            print 'Uploading chunk', part_num
            upload_fp = StringIO.StringIO() # Amazon S3 multipart upload only takes its part content from a file. Emulating it with StringIO
            upload_fp.write(chunk)
            multipart_upload.upload_part_from_file(fp=upload_fp, part_num=part_num)
            upload_fp.close()
            part_num += 1
            # contents = list(key.get_contents_as_string())
            # chunk_size = len(chunk)-1
            # contents[offset:chunk_size] = list(chunk)
            # key.set_contents_from_string(''.join(contents))

@plug.handler()
def abort_upload(metadata):
    if multipart_upload:
         multipart_upload.cancel_upload()

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
                onitu_revision = float(metadata.revision.split('\t')[0])
                remote_revision = time.mktime(time.strptime(key.last_modified, ALL_KEYS_TIMESTAMP_FMT))
                # Some evil timestamp black magic is happening when making times !
                # Sometimes even if metadata.revision is clearly inferior to the remote_revision, it evaluates to False.
                # Explicitly casting to float works around the problem (although they already are floats ...)
                if onitu_revision < remote_revision: 
                    print 'update:', key.name, '!'
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
    plug.initialize(*args, **kwargs)
    global S3Conn

    error_msg = ""
    changes_timer = 0
    try: # S3 Connection
        S3Conn = boto.connect_s3(aws_access_key_id=plug.options["aws_access_key"], aws_secret_access_key=plug.options["aws_secret_key"])
        S3Conn.head_bucket(plug.options["bucket"])  # Check that connection was successful and that the given bucket exists
        changes_timer = int(plug.options["changes_timer"]) # check for positive values later ?
    except KeyError as notfound:
        error_msg = "You must provide the " + str(notfound) + " option in your setup.json."
    except ValueError: # int fail
        error_msg = "The changes_timer option must be an integer (" + plug.options['changes_timer'] + " isn't an integer)."
    except boto.exception.BotoClientError as exc: # invalid bucket's name (upper-case characters, ...)
        error_msg = "Invalid bucket name, please check your setup.json or your Amazon S3 account configuration. " + str(exc)
    except boto.exception.S3ResponseError as exc: # invalid credentials or invalid bucket
        if exc.status == 403:
            error_msg = "Invalid credentials. "
        elif exc.status == 404:
            error_msg = "The bucket '" + plug.options["bucket"] + "' doesn't exist. "
        error_msg += "Please check your setup.json or your Amazon S3 account configuration. " + str(exc)
    if error_msg is "":
        check = CheckChanges(changes_timer)
        check.start()
        plug.listen()
    else:
        plug.logger.error(error_msg)
