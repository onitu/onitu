import sys
import signal

import simplejson
import circus

from circus.exc import ConflictError
from zmq.eventloop import ioloop
from logbook import Logger
from tornado import gen

from utils import connect_to_redis


@gen.coroutine
def load_drivers(*args, **kwargs):
    redis = connect_to_redis()

    with open(entries_file) as f:
        entries = simplejson.load(f)

    for name, conf in entries.items():
        logger.info("Loading entry {}".format(name))

        if ':' in name:
            logger.error("Illegal character ':' in entry {}".format(name))
            continue

        script = 'onitu.drivers.{}'.format(conf['driver'])

        if 'options' in conf:
            redis.hmset('drivers:{}:options'.format(name), conf['options'])

        watcher = arbiter.add_watcher(
            name,
            sys.executable,
            args=['-m', script, name],
            copy_env=True,
        )

        loop.add_callback(start_watcher, watcher)

    logger.info("Entries loaded")


@gen.coroutine
def start_watcher(watcher):
    try:
        watcher.start()
    except ConflictError as e:
        loop.add_callback(start_watcher, watcher)
    except Exception as e:
        logger.warning("Can't start entry {} : {}", watcher.name, e)
        return


if __name__ == '__main__':
    if len(sys.argv) > 1:
        entries_file = sys.argv[1]
    else:
        entries_file = 'entries.json'

    logger = Logger("Onitu")

    ioloop.install()
    loop = ioloop.IOLoop.instance()

    sigint_handler = signal.getsignal(signal.SIGINT)
    sigterm_handler = signal.getsignal(signal.SIGTERM)

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
                'args': '-m onitu.referee',
                'copy_env': True,
            },
        ],
        proc_name="Onitu",
        loop=loop
    )

    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)

    try:
        future = arbiter.start()
        loop.add_future(future, load_drivers)
        arbiter.start_io_loop()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        arbiter.stop()
