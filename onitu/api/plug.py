from multiprocessing import Process
from threading import Thread

import zmq

class Plug(Thread):
    """docstring for Plug"""

    def __init__(self):
        super(Plug, self).__init__()

        self.handlers = {}

    def load(self, entry):
        self.entry = entry

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.REP)
        self.port = self.socket.bind_to_random_port("tcp://*")

        self.entry["port"] = self.port

    def run(self):
        while 42:
            msg = self.socket.recv_json()
            self._respond_to(msg)

    def handler(self, task=None):
        def wrapper(handler):
            if not task:
                task = handler.__name__

            self.handlers[task] = handler
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
        print "{}: Error, unsupported message {}.".format(self.id, msg)
        return {'error': 'Unsupported message'}

    def _get_handler(self, task):
        return self.handlers.get(task, self._default_handler)
