import json

from .entry import Entry

class Entries(dict):

    def __init__(self, core):
        super(Entries, self).__init__()

        self.core = core

        self._load_entries()

    def _load_entries(self):
        with open("entries.json") as f:
            for id, infos in json.load(f).items():
                self._load_entry(id, infos)

    def _load_entry(self, id, infos):
        entry = Entry(id, self.core, infos)

        if entry.ready:
            self[id] = entry
