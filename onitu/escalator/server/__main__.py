import argparse

import zmq

from .databases import Databases
from .worker import Worker


parser = argparse.ArgumentParser("escalator")
parser.add_argument(
    '--bind', default='tcp://*:4224',
    help="Address to bind escalator server"
)
args = parser.parse_args()

context = zmq.Context()

back_uri = 'inproc://workers'

proxy = zmq.devices.ThreadDevice(
    device_type=zmq.QUEUE, in_type=zmq.DEALER, out_type=zmq.ROUTER
)
proxy.bind_out(args.bind)
proxy.bind_in(back_uri)
proxy.start()

print('Starting escalator server on {}'.format(repr(args.bind)))

databases = Databases('dbs')

nb_workers = 8
workers = []

for i in range(nb_workers):
    worker = Worker(databases, back_uri)
    worker.daemon = True
    worker.start()
    workers.append(worker)

while proxy.launcher.isAlive():
    try:
        # If we join the process without a timeout we never
        # get the chance to handle the exception
        proxy.join(100)
    except KeyboardInterrupt:
        databases.close()
        break
