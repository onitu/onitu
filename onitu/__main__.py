"""
This module starts Onitu. It does the following:

- parse the command line options
- configure the logger
- parse the setup
- clean the database
- launch the different elements using the Circus library
"""

import os
import sys
import argparse

import circus

from itertools import chain

from logbook import Logger, INFO, DEBUG, NestedSetup
from logbook import NullHandler, RotatingFileHandler
from logbook.queues import ZeroMQHandler, ZeroMQSubscriber
from logbook.more import ColorizedStderrHandler
from tornado import gen


from .escalator.client import Escalator
from .utils import get_logs_uri, IS_WINDOWS, get_stats_endpoint
from .utils import get_circusctl_endpoint, get_pubsub_endpoint, u

# Time given to each process (Drivers, Referee, API...) to
# exit before being killed. This avoid any hang during
# shutdown
GRACEFUL_TIMEOUT = 1.


# The default directory where Onitu store its informations
if IS_WINDOWS:
    DEFAULT_CONFIG_DIR = os.path.join(
        os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'onitu'
    )
elif sys.platform == 'darwin':
    DEFAULT_CONFIG_DIR = os.path.join(
        os.path.expanduser('~/Library/Application Support'), 'onitu'
    )
else:
    DEFAULT_CONFIG_DIR = os.path.join(
        os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
        'onitu'
    )


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

    with escalator.write_batch() as batch:
        # TODO: handle folders from previous run
        for name, options in setup.get('folders', {}).items():
            if options is None:
                options = {}

            batch.put(u'folder:{}'.format(name), options)

    services = setup.get('services', {})
    escalator.put('services', list(services.keys()))

    yield start_watcher("Referee", 'onitu.referee')

    for service, conf in services.items():
        yield load_service(escalator, service, conf)

    logger.debug("Services loaded")

    yield start_watcher("Rest API", 'onitu.api')


@gen.coroutine
def load_service(escalator, service, conf):
    logger.debug("Loading service {}", service)

    if ':' in service:
        logger.error("Illegal character ':' in service {}", service)
        return

    if 'driver' not in conf:
        logger.error("Service {} does not specify a driver.", service)
        return

    escalator.put(u'service:{}:driver'.format(service), conf['driver'])
    escalator.put(u'service:{}:root'.format(service), conf.get('root', ''))

    escalator.put(
        u'service:{}:options'.format(service), conf.get('options', {})
    )

    folders = conf.get('folders', {})
    escalator.put(u'service:{}:folders'.format(service), list(folders.keys()))

    for name, options in folders.items():
        if not escalator.exists(u'folder:{}'.format(name)):
            logger.warning(
                'Unknown folder {} in service {}', name, service
            )
            continue

        if type(options) != dict:
            path = options
            options = {}
        else:
            path = options.pop('path', '/')

        escalator.put(
            u'service:{}:folder:{}:path'.format(service, name), path
        )
        escalator.put(
            u'service:{}:folder:{}:options'.format(service, name), options
        )

    yield start_watcher(service, 'onitu.service', conf['driver'], service)


@gen.coroutine
def start_watcher(name, module, *args, **kwargs):
    watcher = arbiter.add_watcher(
        name,
        sys.executable,
        args=list(chain(['-m', module, session], args)),
        copy_env=True,
        graceful_timeout=GRACEFUL_TIMEOUT,
        **kwargs
    )
    yield watcher.start()


def get_logs_dispatcher(config_dir, uri, debug=False):
    """Configure the dispatcher that will print the logs received
    on the ZeroMQ channel.
    """
    handlers = []

    if not debug:
        handlers.append(NullHandler(level=DEBUG))

    handlers.append(RotatingFileHandler(
        os.path.join(config_dir, 'onitu.log'),
        level=INFO,
        max_size=1048576,  # 1 Mb
        bubble=True
    ))

    handlers.append(ColorizedStderrHandler(level=INFO, bubble=True))
    subscriber = ZeroMQSubscriber(uri, multi=True)
    return subscriber.dispatch_in_background(setup=NestedSetup(handlers))


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
    except Exception as e:
        logger.error(
            "Error parsing '{}' : {}", setup_file, e
        )


def main():
    global session, setup, logger, arbiter

    logger = Logger("Onitu")

    parser = argparse.ArgumentParser("onitu")
    parser.add_argument(
        '--setup', type=u,
        help="A YAML or JSON file with Onitu's configuration "
             "(defaults to the setup.yml file in your config directory)"
    )
    parser.add_argument(
        '--no-dispatcher', action='store_true',
        help="Use this flag to disable the log dispatcher"
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

    config_dir = args.config_dir

    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    if not args.setup:
        setup_file = os.path.join(config_dir, 'setup.yml')

        if not os.path.exists(setup_file):
            logger.error("You must create a setup.yml file in {}".format(
                config_dir
            ))
            return 1
    else:
        setup_file = args.setup

    setup = get_setup(setup_file)
    if not setup:
        return 1

    session = setup.get('name')

    if not session:
        logger.error("Your setup must have a name.")
        return 1

    logs_uri = get_logs_uri(session)
    if not args.no_dispatcher:
        dispatcher = get_logs_dispatcher(
            config_dir, logs_uri, debug=args.debug
        )
    else:
        dispatcher = None

    with ZeroMQHandler(logs_uri, multi=True):
        try:
            arbiter = circus.get_arbiter(
                (
                    {
                        'name': 'Escalator',
                        'cmd': sys.executable,
                        'args': (
                            '-m', 'onitu.escalator.server', session, config_dir
                        ),
                        'copy_env': True,
                        'graceful_timeout': GRACEFUL_TIMEOUT
                    },
                ),
                proc_name="Onitu",
                controller=get_circusctl_endpoint(session),
                pubsub_endpoint=get_pubsub_endpoint(session),
                stats_endpoint=get_stats_endpoint(session),
                loglevel='WARNING',
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
