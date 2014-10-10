"""
This module starts Onitu. It does the following:

- parse the command line options
- configure the logger
- parse the setup
- clean the database
- launch the different elements using the Circus library
"""

import sys
import time
import argparse
import string
import random

import json
import circus

from logbook import Logger, INFO, DEBUG, NullHandler, NestedSetup
from logbook.queues import ZeroMQHandler, ZeroMQSubscriber
from logbook.more import ColorizedStderrHandler
from tornado import gen
from plyvel import destroy_db


from .escalator.client import Escalator
from .utils import get_open_port

# Time given to each process (Drivers, Referee, API...) to
# exit before being killed. This avoid any hang during
# shutdown
GRACEFUL_TIMEOUT = 1.

setup_file = None
escalator_uri = None
log_uri = None
endpoint = None
session = None
setup = None
logger = None
arbiter = None


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

    entries = setup.get('entries')
    if not entries:
        logger.warn("No entries specified in '{}'", setup_file)
        yield arbiter.stop()

    escalator.put('entries', list(entries.keys()))

    referee = arbiter.add_watcher(
        "Referee",
        sys.executable,
        args=('-m', 'onitu.referee', log_uri, escalator_uri, session),
        copy_env=True,
        graceful_timeout=GRACEFUL_TIMEOUT
    )

    yield referee.start()

    for name, conf in entries.items():
        logger.debug("Loading entry {}", name)

        if ':' in name:
            logger.error("Illegal character ':' in entry {}", name)
            continue

        escalator.put('entry:{}:driver'.format(name), conf['driver'])

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
            graceful_timeout=GRACEFUL_TIMEOUT
        )

        yield watcher.start()

    logger.debug("Entries loaded")

    api = arbiter.add_watcher(
        "Rest API",
        sys.executable,
        args=['-m', 'onitu.api', log_uri, escalator_uri, session, endpoint],
        copy_env=True,
        graceful_timeout=GRACEFUL_TIMEOUT
    )
    yield api.start()


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


def main():
    global setup_file, session, escalator_uri
    global endpoint, setup, logger, log_uri, arbiter

    parser = argparse.ArgumentParser("onitu")
    parser.add_argument(
        '--setup', default='setup.json',
        help="A JSON file with Onitu's configuration (defaults to setup.json)"
    )
    parser.add_argument(
        '--log-uri', help="A ZMQ socket where all the logs will be sent"
    )
    parser.add_argument(
        '--endpoint', help="The ZMQ socket used to manage Onitu"
        "via circusctl. (defaults to tcp://127.0.0.1:5555)",
        default='tcp://127.0.0.1:5555'
    )
    parser.add_argument(
        '--pubsub_endpoint', help="The ZMQ PUB/SUB socket receiving"
        "publications of events. (defaults to tcp://127.0.0.1:5556)",
        default='tcp://127.0.0.1:5556'
    )
    parser.add_argument(
        '--stats_endpoint', help="The ZMQ PUB/SUB socket receiving"
        "publications of stats. (defaults to tcp://127.0.0.1:5557)",
        default='tcp://127.0.0.1:5557'
    )
    parser.add_argument(
        '--debug', action='store_true', help="Enable debugging logging"
    )
    args = parser.parse_args()

    setup_file = args.setup
    log_uri = args.log_uri
    endpoint = args.endpoint
    pubsub_endpoint = args.pubsub_endpoint
    stats_endpoint = args.stats_endpoint

    if not args.log_uri:
        log_uri, dispatcher = get_logs_dispatcher(
            uri=log_uri, debug=args.debug
        )
    else:
        dispatcher = None

    with ZeroMQHandler(log_uri, multi=True):
        logger = Logger("Onitu")

        try:
            setup = get_setup()
            if not setup:
                # Give some time to the dispatcher to print
                # the error before exiting
                time.sleep(0.1)
                return 1

            session = setup.get('name')
            tmp_session = session is None

            if tmp_session:
                # If the current setup does not have a name, we create
                # a random one
                session = ''.join(
                    random.sample(string.ascii_letters + string.digits, 10)
                )
            elif ':' in session:
                logger.error("Illegal character ':' in name '{}'", session)

            escalator_uri = get_open_port()

            arbiter = circus.get_arbiter(
                (
                    {
                        'name': 'Escalator',
                        'cmd': sys.executable,
                        'args': ('-m', 'onitu.escalator.server',
                                 '--bind', escalator_uri,
                                 '--log-uri', log_uri),
                        'copy_env': True,
                        'graceful_timeout': GRACEFUL_TIMEOUT
                    },
                ),
                proc_name="Onitu",
                controller=endpoint,
                pubsub_endpoint=pubsub_endpoint,
                stats_endpoint=stats_endpoint,
            )

            arbiter.start(cb=start_setup)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            if dispatcher and dispatcher.running:
                dispatcher.stop()

            if 'tmp_session' in locals() and tmp_session:
                # Maybe this should be handled in Escalator, but
                # it is not easy since it can manage several dbs
                destroy_db('dbs/{}'.format(session))

if __name__ == '__main__':
    sys.exit(main())
