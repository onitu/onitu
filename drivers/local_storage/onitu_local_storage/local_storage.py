import os

from path import path

from onitu.plug import Plug, DriverError, ServiceError
from onitu.escalator.client import EscalatorClosed
from onitu.utils import IS_WINDOWS, u

if IS_WINDOWS:
    import threading

    import win32api
    import win32file
    import win32con
else:
    import pyinotify

TMP_EXT = '.onitu-tmp'

plug = Plug()


def to_tmp(filename):
    return filename.parent / ('.' + filename.name + TMP_EXT)


def update(metadata, mtime=None):
    try:
        metadata.size = metadata.path.size
        metadata.extra['revision'] = mtime if mtime else metadata.path.mtime
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error updating file '{}': {}".format(metadata.path, e)
        )
    else:
        plug.update_file(metadata)


def delete(metadata):
    plug.delete_file(metadata)


def move(old_metadata, new_filename):
    new_metadata = plug.move_file(old_metadata, new_filename)
    new_metadata.extra['revision'] = path(new_filename).mtime
    new_metadata.write()


def check_changes(folder):
    expected_files = set()

    expected_files.update(plug.list(folder).keys())

    for filename in folder.path.walkfiles():
        if filename.ext == TMP_EXT:
            continue

        expected_files.discard(filename)

        metadata = plug.get_metadata(filename, folder)
        revision = metadata.extra.get('revision', 0.)

        try:
            mtime = filename.mtime
        except (IOError, OSError) as e:
            raise ServiceError(
                u"Error updating file '{}': {}".format(metadata.path, e)
            )
            mtime = 0.

        if mtime > revision:
            update(metadata, mtime)

    for filename in expected_files:
        metadata = plug.get_metadata(filename, folder)
        plug.delete_file(metadata)


@plug.handler()
def normalize_path(p):
    normalized = path(p).expanduser().normpath()
    if not normalized.isabs():
        raise DriverError(u"The folder path '{}' is not absolute.".format(p))

    return normalized


@plug.handler()
def get_chunk(metadata, offset, size):
    try:
        with open(metadata.path, 'rb') as f:
            f.seek(offset)
            return f.read(size)
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error getting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def start_upload(metadata):
    tmp_file = to_tmp(metadata.path)

    try:
        if not tmp_file.exists():
            tmp_file.dirname().makedirs_p()

        tmp_file.open('wb').close()

        if IS_WINDOWS:
            win32api.SetFileAttributes(
                tmp_file, win32con.FILE_ATTRIBUTE_HIDDEN)
    except IOError as e:
        raise ServiceError(
            u"Error creating file '{}': {}".format(tmp_file, e)
        )


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    tmp_file = to_tmp(metadata.path)

    try:
        with open(tmp_file, 'r+b') as f:
            f.seek(offset)
            f.write(chunk)
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error writting file '{}': {}".format(tmp_file, e)
        )


@plug.handler()
def end_upload(metadata):
    tmp_file = to_tmp(metadata.path)

    try:
        if IS_WINDOWS:
            # On Windows we can't move a file
            # if dst exists
            metadata.path.unlink_p()
        tmp_file.move(metadata.path)
        mtime = metadata.path.mtime

        if IS_WINDOWS:
            win32api.SetFileAttributes(
                metadata.path, win32con.FILE_ATTRIBUTE_NORMAL)
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error for file '{}': {}".format(metadata.path, e)
        )

    metadata.extra['revision'] = mtime
    metadata.write()


@plug.handler()
def abort_upload(metadata):
    tmp_file = to_tmp(metadata.path)
    try:
        tmp_file.unlink()
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error deleting file '{}': {}".format(tmp_file, e)
        )


@plug.handler()
def delete_file(metadata):
    try:
        os.unlink(metadata.path)
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error deleting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def move_file(old_metadata, new_metadata):
    parent = new_metadata.path.dirname()
    if not parent.exists():
        parent.makedirs_p()

    try:
        old_metadata.path.rename(new_metadata.path)
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error moving file '{}': {}".format(old_metadata.path, e)
        )


if IS_WINDOWS:
    FILE_LIST_DIRECTORY = 0x0001

    def win32watcherThread(root, file_lock):
        dirHandle = win32file.CreateFile(
            root,
            FILE_LIST_DIRECTORY,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None
        )

        actions_names = {
            1: 'create',
            2: 'delete',
            3: 'write',
            4: 'delete',
            5: 'write'
        }

        while True:
            results = win32file.ReadDirectoryChangesW(
                dirHandle,
                1024,
                True,
                win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                win32con.FILE_NOTIFY_CHANGE_SIZE |
                win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                win32con.FILE_NOTIFY_CHANGE_SECURITY,
                None
            )

            for action, file_ in results:
                abs_path = root / file_

                if (abs_path.isdir() or abs_path.ext == TMP_EXT or
                    not (win32api.GetFileAttributes(abs_path)
                         & win32con.FILE_ATTRIBUTE_NORMAL)):
                    continue

                with file_lock:
                    if actions_names.get(action) == 'write':
                        filename = root.relpathto(abs_path)

                        try:
                            metadata = plug.get_metadata(filename)
                            update(metadata, abs_path)
                        except EscalatorClosed:
                            return

    def watch_changes(folder):
        file_lock = threading.Lock()
        notifier = threading.Thread(target=win32watcherThread,
                                    args=(folder.path, file_lock))
        notifier.setDaemon(True)
        notifier.start()
else:
    class Watcher(pyinotify.ProcessEvent):
        def __init__(self, folder, *args, **kwargs):
            super(Watcher, self).__init__(*args, **kwargs)

            self.folder = folder

        def process_IN_CLOSE_WRITE(self, event):
            self.process_event(event.pathname, update)

        def process_IN_DELETE(self, event):
            self.process_event(event.pathname, delete)

        def process_IN_MOVED_TO(self, event):
            if event.dir:
                for new in path(event.pathname).walkfiles():
                    old = new.replace(event.pathname, event.src_pathname)
                    self.process_event(old, move, u(new))
            else:
                self.process_event(event.src_pathname, move, u(event.pathname))

        def process_event(self, filename, callback, *args):
            filename = path(self.folder.relpath(u(filename)))

            if filename.ext == TMP_EXT:
                return

            try:
                metadata = plug.get_metadata(filename, self.folder)
                callback(metadata, *args)
            except EscalatorClosed:
                return

    def watch_changes(folder):
        manager = pyinotify.WatchManager()
        notifier = pyinotify.ThreadedNotifier(manager, Watcher(folder))
        notifier.daemon = True
        notifier.start()

        mask = (pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE |
                pyinotify.IN_DELETE | pyinotify.IN_MOVED_TO |
                pyinotify.IN_MOVED_FROM)
        manager.add_watch(folder.path, mask, rec=True, auto_add=True)


def start():
    for folder in plug.folders_to_watch:
        try:
            folder.path.makedirs_p()
        except OSError as e:
            raise DriverError(
                u"Cannot create the folder '{}': {}".format(folder.path, e)
            )

        watch_changes(folder)
        check_changes(folder)

    plug.listen()
