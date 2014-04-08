import os

import sh

from tests.utils.testdriver import TestDriver
from tests.utils import files
from tests.utils.tempdirs import dirs


class Driver(TestDriver):
    def __init__(self, *args, **options):
        if 'root' not in options:
            options['root'] = dirs.create()
        super(Driver, self).__init__('local_storage',
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
