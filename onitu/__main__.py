"""
This module starts Onitu. It does the following:

- parse the command line options
- configure the logger
- parse the setup
- clean the database
- launch the different elements using the Circus library
"""

import sys
import argparse
import string
import random

import json
import circus

from circus.exc import ConflictError
from zmq.eventloop import ioloop
from logbook import Logger, INFO, DEBUG, NullHandler, NestedSetup
from logbook.queues import ZeroMQHandler, ZeroMQSubscriber
from logbook.more import ColorizedStderrHandler
from tornado import gen
from plyvel import destroy_db


from .escalator.client import Escalator
from .utils import at_exit, get_open_port


@gen.coroutine
def start_setup(*args, **kwargs):
    """Parse the setup JSON file, clean the database,
    and start the :class:`.Referee` and the drivers.
    """
    escalator = Escalator(escalator_uri, session, create_db=True)

    ports = escalator.range(prefix='port:', include_value=False)

    if ports:
        with escalator.write_batch() as batch:
            for key in ports:
                batch.delete(key)

    escalator.put('referee:rules', setup.get('rules', []))

    if 'entries' not in setup:
        logger.warn("No entries specified in '{}'", setup_file)
        loop.stop()

    entries = setup['entries']

    escalator.put('entries', list(entries.keys()))

    referee = arbiter.add_watcher(
        "Referee",
        sys.executable,
        args=('-m', 'onitu.referee', log_uri, escalator_uri, session),
        copy_env=True,
    )

    loop.add_callback(start_watcher, referee)

    for name, conf in entries.items():
        logger.debug("Loading entry {}", name)

        if ':' in name:
            logger.error("Illegal character ':' in entry {}", name)
            continue

        if 'options' in conf:
            escalator.put(
                'entry:{}:options'.format(name), conf['options']
            )

        watcher = arbiter.add_watcher(
            name,
            sys.executable,
            args=('-m', 'onitu.drivers',
                  conf['driver'], escalator_uri, session, name, log_uri),
            copy_env=True,
        )

        loop.add_callback(start_watcher, watcher)

    logger.debug("Entries loaded")

    api = arbiter.add_watcher(
        "Web API",
        sys.executable,
        args=['-m', 'onitu.webapi'],
        copy_env=True,
    )
    loop.add_callback(start_watcher, api)
    logger.debug("Web API loaded")


@gen.coroutine
def start_watcher(watcher):
    """Start a Circus Watcher.
    If a command is already running, we try again.
    """
    try:
        watcher.start()
    except ConflictError as e:
        loop.add_callback(start_watcher, watcher)
    except Exception as e:
        logger.warning("Can't start entry {} : {}", watcher.name, e)
        return


def get_logs_dispatcher(uri=None, debug=False):
    """Configure the dispatcher that will print the logs received
    on the ZeroMQ channel.
    """
    handlers = []

    if not debug:
        handlers.append(NullHandler(level=DEBUG))

    handlers.append(ColorizedStderrHandler(level=INFO))

    if not uri:
        uri = get_open_port()

    subscriber = ZeroMQSubscriber(uri, multi=True)
    return uri, subscriber.dispatch_in_background(setup=NestedSetup(handlers))


def get_setup():
    logger.info("Loading setup...")
    try:
        with open(setup_file) as f:
            return json.load(f)
    except ValueError as e:
        logger.error("Error parsing '{}' : {}", setup_file, e)
    except Exception as e:
        logger.error(
            "Can't process setup file '{}' : {}", setup_file, e
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser("onitu")
    parser.add_argument(
        '--setup', default='setup.json',
        help="A JSON file with Onitu's configuration (defaults to setup.json)"
    )
    parser.add_argument(
        '--log-uri', help="A ZMQ socket where all the logs will be sent"
    )
    parser.add_argument(
        '--debug', action='store_true', help="Enable debugging logging"
    )
    args = parser.parse_args()

    setup_file = args.setup
    log_uri = args.log_uri
    dispatcher = None

    if not args.log_uri:
        log_uri, dispatcher = get_logs_dispatcher(
            uri=log_uri, debug=args.debug
        )

    with ZeroMQHandler(log_uri, multi=True):
        logger = Logger("Onitu")

        setup = get_setup()
        session = setup.get('name')
        tmp_session = session is None

        if tmp_session:
            # If the current setup does not have a name, we create a random one
            session = ''.join(
                random.sample(string.ascii_letters + string.digits, 10)
            )
        elif ':' in session:
            logger.error("Illegal character ':' in name '{}'", session)

        escalator_uri = get_open_port()

        ioloop.install()
        loop = ioloop.IOLoop.instance()

        arbiter = circus.get_arbiter(
            [
                {
                    'name': 'Escalator',
                    'cmd': sys.executable,
                    'args': ('-m', 'onitu.escalator.server',
                             '--bind', escalator_uri,
                             '--log-uri', log_uri),
                    'copy_env': True,
                },
            ],
            proc_name="Onitu",
            loop=loop
        )

        at_exit(loop.stop)

        try:
            future = arbiter.start()
            loop.add_future(future, start_setup)
            arbiter.start_io_loop()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            logger.info("Exiting...")

            # We wait for all the processes
            # to be killed.
            loop.run_sync(arbiter.stop)

            if dispatcher:
                dispatcher.stop()

            if tmp_session:
                # Maybe this should be handled in Escalator, but
                # it is not easy since it can manage several dbs
                destroy_db('dbs/{}'.format(session))
