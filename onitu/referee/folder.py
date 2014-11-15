

class Folder(object):
    def __init__(self, name, services, **kwargs):
        self.name = name
        self.services = frozenset(services)
        self.options = kwargs

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Folder {}: services={}, options={}>".format(
            self.name, list(self.services), self.options
        )

    @classmethod
    def get_folders(cls, escalator, services):
        service_folders = {
            s: escalator.get('service:{}:folders'.format(s), default=[])
            for s in services
        }

        folders = {}

        for key, options in escalator.range('folder:'):
            name = key.split(':')[-1]
            dest = filter(lambda s: name in service_folders[s], services)
            folders[name] = cls(name, dest, **options)

        return folders

    def targets(self, *excluded):
        return self.services - frozenset(excluded)
