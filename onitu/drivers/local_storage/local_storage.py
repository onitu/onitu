from path import path
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
    filename = root.joinpath(filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)


@plug.handler()
def start_upload(metadata):
    filename = root.joinpath(metadata.filename)

    # We ignore the next Watchdog events concerning this file
    events_to_ignore.add(metadata.filename)

    if not filename.exists():
        filename.dirname().makedirs_p()

    filename.open('w+b').close()


@plug.handler()
def end_upload(metadata):
    filename = root.joinpath(metadata.filename)

    # If this is the last chunk we stop ignoring event
    events_to_ignore.remove(metadata.filename)
    # this is to make sure that no further event concerning
    # this set of writes will be propagated to the Referee
    last_mtime[metadata.filename] = filename.mtime

    metadata.revision = filename.mtime
    metadata.write_revision()


@plug.handler()
def upload_chunk(filename, offset, chunk):
    abs_path = root.joinpath(filename)

    # We make sure events are ignored for this file
    events_to_ignore.add(filename)

    with open(abs_path, 'r+b') as f:
        f.seek(offset)
        f.write(chunk)


def check_changes():
    for abs_path in root.walkfiles():
        filename = abs_path.relpath(root).normpath()

        metadata = plug.get_metadata(filename)
        revision = metadata.revision
        revision = float(revision) if revision else .0

        if abs_path.mtime > revision:
            update_file(metadata, abs_path)


def update_file(metadata, path):
    metadata.size = path.size
    metadata.revision = path.mtime
    plug.update_file(metadata)


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

    def _handle_update(self, abs_path):
        abs_path = path(abs_path)
        filename = root.relpathto(abs_path)

        if filename in events_to_ignore:
            return

        if filename in last_mtime:
            if last_mtime[filename] >= abs_path.mtime:
                # This event concerns a file that hasn't been changed
                # since the last write_chunk, we must ignore the event
                return
            else:
                del last_mtime[filename]

        metadata = plug.get_metadata(filename)
        update_file(metadata, abs_path)


def start(*args, **kwargs):
    plug.start(*args, **kwargs)

    global root
    root = path(plug.options['root'])

    check_changes()

    observer = Observer()
    observer.schedule(EventHandler(), path=root, recursive=True)
    observer.start()

    plug.wait()
