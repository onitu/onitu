import os

import fsevents
from path import path

from onitu.plug import Plug, DriverError, ServiceError

TMP_EXT = '.onitu-tmp'

plug = Plug()

# Ignore the next fsevents event concerning those files
events_to_ignore = set()
# Store the mtime of the last write of each transfered file
last_mtime = {}
last_creation = set()
last_delete = set()
last_move = set()
move_events = {}

root = None


def to_tmp(path):
    return path.parent.joinpath('.' + path.name + TMP_EXT)


@plug.handler()
def get_chunk(metadata, offset, size):
    filename = root / metadata.filename

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
    filename = root / metadata.filename
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
    tmp_file = to_tmp(root / metadata.filename)

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
    filename = root / metadata.filename
    tmp_file = to_tmp(filename)

    try:
        last_creation.add(metadata.filename)
        tmp_file.move(filename)
        mtime = filename.mtime

    except (IOError, OSError) as e:
        raise ServiceError(
            "Error for file '{}': {}".format(filename, e)
        )

    # this is to make sure that no further event concerning
    # this set of writes will be propagated to the Referee
    last_mtime[metadata.filename] = mtime

    metadata.extra['revision'] = mtime
    metadata.write()


@plug.handler()
def abort_upload(metadata):
    filename = root / metadata.filename
    tmp_file = to_tmp(filename)
    try:
        tmp_file.unlink()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(tmp_file, e)
        )


@plug.handler()
def delete_file(metadata):
    filename = root / metadata.filename

    try:
        last_delete.add(metadata.filename)
        filename.unlink()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(filename, e)
        )

    delete_empty_dirs(filename)


@plug.handler()
def move_file(old_metadata, new_metadata):
    old_filename = root / old_metadata.filename
    new_filename = root / new_metadata.filename

    parent = new_filename.dirname()
    if not parent.exists():
        parent.makedirs_p()

    try:
        old_filename.rename(new_filename)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error moving file '{}': {}".format(old_filename, e)
        )

    delete_empty_dirs(old_filename)


def delete_empty_dirs(filename):
    """Remove all the empty parent directories, stopping at the root
    """

    parent = filename.parent

    while parent != root:
        try:
            parent.rmdir()
        except OSError:
            break

        parent = parent.parent


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
            update_file(metadata, abs_path, mtime)


def delete(metadata, _):
    if metadata.filename in last_delete:
        plug.logger.debug("ignore -> last delete")
        last_delete.remove(metadata.filename)
        return

    if plug.name not in metadata.owners:
        return

    plug.delete_file(metadata)


def move_final(old_metadata, old_path, new_path):
    if plug.name not in old_metadata.owners:
        return

    new_filename = root.relpathto(new_path)
    plug.move_file(old_metadata, new_filename)


def move(metadata, path, cookie, mask):
    if metadata.filename in last_move:
        if mask == fsevents.IN_MOVED_FROM:
            return
        else:
            last_move.remove(metadata.filename)
            return

    if cookie in move_events:
        m = move_events.pop(cookie)
        old_metadata = m[0]
        old_path = m[1]
        move_final(old_metadata, old_path, path)
    else:
        move_events[cookie] = (metadata, path)


def update_file(metadata, path, mtime=None):
    if metadata.filename in last_creation:
        plug.logger.debug("ignore -> last creation")
        last_creation.remove(metadata.filename)
        return

    try:
        metadata.size = path.size
        metadata.extra['revision'] = mtime if mtime else path.mtime
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.filename, e)
        )
    plug.update_file(metadata)


def handle_event(name, mask, cookie):
    plug.logger.debug("handle_event")
    abs_path = path(name)

    if abs_path.ext == TMP_EXT:
        plug.logger.debug("TMP_EXT")
        return

    if abs_path.isdir():
        plug.logger.debug("dir")
        return

    filename = root.relpathto(abs_path)
    metadata = plug.get_metadata(filename)

    plug.logger.debug("root    : {}".format(root))
    plug.logger.debug("name    : {}".format(name))
    plug.logger.debug("abs_path: {}".format(abs_path))
    plug.logger.debug("filename: {}".format(filename))

    update_events = (fsevents.IN_MODIFY, fsevents.IN_CREATE)
    delete_events = (fsevents.IN_DELETE)
    move_events = (fsevents.IN_MOVED_FROM, fsevents.IN_MOVED_TO)

    if mask in update_events:
        plug.logger.debug("update file")
        update_file(metadata, abs_path)
    elif mask == delete_events:
        plug.logger.debug("delete file")
        delete(metadata, abs_path)
    elif mask in move_events:
        plug.logger.debug("move event")
        move(metadata, abs_path, cookie, mask)


def file_event_callback(event):
    plug.logger.debug(
        "Mask: {}, Cookie: {}, Name: {}",
        event.mask, event.cookie, event.name
    )

    if event.mask == fsevents.IN_ATTRIB:
        plug.logger.debug("ignore -> bad event")
        return

    handle_event(event.name, event.mask, event.cookie)


def start(*args, **kwargs):
    # plug.initialize(*args, **kwargs)

    global root
    root = path(plug.options['root'])

    if not root.access(os.W_OK | os.R_OK):
        raise DriverError("The root '{}' is not accessible".format(root))

    observer = fsevents.Observer()
    observer.start()
    stream = fsevents.Stream(
        file_event_callback, str(root), file_events=True
    )
    observer.schedule(stream)

    check_changes()
    plug.listen()
    observer.unschedule(stream)
    observer.stop()
    observer.join()
