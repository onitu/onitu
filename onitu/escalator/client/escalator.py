from threading import Lock

import zmq

from onitu.escalator import protocol
from .batch import WriteBatch


class Escalator(object):
    def __init__(self, db_name='default',
                 server='localhost', port=4224, transport='tcp', addr=None,
                 create_db=False):
        super(Escalator, self).__init__()
        self.db_uid = None
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.lock = Lock()
        if addr is None:
            addr = '{}://{}:{}'.format(transport, server, port)
        self.socket.connect(addr)
        if db_name is not None:
            self.connect(db_name, create_db)

    def _request(self, cmd, *args):
        with self.lock:
            self.socket.send(protocol.msg.format_request(cmd,
                                                         self.db_uid,
                                                         *args))
            return protocol.msg.extract_response(self.socket.recv())

    def _request_multi(self, cmd, *args):
        with self.lock:
            self.socket.send(protocol.msg.format_request(cmd,
                                                         self.db_uid,
                                                         *args))
            protocol.msg.extract_response(self.socket.recv())
            l = []
            while self.socket.get(zmq.RCVMORE):
                l.append(protocol.msg.unpack_msg(self.socket.recv()))
            return l

    def create(self, name):
        self._request(protocol.cmd.CREATE, name)

    def connect(self, name, create=False):
        self.db_uid = self._request(protocol.cmd.CONNECT, name, create)[0]

    def get(self, key, pack=True):
        value = self._request(protocol.cmd.GET, key)[0]
        if pack:
            value = protocol.msg.unpack_msg(value)
        return value

    def exists(self, key):
        return self._request(protocol.cmd.EXISTS, key)[0]

    def get_default(self, key, default=None, pack=True):
        try:
            return self.get(key, pack=pack)
        except protocol.status.KeyNotFound:
            return default

    def put(self, key, value, pack=True):
        if pack:
            value = protocol.msg.pack_arg(value)
        self._request(protocol.cmd.PUT, key, value)

    def delete(self, key):
        self._request(protocol.cmd.DELETE, key)

    def range(self,
              prefix=None, start=None, stop=None,
              include_start=True, include_stop=False,
              include_key=True, include_value=True,
              reverse=False, pack=True):
        values = self._request_multi(protocol.cmd.RANGE,
                                     prefix, start, stop,
                                     include_start, include_stop,
                                     include_key, include_value,
                                     reverse)
        if pack and include_value:
            if include_key:
                values = [[key, protocol.msg.unpack_msg(value)]
                          for key, value in values]
            else:
                values = [protocol.msg.unpack_msg(value) for value in values]
        return values

    def write_batch(self, transaction=False):
        return WriteBatch(self, transaction)


if __name__ == '__main__':
    from multiprocessing.pool import ThreadPool

    k = 10000

    def foo(w):
        w += 1
        client = Escalator()
        for i in range(k):
            client.put(str(w * k + i), str(i))

        for i in range(k):
            print(client.get(str(w * k + i)))

    pool = ThreadPool()
    pool.map(foo, range(5))
