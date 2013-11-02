import os

import pyinotify

from onitu.api import Plug

plug = Plug()

@plug.handler()
def read_chunk(filename, offset, size):
    filename = os.path.join(root, filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)

@plug.handler()
def write_chunk(filename, offset, chunk):
    filename = os.path.join(root, filename)
    dirname = os.path.dirname(filename)

    mode = 'r+'

    if not os.path.exists(filename):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        mode = 'w+'

    with open(filename, mode) as f:
        f.seek(offset)
        return f.write(chunk)

class Watcher(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        return self.handle(event)

    def process_IN_CLOSE_WRITE(self, event):
        return self.handle(event)

    def handle(self, event):
        filename = os.path.normpath(os.path.relpath(event.pathname, root))

        if plug.in_transfer(filename):
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
    manager.add_watch(root, mask, rec=True)

    plug.join()
