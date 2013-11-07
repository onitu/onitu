import sys
import time

import redis
import simplejson

from circus.client import CircusClient
from logbook import Logger

logger = Logger("Loader")
circus = CircusClient()
redis = redis.Redis(unix_socket_path='redis/redis.sock')


def load_entry(name, conf):
    logger.info("Loading entry {}".format(name))

    if ':' in name:
        logger.error("Illegal character ':' in entry {}".format(name))
        return

    script = 'onitu.drivers.{}'.format(conf['driver'])

    if 'options' in conf:
        redis.hmset('drivers:{}:options'.format(name), conf['options'])

    watcher = {
        'cmd': sys.executable,
        'args': ['-m', script, name],
        'name': name,
        'start': True
    }

    return circus.send_message('add', **watcher)


if __name__ == '__main__':
    with open('entries.json') as f:
        for name, conf in simplejson.load(f).items():
            load_entry(name, conf)

    logger.info("Entries loaded")
