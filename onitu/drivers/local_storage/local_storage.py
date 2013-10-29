import os

import pyinotify

from onitu.api import Plug

plug = Plug()

# List of events to ignore next time they occur
inotify_ignore_list = []

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

    mode = 'r+'

    if not os.path.exists(filename):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        mode = 'w+'

    # If we are rewritting the file from the begining, we truncate it
    if offset == 0:
        mode = 'w+'

    with open(filename, mode) as f:
        f.seek(offset)
        f.write(chunk)
        inotify_ignore_list.append(rel_filename)

class Watcher(pyinotify.ProcessEvent):

    def process_default(self, event):
        filename = os.path.normpath(os.path.relpath(event.pathname, root))

        if filename in inotify_ignore_list:
            inotify_ignore_list.remove(filename)
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

    # We could use notifier.coalesce_events() to buffer the changes
    # made in a certain period, but it would slow the
    # change detection. We should find a compromise.
    # http://github.com/seb-m/pyinotify/blob/master/python2/examples/coalesce.py

    mask = pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE
    manager.add_watch(root, mask, rec=True, auto_add=True)

    plug.join()
