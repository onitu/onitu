import hashlib
import os
import sys
import string
import random
from path import path
# Python 2/3 compatibility
if sys.version_info.major == 2:
    from StringIO import StringIO as IOStream
elif sys.version_info.major == 3:
    # In Py3k, chunks are passed as raw bytes. Hence we can't use StringIO
    from io import BytesIO as IOStream

import requests

import tinys3

from tests.utils import driver
from onitu.utils import u


class Driver(driver.Driver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        if u'root' not in options:
            rand = u''.join(random.sample(
                string.ascii_letters + string.digits, 10))
            options[u'root'] = u"/{}/".format(rand)
        if u'aws_access_key' not in options:
            options[u'aws_access_key'] = os.environ['ONITU_AWS_ACCESS_KEY']
        if u'aws_secret_key' not in options:
            options[u'aws_secret_key'] = os.environ['ONITU_AWS_SECRET_KEY']
        if "bucket" not in options:
            options[u'bucket'] = u'onitu-test-2'
        self.conn = tinys3.Connection(options[u'aws_access_key'],
                                      options[u'aws_secret_key'],
                                      default_bucket=options[u'bucket'],
                                      tls=True)
        super(Driver, self).__init__('amazon_s3',
                                     *args,
                                     **options)

    @property
    def root(self):
        root = u(self.options['root'])
        # S3 doesn't like leading slashes
        if root.startswith(u'/'):
            root = root[1:]
        if not root.endswith(u'/'):
            root += u'/'
        return path(root)

    def close(self):
        root = u(str(self.root))
        for key in self.conn.list(prefix=root):
            self.conn.delete(key['key'])
        # Don't delete the whole bucket !
        if root.endswith(u'/'):
            root = root[:-1]
        if root != u'':
            self.conn.delete(root)

    def mkdir(self, subdirs):
        subdirs = u(str(self.root)) + u(subdirs)
        self.write(subdirs, u'', True)

    def rmdir(self, path):
        path = u(str(self.root)) + u(path)
        self.unlink(path)

    def write(self, filename, content, includes_root=False):
        if not includes_root:
            filename = u(str(self.root) + filename)
        if sys.version_info.major == 3 and not isinstance(content, bytes):
            content = content.encode()
        s = IOStream(content)
        self.conn.upload(filename, s)
        s.close()

    def generate(self, filename, size):
        filename = u(str(self.root) + filename)
        self.write(filename, os.urandom(size), True)

    def unlink(self, filename):
        filename = u(str(self.root) + filename)
        if filename != u'':
            self.conn.delete(filename)

    def exists(self, filename):
        filename = u(str(self.root) + filename)
        try:
            self.conn.head_object(filename)
        except requests.HTTPError:
            return False
        return True

    def rename(self, source, target):
        source = u(str(self.root) + source)
        target = u(str(self.root) + target)
        bucket = u(self.options['bucket'])
        self.conn.copy(source, bucket, target, bucket)
        self.conn.delete(source)

    def checksum(self, filename):
        filename = u(str(self.root) + filename)
        file = self.conn.get(filename)
        return hashlib.md5(file.content).hexdigest()


class DriverFeatures(driver.DriverFeatures):
    pass
