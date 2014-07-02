import os

import sh
from path import path

from tests.utils.testdriver import TestDriver
from tests.utils import files
from tests.utils.tempdirs import dirs


class Driver(TestDriver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        if 'root' not in options:
            options['root'] = dirs.create()
        super(Driver, self).__init__('local_storage',
                                     *args,
                                     **options)

    @property
    def root(self):
        return path(self.options['root'])

    def close(self):
        dirs.delete(self.root)

    def mkdir(self, subdirs):
        return sh.mkdir('-p', self.root / subdirs)

    def write(self, filename, content):
        with open(self.root / filename, 'w+') as f:
            f.write(content)

    def generate(self, filename, size):
        return files.generate(self.root / filename, size)

    def exists(self, filename):
        return os.path.exists(self.root / filename)

    def unlink(self, filename):
        return os.unlink(self.root / filename)

    def checksum(self, filename):
        return files.checksum(self.root / filename)
