from .drivers import Drivers

class Core(object):
    """Core object of the server"""

    def __init__(self):
        self.drivers = Drivers()

    def run(self):
        """Method called to start the server and all the drivers"""

        self.drivers.load()
