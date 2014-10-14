from onitu.plug import Plug
import libdrive
import threading
import time
import json
from onitu.plug.metadata import Metadata

global tree


mutex = threading.Lock()
plug = Plug()
ft = 'application/vnd.google-apps.folder'


def check_and_add_folder(metadata):
    mutex.acquire()
    global access_token
    global root_id
    global tree
    try:
        path = metadata.filename.split("/")
        path = [p for p in path if p != u""]
        tmproot = root_id
        if len(path) > 1:
            for f in path[:len(path)-1]:
                ret_val, _, data = libdrive.get_information(access_token,
                                                            f, tmproot)
                data = json.loads(data)
                if ret_val == 200:
                    if (data["items"] != []):
                        prev_id = tmproot
                        tmproot = data["items"][0]["id"]
                        tree[tmproot] = prev_id
                    else:
                        ret_val, _, data = libdrive.add_folder(access_token,
                                                               f, tmproot)
                        data = json.loads(data)
                        if ret_val == 200:
                            prev_id = tmproot
                            tmproot = data["id"]
                            tree[tmproot] = prev_id
                        else:
                            plug.logger.error("Can not add folder: "
                                              + data["error"]["message"])
                else:
                    plug.logger.error("Can not get information: "
                                      + data["error"]["message"])
    finally:
        mutex.release()
    return tmproot, path


def get_token():
    global access_token
    global token_expi

    if time.time() + 20.0 < token_expi:
        return
    ret_val, _, data = libdrive.get_token(plug.options["client_id"],
                                          plug.options["client_secret"],
                                          plug.options["refresh_token"])
    data = json.loads(data)
    if ret_val == 200:
        access_token = data["access_token"]
        token_expi = time.time() + data["expires_in"]
    else:
        plug.logger.error("Can not get token: " + data["error"]["message"])


@plug.handler()
def get_chunk(metadata, offset, size):
    if size > metadata.size:
        size = metadata.size
    ret_val, _, content = libdrive.get_chunk(access_token,
                                             metadata.extra["downloadUrl"],
                                             offset, size)
    return content


@plug.handler()
def start_upload(metadata):
    global access_token

    metadata.extra["inProcess"] = ""
    metadata.write()

    tmproot, path = check_and_add_folder(metadata)

    self_id = None
    if "id" in metadata.extra.keys():
        self_id = metadata.extra["id"]
    if metadata.size == 0:
        ret_val, h, data = libdrive.send_metadata(access_token,
                                                  path[len(path)-1],
                                                  tmproot, self_id, 0)
    else:
        ret_val, h, data = libdrive.start_upload(access_token,
                                                 path[len(path)-1],
                                                 tmproot, self_id)
        metadata.extra["location"] = h["location"]
    metadata.extra["parent_id"] = tmproot
    metadata.write()


@plug.handler()
def end_upload(metadata):
    global access_token
    del metadata.extra["inProcess"]
    if "location" in metadata.extra.keys():
        del metadata.extra["location"]
    path = metadata.filename.split("/")
    path = [p for p in path if p != u""]
    ret_val, _, data = libdrive.get_information(access_token,
                                                path[len(path)-1],
                                                metadata.extra["parent_id"])
    data = json.loads(data)
    if ret_val == 200:
        metadata.extra["id"] = data["items"][0]["id"]
        metadata.extra["revision"] = data["items"][0]["md5Checksum"]
        metadata.extra["downloadUrl"] = data["items"][0]["downloadUrl"]
        db = plug.entry_db
        db.put('listes:{}'.format(metadata.extra["id"]), metadata.fid)
    else:
        plug.logger.error("Can not get information: "
                          + data["error"]["message"])
    metadata.write()


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    global access_token
    ret_val, _, data = libdrive.upload_chunk(access_token,
                                             metadata.extra["location"],
                                             offset, chunk, metadata.size)
    if ret_val != 200 and ret_val != 308:
        data = json.loads(data)
        plug.logger.error("Can not upload chunk: " + data["error"]["message"])


@plug.handler()
def restart_upload(metadata, offset):
    start_upload(metadata)


@plug.handler()
def abort_upload(metadata):
    global tree
    if "id" in metadata.extra.keys():
        id_d = metadata.extra["id"]
        tree = {k: v for k, v in tree.items() if v == id_d or k == id_d}
        libdrive.delete_by_id(access_token, metadata.extra["id"])


@plug.handler()
def set_chunk_size(size):
    ret = size // (256*1024)
    if ret * 256 * 1024 == size:
        return size
    return (ret+1) * (256*1024)


@plug.handler()
def delete_file(metadata):
    global access_token
    global tree
    id_d = metadata.extra["id"]
    tree = {k: v for k, v in tree.items() if v == id_d or k == id_d}
    libdrive.delete_by_id(access_token, id_d)


@plug.handler()
def move_file(old_metadata, new_metadata):
    global access_token

    tmproot, path = check_and_add_folder(new_metadata)

    params = {
        "addParents": [tmproot],
        "removeParents":  [old_metadata.extra["parent_id"]]
        }
    ret_val, _, data = libdrive.send_metadata(access_token, path[len(path)-1],
                                              None, old_metadata.extra["id"],
                                              new_metadata.size, params)
    data = json.loads(data)
    if ret_val == 200:
        new_metadata.size = int(data["fileSize"])
        new_metadata.extra["revision"] = data["md5Checksum"]
        new_metadata.extra["id"] = data["id"]
        new_metadata.extra["parent_id"] = tmproot
        new_metadata.extra["downloadUrl"] = data["downloadUrl"]
    else:
        plug.logger.error("Can not send metadata: " + data["error"]["message"])
    new_metadata.write()


class CheckChanges(threading.Thread):

    def __init__(self, timer):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer
        self.lasterChangeId = 0

    def update_metadata(self, filepath, f):
        metadata = plug.get_metadata(filepath)
        while "inProcess" in metadata.extra.keys():
            metadata = plug.get_metadata(filepath)
            time.sleep(1)
        if "revision" in metadata.extra.keys():
            revision = metadata.extra["revision"]
            if f["md5Checksum"] != revision:
                metadata.size = int(f["fileSize"])
                metadata.extra["revision"] = f["md5Checksum"]
                plug.update_file(metadata)

    def check_folder_list_file(self, path, path_id):
        ret_val, _, data = libdrive.get_files_by_path(access_token, path_id)
        data = json.loads(data)
        if ret_val == 200:
            filelist = data
        else:
            plug.logger.error("Can not get file list: "
                              + data["error"]["message"])
            filelist = {"items": []}
        for f in filelist["items"]:
            if f["mimeType"] == "application/vnd.google-apps.folder":
                if path == "":
                    self.check_folder_list_file(f["title"], f["id"])
                else:
                    self.check_folder_list_file(path+"/"+f["title"], f["id"])
            else:
                if path == "":
                    filepath = f["title"]
                else:
                    filepath = path + "/" + f["title"]
                self.update_metadata(filepath, f)

    def add_to_buf(self, change, buf):
        cc = change["file"]["mimeType"]
        if cc != ft:
            t = {}
            t["id"] = change["file"]["id"]
            t["title"] = change["file"]["title"]
            t["parents"] = change["file"]["parents"][0]["id"]
            t["md5Checksum"] = change["file"]["md5Checksum"]
            t["fileSize"] = change["file"]["fileSize"]
            t["modificationDate"] = change["modificationDate"]
            c = change
            b = t["id"] in buf \
                and buf[t["id"]]["modificationDate"] < c["modificationDate"]
            if t["id"] not in buf or b:
                return (True, t)
        return (False, None)

    def add_to_bufdel(self, change):
        cc = change["mimeType"]
        if cc != ft:
            t = {}
            t["id"] = change["id"]
            t["title"] = change["title"]
            t["parents"] = change["parents"][0]["id"]
            t["md5Checksum"] = change["md5Checksum"]
            t["fileSize"] = change["fileSize"]
            return t
        return None

    def check_if_path_exist(self, path_id):
        global tree
        if path_id in tree:
            return True
        return False

    def get_path(self, parent_id):
        path = []
        global root_id
        global access_token
        global tree
        while parent_id != root_id and parent_id != "root":
            ret_val, _, data = libdrive.get_information_by_id(access_token,
                                                              parent_id)
            data = json.loads(data)
            if ret_val == 200:
                info = data
            else:
                plug.logger.error("Can not get information: "
                                  + data["error"]["message"])
            path.append(info["title"])
            parent_id = tree[parent_id]
        return "/".join(reversed(path))

    def check_if_parent_exist(self, file_id):
        global access_token
        global root_id
        global tree
        ret_val, _, data = libdrive.get_parent(access_token, file_id)
        parent = json.loads(data)
        if ret_val != 200:
            plug.logger.error("Can not get parent: "
                              + parent["error"]["message"])
        if "items" not in parent.keys():
            return False
        p = parent["items"][0]
        if self.check_if_path_exist(p["id"]):
            ret_val, _, data = libdrive.get_information_by_id(access_token,
                                                              p["id"])
            data = json.loads(data)
            if ret_val == 200:
                info = data
            else:
                plug.logger.error("Can not get information: "
                                  + data["error"]["message"])
            if info["mimeType"] == "application/vnd.google-apps.folder":
                tree[file_id] = p["id"]
            return True
        else:
            if p["isRoot"] is True or p["id"] == root_id:
                return False
            else:
                ret = self.check_if_parent_exist(p["id"])
                if ret is False:
                    return False
                else:
                    ret_v, _, d = libdrive.get_information_by_id(access_token,
                                                                 p["id"])
                    data = json.loads(d)
                    if ret_v == 200:
                        i = data
                    else:
                        plug.logger.error("Can not get information: "
                                          + data["error"]["message"])
                    if i["mimeType"] == "application/vnd.google-apps.folder":
                        tree[file_id] = p["id"]
                    return True

    def check_folder(self, path, path_id):
        global access_token
        global root_id
        global tree
        if self.lasterChangeId == 0:
            ret_val, _, data = libdrive.get_change(access_token, 1, 1)
            data = json.loads(data)
            if ret_val == 200:
                self.lasterChangeId = data["largestChangeId"]
            else:
                plug.logger.error("Can not get change: "
                                  + data["error"]["message"])
            self.check_folder_list_file("", root_id)
        else:
            buf = {}
            bufDel = {}
            page_token = None
            while True:
                ret_val, _, data = libdrive.get_change(access_token, 1000,
                                                       self.lasterChangeId)
                data = json.loads(data)
                if ret_val != 200:
                    plug.logger.error("Can not get change: "
                                      + data["error"]["message"])
                if self.lasterChangeId == data["largestChangeId"]:
                    return
                for change in data["items"]:
                    if change["deleted"] is True:
                        fileId = change["fileId"]
                        bufDel[change["fileId"]] = change["fileId"]
                        if fileId in buf:
                            del buf[fileId]
                    else:
                        b, tmp = self.add_to_buf(change, buf)
                        if b:
                            if tmp["id"] in bufDel:
                                del bufDel[tmp["id"]]
                            buf[tmp["id"]] = tmp
                self.lasterChangeId = data["largestChangeId"]
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            for id_file in buf.keys():
                f = buf[id_file]
                if self.check_if_path_exist(f["parents"]):
                    path = self.get_path(f["parents"])
                else:
                    if self.check_if_parent_exist(f["id"]) is False:
                        continue
                    path = self.get_path(f["parents"])
                if path == "":
                    filepath = f["title"]
                else:
                    filepath = path + "/" + f["title"]
                self.update_metadata(filepath, f)
            for id_file in bufDel.keys():
                db = plug.entry_db
                if db.exists('listes:{}'.format(id_file)):
                    fid = db.get('listes:{}'.format(id_file))
                    m = Metadata.get_by_id(plug, fid)
                    if m is not None:
                        plug.delete_file(m)

    def run(self):
        while not self.stop.isSet():
            get_token()
            self.check_folder("", root_id)
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start(*args, **kwargs):
    if plug.options["refresh_token"] != "":
        path = plug.options["root"].split("/")
        path = [p for p in path if p != u""]
        global access_token
        access_token = ""
        global token_expi
        token_expi = 0.0
        global root_id
        root_id = "root"
        global tree
        tree = {}
        get_token()
        for f in path:
            ret_val, _, data = libdrive.get_information(access_token,
                                                        f, root_id)
            data = json.loads(data)
            if ret_val == 200:
                if (data["items"] != []):
                    prev_id = root_id
                    root_id = data["items"][0]["id"]
                    tree[root_id] = prev_id
                else:
                    ret_val, _, data = libdrive.add_folder(access_token,
                                                           f, root_id)
                    data = json.loads(data)
                    if ret_val == 200:
                        prev_id = root_id
                        root_id = data["id"]
                        tree[root_id] = prev_id
                    else:
                        plug.logger.error("Can not add folder: "
                                          + data["error"]["message"])
            else:
                plug.logger.error("Can not get information: "
                                  + data["error"]["message"])
        check = CheckChanges(int(plug.options['changes_timer']))
        check.setDaemon(True)
        check.start()
        plug.listen()
    else:
        plug.logger.error("Error: You must specify a refresh_token, "
                          "Look at README in driver folder")
