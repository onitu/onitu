from .manager import Manager

class Drivers(dict):
    """Dictionary containing all the drivers.

    It's the exposed part of driver management.
    """

    def __init__(self):
        super(Drivers, self).__init__()

        self.manager = Manager()

    def load(self):
        """Load and start all the drivers"""

        drivers = self.manager.load()
        self.update(drivers)

    def stop(self):
        """Stop all the drivers"""

        self.manager.stop()
        self.clear()