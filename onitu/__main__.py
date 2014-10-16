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
from .utils import get_logs_uri, IS_WINDOWS, get_stats_endpoint
from .utils import get_circusctl_endpoint, get_pubsub_endpoint

# Time given to each process (Drivers, Referee, API...) to
# exit before being killed. This avoid any hang during
# shutdown
GRACEFUL_TIMEOUT = 1.

setup_file = None
session = None
setup = None
logger = None
arbiter = None


@gen.coroutine
def start_setup(*args, **kwargs):
    """Parse the setup JSON file, clean the database,
    and start the :class:`.Referee` and the drivers.
    """
    escalator = Escalator(session, create_db=True)

    escalator.put('referee:rules', setup.get('rules', []))

    entries = setup.get('entries')
    if not entries:
        logger.warn("No entries specified in '{}'", setup_file)
        yield arbiter.stop()

    escalator.put('entries', list(entries.keys()))

    referee = arbiter.add_watcher(
        "Referee",
        sys.executable,
        args=('-m', 'onitu.referee', session),
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
                  conf['driver'], session, name),
            copy_env=True,
            graceful_timeout=GRACEFUL_TIMEOUT
        )

        yield watcher.start()

    logger.debug("Entries loaded")

    api = arbiter.add_watcher(
        "Rest API",
        sys.executable,
        args=['-m', 'onitu.api', session],
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
    global setup_file, session, setup, logger, arbiter

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
        '--debug', action='store_true', help="Enable debugging logging"
    )
    args = parser.parse_args()

    setup_file = args.setup

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
            arbiter = circus.get_arbiter(
                (
                    {
                        'name': 'Escalator',
                        'cmd': sys.executable,
                        'args': ('-m', 'onitu.escalator.server', session),
                        'copy_env': True,
                        'graceful_timeout': GRACEFUL_TIMEOUT
                    },
                ),
                proc_name="Onitu",
                controller=get_circusctl_endpoint(session),
                pubsub_endpoint=get_pubsub_endpoint(session),
                stats_endpoint=get_stats_endpoint(session),
                statsd=True
            )

            arbiter.start(cb=start_setup)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            if dispatcher and dispatcher.running:
                dispatcher.stop()

            if IS_WINDOWS:
                from .utils import delete_sock_files
                delete_sock_files()


if __name__ == '__main__':
    sys.exit(main())
