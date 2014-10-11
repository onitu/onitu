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

import json
import circus

from logbook import Logger, INFO, DEBUG, NullHandler, NestedSetup
from logbook.queues import ZeroMQHandler, ZeroMQSubscriber
from logbook.more import ColorizedStderrHandler
from tornado import gen


from .escalator.client import Escalator
from .utils import get_logs_uri, get_open_port, IS_WINDOWS

# Time given to each process (Drivers, Referee, API...) to
# exit before being killed. This avoid any hang during
# shutdown
GRACEFUL_TIMEOUT = 1.

setup_file = None
escalator_uri = None
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

    if IS_WINDOWS:
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
        args=('-m', 'onitu.referee', escalator_uri, session),
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
                  conf['driver'], escalator_uri, session, name),
            copy_env=True,
            graceful_timeout=GRACEFUL_TIMEOUT
        )

        yield watcher.start()

    logger.debug("Entries loaded")

    api = arbiter.add_watcher(
        "Rest API",
        sys.executable,
        args=['-m', 'onitu.api', escalator_uri, session, endpoint],
        copy_env=True,
        graceful_timeout=GRACEFUL_TIMEOUT
    )
    yield api.start()


def get_logs_dispatcher(uri, debug=False):
    """Configure the dispatcher that will print the logs received
    on the ZeroMQ channel.
    """
    handlers = []

    if not debug:
        handlers.append(NullHandler(level=DEBUG))

    handlers.append(ColorizedStderrHandler(level=INFO))

    subscriber = ZeroMQSubscriber(uri, multi=True)
    return subscriber.dispatch_in_background(setup=NestedSetup(handlers))


def get_setup():
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
    global endpoint, setup, logger, arbiter

    logger = Logger("Onitu")

    parser = argparse.ArgumentParser("onitu")
    parser.add_argument(
        '--setup', default='setup.json',
        help="A JSON file with Onitu's configuration (defaults to setup.json)"
    )
    parser.add_argument(
        '--no-dispatcher', action='store_true',
        help="Use this flag to disable the log dispatcher"
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
    endpoint = args.endpoint
    pubsub_endpoint = args.pubsub_endpoint
    stats_endpoint = args.stats_endpoint

    setup = get_setup()
    if not setup:
        return 1

    session = setup.get('name')

    logs_uri = get_logs_uri(session)
    if not args.no_dispatcher:
        dispatcher = get_logs_dispatcher(debug=args.debug, uri=logs_uri)
    else:
        dispatcher = None

    with ZeroMQHandler(logs_uri, multi=True):
        try:
            escalator_uri = get_open_port()

            arbiter = circus.get_arbiter(
                (
                    {
                        'name': 'Escalator',
                        'cmd': sys.executable,
                        'args': ('-m', 'onitu.escalator.server',
                                 '--bind', escalator_uri,
                                 '--log-uri', logs_uri),
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


if __name__ == '__main__':
    sys.exit(main())
