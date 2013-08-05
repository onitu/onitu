from importlib import import_module

import json

class Entries(dict):

    def __init__(self):
        super(Entries, self).__init__()

        self._load_entries()

    def launch(self, *ids):
        """Launch all the entries"""

        if not ids:
            ids = self.keys()

        for id in ids:
            self._launch_entry(self[id])

    def stop(self):
        """Stop all the entries"""

        self.manager.stop()
        self.clear()

    def _load_entries(self):
        with open("entries.json") as f:
            for id, infos in json.load(f).items():
                self._load_entry(id, infos)

    def _load_entry(self, id, infos):
        entry = infos

        self._load_driver(entry)

        if entry["driver"]:
            self[id] = entry

    def _load_driver(self, entry):
        name = entry["driver"]

        try:
            driver = import_module(name, "onitu.drivers")
            assert driver.start
        except (ImportError, AttributeError) as e:
            driver = None
            print "Imposible to load driver {} :".format(name), e

        entry["driver"] = driver

    def _launch_entry(entry):
        process = Process(target=entry["driver"].start())
        process.start()

        entry["process"] = process
