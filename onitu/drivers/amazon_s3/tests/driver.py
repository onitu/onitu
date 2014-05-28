import hashlib
import os
from path import path

import boto

from tests.utils.testdriver import TestDriver
from tests.utils.tempdirs import dirs


class Driver(TestDriver):
    def __init__(self, *args, **options):
        if "root" not in options:
            options['root'] = dirs.create()
        if "aws_access_key" not in options:
            options["aws_access_key"] = os.environ["ONITU_AWS_ACCESS_KEY"]
        if "aws_secret_key" not in options:
            options["aws_secret_key"] = os.environ["ONITU_AWS_SECRET_KEY"]
        if "bucket" not in options:
            options["bucket"] = 'onitu-test-2'
        self.conn = boto.connect_s3(
            aws_access_key_id=options["aws_access_key"],
            aws_secret_access_key=options["aws_secret_key"])
        super(Driver, self).__init__('amazon_s3',
                                     *args,
                                     **options)

    def create_file(self, filename, content=""):
        bucket = self.conn.get_bucket(self.options["bucket"])
        key = boto.s3.key.Key(bucket)
        key.key = filename
        key.set_contents_from_string(content)
        
    @property
    def root(self):
        return path(self.options['root'])

    def close(self):
        bucket = self.conn.get_bucket(self.options["bucket"])
        todel = self.options['root']
        if not todel.endswith('/'):
            todel += '/'
        for key in bucket.list(prefix=todel):
            bucket.delete_key(key)
        bucket.delete_key(self.options['root'])

    def mkdir(self, subdirs):
        self.create_file(subdirs)

    def write(self, filename, content):
        bucket = self.conn.get_bucket(self.options["bucket"])
        key = bucket.get_key(filename)
        if key is None:
            self.create_file(filename, content)
        else:
            key.set_contents_from_string(content)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        bucket = self.conn.get_bucket(self.options["bucket"])
        bucket.delete_key(filename)

    def checksum(self, filename):
        bucket = self.conn.get_bucket(self.options["bucket"])
        key = bucket.get_key(filename)
        contents = key.get_contents_as_string()
        return hashlib.md5(contents).hexdigest()
