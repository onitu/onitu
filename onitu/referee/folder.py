from fnmatch import fnmatchcase


class Folder(object):
    def __init__(self, name, services, logger, options={}):
        self.name = name
        self.services = services
        self.logger = logger
        self.options = options

    def __str__(self):
        return self.name

    def __repr__(self):
        return u"<Folder {}: services={}, options={}>".format(
            self.name, list(self.services), self.options
        )

    @classmethod
    def get_folders(cls, escalator, services, logger):

        sfopts = {}
        for s in services:
            folders = {}
            for f in escalator.get(u'service:{}:folders'.format(s)):
                folders[f] = escalator.get(
                    u'service:{}:folder:{}:options'.format(s, f))
            sfopts[s] = folders

        folders = {}

        for key, options in escalator.range('folder:'):
            name = key.split(':')[-1]
            dest = {s: o[name] for s, o in sfopts.items() if name in o}
            folders[name] = cls(name, dest, logger, options)

        return folders

    def targets(self, metadata, source):

        # To decide which targets are relevant there are two things we
        # should take into account. folder options and service/folder
        # options.

        # Step 1: Do we (the folder) want the file?

        if not self.assert_options(self.options, metadata):
            return set()

        # Step 2: Does the source want to share it?

        options = self.services[source]
        if not self.assert_options(options, metadata,
                                   authority="{} (source)".format(source)):
            return set()

        # Step 3: Check who else is interested.

        targets = set()
        for service, options in self.services.items():
            if service == source:
                continue
            if self.assert_options(options, metadata, authority=service):
                targets.add(service)

        return targets

    def assert_options(self, options, metadata, mode="", authority=None):

        def check_list(l, c):
            if l is None:
                return None
            return any(fnmatchcase(c, rule) for rule in l)

        # Those options are either our own or those of a service.
        # This is because there is no difference between
        # service/folder and folder options.

        if authority is None:
            authority = "Folder <{}>".format(self.name)
        else:
            authority = "Service <{}> in Folder <{}>".format(
                authority, self.name)

        # mode

        modeopts = options.get("mode", "rw")
        if any(c not in modeopts for c in mode):
            return False

        # min/max size

        minsz = options.get("file_size", {}).get("min")
        maxsz = options.get("file_size", {}).get("max")

        if minsz is not None and metadata['size'] < self._to_bytes(minsz):
            self.logger.info(
                "{} ignores event for '{}' due to its size: {} bytes",
                authority, metadata['filename'], metadata['size'])
            return False

        if maxsz is not None and metadata['size'] > self._to_bytes(maxsz):
            self.logger.info(
                "{} ignores event for '{}' due to its size: {} bytes",
                authority, metadata['filename'], metadata['size'])
            return False

        # mimetypes

        if check_list(options.get("mimetypes"), metadata['mimetype']) is False:
            self.logger.info(
                "{} ignores event for '{}' due to its mimetype: {}",
                authority, metadata['filename'], metadata['mimetype'])
            return False

        # black/white list

        if check_list(options.get("blacklist"), metadata['filename']) is True:
            self.logger.info(
                "{} ignores event for '{}' because it is blacklisted",
                authority, metadata['filename'])
            return False

        if check_list(options.get("whitelist"), metadata['filename']) is False:
            self.logger.info(
                "{} ignores event for '{}' because it is not whitelisted",
                authority, metadata['filename'])
            return False

        return True

    def _to_bytes(self, size):
        units = {
            '': 1e0,
            'b': 1e0,
            'o': 1e0,

            'k': 1e3,
            'ko': 1e3,
            'kb': 1e3,

            'm': 1e6,
            'mo': 1e6,
            'mb': 1e6,

            'g': 1e9,
            'go': 1e9,
            'gb': 1e9,

            't': 1e12,
            'to': 1e12,
            'tb': 1e12,

            'p': 1e15,
            'po': 1e15,
            'pb': 1e15,

            'ki': 2 ** 10,
            'mi': 2 ** 20,
            'gi': 2 ** 30,
            'ti': 2 ** 40,
            'pi': 2 ** 50,
        }

        if size is None:
            return None

        try:
            return int(size)
        except ValueError:
            pass

        size = size.replace(' ', '')
        unit = size.lstrip('0123456789.').lower()
        size = size[:-len(unit)] if len(unit) else size

        if unit not in units:
            return None

        try:
            return int(float(size) * units[unit])
        except ValueError:
            pass

        return None
