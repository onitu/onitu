import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from onitu.api import Plug

plug = Plug()

# Ignore the next Watchdog event concerning those files
events_to_ignore = set()
# Store the mtime of the last write of each transfered file
last_mtime = {}

root = None


@plug.handler()
def get_chunk(filename, offset, size):
    filename = os.path.join(root, filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)


@plug.handler()
def start_upload(metadata):
    filename = os.path.join(root, metadata.filename)

    if not os.path.exists(filename):
        dirname = os.path.dirname(filename)

        if not os.path.exists(dirname):
            os.makedirs(dirname)

    # We ignore the next Watchdog events concerning this file
    events_to_ignore.add(metadata.filename)

    open(filename, 'w+').close()


@plug.handler()
def end_upload(metadata):
    filename = os.path.join(root, metadata.filename)

    # If this is the last chunk we stop ignoring event
    events_to_ignore.remove(metadata.filename)
    # this is to make sure that no further event concerning
    # this set of writes will be propagated to the Referee
    last_mtime[metadata.filename] = os.path.getmtime(filename)


@plug.handler()
def upload_chunk(rel_filename, offset, chunk):
    filename = os.path.join(root, rel_filename)

    with open(filename, 'wb+') as f:
        f.seek(offset)
        f.write(chunk)


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
    plug.start(*args, **kwargs)

    global root
    root = plug.options['root']

    observer = Observer()
    observer.schedule(EventHandler(), path=root, recursive=True)
    observer.start()

    plug.wait()
