from onitu.utils import pack_msg, unpack_msg
from .exceptions import DriverError

class FolderWrapper(object):
    def __init__(self, name, path, options):
        self.name = name
        self.path = path
        self.options = options

    @classmethod
    def get_folders(cls, plug):
        r = plug.request(pack_msg('get_folders'))
        folders = unpack_msg(r)
        folders = {name: plug.folder_unserialize(value)
                   for (name, value) in folders.items()}
        return folders

    @classmethod
    def get(cls, plug, folder):
        r = plug.request(pack_msg('get_folder', folder))
        return plug.folder_unserialize(unpack_msg(r))

    def relpath(self, filename):
        if not filename.startswith(self.path):
            raise DriverError(
                u"'{}' is not in the folder {}".format(filename, self.name)
            )
        return filename[len(self.path):].lstrip('/')

    def join(self, filename):
        if filename.startswith(self.path):
            filename = filename[len(self.path):]
        return self.path.rstrip('/') + '/' + filename.lstrip('/')

    def contains(self, filename):
        return filename != self.path and filename.startswith(self.path)

def folder_serializer(f):
    return f.name, f.path, f.options
