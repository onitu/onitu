import os

import pyinotify
from path import path

from onitu.api import Plug, DriverError, ServiceError

TMP_EXT = '.onitu-tmp'

plug = Plug()
root = None


def to_tmp(path):
    return path.parent.joinpath('.' + path.name + TMP_EXT)


def update(metadata, path, mtime=None):
    try:
        metadata.size = path.size
        metadata.extra['revision'] = mtime if mtime else path.mtime
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.filename, e)
        )
    else:
        plug.update_file(metadata)


def delete(metadata, _):
    if plug.name not in metadata.owners:
        return

    plug.delete_file(metadata)


def check_changes():
    for abs_path in root.walkfiles():
        if abs_path.ext == TMP_EXT:
            continue

        filename = abs_path.relpath(root).normpath()

        metadata = plug.get_metadata(filename)
        revision = metadata.extra.get('revision', 0.)

        try:
            mtime = abs_path.mtime
        except (IOError, OSError) as e:
            raise ServiceError(
                "Error updating file '{}': {}".format(filename, e)
            )
            mtime = 0.

        if mtime > revision:
            update(metadata, abs_path, mtime)


@plug.handler()
def get_chunk(metadata, offset, size):
    filename = root.joinpath(metadata.filename)

    try:
        with open(filename, 'rb') as f:
            f.seek(offset)
            return f.read(size)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(filename, e)
        )


@plug.handler()
def start_upload(metadata):
    filename = root.joinpath(metadata.filename)
    tmp_file = to_tmp(filename)

    try:
        if not tmp_file.exists():
            tmp_file.dirname().makedirs_p()

        tmp_file.open('wb').close()
    except IOError as e:
        raise ServiceError(
            "Error creating file '{}': {}".format(tmp_file, e)
        )


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    tmp_file = to_tmp(root.joinpath(metadata.filename))

    try:
        with open(tmp_file, 'r+b') as f:
            f.seek(offset)
            f.write(chunk)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error writting file '{}': {}".format(tmp_file, e)
        )


@plug.handler()
def end_upload(metadata):
    filename = root.joinpath(metadata.filename)
    tmp_file = to_tmp(filename)

    try:
        tmp_file.move(filename)
        mtime = filename.mtime
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error for file '{}': {}".format(filename, e)
        )

    metadata.extra['revision'] = mtime
    metadata.write()


@plug.handler()
def abort_upload(metadata):
    filename = root.joinpath(metadata.filename)
    tmp_file = to_tmp(filename)
    try:
        tmp_file.unlink()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(tmp_file, e)
        )


@plug.handler()
def delete_file(metadata):
    filename = root.joinpath(metadata.filename)

    try:
        filename.unlink()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(filename, e)
        )


class Watcher(pyinotify.ProcessEvent):
    def process_IN_CLOSE_WRITE(self, event):
        self.process_event(event, update)

    def process_IN_DELETE(self, event):
        self.process_event(event, delete)

    def process_event(self, event, callback):
        abs_path = path(event.pathname)

        if abs_path.ext == TMP_EXT:
            return

        filename = root.relpathto(abs_path)
        metadata = plug.get_metadata(filename)
        callback(metadata, abs_path)


def start():
    global root
    root = path(plug.options['root'])

    if not root.access(os.W_OK | os.R_OK):
        raise DriverError("The root '{}' is not accessible".format(root))

    manager = pyinotify.WatchManager()
    notifier = pyinotify.ThreadedNotifier(manager, Watcher())
    notifier.daemon = True
    notifier.start()

    mask = pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE | pyinotify.IN_DELETE
    manager.add_watch(root, mask, rec=True, auto_add=True)

    check_changes()
    plug.listen()
    notifier.stop()
