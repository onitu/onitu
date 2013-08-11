from onitu.entries import Entries

class Core(object):
    """Core object of the server"""

    def __init__(self):
        self.entries = Entries()

    def launch(self):
        """Method called to start the server and all the drivers"""

        self.entries.launch()

        # This is pure bullshit, we should have something like a Pool and join it
        # Maybe circus could help
        try:
            for id, entry in self.entries.items():
                print "Joining ", id
                entry.process.join()
        except:
            for entry in self.entries.values():
                entry.process.terminate()
