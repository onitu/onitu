import os
import hashlib

from dropbox.session import DropboxSession
from dropbox.client import DropboxClient
from dropbox.rest import ErrorResponse

from tests.utils import driver
from onitu.utils import u, b, get_random_string
from onitu_dropbox.dropbox_driver import (ONITU_APP_KEY,
                                          ONITU_APP_SECRET,
                                          ONITU_ACCESS_TYPE)


class Driver(driver.Driver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        self._root = "/{}/".format(get_random_string(10))

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
        sess.set_token(options[u'access_key'], options[u'access_secret'])
        self.dropbox_client = DropboxClient(sess)
        super(Driver, self).__init__(u'dropbox',
                                     *args,
                                     **options)

    @property
    def root(self):
        return self._root

    def close(self):
        try:
            self.dropbox_client.file_delete(self.root)
        # It arrives that we try to delete the root twice.
        # When trying it Dropbox raises a 404 Error because the root
        # is already deleted. Since it isn't a real issue, we can ignore it
        except ErrorResponse:
            pass

    def mkdir(self, subdirs):
        self.dropbox_client.file_create_folder(u(subdirs))

    def rmdir(self, path):
        self.unlink(path)

    def write(self, filename, content):
        self.dropbox_client.put_file(u(filename), content)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def exists(self, filename):
        metadata = self.dropbox_client.metadata(
            u(filename),
            include_deleted=True
        )
        return not metadata.get(u'is_deleted', False)

    def unlink(self, filename):
        # Dropbox needs bytes for file_delete, for god-knows-what reason
        self.dropbox_client.file_delete(b(filename))

    def rename(self, source, target):
        # Same thing than for file_delete
        self.dropbox_client.file_move(
            from_path=b(source),
            to_path=b(target)
        )

    def checksum(self, filename):
        data = self.dropbox_client.get_file(u(filename))
        return hashlib.md5(data.read()).hexdigest()


class DriverFeatures(driver.DriverFeatures):
    move_file_to_onitu = False
    move_directory_to_onitu = False
    move_tree_to_onitu = False
    dectect_moved_file_on_launch = False
