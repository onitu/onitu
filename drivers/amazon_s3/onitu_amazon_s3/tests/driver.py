import hashlib
import os
import sys

import requests

import tinys3

from onitu.utils import get_random_string
from tests.utils import driver

# Python 2/3 compatibility
if sys.version_info.major == 2:
    from StringIO import StringIO as IOStream
else:
    # In Py3k, chunks are passed as raw bytes. Hence we can't use StringIO
    from io import BytesIO as IOStream


class Driver(driver.Driver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        if "aws_access_key" not in options:
            options['aws_access_key'] = os.environ['ONITU_AWS_ACCESS_KEY']
        if "aws_secret_key" not in options:
            options['aws_secret_key'] = os.environ['ONITU_AWS_SECRET_KEY']
        if "bucket" not in options:
            options['bucket'] = 'onitu-test-2'

        self._root = get_random_string(10)
        self.bucket = options['bucket']
        self.conn = tinys3.Connection(options['aws_access_key'],
                                      options['aws_secret_key'],
                                      default_bucket=options['bucket'],
                                      tls=True)
        super(Driver, self).__init__('amazon_s3',
                                     *args,
                                     **options)

    @property
    def root(self):
        return self._root + u"/"

    def close(self):
        root = self.root
        for key in self.conn.list(prefix=root):
            self.conn.delete(key['key'])
        # Don't delete the whole bucket !
        if root.endswith(u"/"):
            root = root[:-1]
        if root != u'':
            self.conn.delete(root)

    def mkdir(self, subdirs):
        self.write(subdirs, u'')

    def rmdir(self, path):
        self.unlink(path)

    def write(self, filename, content):
        if sys.version_info.major == 3 and not isinstance(content, bytes):
            content = content.encode()
        s = IOStream(content)
        self.conn.upload(filename, s)
        s.close()

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        self.conn.delete(filename)

    def exists(self, filename):
        try:
            self.conn.head_object(filename)
        except requests.HTTPError:
            return False
        return True

    def rename(self, source, target):
        bucket = self.bucket
        self.conn.copy(source, bucket, target, bucket)
        self.conn.delete(source)

    def checksum(self, filename):
        fileKey = self.conn.get(filename)
        return hashlib.md5(fileKey.content).hexdigest()


class DriverFeatures(driver.DriverFeatures):
    del_file_to_onitu = False
    move_file_to_onitu = False

    del_directory_to_onitu = False
    move_directory_to_onitu = False

    del_tree_to_onitu = False
    move_tree_to_onitu = False

    detect_del_file_on_launch = False
    dectect_moved_file_on_launch = False
