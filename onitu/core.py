import time

import redis

from circus.client import CircusClient

from onitu.entries import Entries

class Core(object):
    """Core object of the server"""

    def __init__(self):
        self.circus = CircusClient()

        self.redis = redis.Redis()

        self.entries = Entries(self)

    def launch(self):
        """Method called to start the server and all the drivers"""
        try:
            while 42:
                time.sleep(0.1)
        finally:
            exit()
