import hashlib
import os
import requests

from onitu_hubic import Hubic
from onitu.utils import b, u, get_random_string

from onitu.plug import ServiceError
from tests.utils import driver

# Those two are set in the manifest.json but that is not yet parsed
# at this point so we hardcode them here.
CLIENTID = \
    "api_hubic_yExkTKwof2zteYA8kQG4gYFmnmHVJoNl"
CLIENTSECRET = \
    "CWN2NMOVwM4wjsg3RFRMmE6OpUNJhsADLaiduV49e7SpBsHDAKdtm5WeR5KEaDvc"

# This needs to be updated using the script and will be used during the tests.
REFRESHTOKEN = \
    "Iz7vAcy3yMpTLNb4eDEvr4JfxPHrxj23rV1oeOm9VZb3GCCdiuKtJiB8TV0S5eY2"


class Driver(driver.Driver):

    def __init__(self, *args, **options):
        if 'client_id' not in options:
            options['client_id'] = CLIENTID
        if 'client_secret' not in options:
            options['client_secret'] = CLIENTSECRET
        if 'refresh_token' not in options:
            options['refresh_token'] = REFRESHTOKEN
        if 'changes_timer' not in options:
            options['changes_timer'] = 2

        self._root = get_random_string(10)

        self.hubic = Hubic(options['client_id'], options['client_secret'],
                           options['refresh_token'], self.root)

        super(Driver, self).__init__('hubic', *args, **options)

    @property
    def root(self):
        return self._root

    def get_path(self, filename):
        return u(os.path.join(self.root, filename))

    def mkdir(self, subdirs):
        # We don't need to create subdirs on Hubic
        pass

    def write(self, filename, content):
        filename = self.hubic.get_path(filename)
        self.hubic.os_call('put', 'default/' + filename, content)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        filename = self.get_path(filename)
        if filename != '':
            self.hubic.os_call('delete', 'default/' + filename)

    def close(self):
        path = self.get_path('')
        if path.endswith('/'):
            path = path[:-1]
        try:
            self.hubic.os_call('delete', 'default/' + path)
        except requests.HTTPError:
            pass

    def rmdir(self, path):
        filename = self.get_path(path)
        self.hubic.os_call('delete', 'default/' + filename)

    def exists(self, filename):
        filename = self.get_path(filename)
        try:
            self.hubic.os_call('head', 'default/' + filename)
        except requests.HTTPError:
            return False
        return True

    def rename(self, source, target):
        old_filename = self.get_path(source)
        new_filename = self.get_path(target)

        headers = {'X-Copy-From': 'default/' + b(old_filename)}

        try:
            self.hubic.os_call('put', 'default/' + new_filename,
                               headers=headers)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                u"Cannot rename file '{}' to '{}': {}".format(
                    old_filename, new_filename, e
                    )
                )

        self.unlink(source)

    def checksum(self, filename):
        filename = self.get_path(filename)
        headers = {'Range': 'FIRST_BYTE_OFFSET-LAST_BYTE_OFFSET'}
        f = self.hubic.os_call('get', 'default/' + filename,
                               headers=headers).content
        return hashlib.md5(f).hexdigest()


class DriverFeatures(driver.DriverFeatures):

    # This features aren't functional in this driver.

    del_file_to_onitu = False
    del_directory_to_onitu = False
    copy_tree_to_onitu = False
    del_tree_to_onitu = False
    detect_del_file_on_launch = False
    detect_moved_file_on_launch = False
    move_file_to_onitu = False
    move_directory_to_onitu = False
