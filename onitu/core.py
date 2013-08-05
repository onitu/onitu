from onitu.entries import Entries

class Core(object):
    """Core object of the server"""

    def __init__(self):
        self.entries = Entries()

    def run(self):
        """Method called to start the server and all the drivers"""

        self.entries.launch()
