"""
This module provides a set of classes and functions useful in several
parts of Onitu.
"""

import time
import functools

import redis


class Redis(redis.Redis):
    """This is a simple wrapper around the :class:`redis.Redis` object
    from the redis-py library.

    It adds a :attr:`session` attribute, which can be used as a
    standard :class:`redis.Redis` object, but will prefix every key
    by the current session-key.

    This session key is used by Onitu to separate the different
    sessions in the database. As Redis only handles a small finite
    number of databases, we use a single database, but prefix all the
    keys.

    The session attribute should always be used.
    """

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
    """This class return a new :class:`.Redis` object, ready to
    receive requests, with the session enabled.
    It blocks until the connection is made.

    You can pass extra arguments to the :class:`.Redis` class by
    giving them to this function.
    """
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
