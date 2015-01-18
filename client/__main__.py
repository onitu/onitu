#!/usr/bin/env python

import os
import argparse

from logbook import Logger, INFO, DEBUG, NullHandler, NestedSetup
from logbook.queues import ZeroMQHandler, ZeroMQSubscriber
from logbook.more import ColorizedStderrHandler

from onitu.utils import get_available_drivers, get_logs_uri

os.environ['ONITU_CLIENT'] = 'client'

logger = None


def get_logs_dispatcher(uri=None, debug=False):
    """Configure the dispatcher that will print the logs received
    on the ZeroMQ channel.
    """
    handlers = []

    if not debug:
        handlers.append(NullHandler(level=DEBUG))

    handlers.append(ColorizedStderrHandler(level=INFO))

    if not uri:
        uri = get_logs_uri('client')

    subscriber = ZeroMQSubscriber(uri, multi=True)
    return uri, subscriber.dispatch_in_background(setup=NestedSetup(handlers))


def get_setup(setup_file):
    if setup_file.endswith(('.yml', '.yaml')):
        try:
            import yaml
        except ImportError:
            logger.error(
                "You provided a YAML setup file, but PyYAML was not found on "
                "your system."
            )
        loader = lambda f: yaml.load(f.read())
    elif setup_file.endswith('.json'):
        import json
        loader = json.load
    else:
        logger.error(
            "The setup file must be either in JSON or YAML."
        )
        return

    try:
        with open(setup_file) as f:
            return loader(f)
    except ValueError as e:
        logger.error("Error parsing '{}' : {}", setup_file, e)
    except Exception as e:
        logger.error(
            "Can't process setup file '{}' : {}", setup_file, e
        )


def main():
    global logger

    logger = Logger("Onitu client")

    parser = argparse.ArgumentParser("onitu")
    parser.add_argument(
        '--setup', default='setup.yml',
        help="A JSON file with Onitu's configuration (defaults to setup.json)"
    )
    parser.add_argument(
        '--log-uri', help="A ZMQ socket where all the logs will be sent"
    )
    parser.add_argument(
        '--debug', action='store_true', help="Enable debugging logging"
    )
    args = parser.parse_args()

    log_uri, dispatcher = get_logs_dispatcher(
        uri=args.log_uri, debug=args.debug
    )

    with ZeroMQHandler(log_uri, multi=True):
        logger.info('Started')
        setup = get_setup(args.setup)
        if setup is None:
            return
        driver_name = setup['service']['driver']
        driver = None

        try:
            drivers = get_available_drivers()
            if driver_name not in drivers:
                logger.error("Driver {} not found.", driver_name)
                return

            entry_point = drivers[driver_name]
            driver = entry_point.load()
            driver.plug.initialize(setup)
            driver.start()
        except ImportError as e:
            logger.error("Error importing driver {}: {}", driver_name, e)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            logger.info("Exiting...")
            if driver is not None:
                driver.plug.close()
            if dispatcher:
                dispatcher.stop()

if __name__ == '__main__':
    main()
