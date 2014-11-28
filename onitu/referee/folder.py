from fnmatch import fnmatchcase


class Folder(object):
    def __init__(self, name, services,
                 mimetypes=None,
                 min_size=None, max_size=None,
                 blacklist=None, whitelist=None, **kwargs):
        self.name = name
        self.services = frozenset(services)
        self.options = kwargs

        self.mimetypes = mimetypes

        self.min_size = self._to_bytes(min_size)
        self.max_size = self._to_bytes(max_size)

        self.blacklist = blacklist
        self.whitelist = whitelist

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

    def targets(self, metadata, source):
        if not self.check_size(metadata['size']):
            return

        if not self.check_mimetype(metadata['mimetype']):
            return

        if self.blacklisted(metadata['filename']):
            return

        if not self.whitelisted(metadata['filename']):
            return

        return self.services - frozenset((source,))

    def check_size(self, size):
        if self.min_size is not None and size < self.min_size:
            return False

        if self.max_size is not None and size > self.max_size:
            return False

        return True

    def check_mimetype(self, mimetype):
        if self.mimetypes is None:
            return True

        for predicate in self.mimetypes:
            if '/' not in predicate:
                predicate += '/'

            if predicate.endswith('/'):
                if mimetype.startswith(predicate):
                    return True
            else:
                if predicate == mimetype:
                    return True

        return False

    def blacklisted(self, filename):
        if self.blacklist is None:
            return False

        return any(fnmatchcase(filename, rule) for rule in self.blacklist)

    def whitelisted(self, filename):
        if self.whitelist is None:
            return True

        return any(fnmatchcase(filename, rule) for rule in self.whitelist)

    def _to_bytes(self, size):
        units = {
            'B': 1e0,
            'o': 1e0,

            'K': 1e3,
            'k': 1e3,
            'ko': 1e3,
            'kb': 1e3,
            'KB': 1e3,

            'M': 1e6,
            'm': 1e6,
            'mo': 1e6,
            'mb': 1e6,
            'MB': 1e6,

            'G': 1e9,
            'g': 1e9,
            'go': 1e9,
            'gb': 1e9,
            'GB': 1e9,

            'T': 1e12,
            't': 1e12,
            'to': 1e12,
            'tb': 1e12,
            'TB': 1e12,

            'P': 1e15,
            'p': 1e15,
            'po': 1e15,
            'pb': 1e15,
            'PB': 1e15,

            'Ki': 2 ** 10,
            'Mi': 2 ** 20,
            'Gi': 2 ** 30,
            'Ti': 2 ** 40,
            'Pi': 2 ** 50,
        }

        if not size:
            return None

        try:
            return float(size)
        except ValueError:
            pass

        size = size.strip()
        unit = size.lstrip('0123456789.')

        if unit not in units:
            return None

        try:
            return float(size[:-len(unit)]) * units[unit]
        except ValueError:
            return None

        return None
