import time

import redis


def connect_to_redis(*args, **kwargs):
    client = redis.Redis(*args, unix_socket_path='redis/redis.sock', **kwargs)

    while True:
        try:
            assert client.ping()
        except (redis.exceptions.ConnectionError, AssertionError):
            time.sleep(0.5)
        else:
            return client
