import zmq

from .databases import Databases
from .worker import Worker

context = zmq.Context()

back_uri = 'tcp://127.0.0.1:4225'

proxy = zmq.devices.ProcessDevice(
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

try:
    proxy.join()
except KeyboardInterrupt:
    print("Stopping...")
    pass
