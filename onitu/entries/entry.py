from multiprocessing.managers import BaseManager
from importlib import import_module

class Entry(dict):

    def __init__(self, *args, **kwargs):
        super(Entry, self).__init__(*args, **kwargs)

        self._load_driver()

    def launch(self):
        process = Process(target=self["driver"].start())
        process.start()

        self["process"] = process


    def _load_driver(self):
        name = self["driver_name"]

        try:
            driver = import_module(name, "onitu.drivers")
            assert driver.start
        except (ImportError, AttributeError) as e:
            driver = None
            print "Imposible to load driver {} :".format(name), e

        self["driver"] = driver


class EntryManager(BaseManager):
    def __init__(self):
        super(EntryManager, self).__init__()

        self.register('Entry', Entry)
        self.start()

ProxyEntry = EntryManager().Entry