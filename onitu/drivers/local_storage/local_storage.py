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

    try:
        with open(filename, 'rb') as f:
            f.seek(offset)
            return f.read(size)
    except IOError as e:
        plug.logger.warn("Error getting file `{}`: {}", filename, e)


@plug.handler()
def start_upload(metadata):
    filename = root.joinpath(metadata.filename)

    # We ignore the next Watchdog events concerning this file
    events_to_ignore.add(metadata.filename)

    try:
        if not filename.exists():
            filename.dirname().makedirs_p()

        filename.open('wb').close()
    except IOError as e:
        plug.logger.warn("Error creating file `{}`: {}", filename, e)


@plug.handler()
def end_upload(metadata):
    filename = root.joinpath(metadata.filename)

    # this is to make sure that no further event concerning
    # this set of writes will be propagated to the Referee
    last_mtime[metadata.filename] = filename.mtime

    metadata.revision = filename.mtime
    metadata.write_revision()

    if metadata.filename in events_to_ignore:
        events_to_ignore.remove(metadata.filename)


@plug.handler()
def upload_chunk(filename, offset, chunk):
    abs_path = root.joinpath(filename)

    # We make sure events are ignored for this file
    events_to_ignore.add(filename)

    try:
        # We should not append the file but seek to the right
        # position.
        # However, the behavior of `offset` isn't well defined
        with open(abs_path, 'ab') as f:
            f.write(chunk)
    except IOError as e:
        plug.logger.warn("Error writting file `{}`: {}", filename, e)


def check_changes():
    for abs_path in root.walkfiles():
        filename = abs_path.relpath(root).normpath()

        metadata = plug.get_metadata(filename)
        revision = metadata.revision
        revision = float(revision) if revision else .0

        if abs_path.mtime > revision:
            update_file(metadata, abs_path)


def update_file(metadata, path):
    if metadata.filename in events_to_ignore:
        return

    if metadata.filename in last_mtime:
        if last_mtime[metadata.filename] >= path.mtime:
            # We're about to send an event for a file that hasn't changed
            # since the last upload, we stop here
            return
        else:
            del last_mtime[metadata.filename]

    metadata.size = path.size
    metadata.revision = path.mtime
    plug.update_file(metadata)


class EventHandler(FileSystemEventHandler):
    def on_moved(self, event):
        def handle_move(event):
            if event.is_directory:
                return

            #if event.src_path:
                #self._handle_deletion(event.src_path.decode())
            self._handle_update(event.dest_path.decode())

        handle_move(event)
        if event.is_directory:
            for subevent in event.sub_moved_events():
                handle_move(subevent)

    def on_modified(self, event):
        if event.is_directory:
            return

        self._handle_update(event.src_path.decode())

    def _handle_update(self, abs_path):
        abs_path = path(abs_path)
        filename = root.relpathto(abs_path)
        metadata = plug.get_metadata(filename)
        update_file(metadata, abs_path)


def start(*args, **kwargs):
    plug.start(*args, **kwargs)

    global root
    root = path(plug.options['root'])

    observer = Observer()
    observer.schedule(EventHandler(), path=root, recursive=True)
    observer.start()

    check_changes()
    plug.wait()
