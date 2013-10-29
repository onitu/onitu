from multiprocessing import Process
from threading import Thread

import zmq
import redis

class Plug(Thread):
    """docstring for Plug"""

    def __init__(self):
        super(Plug, self).__init__()

        self.handlers = {}

        self.redis = redis.Redis(unix_socket_path='redis/redis.sock')

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.REP)
        self.port = self.socket.bind_to_random_port("tcp://*")

    def launch(self, id):
        self.id = id
        self.options = self.redis.hgetall("onitu:options:{}".format(self.id))

        self.redis.hset("onitu:sockets:{}".format(self.id), "port", self.port)

        self.start()

    def run(self):
        while 42:
            msg = self.socket.recv_json()
            self._respond_to(msg)

    def handler(self, task=None):
        def wrapper(handler):
            self.handlers[task if task else handler.__name__] = handler
            return handler

        return wrapper

    def _respond_to(self, msg):
        def inner():
            handler = self._get_handler(msg.get("task"))
            response = handler(msg)
            self.socket.send_json(response)

        thread = Thread(target=inner)
        thread.start()

    def _default_handler(self, task):
        print("{}: Error, unsupported message {}.".format(self.id, msg))
        return {'error': 'Unsupported message'}

    def _get_handler(self, task):
        return self.handlers.get(task, self._default_handler)
