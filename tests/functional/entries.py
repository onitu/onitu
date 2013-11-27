from collections import namedtuple
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

class LocalStorageEntry(EntryBase):
    def __init__(self, *args, **kwargs):
        super(LocalStorageEntry, self).__init__(*args, **kwargs)
        if not 'root' in self.options:
            self.options['root'] = 'test/driver_' + slugify(self.name)

class Entry(EntryBase):
    _types = {
        'local_storage': LocalStorageEntry
    }
    def __new__(cls, driver, *args, **kwargs):
        driver_type = cls._types.get(driver, None)
        if driver_type:
            return driver_type(driver, *args, **kwargs)
        return super(Entry, cls).__new__(cls)


class Entries(object):
    def __init__(self):
        self._items = {}
    def add(self, driver, name=None):
        if name is None:
            name = driver
        self._items[name] = Entry(driver, name)
    @property
    def dump(self):
        return {k:v.dump for (k, v) in self._items.items()}
    @property
    def json(self):
        return json.dumps(self.dump, indent=2)
