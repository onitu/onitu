import os
import threading

import easywebdav

from onitu.plug import Plug, ServiceError
from onitu.escalator.client import EscalatorClosed

plug = Plug()
root = None
webdav = None
prefix = None
events_to_ignore = set()


def create_dirs(webdav, path):
    path = '/'.join([root, path])
    webdav.mkdirs(path)


@plug.handler()
def get_file(metadata):
    try:
        path = '/'.join([root, metadata.filename])
        # TODO: we should not have a local file.
        local_file = "/tmp/{}.onitu-tmp".format(
            os.path.basename(metadata.filename)
        )
        webdav.download(path, local_file)
        with open(local_file, 'r') as f:
            data = f.read()
        return data

    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def start_upload(metadata):
    events_to_ignore.add(metadata.filename)
    create_dirs(webdav, os.path.dirname(metadata.filename))


@plug.handler()
def end_upload(metadata):
    try:
        path = '/'.join([root, metadata.filename])
        f = webdav.ls(path)[0]
        metadata.extra['revision'] = f.mtime
        metadata.write()

    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error while updating metadata on file '{}': {}".format(
                metadata.filename, e)
        )
    finally:
        if metadata.filename in events_to_ignore:
            events_to_ignore.remove(metadata.filename)


@plug.handler()
def upload_file(metadata, content):
    try:
        path = '/'.join([root, metadata.filename])
        local_file = "/tmp/{}.onitu-tmp".format(
            os.path.basename(metadata.filename)
        )
        with open(local_file, 'w') as f:
            f.write(content)
        webdav.upload(local_file, path)
    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error writting file '{}': {}".format(metadata.filename, e)
        )


def update_file(metadata, f):
    try:
        metadata.size = f.size
        metadata.extra['revision'] = f.mtime
        metadata.write()
        plug.update_file(metadata)
    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.filename, e)
        )


class CheckChanges(threading.Thread):

    def __init__(self, timer, webdav):
        super(CheckChanges, self).__init__()
        self.stop = threading.Event()
        self.timer = timer
        self.webdav = webdav

    def check_folder(self, path=''):
        path = '/'.join([root, path])
        try:
            filelist = self.webdav.ls(path)
        except easywebdav.client.OperationFailed as e:
            raise ServiceError(
                "Error listing file in '{}': {}".format(path, e)
            )

        for f in filelist[1:]:
            filepath = f.name.replace(prefix, "")

            metadata = plug.get_metadata(filepath)
            onitu_rev = metadata.extra.get('revision', 0.)

            if f.mtime > onitu_rev:
                # TODO: is it the same thing with a webdav server on windows?
                if f.contenttype == "httpd/unix-directory":
                    self.check_folder(filepath)
                else:
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
    root = plug.options['root']
    if root.endswith('/'):
        root = root[:-1]

    protocol = plug.options['protocol']
    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    port = plug.options['port']
    timer = plug.options['changes_timer']

    global prefix
    prefix = "{}://{}:{}{}/".format(
        protocol,
        hostname,
        port,
        root
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
