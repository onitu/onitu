import os
import random
import string
import json

from plyvel import destroy_db

from onitu.utils import TMPDIR


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
    def __init__(self):
        self.entries = set()
        self.rules = []

        self._json = None

        self.name = ''.join(
            random.sample(string.ascii_letters + string.digits, 20)
        )
        self.filename = os.path.join(TMPDIR, "{}.json".format(self.name))

    def add(self, driver):
        driver.connect(self.name)
        self.entries.add(driver)
        return self

    def add_rule(self, rule):
        self.rules.append(rule)
        return self

    def clean(self, entries=True):
        if entries:
            for entry in self.entries:
                entry.close()

        try:
            os.unlink(self.filename)
            destroy_db('dbs/{}'.format(self.name))
        except (OSError, IOError):
            pass

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
        if not self._json:
            self._json = json.dumps(self.dump, indent=2)

        return self._json

    @json.setter
    def json(self, content):
        self._json = content

    def save(self):
        print('Setup:')
        print(self.json)

        with open(self.filename, 'w+') as f:
            f.write(self.json)
