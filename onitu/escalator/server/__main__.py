import zmq

from .databases import Databases
from .worker import Worker

context = zmq.Context()

back_uri = 'inproc://workers'

proxy = zmq.devices.ThreadDevice(
    device_type=zmq.QUEUE, in_type=zmq.DEALER, out_type=zmq.ROUTER
)
proxy.bind_out('tcp://*:4224')
proxy.bind_in(back_uri)
proxy.start()

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
