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
    from pywintypes import OVERLAPPED
    from time import time, sleep
    from win32event import (
        CreateEvent,
        WaitForMultipleObjects,
        INFINITE,
        WAIT_TIMEOUT,
        WAIT_OBJECT_0)
else:
    import pyinotify

TMP_EXT = '.onitu-tmp'

plug = Plug()
root = None

if IS_WINDOWS:
    ignoreNotif = dict()
    FILE_LIST_DIRECTORY = 0x0001


def to_tmp(filename):
    filename = path(filename)
    return filename.parent / ('.' + filename.name + TMP_EXT)


def update(metadata, abs_path, mtime=None):

    try:
        if metadata is None:
            return
        metadata.size = abs_path.getsize()
        metadata.extra['revision'] = mtime if mtime else abs_path.mtime
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error updating file '{}': {}".format(metadata.path, e)
        )
    else:
        plug.update_file(metadata)


def delete(metadata, _):
    if metadata is not None:
        plug.delete_file(metadata)


def move(old_metadata, new_path):
    if IS_WINDOWS and old_metadata is None:
        writingDict[abs_path] = Rtime
        return
    new_filename = root.relpathto(new_path)
    new_filename = root.relpathto(new_path)
    if IS_WINDOWS:
        new_metadata = plug.move_file(old_metadata, new_path)
    else:
        new_metadata = plug.move_file(old_metadata, new_filename)
    new_metadata.extra['revision'] = path(root / new_path).mtime
    new_metadata.write()

def delete_empty_dirs(filename):
    """
    Remove all the empty parent directories, stopping at the root
    """
    filename = path(filename)
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
                u"Error updating file '{}': {}".format(filename, e)
            )
            mtime = 0.

        if mtime > revision:
            update(metadata, abs_path, mtime)


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
    plug.logger.info("start_upload {} {}".format(tmp_file, metadata.path))
    if IS_WINDOWS:
        ignoreNotif[metadata.path] = False
        sleep(1)
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
            path(metadata.path).unlink_p()
        tmp_file.move(metadata.path)
        mtime = os.path.getmtime(metadata.path)

        if IS_WINDOWS:
            win32api.SetFileAttributes(
                metadata.path, win32con.FILE_ATTRIBUTE_NORMAL)
    except (IOError, OSError) as e:
        raise ServiceError(
            u"Error for file '{}': {}".format(metadata.path, e)
        )

    metadata.extra['revision'] = mtime
    metadata.write()
    if IS_WINDOWS:
        if metadata.path in ignoreNotif and \
           not ignoreNotif[metadata.path]:
            ignoreNotif[metadata.path] = time() + 1


@plug.handler()
def abort_upload(metadata):
    tmp_file = to_tmp(metadata.path)

    if IS_WINDOWS:
        if metadata.filename in ignoreNotif:
            del ignoreNotif[metadata.path]
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

    delete_empty_dirs(metadata.path)


@plug.handler()
def move_file(old_metadata, new_metadata):
    old_path = path(old_metadata.path)
    new_path = path(new_metadata.path)

    parent = new_path.dirname()
    if not parent.exists():
        parent.makedirs_p()
    if IS_WINDOWS:
        ignoreNotif[new_metadata.path] = False
        ignoreNotif[old_metadata.path] = False
    try:
        old_path.rename(new_path)
    except (IOError, OSError) as e:
        if IS_WINDOWS:
            del ignoreNotif[new_metadata.path]
            del ignoreNotif[old_metadata.path]
        raise ServiceError(
            u"Error moving file '{}': {}".format(old_path, e)
        )
    delete_empty_dirs(old_path)
    if IS_WINDOWS:
        del ignoreNotif[new_metadata.path]
        del ignoreNotif[old_metadata.path]

if IS_WINDOWS:
    def verifDictModifFile(writingDict, Rtime, cleanOld=False):
        for i, j in list(writingDict.items()):
            if cleanOld is False:
                if Rtime - j >= 1.0:
                        try:
                            fd = os.open(i, os.O_RDONLY)
                        except(IOError, OSError) as e:
                            continue
                        else:
                            os.close(fd)
                            filename = root.relpathto(i)
                            metadata = plug.get_metadata(filename)
                            update(metadata, i)
                            del writingDict[i]
            else:
                if j > 1 and Rtime - j >= 2:
                        del writingDict[i]
        return writingDict

    def fileAction(filename, abs_path, action, ignoreNotif, writingDict,
                   transferSet, actions_names, Rtime):
        metadata = plug.get_metadata(filename)
        if metadata == None:
            return
        if (actions_names.get(action) == 'write' or
            actions_names.get(action) == 'create') and \
           metadata.path not in ignoreNotif:
            if os.access(abs_path, os.R_OK):
                writingDict[abs_path] = Rtime
        elif actions_names.get(action) == 'delete' and \
                metadata.path not in ignoreNotif:
            delete(metadata, abs_path)
        elif actions_names.get(action) == 'moveFrom' and \
                filename not in ignoreNotif:
            old_path = filename
            fileAction.oldMetadata = metadata
            if old_path.endswith(TMP_EXT):
                ignoreNotif[root + old_path[1:len(TMP_EXT)]] = \
                    False
            elif fileAction.oldMetadata is not None:
                ignoreNotif[fileAction.oldMetadata.path] = False
                fileAction.moving = True
#            if fileAction.oldMetadata is None:
                # may need to verify this in moveTo and do an update instead
#                return
        elif actions_names.get(action) == 'moveTo' and fileAction.moving:
            ignoreNotif[metadata.path] = False
            move(fileAction.oldMetadata, filename)
            fileAction.moving = False
            if fileAction.oldMetadata.filename.endswith(TMP_EXT):
                del ignoreNotif[fileAction.oldMetadata.filename[:len(TMP_EXT)]]
            else:
                del ignoreNotif[fileAction.oldMetadata.path]
                ignoreNotif[metadata.path] = Rtime
        if (actions_names.get(action) == 'create' or
            actions_names.get(action) == 'write') and \
                filename not in transferSet and filename in ignoreNotif:
            if ignoreNotif[metadata.path] is not False:
                transferSet.add(metadata.path)

    def win32watcherThread(root, file_lock):
        dirHandle = win32file.CreateFile(
            root,
            FILE_LIST_DIRECTORY,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS |
            win32con.FILE_FLAG_OVERLAPPED,
            None
        )
        actions_names = {
            1: 'create',
            2: 'delete',
            3: 'write',
            4: 'moveFrom',
            5: 'moveTo'
        }
        global ignoreNotif
        fileAction.moving = False
        old_path = None
        old_metadata = None
        writingDict = dict()
        overlapped = OVERLAPPED()
        overlapped.hEvent = CreateEvent(None, 0, 0, None)
        stop = CreateEvent(None, 0, 0, None)
        while True:
            buf = win32file.AllocateReadBuffer(10000)
            results = win32file.ReadDirectoryChangesW(
                dirHandle,
                buf,
                True,
                win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                win32con.FILE_NOTIFY_CHANGE_SIZE |
                win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                win32con.FILE_NOTIFY_CHANGE_SECURITY,
                overlapped
            )
            rc = WAIT_TIMEOUT
            while rc == WAIT_TIMEOUT:
                rc = WaitForMultipleObjects((stop, overlapped.hEvent), 0, 200)
                if rc == WAIT_TIMEOUT:
                    writingDict = verifDictModifFile(writingDict, time())
                    ignoreNotif = verifDictModifFile(ignoreNotif, time(), True)
                if rc == WAIT_OBJECT_0:
                    break

            data = win32file.GetOverlappedResult(dirHandle, overlapped, True)
            events = win32file.FILE_NOTIFY_INFORMATION(buf, data)
            Rtime = time()
            transferSet = set()
            for action, file_ in events:
                abs_path = root / file_
                if actions_names[action] != 'write' and abs_path.isdir() and \
                   os.access(abs_path, os.R_OK) and \
                   len(os.listdir(abs_path)) != 0:
                    for file in abs_path.walkfiles():
                        filename = root.relpathto(file)
                    try:
                        with file_lock:
                            fileAction(filename, file, action, ignoreNotif,
                                       writingDict, transferSet, actions_names,
                                       Rtime)
                    except EscalatorClosed:
                        return
                if (abs_path.isdir() or abs_path.ext == TMP_EXT or
                    os.path.exists(abs_path) and
                    (not (win32api.GetFileAttributes(abs_path)
                          & win32con.FILE_ATTRIBUTE_NORMAL) and
                    not (win32api.GetFileAttributes(abs_path)
                         & win32con.FILE_ATTRIBUTE_ARCHIVE))):
                    continue
                filename = root.relpathto(abs_path)
                try:
                    with file_lock:
                        fileAction(filename, abs_path, action, ignoreNotif,
                                   writingDict, transferSet, actions_names,
                                   Rtime)
                except EscalatorClosed:
                    return
            for file in transferSet:
                if file in ignoreNotif:
                    del ignoreNotif[file]
            transferSet.clear()
            try:
                writingDict = verifDictModifFile(writingDict, Rtime)
                ignoreNotif = verifDictModifFile(ignoreNotif, Rtime, True)
            except EscalatorClosed:
                return

    def watch_changes():
        file_lock = threading.Lock()
        notifier = threading.Thread(target=win32watcherThread,
                                    args=(root.abspath(), file_lock))
        notifier.setDaemon(True)
        notifier.start()
else:
    class Watcher(pyinotify.ProcessEvent):
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

        def process_event(self, abs_path, callback, *args):
            abs_path = path(u(abs_path))

            if abs_path.ext == TMP_EXT:
                return

            filename = root.relpathto(abs_path)

            try:
                metadata = plug.get_metadata(filename)
                callback(metadata, abs_path, *args)
            except EscalatorClosed:
                return

    def watch_changes():
        manager = pyinotify.WatchManager()
        notifier = pyinotify.ThreadedNotifier(manager, Watcher())
        notifier.daemon = True
        notifier.start()

        mask = (pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE |
                pyinotify.IN_DELETE | pyinotify.IN_MOVED_TO |
                pyinotify.IN_MOVED_FROM)
        manager.add_watch(root, mask, rec=True, auto_add=True)


def start():
    global root
    root = path(plug.root)

    if not root.access(os.W_OK | os.R_OK):
        raise DriverError(u"The root '{}' is not accessible".format(root))

    watch_changes()
    check_changes()
    plug.listen()
