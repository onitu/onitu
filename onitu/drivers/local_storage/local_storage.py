from onitu.api.plug import Plug
from os import path, makedirs
from pyinotify import WatchManager, ThreadedNotifier, EventsCodes, ProcessEvent

root = './'
plug = Plug()

@plug.handler
def send_chunk(chunk):
    # send ...
    return True

@plug.handler
def read_chunk(filename, offset, size):
    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)

@plug.handler
def write_chunk(filename, offset, chunk):
    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.write(chunk)

@plug.handler
def new_file(metadatas):
    filepath = root + metadatas['path']
    if not path.exists(filepath):
        makedirs(filepath)
    open(path.join(filepath, metadatas['filename']), 'w+').close()

def watch_new_file(event):
    print 'Created %s' % path.join(event.path, event.name)

class Watcher(ProcessEvent):
    def process_IN_CREATE(self, event):
        return watch_new_file(event)

def start(*args, **kwargs):
    wm = WatchManager()
    notifier = ThreadedNotifier(wm, Watcher())
    notifier.start()
    wm.add_watch(root, EventsCodes.ALL_FLAGS['IN_CREATE'], rec=True)
    plug.start()
    plug.join()
