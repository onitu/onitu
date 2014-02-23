import os

import sh

from utils import files
from utils.tempdirs import dirs


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

    def mkdir(self, subdirs):
        return sh.mkdir('-p', os.path.join(self.directory, subdirs))

    def touch(self, filename):
        return sh.touch(os.path.join(self.directory, filename))

    def generate(self, filename, bs, count=1):
        return files.generate(os.path.join(self.directory, filename),
                              bs, count)

    def unlink(self, filename):
        return os.unlink(os.path.join(self.directory, filename))

    def filesize(self, filename):
        return os.path.getsize(os.path.join(self.directory, filename))

    def checksum(self, filename):
        return files.checksum(os.path.join(self.directory, filename))
