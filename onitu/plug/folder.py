import os


class Folder(object):
    def __init__(self, name, path, options=None):
        self.name = name
        self.path = path

        self.options = options if options is not None else {}

    def __str__(self):
        return self.name

    @classmethod
    def get_folders(cls, escalator, service):
        folders = {}
        for name in escalator.get('service:{}:folders'.format(service),
                                  default=[]):
            folders[name] = cls.get(escalator, service, name)
        return folders

    @classmethod
    def get(cls, escalator, service, name):
        prefix = 'service:{}:folder:{}'.format(service, name)
        path = escalator.get('{}:path'.format(prefix), default="")
        options = escalator.get('{}:options'.format(prefix), default={})

        return cls(name, path, options)

    def relpath(self, filename):
        return os.path.relpath(filename, self.path)

    def join(self, filename):
        return os.path.join(self.path, filename)

    def contains(self, filename):
        return filename.startswith(self.path)
