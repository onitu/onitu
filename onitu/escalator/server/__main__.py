import argparse

import zmq

from logbook import Logger
from logbook import StderrHandler
from logbook.queues import ZeroMQHandler

from .databases import Databases
from .worker import Worker

back_uri = 'inproc://workers'

logger = Logger('Escalator')


def main(logger):
    proxy = zmq.devices.ThreadDevice(
        device_type=zmq.QUEUE, in_type=zmq.DEALER, out_type=zmq.ROUTER
    )
    proxy.bind_out(args.bind)
    proxy.bind_in(back_uri)
    proxy.start()

    logger.info("Starting on '{}'", args.bind)

    databases = Databases('dbs')

    nb_workers = 8
    workers = []

    for i in range(nb_workers):
        worker = Worker(databases, back_uri, logger)
        worker.daemon = True
        worker.start()
        workers.append(worker)

    while proxy.launcher.isAlive():
        try:
            # If we join the process without a timeout we never
            # get the chance to handle the exception
            proxy.join(100)
        except KeyboardInterrupt:
            break

    logger.info("Exiting")
    databases.close()


parser = argparse.ArgumentParser("escalator")
parser.add_argument(
    '--bind', default='tcp://127.0.0.1:4224',
    help="Address to bind escalator server"
)
parser.add_argument(
    '--log-uri',
    help="The URI of the ZMQ handler listening to the logs"
)

args = parser.parse_args()

if args.log_uri:
    handler = ZeroMQHandler(args.log_uri, multi=True)
else:
    handler = StderrHandler()

with handler.applicationbound():
    main(logger)
