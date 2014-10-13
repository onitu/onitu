import os
import time
import json
import tempfile

from path import path

from tests.utils.testdriver import TestDriver
from tests.utils.tempdirs import dirs
import onitu_google_drive.libdrive as libdrive


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
        self.get_token(options['client_id'], options['client_secret'])
	self.options = options

        path = options["root"].split("/")
	path = [p for p in path if p != u""]

        for f in path:
            ret_val, _, data = libdrive.get_information(self.access_token, f, self.root_id)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    self.root_id = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token, f, self.root_id)
		    data = json.loads(data)
                    if ret_val == 200:
                        self.root_id = data["id"]

        super(Driver, self).__init__('google_drive',
                                     *args,
                                     **options)

    def get_token(self, client_id, client_secret):
        if time.time() + 20.0 < self.token_expi:
            return
        ret_val, _, data = libdrive.get_token("6155769202.apps.googleusercontent.com",
                                              "ZcxluuTcGL2WkurnYSJgJvbN",
                                              refresh_token)
        data = json.loads(data)
        if ret_val == 200:
            self.access_token = data["access_token"]
            self.token_expi = time.time() + data["expires_in"]

    @property
    def root(self):
        return path(self.options['root'])

    def close(self):
        self.get_token(self.options['client_id'], self.options['client_secret'])
        libdrive.delete_by_id(self.access_token, self.root_id)
        #self.google_drive.delete_id(self.google_drive.folder_root_id)

    def mkdir(self, subdirs):
        self.get_token(self.options['client_id'], self.options['client_secret'])
        path = subdirs.split("/")
	path = [p for p in path if p != u""]
        tmproot = self.root_id
        for f in path:
            ret_val, _, data = libdrive.get_information(self.access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token, f, tmproot)
                    if ret_val == 200:
                        data = json.loads(data)
                        tmproot = data["id"]
    # self.google_drive.add_folders(subdirs+"/toto", False)

    def write(self, filename, content):
        self.get_token(self.options['client_id'], self.options['client_secret'])
        path = filename.split("/")
	path = [p for p in path if p != u""]
        tmproot = self.root_id
        if len (path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(self.access_token, f, tmproot)
                data = json.loads(data)
                if ret_val == 200:
                    if (data["items"] != []):
                        tmproot = data["items"][0]["id"]
                    else:
                        ret_val, _, data = libdrive.add_folder(self.access_token, f, tmproot)
                        if ret_val == 200:
                            data = json.loads(data)
                            tmproot = data["id"]
        self_id = None
        ret_val, h, data = libdrive.start_upload(self.access_token, path[len(path)-1], tmproot, self_id)
        ret_val, _, data = libdrive.upload_chunk(self.access_token, h["location"],
                                                 0, content, len(content))
        
        # self.google_drive.start_upload(filename, len(content))
        # self.google_drive.upload_chunk(filename, 0, content, len(content))
        # self.google_drive.end_upload(filename)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        self.get_token(self.options['client_id'], self.options['client_secret'])
        path = filename.split("/")
	path = [p for p in path if p != u""]
        tmproot = self.root_id
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(self.access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token, f, tmproot)
                    if ret_val == 200:
                        data = json.loads(data)
                        tmproot = data["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(self.access_token, path[len(path)-1], id_folder)
        info = json.loads(info)
        libdrive.delete_by_id(self.access_token, info["items"][0]["id"])

    def checksum(self, filename):
        self.get_token(self.options['client_id'], self.options['client_secret'])
        path = filename.split("/")
	path = [p for p in path if p != u""]
	tmproot = self.root_id
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(self.access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(self.access_token, path[len(path)-1], id_folder)
        info = json.loads(info)
        return info["items"][0]["md5Checksum"]

    def exists(self, filename):
        self.get_token(self.options['client_id'], self.options['client_secret'])
        tmproot = self.root_id
        path = filename.split("/")
	path = [p for p in path if p != u""]
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(self.access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(self.access_token, f, tmproot)
                    if ret_val == 200:
                        data = json.loads(data)
                        tmproot = data["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(self.access_token, path[len(path)-1], id_folder)
        info = json.loads(info)
        if info["items"] != []:
            return True
        return False

    def rename(self, old, new):
        path = old.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        if len (path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(self.access_token, f, tmproot)
                data = json.loads(data)
                if ret_val == 200:
                    if (data["items"] != []):
                        prev_id = tmproot
                        tmproot = data["items"][0]["id"]
                        tree[tmproot] = prev_id
                    else:
                        ret_val, _, data = libdrive.add_folder(self.access_token, f, tmproot)
                        if ret_val == 200:
                            data = json.loads(data)
                            prev_id = tmproot
                            tmproot = data["id"]
                            tree[tmproot] = prev_id
        _, _, data = libdrive.get_information(self.access_token, path[len(path)-1], tmproot)

        old_data = json.loads(data)
        
        path = new.split("/")
        path = [p for p in path if p != u""]
        tmproot = self.root_id
        if len (path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(self.access_token, f, tmproot)
                data = json.loads(data)
                if ret_val == 200:
                    if (data["items"] != []):
                        prev_id = tmproot
                        tmproot = data["items"][0]["id"]
                        tree[tmproot] = prev_id
                    else:
                        ret_val, _, data = libdrive.add_folder(self.access_token, f, tmproot)
                        if ret_val == 200:
                            data = json.loads(data)
                            prev_id = tmproot
                            tmproot = data["id"]
                            tree[tmproot] = prev_id
        ret_val, _, data = libdrive.send_metadata(self.access_token, path[len(path)-1],
                                                  tmproot, old_data["items"][0]["id"], old_data["items"][0]["fileSize"])
