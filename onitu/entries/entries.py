import json

from .entry import Entry

class Entries(dict):

    def __init__(self):
        super(Entries, self).__init__()

        self._load_entries()

    def launch(self, *ids):
        """Launch all the entries"""

        if not ids:
            ids = self.keys()

        for id in ids:
            self[id].launch()


    def _load_entries(self):
        with open("entries.json") as f:
            for id, infos in json.load(f).items():
                self._load_entry(id, infos)

    def _load_entry(self, id, infos):
        entry = Entry(id, infos)

        if entry.driver:
            self[id] = entry
