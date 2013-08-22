import redis
import circus

from onitu.entries import Entries

class Core(object):
    """Core object of the server"""

    def __init__(self):
        # Let's assume that there isn't any Redis server started yet
        # YOLO
        self.arbiter = circus.get_arbiter([{'cmd': "redis-server", 'priority': 42}])
        # We start redis before everyone else. Pretty ugly.
        self.arbiter.watchers[0].start()

        self.redis = redis.Redis()

        self.entries = Entries(self)

    def launch(self):
        """Method called to start the server and all the drivers"""
        try:
            self.arbiter.start()
        finally:
            self.arbiter.stop()
