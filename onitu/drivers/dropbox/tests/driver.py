import os
import hashlib
from path import path

from dropbox.session import DropboxSession
from dropbox.client import DropboxClient

from tests.utils.testdriver import TestDriver
from onitu.drivers.dropbox.dropbox_driver import (ONITU_APP_KEY,
                                                  ONITU_APP_SECRET,
                                                  ONITU_ACCESS_TYPE)


class Driver(TestDriver):
    def __init__(self, *args, **options):
        if 'root' not in options:
            options['root'] = '/onitu/'
        if 'key' not in options:
            options['key'] = os.environ['ONITU_DROPBOX_KEY']
        if 'secret' not in options:
            options['secret'] = os.environ['ONITU_DROPBOX_SECRET']
        if 'changes_timer' not in options:
            options['changes_timer'] = 60
        sess = DropboxSession(ONITU_APP_KEY,
                              ONITU_APP_SECRET,
                              ONITU_ACCESS_TYPE)
        # Use the OAuth access token previously retrieved by the user and typed
        # into Onitu configuration.
        sess.set_token(options['key'], options['secret'])
        self.dropbox_client = DropboxClient(sess)
        super(Driver, self).__init__('dropbox',
                                     *args,
                                     **options)


    @property
    def root(self):
        root = self.options['root']
        if not root.endswith('/'):
            root += '/'
        return path(root)

    def close(self):
        self.dropbox_client.file_delete(str(self.root))

    def mkdir(self, subdirs):
        self.dropbox_client.file_create_folder(str(self.root)+subdirs)

    def write(self, filename, content):
        filename = str(self.root) + filename
        self.dropbox_client.put_file(filename, content)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        self.dropbox_client.file_delete(str(self.root) + filename)

    def checksum(self, filename):
        data = self.dropbox_client.get_file(str(self.root) + filename)
        return hashlib.md5(data.read()).hexdigest()
