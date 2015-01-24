from onitu.utils import u

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

        # If after the normalization any folder is embedded in another, we
        # throw an error.
        for folder in folders.values():
            for candidate in folders.values():
                if candidate.contains(folder.path):
                    raise DriverError(
                        'Folder {} is embedded in folder {}. Please check '
                        'your configuration.'.format(folder, candidate)
                    )

        return folders

    @classmethod
    def get(cls, plug, folder):
        folder = u(folder)
        prefix = u'service:{}:folder:{}'.format(plug.name, folder)
        path = plug.escalator.get(u'{}:path'.format(prefix), default="")
        options = plug.escalator.get(u'{}:options'.format(prefix), default={})

        normalized_path = plug.call('normalize_path', path)

        if normalized_path is not None:
            path = normalized_path

        return cls(folder, path, options)

    def relpath(self, filename):
        path = self._normalize(self.path)

        if not filename.startswith(path):
            raise DriverError(
                u"'{}' is not in the folder {}".format(filename, self.name)
            )
        return filename[len(path):].lstrip('/')

    def join(self, filename):
        path = self._normalize(self.path)

        if filename.startswith(path):
            filename = filename[len(path):]
        return path + filename.lstrip('/')

    def contains(self, candidate):
        path = self._normalize(self.path)
        candidate = self._normalize(candidate)
        return candidate != path and candidate.startswith(path)

    def _normalize(self, path):
        return path.rstrip('/') + '/'
