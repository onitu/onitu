import os

from path import path

from tests.utils.testdriver import TestDriver
from tests.utils.tempdirs import dirs
from onitu.drivers.google_drive.libdrive import LibDrive

refresh_token = "1/ezUs-qa0qMRXYDj4x0rcq0ODO_1nG-qiG-3POqzjs8w"


class Driver(TestDriver):
    def __init__(self, *args, **options):
        if 'root' not in options:
            options['root'] = dirs.create()
        if 'refresh_token' not in options:
            options['refresh_token'] = refresh_token
        if 'client_id' not in options:
            options['client_id'] = "6155769202.apps.googleusercontent.com"
        if 'client_secret' not in options:
            options['client_secret'] = "ZcxluuTcGL2WkurnYSJgJvbN"
        if 'changes_timer' not in options:
            options['changes_timer'] = 2.0
        self.google_drive = LibDrive(options)
        super(Driver, self).__init__('google_drive',
                                     *args,
                                     **options)

    @property
    def root(self):
        return path(self.options['root'])

    def close(self):
        self.google_drive.delete_id(self.google_drive.folder_root_id)

    def mkdir(self, subdirs):
        self.google_drive.add_folders(subdirs+"/toto", False)

    def write(self, filename, content):
        self.google_drive.start_upload(filename, len(content))
        self.google_drive.upload_chunk(filename, 0, content, len(content))
        self.google_drive.end_upload(filename)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        path = self.google_drive.parse_path(filename)
        id_folder = self.google_drive.add_folders(path, False)
        info = self.google_drive.get_information(path[len(path)-1], id_folder)
        self.google_drive.delete_id(info["items"][0]["id"])

    def checksum(self, filename):
        path = self.google_drive.parse_path(filename)
        id_folder = self.google_drive.add_folders(path, False)
        info = self.google_drive.get_information(path[len(path)-1], id_folder)
        return info["items"][0]["md5Checksum"]

    def exists(self, filename):
        path = self.google_drive.parse_path(filename)
        id_folder = self.google_drive.add_folders(path, False)
        info = self.google_drive.get_information(path[len(path)-1], id_folder)
        if info["items"] != []:
            return True
        return False
