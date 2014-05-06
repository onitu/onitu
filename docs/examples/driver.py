import os

from onitu.api import Plug

# A dummy library supposed to watch the file system
from fsmonitor import FSWatcher

plug = Plug()


@plug.handler()
def get_chunk(metadata, offset, size):
    with open(metadata.filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    with open(metadata.filename, 'r+b') as f:
        f.seek(offset)
        f.write(chunk)


@plug.handler()
def end_upload(metadata):
    metadata.revision = os.path.getmtime(metadata.filename)
    metadata.write_revision()


class Watcher(FSWatcher):
    def on_update(self, filename):
        """Called each time an update of a file is detected
        """
        metadata = plug.get_metadata(filename)
        metadata.revision = os.path.getmtime(metadata.filename)
        metadata.size = os.path.getsize(metadata.filename)
        plug.update_file(metadata)

    def check_changes(self):
        """Check the changes on the file system since the last launch
        """
        for filename in self.files:
            revision = os.path.getmtime(filename)
            metadata = plug.get_metadata(filename)

            # If the file is more recent
            if revision > metadata.revision:
                metadata.revision = os.path.getmtime(metadata.filename)
                metadata.size = os.path.getsize(metadata.filename)
                plug.update_file(metadata)


def start(*args, **kwargs):
    plug.initialize(*args, **kwargs)

    root = plug.options['root']
    os.chdir(root)

    watcher = Watcher(root)
    watcher.check_changes()
    watcher.start()

    plug.listen()
