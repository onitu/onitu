import os
import shutil

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
        with open(self.root / filename, 'w+') as f:
            f.write(content)

    def generate(self, filename, size):
        return files.generate(self.root / filename, size)

    def exists(self, filename):
        return os.path.exists(self.root / filename)

    def unlink(self, filename):
        return os.unlink(self.root / filename)

    def rename(self, source, target):
        return os.rename(self.root / source, self.root / target)

    def checksum(self, filename):
        return files.checksum(self.root / filename)
