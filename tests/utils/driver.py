import os

import sh

from . import files
from .tempdirs import dirs


class Driver(object):
    def __init__(self, name):
        self.name = name


class LocalStorageDriver(Driver):
    def __init__(self, name):
        super(LocalStorageDriver, self).__init__(name)
        self.directory = dirs.create()

    @property
    def setup(self):
        return ('local_storage', self.name, {'root': self.directory})

    def close(self):
        dirs.delete(self.directory)

    def mkdir(self, subdirs):
        return sh.mkdir('-p', os.path.join(self.directory, subdirs))

    def generate(self, filename, size):
        return files.generate(os.path.join(self.directory, filename),
                              size)

    def unlink(self, filename):
        return os.unlink(os.path.join(self.directory, filename))

    def checksum(self, filename):
        return files.checksum(os.path.join(self.directory, filename))


class TargetDriver(Driver):
    _types = {
        'local_storage': LocalStorageDriver
    }

    def __new__(cls, name):
        driver = os.environ.get('ONITU_TEST_DRIVER', 'local_storage')
        try:
            driver_type = cls._types[driver]
        except KeyError:
            raise KeyError("No such driver {}".format(repr(driver)))
        return driver_type(name)
