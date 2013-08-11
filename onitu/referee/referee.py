from multiprocessing import Process

import zmq

class Referee(Process):
    """docstring for Referee"""

    def __init__(self, port):
        super(Referee, self).__init__()

        self.context = zmq.Context()


    def run(self):
        pass