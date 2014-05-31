import os
import shutil
import random
import string
from subprocess import Popen

import pytest

from onitu.escalator.client import Escalator
from onitu.escalator import protocol
from onitu.utils import get_escalator_uri

server = None
client = None
directory = 'dbs_tests'


def setup_module(module):
    os.mkdir(directory)


def teardown_module(module):
    shutil.rmtree(directory)


def setup_function(function):
    global server, client
    session = 'tests-{}'.format(function.__name__)
    server = Popen(('python', '-m', 'onitu.escalator.server',
                    '--bind', get_escalator_uri(session),
                    '--working-dir', directory))
    client = Escalator(session, create_db=True)


def teardown_function(function):
    server.kill()


def test_exists():
    global client

    assert not client.exists('a')
    client.put('a', 'b')
    assert client.exists('a')


def test_get():
    global client

    with pytest.raises(protocol.status.KeyNotFound):
        client.get('a')
    assert client.get('a', default='ok') == 'ok'

    client.put('a', 731)
    assert client.get('a') == 731
    assert client.get('a', default='ok') == 731

    assert isinstance(client.get('a'), int)
    assert isinstance(client.get('a', pack=False), bytes)


def test_put():
    global client

    client.put('a', 'b')
    assert client.get('a') == 'b'

    client.put('a', b'b', pack=False)
    assert client.get('a', pack=False) == b'b'


def test_delete():
    global client

    client.put('a', 'b')
    assert client.exists('a')
    client.delete('a')
    assert not client.exists('a')


def test_range():
    global client

    db = [(''.join(random.choice(string.ascii_lowercase)
                   for _ in range(random.randint(5, 10))).encode(),
           random.randint(0, 100)) for _ in range(100)]
    db.sort()
    for key, value in db:
        client.put(key, value)

    assert client.range() == db
    assert client.range(start=db[0][0], stop=db[-1][0],
                        include_stop=True) == db

    assert client.range(start=db[20][0]) == db[20:]
    assert client.range(start=db[20][0], include_start=False) == db[21:]
    assert client.range(stop=db[60][0]) == db[:60]
    assert client.range(stop=db[60][0], include_stop=True) == db[:61]
    assert client.range(start=db[20][0], stop=db[60][0]) == db[20:60]
    assert client.range(start=db[20][0], stop=db[60][0],
                        include_start=False) == db[21:60]
    assert client.range(start=db[20][0], stop=db[60][0],
                        include_stop=True) == db[20:61]
    assert client.range(start=db[20][0], stop=db[60][0],
                        include_start=False, include_stop=True) == db[21:61]

    db_e = [(k, v) for k, v in db if k.decode().startswith('e')]
    assert client.range(prefix='e') == db_e

    assert client.range(reverse=True) == list(reversed(db))
    assert client.range(prefix='e', reverse=True) == list(reversed(db_e))

    assert client.range(include_value=False) == [k for k, _ in db]
    assert client.range(include_key=False) == [v for _, v in db]

    for _, value in client.range():
        assert isinstance(value, int)
    for _, value in client.range(pack=False):
        assert isinstance(value, bytes)


def test_batch():
    global client

    with client.write_batch() as wb:
        wb.put('a', 'b')
        assert not client.exists('a')
    assert client.exists('a')
    assert client.get('a') == 'b'

    with client.write_batch() as wb:
        wb.delete('a')
        assert client.exists('a')
    assert not client.exists('a')
