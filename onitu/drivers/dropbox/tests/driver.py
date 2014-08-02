import os
import hashlib
from path import path

from dropbox.session import DropboxSession
from dropbox.client import DropboxClient
from dropbox.rest import ErrorResponse

from tests.utils.testdriver import TestDriver
from onitu.drivers.dropbox.dropbox_driver import (ONITU_APP_KEY,
                                                  ONITU_APP_SECRET,
                                                  ONITU_ACCESS_TYPE)


class Driver(TestDriver):
    def __init__(self, *args, **options):
        if 'root' not in options:
            options['root'] = '/onitu/'
        if 'key' not in options:
            options['access_key'] = os.environ['ONITU_DROPBOX_KEY']
        if 'secret' not in options:
            options['access_secret'] = os.environ['ONITU_DROPBOX_SECRET']
        if 'changes_timer' not in options:
            options['changes_timer'] = 10
        sess = DropboxSession(ONITU_APP_KEY,
                              ONITU_APP_SECRET,
                              ONITU_ACCESS_TYPE)
        # Use the OAuth access token previously retrieved by the user and typed
        # into Onitu configuration.
        sess.set_token(options['access_key'], options['access_secret'])
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
        try:
            self.dropbox_client.file_delete(str(self.root))
        # It arrives that we try to delete the root twice.
        # When trying it Dropbox raises a 404 Error because the root
        # is already deleted. Since it isn't a real issue, we can ignore it
        except ErrorResponse:
            pass

    def mkdir(self, subdirs):
        self.dropbox_client.file_create_folder(str(self.root)+subdirs)

    def rmdir(self, path):
        filename = str(self.root) + path
        self.unlink(filename)

    def write(self, filename, content):
        filename = str(self.root) + filename
        self.dropbox_client.put_file(filename, content)

    def generate(self, filename, size):
        filename = str(self.root) + filename
        self.write(filename, os.urandom(size))

    def exists(self, filename):
        filename = str(self.root) + filename
        metadata = self.dropbox_client.metadata(filename,
                                                include_deleted=True)
        return not metadata.get('is_deleted', False)

    def unlink(self, filename):
        self.dropbox_client.file_delete(str(self.root) + filename)

    def rename(self, source, target):
        root = str(self.root)
        self.dropbox_client.file_move(from_path=root+source,
                                      to_path=root+target)

    def checksum(self, filename):
        data = self.dropbox_client.get_file(str(self.root) + filename)
        return hashlib.md5(data.read()).hexdigest()
