import os
import argparse

import zmq

from logbook import Logger
from logbook import StderrHandler
from logbook.queues import ZeroMQHandler

from onitu.utils import at_exit

from .databases import Databases
from .worker import Worker

back_uri = 'inproc://workers'

logger = Logger('Escalator')


def main(logger):
    proxy = zmq.devices.ThreadDevice(
        device_type=zmq.QUEUE, in_type=zmq.DEALER, out_type=zmq.ROUTER
    )
    proxy.bind_out(bind_uri)
    proxy.bind_in(back_uri)
    proxy.start()

    logger.info("Starting on '{}'", args.bind)

    nb_workers = 8
    workers = []

    for i in range(nb_workers):
        worker = Worker(databases, back_uri, logger)
        worker.daemon = True
        worker.start()
        workers.append(worker)

    while proxy.launcher.is_alive():
        try:
            # If we join the process without a timeout we never
            # get the chance to handle the exception
            proxy.join(100)
        except KeyboardInterrupt:
            break


def cleanup():
    databases.close()

    if bind_uri.startswith("ipc://"):
        # With ZMQ < 4.1 (which isn't released yet), we can't
        # close the device in a clean way.
        # This will be possible with ZMQ 4.1 by using
        # zmq_proxy_steerable.
        # In the meantime, we must delete the Unix socket by hand.
        sock_file = bind_uri[6:]

        try:
            os.unlink(sock_file)
        except OSError:
            pass

    logger.info("Exited")

    exit()

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

bind_uri = args.bind
databases = Databases('dbs')

at_exit(cleanup)

if args.log_uri:
    handler = ZeroMQHandler(args.log_uri, multi=True)
else:
    handler = StderrHandler()

with handler.applicationbound():
    main(logger)
    cleanup()
