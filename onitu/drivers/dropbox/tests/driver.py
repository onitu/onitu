import os

from path import path

from tests.utils.testdriver import TestDriver
from tests.utils.tempdirs import dirs
from onitu.drivers.dropbox.libDropbox import LibDropbox

class Driver(TestDriver):
    def __init__(self, *args, **options):
        if 'root' not in options:
            options['root'] = dirs.create()
        if 'key' not in options:
            options['key'] = "38jd72msqedx5n9"
        if 'secret' not in options:
            options['secret'] = "g4favy0bgjstt2w"
        if 'changes_timer' not in options:
            options['changes_timer'] = 600.0
        self.google_drive = LibDrive(options)
        super(Driver, self).__init__('dropbox',
                                     *args,
                                     **options)

    @property
    def root(self):
        return path(self.options['root'])

    def close(self):
        self.drop.delete_file('/')

    def mkdir(self, subdirs):
        self.drop.create_dir(subdirs+"/toto")

    def write(self, filename, content):
        metadata = {"size": len(content), "filename": filename}
        self.drop.upload_chunk(metadata, 0, content, len(content))

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        self.drop.delete_file(filename)

    def checksum(self, filename):
        return "LOL----LOL"
