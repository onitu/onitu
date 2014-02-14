import time
import functools

import redis


class Redis(redis.Redis):

    class RedisSession(object):

        def __init__(self, redis, prefix=''):
            self.prefix = prefix
            self.redis = redis

        def start(self, prefix):
            self.prefix = prefix + ':' if prefix else ''

        def __getattr__(self, name):
            try:
                return self._wrap(getattr(self.redis, name))
            except AttributeError:
                return super(Redis.RedisSession, self).__getattr__(name)

        def _wrap(self, method):
            @functools.wraps(method)
            def wrapper(*args, **kwargs):
                if len(args) and isinstance(args[0], str):
                    args = (self.prefix + args[0],) + args[1:]
                return method(*args, **kwargs)

            return wrapper

    def __init__(self, *args, **kwargs):
        super(Redis, self).__init__(*args, **kwargs)
        self.session = self.RedisSession(self)


def connect_to_redis(*args, **kwargs):
    client = Redis(
        *args,
        unix_socket_path='redis/redis.sock',
        decode_responses=True,
        **kwargs
    )

    while True:
        try:
            assert client.ping()
        except (redis.exceptions.ConnectionError, AssertionError):
            time.sleep(0.05)
        else:
            client.session.start(client.get('session'))
            return client
