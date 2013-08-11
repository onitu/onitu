from multiprocessing.managers import Process
from importlib import import_module

class Entry(dict):

    def __init__(self, id, *args, **kwargs):
        super(Entry, self).__init__(*args, **kwargs)

        self.id = id

        self.driver = None

        self._load_driver()

    def launch(self):
        self.process = Process(target=self.driver.start, args=(self,))
        self.process.start()

    def _load_driver(self):
        name = self.get("driver_name", "Nameless")

        try:
            driver = import_module("onitu.drivers.{}".format(name))
            driver.plug.load(self)
            assert driver.start
        except (ImportError, AttributeError) as e:
            driver = None
            print "Impossible to load driver {} :".format(name), e

        self.driver = driver
