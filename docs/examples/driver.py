import os

from onitu.api import Plug, ServiceError, DriverError

# A dummy library supposed to watch the file system
from fsmonitor import FSWatcher

plug = Plug()


@plug.handler()
def get_chunk(metadata, offset, size):
    try:
        with open(metadata.filename, 'rb') as f:
            f.seek(offset)
            return f.read(size)
    except IOError as e:
        raise ServiceError(
            "Error reading '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    try:
        with open(metadata.filename, 'r+b') as f:
            f.seek(offset)
            f.write(chunk)
    except IOError as e:
        raise ServiceError(
            "Error writting '{}': {}".format(metadata.filename, e)
        )


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


def start():
    try:
        root = plug.options['root']
        os.chdir(root)
    except OSError as e:
        raise DriverError("Can't access '{}': {}".format(root, e))

    watcher = Watcher(root)
    watcher.check_changes()
    watcher.start()

    plug.listen()
