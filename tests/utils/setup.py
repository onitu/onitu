import random
import string
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
        if 'root' not in self.options:
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


class Rule(object):
    def __init__(self):
        self._match = {}
        self._sync = []

    def match_path(self, path):
        self._match['path'] = path
        return self

    def match_mime(self, *mimes):
        self._match['mime'] = self._match.get('mime', []) + list(mimes)
        return self

    def sync(self, *entries):
        self._sync += list(entries)
        return self

    @property
    def dump(self):
        return {'match': self._match, 'sync': self._sync}


class Setup(object):
    def __init__(self, session=True):
        self.entries = set()
        self.rules = []

        if session:
            # Each time the launcher will be started, it will use the
            # same session
            self.name = ''.join(
                random.sample(string.ascii_letters + string.digits, 20)
            )
        else:
            self.name = None

    def add(self, driver, name=None, options=None):
        if name is None:
            name = driver
        self.entries.add(Entry(driver, name, options))
        return self

    def add_rule(self, rule):
        self.rules.append(rule)
        return self

    @property
    def dump(self):
        setup = {}
        if self.name:
            setup['name'] = self.name
        setup['entries'] = {e.name: e.dump for e in self.entries}
        setup['rules'] = [r.dump for r in self.rules]
        return setup

    @property
    def json(self):
        return json.dumps(self.dump, indent=2)

    def save(self, filename):
        with open(filename, 'w+') as f:
            json.dump(self.dump, f, indent=2)
