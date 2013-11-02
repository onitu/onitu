import simplejson

from .entry import Entry

class Entries(dict):

    def __init__(self, core):
        super(Entries, self).__init__()

        self.core = core

        self._load_entries()

    def _load_entries(self):
        with open('entries.json') as f:
            for name, infos in simplejson.load(f).items():
                self._load_entry(name, infos)

    def _load_entry(self, name, infos):
        if ':' in name:
            print("Illegal character ':' in entry name :", name)
            return

        entry = Entry(name, self.core, infos)

        if entry.ready:
            self[name] = entry
