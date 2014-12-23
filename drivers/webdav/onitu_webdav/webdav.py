import os
import threading
import datetime

import easywebdav

from path import path

from onitu.plug import Plug, ServiceError
from onitu.escalator.client import EscalatorClosed
from onitu.utils import u

TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S %Z'
plug = Plug()
root = None
webdav = None
prefix = None
events_to_ignore = set()


def create_dirs(webdav, path):
    plug.logger.debug("create dirs: {}", path)
    webdav.mkdirs(path)


@plug.handler()
def get_file(metadata):
    try:
        plug.logger.debug("get file, metadata {}", metadata.path)
        # TODO: we should not have a local file.
        local_file = "/tmp/{}.onitu-tmp".format(
            os.path.basename(metadata.path)
        )
        webdav.download(metadata.path, local_file)
        with open(local_file, 'r') as f:
            data = f.read()
        return data

    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def start_upload(metadata):
    plug.logger.debug("start upload: {}", metadata.path)
    events_to_ignore.add(metadata.path)
    create_dirs(webdav, os.path.dirname(metadata.path))


@plug.handler()
def upload_file(metadata, content):
    try:
        plug.logger.debug("upload file, metadata {}", metadata.path)
        local_file = "/tmp/{}.onitu-tmp".format(
            os.path.basename(metadata.path)
        )
        with open(u(local_file), 'w') as f:
            f.write(content)
        webdav.upload(content, metadata.path)
    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error writting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def end_upload(metadata):
    try:
        plug.logger.debug("end upload, metadata {}", metadata.path)
        f = webdav.ls(metadata.path)[0]
        metadata.extra['revision'] = f.mtime
        metadata.write()

    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error while updating metadata on file '{}': {}".format(
                metadata.path, e)
        )
    finally:
        if metadata.path in events_to_ignore:
            events_to_ignore.remove(metadata.path)


def update_file(metadata, f):
    try:
        metadata.size = f.size
        metadata.extra['revision'] = f.mtime
        metadata.write()
        plug.update_file(metadata)
    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.path, e)
        )


class CheckChanges(threading.Thread):

    def __init__(self, timer, webdav):
        super(CheckChanges, self).__init__()
        self.stop = threading.Event()
        self.timer = timer
        self.webdav = webdav

    def check_folder(self, path=''):
        plug.logger.debug("check folder: path {}", path)
        try:
            filelist = self.webdav.ls(path)
        except easywebdav.client.OperationFailed as e:
            raise ServiceError(
                "Error listing file in '{}': {}".format(path, e)
            )

        for f in filelist[1:]:
            filepath = u(f.name.replace(prefix, ""))

            # TODO: is it the same thing with a webdav server on windows?
            if f.contenttype == "httpd/unix-directory":
                self.check_folder(filepath)
            else:
                relpath = root.relpathto(filepath)
                metadata = plug.get_metadata(relpath)
                if metadata is None:
                    continue
                mtime_onitu = metadata.extra.get(
                    'revision',
                    datetime.datetime.min
                )
                mtime_local = datetime.datetime.strptime(
                    f.mtime, TIMESTAMP_FMT
                )
                if mtime_local > mtime_onitu:
                    update_file(metadata, f)

    def run(self):
        while not self.stop.isSet():
            try:
                self.check_folder()
            except EscalatorClosed:
                # We are closing
                return
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    global root

    # Clean the root
    root = plug.root
    if root.endswith('/'):
        root = root[:-1]
    root = path(root)

    protocol = plug.options['protocol']
    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    port = plug.options['port']
    timer = plug.options['changes_timer']

    global prefix
    prefix = "{}://{}:{}".format(
        protocol,
        hostname,
        port
    )

    global webdav
    webdav = easywebdav.connect(
        hostname,
        username=username,
        password=password,
        protocol=protocol,
        port=port
    )

    # Launch the changes detection
    check_changes = CheckChanges(timer, webdav)
    check_changes.daemon = True
    check_changes.start()

    plug.listen()
