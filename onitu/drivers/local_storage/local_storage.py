import os

import pyinotify

from onitu.api import Plug

plug = Plug()

# Ignore the next Inotify event concerning those files
events_to_ignore = list()

@plug.handler()
def read_chunk(filename, offset, size):
    filename = os.path.join(root, filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)

@plug.handler()
def write_chunk(rel_filename, offset, chunk):
    filename = os.path.join(root, rel_filename)
    dirname = os.path.dirname(filename)

    mode = 'rb+'

    if not os.path.exists(filename):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        mode = 'wb+'

    # If we are rewritting the file from the begining, we truncate it
    if offset == 0:
        mode = 'wb+'

    events_to_ignore.append(rel_filename)

    with open(filename, mode) as f:
        f.seek(offset)
        f.write(chunk)

class Watcher(pyinotify.ProcessEvent):
    def process_default(self, event):
        filename = os.path.normpath(os.path.relpath(event.pathname, root))

        if filename in events_to_ignore:
            events_to_ignore.remove(filename)
            return

        metadata = plug.get_metadata(filename)
        metadata.size = os.path.getsize(event.pathname)
        metadata.last_update = os.path.getmtime(event.pathname)

        plug.update_file(metadata)

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)

    global root
    root = plug.options['root']

    manager = pyinotify.WatchManager()
    notifier = pyinotify.ThreadedNotifier(manager, Watcher())
    notifier.start()

    mask = pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE
    manager.add_watch(root, mask, rec=True, auto_add=True)

    plug.join()