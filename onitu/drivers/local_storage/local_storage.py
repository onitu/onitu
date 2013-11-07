import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from onitu.api import Plug

plug = Plug()

# Ignore the next Watchdog event concerning those files
events_to_ignore = set()
# Store the mtime of the last write of each transfered file
last_mtime = {}

@plug.handler()
def read_chunk(filename, offset, size):
    filename = os.path.join(root, filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)

@plug.handler()
def write_chunk(rel_filename, offset, chunk, total):
    filename = os.path.join(root, rel_filename)

    mode = 'rb+'

    if not os.path.exists(filename):
        dirname = os.path.dirname(filename)

        if not os.path.exists(dirname):
            os.makedirs(dirname)
        mode = 'wb+'

    if offset == 0:
        # If we are rewritting the file from the begining, we truncate it
        mode = 'wb+'
        # and we tell the event listener to skip events about him
        events_to_ignore.add(rel_filename)

    with open(filename, mode) as f:
        f.seek(offset)
        f.write(chunk)

    if offset + len(chunk) >= total:
        # If this is the last chunk we stop ignoring event
        events_to_ignore.remove(rel_filename)
        # this is to make sure that no further event concerning
        # this set of writes will be propagated to the Referee
        last_mtime[rel_filename] = os.path.getmtime(filename)


class EventHandler(FileSystemEventHandler):

    events = 0

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
            return

        mtime = os.path.getmtime(abs_filename)
        if filename in last_mtime:
            if last_mtime[filename] >= mtime:
                # This event concerns a file that hasn't been changed
                # since the last write_chunk, we must ignore the event
                return
            else:
                del last_mtime[filename]

        metadata = plug.get_metadata(filename)
        metadata.size = os.path.getsize(abs_filename)
        metadata.last_update = mtime
        plug.update_file(metadata)

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)

    global root
    root = plug.options['root']

    observer = Observer()
    observer.schedule(EventHandler(), path=root, recursive=True)
    observer.start()

    plug.join()