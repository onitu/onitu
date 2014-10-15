import os
import time
import json
import tempfile

from path import path

from tests.utils.testdriver import TestDriver
from onitu_google_drive import libdrive


refresh_token = "1/ezUs-qa0qMRXYDj4x0rcq0ODO_1nG-qiG-3POqzjs8w"


class Driver(TestDriver):
    def __init__(self, *args, **options):
        tmp = tempfile.NamedTemporaryFile()
        _, fileName = os.path.split(tmp.name)
        if 'root' not in options:
            options['root'] = fileName
        if 'refresh_token' not in options:
            options['refresh_token'] = refresh_token
        if 'client_id' not in options:
            options['client_id'] = "6155769202.apps.googleusercontent.com"
        if 'client_secret' not in options:
            options['client_secret'] = "ZcxluuTcGL2WkurnYSJgJvbN"
        if 'changes_timer' not in options:
            options['changes_timer'] = 2.0
        self.root_id = "root"
        self.token_expi = 0
        self.access_token = ""
        self.options = options
        self.get_token(options['client_id'], options['client_secret'])

        path = options["root"].split("/")
        path = [p for p in path if p != u""]

        for f in path:
            ret_val, _, data = libdrive.get_information(self.access_token, f,
                                                        self.root_id)
            if ret_val == 200:
                if (data["items"] != []):
                    self.root_id = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token,
                                                           f, self.root_id)
                    if ret_val == 200:
                        self.root_id = data["id"]

        super(Driver, self).__init__('google_drive',
                                     *args,
                                     **options)

    def get_token(self, client_id, client_secret):
        if time.time() + 20.0 < self.token_expi:
            return
        ret_val, _, data = libdrive.get_token(self.options['client_id'],
                                              self.options['client_secret'],
                                              refresh_token)
        if ret_val == 200:
            self.access_token = data["access_token"]
            self.token_expi = time.time() + data["expires_in"]

    @property
    def root(self):
        return path(self.options['root'])

    def close(self):
        self.get_token(self.options['client_id'],
                       self.options['client_secret'])
        libdrive.delete_by_id(self.access_token, self.root_id)

    def mkdir(self, subdirs):
        self.get_token(self.options['client_id'],
                       self.options['client_secret'])
        path = subdirs.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        for f in path:
            ret_val, _, data = libdrive.get_information(self.access_token,
                                                        f, tmproot)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token,
                                                           f, tmproot)
                    if ret_val == 200:
                        tmproot = data["id"]

    def write(self, filename, content):
        self.get_token(self.options['client_id'],
                       self.options['client_secret'])
        path = filename.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        if len(path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(self.access_token,
                                                            f, tmproot)
                if ret_val == 200:
                    if (data["items"] != []):
                        tmproot = data["items"][0]["id"]
                    else:
                        ret_val, _, d = libdrive.add_folder(self.access_token,
                                                            f, tmproot)
                        if ret_val == 200:
                            tmproot = d["id"]
        self_id = None
        ret_val, h, data = libdrive.start_upload(self.access_token,
                                                 path[len(path)-1],
                                                 tmproot,
                                                 self_id)
        ret_val, _, data = libdrive.upload_chunk(self.access_token,
                                                 h["location"],
                                                 0, content, len(content))

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        self.get_token(self.options['client_id'],
                       self.options['client_secret'])
        path = filename.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(self.access_token,
                                                        f, tmproot)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token,
                                                           f, tmproot)
                    if ret_val == 200:
                        tmproot = data["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(self.access_token,
                                                    path[len(path)-1],
                                                    id_folder)
        libdrive.delete_by_id(self.access_token, info["items"][0]["id"])

    def checksum(self, filename):
        self.get_token(self.options['client_id'],
                       self.options['client_secret'])
        path = filename.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(self.access_token,
                                                        f, tmproot)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(self.access_token,
                                                    path[len(path)-1],
                                                    id_folder)
        return info["items"][0]["md5Checksum"]

    def exists(self, filename):
        self.get_token(self.options['client_id'],
                       self.options['client_secret'])
        tmproot = self.root_id
        path = filename.split("/")
        path = [p for p in path if p != u""]
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(self.access_token,
                                                        f,
                                                        tmproot)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token,
                                                           f, tmproot)
                    if ret_val == 200:
                        tmproot = data["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(self.access_token,
                                                    path[len(path)-1],
                                                    id_folder)
        if info["items"] != []:
            return True
        return False

    def rename(self, old, new):
        path = old.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        if len(path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(self.access_token,
                                                            f, tmproot)
                if ret_val == 200:
                    if (data["items"] != []):
                        tmproot = data["items"][0]["id"]
                    else:
                        ret_val, _, d = libdrive.add_folder(self.access_token,
                                                            f, tmproot)
                        if ret_val == 200:
                            tmproot = d["id"]
        _, _, old_data = libdrive.get_information(self.access_token,
                                              path[len(path)-1], tmproot)

        path = new.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        if len(path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(self.access_token,
                                                            f, tmproot)
                if ret_val == 200:
                    if (data["items"] != []):
                        tmproot = data["items"][0]["id"]
                    else:
                        ret_val, _, d = libdrive.add_folder(self.access_token,
                                                            f, tmproot)
                        if ret_val == 200:
                            tmproot = d["id"]
        ret_v, _, _ = libdrive.send_metadata(self.access_token,
                                             path[len(path)-1],
                                             tmproot,
                                             old_data["items"][0]["id"],
                                             old_data["items"][0]["fileSize"])
