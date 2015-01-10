from .exceptions import DriverError


class Folder(object):
    def __init__(self, name, path, options=None):
        self.name = name
        self.path = path

        self.options = options if options is not None else {}

    def __str__(self):
        return self.name

    @classmethod
    def get_folders(cls, plug):
        folders = {}
        names = plug.escalator.get(u'service:{}:folders'.format(plug.name),
                                   default=())
        for folder in names:
            folders[folder] = cls.get(plug, folder)

        return folders

    @classmethod
    def get(cls, plug, folder):
        prefix = u'service:{}:folder:{}'.format(plug.name, folder)
        path = plug.escalator.get(u'{}:path'.format(prefix), default="")
        options = plug.escalator.get(u'{}:options'.format(prefix), default={})

        normalized_path = plug.call('normalize_path', path)

        if normalized_path is not None:
            path = normalized_path

        return cls(folder, path, options)

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
