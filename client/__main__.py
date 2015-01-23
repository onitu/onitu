#!/usr/bin/env python

import os
import argparse
import os.path

from logbook import Logger
from logbook.queues import ZeroMQHandler
from onitu.utils import get_available_drivers
from onitu.utils import get_logs_dispatcher, get_logs_uri, get_setup, u
from onitu.utils import DEFAULT_CONFIG_DIR

os.environ['ONITU_CLIENT'] = 'client'

logger = None


def main():
    global logger

    logger = Logger("Onitu client")

    parser = argparse.ArgumentParser("onitu")
    parser.add_argument(
        '--setup', default=None, type=u,
        help="A YAML or JSON file with Onitu's configuration "
             "(defaults to the setup.yml file in your config directory)",
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
        '--server-key',
        help="Server's public key file "
             "(defaults to keys/server.key in config directory)",
        default=None
    )
    parser.add_argument(
        '--client-key',
        help="Client's secret key file"
             "(defaults to keys/client.key_secret in config directory)",
        default=None
    )
    parser.add_argument(
        '--debug', action='store_true', help="Enable debugging logging"
    )
    parser.add_argument(
        '--config-dir', default=DEFAULT_CONFIG_DIR, type=u,
        help="The directory where Onitu store its informations and gets the "
             "default setup. Defaults to {}".format(DEFAULT_CONFIG_DIR)
    )
    args = parser.parse_args()

    log_uri = args.log_uri
    if not log_uri:
        log_uri = get_logs_uri('client')

    dispatcher = get_logs_dispatcher(
        args.config_dir, uri=log_uri, debug=args.debug
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
            server_key = args.server_key
            if server_key is None:
                server_key = os.path.join(args.config_dir, "keys/server.key")
            client_key = args.client_key
            if client_key is None:
                client_key = os.path.join(args.config_dir,
                                          "keys/client.key_secret")
            driver.plug.initialize(setup, args.auth,
                                   (server_key, client_key))
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
