import os
import time
import json

from path import path

from tests.utils.testdriver import TestDriver
from tests.utils.tempdirs import dirs
import onitu.drivers.google_drive.libdrive as libdrive


refresh_token = "1/ezUs-qa0qMRXYDj4x0rcq0ODO_1nG-qiG-3POqzjs8w"


def get_token(client_id, client_secret):
    global access_token
    global token_expi
    if time.time() + 20.0 < token_expi:
        return
    ret_val, _, data = libdrive.get_token("6155769202.apps.googleusercontent.com",
                                          "ZcxluuTcGL2WkurnYSJgJvbN",
                                          refresh_token)
    data = json.loads(data)
    if ret_val == 200:
        access_token = data["access_token"]
        token_expi = time.time() + data["expires_in"]
    else:
        plug.logger.error("Can not get token: " + data["error"]["message"])


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
        global root_id
        root_id = "root"
        global token_expi
        token_expi = 0
        global access_token
        access_token = ""
        get_token(options['client_id'], options['client_secret'])
	self.options = options
        super(Driver, self).__init__('google_drive',
                                     *args,
                                     **options)

    @property
    def root(self):
        return path(self.options['root'])

    def close(self):
        get_token(self.options['client_id'], self.options['client_secret'])
	global root_id
	global access_token
        libdrive.delete_by_id(access_token, root_id)
        #self.google_drive.delete_id(self.google_drive.folder_root_id)

    def mkdir(self, subdirs):
        get_token(self.options['client_id'], self.options['client_secret'])
	global root_id
	global access_token
        path = subdirs.split("/")
        tmproot = root_id
        for f in path:
            ret_val, _, data = libdrive.get_information(access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(access_token, f, tmproot)
                    if ret_val == 200:
                        data = json.loads(data)
                        tmproot = data["id"]
    # self.google_drive.add_folders(subdirs+"/toto", False)

    def write(self, filename, content):
        get_token(self.options['client_id'], self.options['client_secret'])
	global root_id
	global access_token
        path = filename.split("/")
        tmproot = root_id
        if len (path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(access_token, f, tmproot)
                data = json.loads(data)
                if ret_val == 200:
                    if (data["items"] != []):
                        tmproot = data["items"][0]["id"]
                    else:
                        ret_val, _, data = libdrive.add_folder(access_token, f, tmproot)
                        if ret_val == 200:
                            data = json.loads(data)
                            tmproot = data["id"]
        self_id = None
        ret_val, h, data = libdrive.start_upload(access_token, path[len(path)-1], tmproot, self_id)
        ret_val, _, data = libdrive.upload_chunk(access_token, h["location"],
                                                 0, content, len(content))
        
        # self.google_drive.start_upload(filename, len(content))
        # self.google_drive.upload_chunk(filename, 0, content, len(content))
        # self.google_drive.end_upload(filename)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def unlink(self, filename):
        get_token(self.options['client_id'], self.options['client_secret'])
	global root_id
	global access_token
        path = filename.split("/")
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(access_token, f, tmproot)
                    if ret_val == 200:
                        data = json.loads(data)
                        tmproot = data["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(access_token, path[len(path)-1], id_folder)
        info = json.loads(info)
        libdrive.delete_by_id(access_token, info["items"][0]["id"])

    def checksum(self, filename):
        get_token(self.options['client_id'], self.options['client_secret'])
	global root_id
	global access_token
        path = filename.split("/")
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(access_token, f, tmproot)
                    if ret_val == 200:
                        data = json.loads(data)
                        tmproot = data["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(access_token, path[len(path)-1], id_folder)
        info = json.loads(info)
        return info["items"][0]["md5Checksum"]

    def exists(self, filename):
        get_token(self.options['client_id'], self.options['client_secret'])
	global root_id
	global access_token
        path = filename.split("/")
        for f in path[:len(path)-1]:
            ret_val, _, data = libdrive.get_information(access_token, f, tmproot)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    tmproot = data["items"][0]["id"]
                else:
                    ret_val, _, data = libdrive.add_folder(access_token, f, tmproot)
                    if ret_val == 200:
                        data = json.loads(data)
                        tmproot = data["id"]
        id_folder = tmproot
        ret_val, _, info = libdrive.get_information(access_token, path[len(path)-1], id_folder)
        info = json.loads(info)
        if info["items"] != []:
            return True
        return False
