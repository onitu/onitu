import random
import string
import json


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

    def add(self, driver):
        self.entries.add(driver)
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
        config = json.dumps(self.dump, indent=2)
        print('config = """%s"""' % config)

        with open(filename, 'w+') as f:
            json.dump(self.dump, f, indent=2)
