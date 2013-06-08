class Manager(object):
    """Used by Drivers to manage the drivers"""

    def __init__(self):
        pass

    def load(self, *names):
        """Load & start a list of drivers. Load all of them if none is specified"""

        if not names:
            names = self.get_all_drivers()

        # TODO : Define the Driver class
        drivers = {name: Driver(name) for name in names}

        for driver in drivers.items():
            driver.start()

    def get_all_drivers():
        """Get all the installed drivers"""
        # TODO : Find a clean solution to manage configuration
        pass
