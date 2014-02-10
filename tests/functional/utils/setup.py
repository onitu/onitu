import json
import re


def slugify(s):
    return re.sub(r'__+', '_', re.sub(r'[^a-z0-9]', '_', s.lower()))


class EntryBase(object):
    def __init__(self, driver, name, options=None):
        self.driver = driver
        self.name = name
        self.options = options if options is not None else {}

    @property
    def dump(self):
        return {'driver': self.driver, 'options': self.options}

    def __hash__(self):
        return hash((self.driver, self.name))

    def __eq__(self, other):
        return hash(self) == hash(other)


class LocalStorageEntry(EntryBase):
    def __init__(self, *args, **kwargs):
        super(LocalStorageEntry, self).__init__(*args, **kwargs)
        if not 'root' in self.options:
            self.options['root'] = 'test/driver_' + slugify(self.name)

    def __hash__(self):
        return hash((self.driver, self.options['root']))


class Entry(EntryBase):
    _types = {
        'local_storage': LocalStorageEntry
    }

    def __new__(cls, driver, *args, **kwargs):
        driver_type = cls._types.get(driver, None)
        if driver_type:
            return driver_type(driver, *args, **kwargs)
        return super(Entry, cls).__new__(cls)


class Setup(object):
    def __init__(self, name=None):
        self.entries = set()
        self.name = name

    def add(self, driver, name=None, options=None):
        if name is None:
            name = driver
        self.entries.add(Entry(driver, name, options))

    @property
    def dump(self):
        setup = {}
        if self.name:
            setup['name'] = self.name
        setup['entries'] = {e.name: e.dump for e in self.entries}
        return setup

    @property
    def json(self):
        return json.dumps(self.dump, indent=2)

    def save(self, filename):
        with open(filename, 'w+') as f:
            json.dump(self.dump, f, indent=2)
