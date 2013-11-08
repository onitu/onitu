"""
Script used to load all the entries listed in the file `entries.json`
and to start them with the running `circusd` instance.
"""

import sys

import redis
import simplejson

from circus.client import CircusClient
from logbook import Logger

logger = Logger("Loader")
circus = CircusClient()
redis = redis.Redis(unix_socket_path='redis/redis.sock')

if __name__ == '__main__':
    with open('entries.json') as f:
        entries = simplejson.load(f)

    for name, conf in entries.items():
        logger.info("Loading entry {}".format(name))

        if ':' in name:
            logger.error("Illegal character ':' in entry {}".format(name))
            continue

        script = 'onitu.drivers.{}'.format(conf['driver'])

        if 'options' in conf:
            redis.hmset('drivers:{}:options'.format(name), conf['options'])

        watcher = {
            'cmd': sys.executable,
            'args': ['-m', script, name],
            'name': name,
            'start': True
        }

        circus.send_message('add', **watcher)

    logger.info("Entries loaded")
