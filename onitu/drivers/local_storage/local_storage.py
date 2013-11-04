import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from onitu.api import Plug

plug = Plug()

# Ignore the next Watchdog event concerning those files
events_to_ignore = set()

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
        events_to_ignore.add(rel_filename)

class EventHandler(FileSystemEventHandler):

    def on_moved(self, event):
        def handle_move(event):
            if event.is_directory:
                return

            #if event.src_path:
                #self._handle_deletion(event.src_path)
            self._handle_update(event.dest_path)

        handle_move(event)

        if event.is_directory:
            for subevent in event.sub_moved_events():
                handle_move(subevent)

    def on_modified(self, event):
        if event.is_directory:
            return

        self._handle_update(event.src_path)

    def _handle_update(self, abs_filename):
        filename = os.path.normpath(os.path.relpath(abs_filename, root))

        if filename in events_to_ignore:
            events_to_ignore.remove(filename)
            return

        metadata = plug.get_metadata(filename)
        metadata.size = os.path.getsize(abs_filename)
        metadata.last_update = os.path.getmtime(abs_filename)

        plug.update_file(metadata)

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)

    global root
    root = plug.options['root']

    observer = Observer()
    observer.schedule(EventHandler(), path=root, recursive=True)
    observer.start()

    plug.join()