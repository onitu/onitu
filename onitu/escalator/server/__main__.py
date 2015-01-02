import os
import sys

import zmq

from logbook import Logger
from logbook.queues import ZeroMQHandler

from onitu.utils import at_exit, get_escalator_uri, get_logs_uri, u

from .databases import Databases
from .worker import Worker

back_uri = 'inproc://workers'

logger = Logger('Escalator')


def main(logger):
    proxy = zmq.devices.ThreadDevice(
        device_type=zmq.QUEUE, in_type=zmq.DEALER, out_type=zmq.ROUTER
    )
    proxy.bind_out(get_escalator_uri(session))
    proxy.bind_in(back_uri)
    proxy.start()

    nb_workers = 8
    workers = []

    for i in range(nb_workers):
        worker = Worker(databases, back_uri, logger)
        worker.daemon = True
        worker.start()
        workers.append(worker)

    logger.info("Started")

    while proxy.launcher.is_alive():
        try:
            # If we join the process without a timeout we never
            # get the chance to handle the exception
            proxy.join(100)
        except KeyboardInterrupt:
            break


def cleanup():
    databases.close()
    zmq.Context.instance().term()

    logger.info("Exited")

    exit()


session = u(sys.argv[1])
config_dir = u(sys.argv[2])
databases_dir = os.path.join(config_dir, 'dbs')

if not os.path.exists(databases_dir):
    os.makedirs(databases_dir)

databases = Databases(databases_dir)

at_exit(cleanup)


with ZeroMQHandler(get_logs_uri(session), multi=True).applicationbound():
    main(logger)
