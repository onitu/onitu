import sys
import signal
import socket
import argparse
import string
import random

import simplejson
import circus

from circus.exc import ConflictError
from zmq.eventloop import ioloop
from logbook import Logger, INFO, DEBUG, NullHandler, NestedSetup
from logbook.queues import ZeroMQHandler, ZeroMQSubscriber
from logbook.more import ColorizedStderrHandler
from tornado import gen

from .utils import connect_to_redis


@gen.coroutine
def load_drivers(*args, **kwargs):
    logger.info("Loading setup...")

    redis = connect_to_redis()
    redis.delete('ports')
    redis.delete('entries')
    redis.delete('session')
    redis.delete('events')

    try:
        with open(setup_file) as f:
            setup = simplejson.load(f)
    except simplejson.JSONDecodeError as e:
        logger.error("Error parsing '{}' : {}", setup_file, e)
        loop.stop()
    except Exception as e:
        logger.error(
            "Can't process setup file '{}' : {}", setup_file, e
        )
        loop.stop()

    if not 'name' in setup:
        # If the current setup does not have a name, we create a random one
        setup['name'] = ''.join(
            random.sample(string.letters + string.digits, 10)
        )

    if not 'entries' in setup:
        logger.warn("No entries specified in '{}'", setup_file)
        loop.stop()

    entries = setup['entries']

    redis.sadd('entries', *entries.keys())

    for name, conf in entries.items():
        logger.debug("Loading entry {}", name)

        if ':' in name:
            logger.error("Illegal character ':' in entry {}", name)
            continue

        script = 'onitu.drivers.{}'.format(conf['driver'])

        if 'options' in conf:
            redis.hmset('drivers:{}:options'.format(name), conf['options'])

        watcher = arbiter.add_watcher(
            name,
            sys.executable,
            args=['-m', script, name, log_uri],
            copy_env=True,
        )

        loop.add_callback(start_watcher, watcher)

    logger.debug("Entries loaded")


@gen.coroutine
def start_watcher(watcher):
    try:
        watcher.start()
    except ConflictError as e:
        loop.add_callback(start_watcher, watcher)
    except Exception as e:
        logger.warning("Can't start entry {} : {}", watcher.name, e)
        return


def get_logs_dispatcher(uri=None, debug=False):
    handlers = []

    if not debug:
        handlers.append(NullHandler(level=DEBUG))

    handlers.append(ColorizedStderrHandler(level=INFO))

    if not uri:
        # Find an open port.
        # This is a race condition as the port could be used between
        # the check and its binding. However, this is probably one of the
        # best solution without patching Logbook.
        tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmpsock.bind(('localhost', 0))
        uri = 'tcp://{}:{}'.format(*tmpsock.getsockname())
        tmpsock.close()

    subscriber = ZeroMQSubscriber(uri, multi=True)
    return uri, subscriber.dispatch_in_background(setup=NestedSetup(handlers))


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

        ioloop.install()
        loop = ioloop.IOLoop.instance()

        arbiter = circus.get_arbiter(
            [
                {
                    'cmd': 'redis-server',
                    'args': 'redis/redis.conf',
                    'copy_env': True,
                    'priority': 1,
                },
                {
                    'cmd': sys.executable,
                    'args': ['-m', 'onitu.referee', log_uri],
                    'copy_env': True,
                },
            ],
            proc_name="Onitu",
            loop=loop
        )

        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
            signal.signal(s, lambda *args, **kwargs: loop.stop())

        try:
            future = arbiter.start()
            loop.add_future(future, load_drivers)
            arbiter.start_io_loop()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            arbiter.stop()
            if dispatcher:
                dispatcher.stop()
