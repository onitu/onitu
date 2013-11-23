import sys

import simplejson
import circus

from redis import Redis
from zmq.eventloop import ioloop
from logbook import Logger


def load_drivers(arg):
    redis = Redis(unix_socket_path='redis/redis.sock')

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

        arbiter.add_watcher(
            name,
            sys.executable,
            args=['-m', script, name],
            copy_env=True
        )

    logger.info("Entries loaded")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        entries_file = sys.argv[1]
    else:
        entries_file = 'entries.json'

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
                'args': '-m onitu.referee',
                'copy_env': True,
            },
        ],
        proc_name="Onitu",
        loop=loop
    )

    try:
        future = arbiter.start()
        loop.add_future(future, load_drivers)
        arbiter.start_io_loop()
    except KeyboardInterrupt:
        pass
    finally:
        arbiter.stop()
