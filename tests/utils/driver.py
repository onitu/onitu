import os
import re

import sh

from . import files
from .tempdirs import dirs


class Driver(object):
    def __init__(self, type, name=None, **options):
        self.type = type
        self.name = name if name else type
        self.options = options

    @property
    def slugname(self):
        return re.sub(r'__+', '_', re.sub(r'[^a-z0-9]', '_',
                                          self.name.lower()))

    @property
    def dump(self):
        return {'driver': self.type, 'options': self.options}

    @property
    def id(self):
        return (self.type, self.name)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


class LocalStorageDriver(Driver):
    def __init__(self, *args, **options):
        if 'root' not in options:
            options['root'] = dirs.create()
        super(LocalStorageDriver, self).__init__('local_storage',
                                                 *args,
                                                 **options)

    @property
    def root(self):
        return self.options['root']

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
