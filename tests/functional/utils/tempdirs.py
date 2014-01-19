import tempfile
from shutil import rmtree


class TempDirs(object):
    def __init__(self):
        self.dirs = set()

    def __del__(self):
        for d in self.dirs:
            rmtree(d)

    def create(self):
        d = tempfile.mkdtemp()
        self.dirs.add(d)
        return d
