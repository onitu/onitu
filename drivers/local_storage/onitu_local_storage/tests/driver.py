import os
import shutil
import hashlib
import tempfile

from path import path

from tests.utils import driver
from onitu.utils import b

class Driver(driver.Driver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        self._root = path(tempfile.mkdtemp())
        super(Driver, self).__init__('local_storage',
                                     *args,
                                     **options)

    @property
    def root(self):
        return self._root

    def close(self):
        self.root.rmtree('.')

    def mkdir(self, subdirs):
        (self.root / subdirs).makedirs_p()

        # Give some time to inotify in order
        # to avoid a known bug where new files
        # if a recently created directory are
        # ignored
        # cf http://stackoverflow.com/a/17586891/180751
        import time
        time.sleep(0.1)

    def rmdir(self, path):
        shutil.rmtree(self.root / path)

    def write(self, filename, content):
        with open(self.root / filename, 'wb+') as f:
            f.write(content)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def exists(self, filename):
        return os.path.exists(self.root / filename)

    def unlink(self, filename):
        return os.unlink(self.root / filename)

    def rename(self, source, target):
        return os.rename(self.root / source, self.root / target)

    def checksum(self, filename):
        with open(self.root / filename, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()


class DriverFeatures(driver.DriverFeatures):
    pass
