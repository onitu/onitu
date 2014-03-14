import os

import pyinotify
from path import path

from onitu.api import Plug

TMP_EXT = '.onitu-tmp'

plug = Plug()
root = None


def to_tmp(path):
    return path.parent.joinpath('.' + path.name + TMP_EXT)


def update_file(metadata, path):
    metadata.size = path.size
    metadata.revision = path.mtime
    plug.update_file(metadata)


def check_changes():
    for abs_path in root.walkfiles():
        if abs_path.ext == TMP_EXT:
            continue

        filename = abs_path.relpath(root).normpath()

        metadata = plug.get_metadata(filename)
        revision = metadata.revision
        revision = float(revision) if revision else .0

        if abs_path.mtime > revision:
            update_file(metadata, abs_path)


@plug.handler()
def get_chunk(filename, offset, size):
    filename = root.joinpath(filename)

    try:
        with open(filename, 'rb') as f:
            f.seek(offset)
            return f.read(size)
    except IOError as e:
        plug.logger.warn("Error getting file `{}`: {}", filename, e)


@plug.handler()
def start_upload(metadata):
    filename = root.joinpath(metadata.filename)
    tmp_file = to_tmp(filename)

    try:
        if not tmp_file.exists():
            tmp_file.dirname().makedirs_p()

        tmp_file.open('wb').close()
    except IOError as e:
        plug.logger.warn("Error creating file `{}`: {}", tmp_file, e)


@plug.handler()
def upload_chunk(filename, offset, chunk):
    tmp_file = to_tmp(root.joinpath(filename))

    try:
        # We should not append the file but seek to the right
        # position.
        # However, the behavior of `offset` isn't well defined
        with open(tmp_file, 'ab') as f:
            f.write(chunk)
    except IOError as e:
        plug.logger.warn("Error writting file `{}`: {}", tmp_file, e)


@plug.handler()
def end_upload(metadata):
    filename = root.joinpath(metadata.filename)
    tmp_file = to_tmp(filename)

    try:
        tmp_file.move(filename)
        mtime = filename.mtime
    except OSError as e:
        plug.logger.warn("Error for file `{}`: {}", filename, e)
        return

    metadata.revision = mtime
    metadata.write_revision()


@plug.handler()
def abort_upload(metadata):
    filename = root.joinpath(metadata.filename)
    tmp_file = to_tmp(filename)
    try:
        tmp_file.unlink()
    except OSError as e:
        plug.logger.warn("Error deleting file `{}`: {}", tmp_file, e)
        return


class Watcher(pyinotify.ProcessEvent):
    def process_IN_CLOSE_WRITE(self, event):
        abs_path = path(event.pathname)

        if abs_path.ext == TMP_EXT:
            return

        filename = root.relpathto(abs_path)
        metadata = plug.get_metadata(filename)
        update_file(metadata, abs_path)


def start(*args, **kwargs):
    plug.initialize(*args, **kwargs)

    global root
    root = path(plug.options['root'])

    if not root.access(os.W_OK | os.R_OK):
        plug.logger.error("Can't access directory `{}`.", root)
        return

    manager = pyinotify.WatchManager()
    notifier = pyinotify.ThreadedNotifier(manager, Watcher())
    notifier.start()

    mask = pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE
    manager.add_watch(root, mask, rec=True, auto_add=True)

    check_changes()
    plug.listen()
    notifier.stop()
