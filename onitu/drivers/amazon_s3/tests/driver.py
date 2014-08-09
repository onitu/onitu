import hashlib
import os
import sys
from path import path
# Python 2/3 compatibility
if sys.version_info.major == 2:
    from StringIO import StringIO as IOStream
elif sys.version_info.major == 3:
    # In Py3k, chunks are passed as raw bytes. Hence we can't use StringIO
    from io import BytesIO as IOStream

import requests

import tinys3
from tests.utils.testdriver import TestDriver


class Driver(TestDriver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        if "root" not in options:
            options['root'] = 'onitu'  # bug: don't put a trailing slash
        if "aws_access_key" not in options:
            options['aws_access_key'] = os.environ['ONITU_AWS_ACCESS_KEY']
        if "aws_secret_key" not in options:
            options['aws_secret_key'] = os.environ['ONITU_AWS_SECRET_KEY']
        if "bucket" not in options:
            options['bucket'] = 'onitu-test-2'
        self.conn = tinys3.Connection(options['aws_access_key'],
                                      options['aws_secret_key'],
                                      default_bucket=options['bucket'],
                                      tls=True)
        super(Driver, self).__init__('amazon_s3',
                                     *args,
                                     **options)

    @property
    def root(self):
        root = self.options['root']
        # S3 doesn't like leading slashes
        if root.startswith('/'):
            root = root[1:]
        if not root.endswith('/'):
            root += '/'
        return path(root)

    def close(self):
        root = str(self.root)
        for key in self.conn.list(prefix=root):
            self.conn.delete(key['key'])
        # Don't delete the whole bucket !
        if root.endswith('/'):
            root = root[:-1]
        if root != '':
            self.conn.delete(root)

    def mkdir(self, subdirs):
        subdirs = str(self.root) + subdirs
        self.write(subdirs, '', True)

    def rmdir(self, path):
        path = str(self.root) + path
        self.unlink(path)

    def write(self, filename, content, includes_root=False):
        if not includes_root:
            filename = str(self.root) + filename
        if sys.version_info.major == 3 and not isinstance(content, bytes):
            content = content.encode()
        s = IOStream(content)
        self.conn.upload(filename, s)
        s.close()

    def generate(self, filename, size):
        filename = str(self.root) + filename
        self.write(filename, os.urandom(size), True)

    def unlink(self, filename):
        filename = str(self.root) + filename
        if filename != '':
            self.conn.delete(filename)

    def exists(self, filename):
        filename = str(self.root) + filename
        try:
            self.conn.head_object(filename)
        except requests.HTTPError:
            return False
        return True

    def rename(self, source, target):
        source = str(self.root) + source
        target = str(self.root) + target
        bucket = self.options['bucket']
        self.conn.copy(source, bucket, target, bucket)
        self.conn.delete(source)

    def checksum(self, filename):
        filename = str(self.root) + filename
        file = self.conn.get(filename)
        return hashlib.md5(file.content).hexdigest()
