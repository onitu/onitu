#!/usr/bin/env python

import os
import argparse

from logbook import Logger
from logbook.queues import ZeroMQHandler
from onitu.utils import get_available_drivers
from onitu.utils import get_logs_dispatcher, get_setup

os.environ['ONITU_CLIENT'] = 'client'

logger = None


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
        '--no-auth',
        help="Disable authentication",
        dest='auth',
        action='store_false'
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
        setup = get_setup(args.setup, logger)
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
            driver.plug.initialize(setup, args.auth)
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
