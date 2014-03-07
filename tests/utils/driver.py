import os

import sh

from . import files
from .tempdirs import dirs


class Driver(object):
    def __init__(self, name, chunk_size=None):
        self.type = None
        self.root = None
        self.name = name
        self.chunk_size = chunk_size

    def options(self):
        options = {
            'root': self.root
        }

        if self.chunk_size:
            options['chunk_size'] = self.chunk_size

        return options

    @property
    def setup(self):
        return (self.type, self.name, self.options())


class LocalStorageDriver(Driver):
    def __init__(self, *args, **kwargs):
        super(LocalStorageDriver, self).__init__(*args, **kwargs)
        self.type = 'local_storage'
        self.root = dirs.create()

    def close(self):
        dirs.delete(self.root)

    def mkdir(self, subdirs):
        return sh.mkdir('-p', os.path.join(self.root, subdirs))

    def write(self, filename, content):
        with open(os.path.join(self.root, filename), 'w+') as f:
            f.write(content)

    def generate(self, filename, size):
        return files.generate(os.path.join(self.root, filename), size)

    def unlink(self, filename):
        return os.unlink(os.path.join(self.root, filename))

    def checksum(self, filename):
        return files.checksum(os.path.join(self.root, filename))


class TargetDriver(Driver):
    _types = {
        'local_storage': LocalStorageDriver
    }

    def __new__(cls, *args, **kwargs):
        driver = os.environ.get('ONITU_TEST_DRIVER', 'local_storage')
        try:
            driver_type = cls._types[driver]
        except KeyError:
            raise KeyError("No such driver {}".format(repr(driver)))
        return driver_type(*args, **kwargs)
