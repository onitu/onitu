import hashlib
import os
import requests

from onitu.plug import ServiceError
from onitu.drivers.hubic import Hubic
from tests.utils.testdriver import TestDriver


class Driver(TestDriver):

    def __init__(self, *args, **options):
        if "root" not in options:
            options['root'] = 'onitu_tests'
        if "client_id" not in options:
            options['client_id'] = ''
        if "client_secret" not in options:
            options['client_secret'] = ''
        if "refresh_token" not in options:
            options['refresh_token'] = ''
        if "changes_timer" not in options:
            options['changes_timer'] = 15

        self.hubic = Hubic(options['client_id'], options['client_secret'],
                           options['refresh_token'], options['root'])

        super(Driver, self).__init__('hubic',
                                     *args,
                                     **options)

    def get_path(self, filename):
        return str(os.path.join(self.options['root'], filename))

    def mkdir(self, subdirs):
        subdirs = self.get_path(subdirs)
        self.hubic.create_folders(subdirs)

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
        path = self.hubic.get_path('')
        if path.endswith('/'):
            path = path[:-1]
        try:
            self.hubic.os_call('delete', 'default/' + path)
        except requests.HTTPError:
            pass

    def rmdir(self, path):
        filename = self.hubic.get_path(path)
        self.hubic.os_call('delete', 'default/' + filename)

    def exists(self, filename):
        filename = self.get_path(filename)
        try:
            self.hubic.os_call('head', 'default/' + filename)
        except requests.HTTPError:
            return False
        return True

    def rename(self, source, target):
        old_filename = self.hubic.get_path(source)
        new_filename = self.hubic.get_path(target)

        self.hubic.create_folders(os.path.dirname(target))

        headers = {'X-Copy-From': 'default/' + old_filename}

        try:
            self.hubic.os_call('put', 'default/' + new_filename,
                               headers=headers)
        except requests.exceptions.RequestException as e:
            raise ServiceError(
                "Cannot rename file '{}' to '{}': {}".format(
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
