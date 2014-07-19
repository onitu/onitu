import hashlib
import os
import sys
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

    def __init__(self, *args, **options):
        if "root" not in options:
            options['root'] = ''
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

    def prefix_with_root(self, filename):
        root = self.root()
        real_filename = root + filename
        return real_filename

    def create_file(self, filename, content=""):
        self.write(filename, content)

    def root(self):
        root = self.options['root']
        # S3 doesn't like leading slashes
        if root.startswith('/'):
            root = root[1:]
        if not root.endswith('/'):
            root += '/'
        return root

    def close(self):
        root = self.root()
        for key in self.conn.list_keys(extra_params={'prefix': root}):
            self.conn.delete(key.key)
        # Don't delete the whole bucket !
        if root != '/':
            self.conn.delete(root)

    def mkdir(self, subdirs):
        subdirs = self.prefix_with_root(subdirs)
        self.create_file(subdirs)

    def write(self, filename, content, includes_root=False):
        if not includes_root:
            filename = self.prefix_with_root(filename)
        if sys.version_info.major == 3 and not isinstance(content, bytes):
            content = content.encode()
        s = IOStream(content)
        self.conn.upload(filename, s)
        s.close()

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        filename = self.prefix_with_root(filename)
        if filename != '':
            self.conn.delete(filename)

    def exists(self, filename):
        filename = self.prefix_with_root(filename)
        try:
            self.conn.head_object(filename)
        except requests.HTTPError:
            return False
        return True

    def checksum(self, filename):
        filename = self.prefix_with_root(filename)
        file = self.conn.get(filename)
        return hashlib.md5(file.content).hexdigest()
