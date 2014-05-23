from threading import Lock

import zmq

from onitu.escalator import protocol
from onitu.utils import get_escalator_uri
from .batch import WriteBatch


class Escalator(object):
    def __init__(self, session, create_db=False):
        super(Escalator, self).__init__()
        self.db_uid = None
        self.context = zmq.Context().instance()
        self.socket = self.context.socket(zmq.REQ)
        self.lock = Lock()
        self.socket.connect(get_escalator_uri(session))
        self.connect(session, create_db)

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

    def get(self, key, **kwargs):
        try:
            value = self._request(protocol.cmd.GET, key)[0]

            if kwargs.get('pack', True):
                value = protocol.msg.unpack_msg(value)
        except protocol.status.KeyNotFound:
            if 'default' in kwargs:
                value = kwargs['default']
            else:
                raise

        return value

    def exists(self, key):
        return self._request(protocol.cmd.EXISTS, key)[0]

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
                values = [(key, protocol.msg.unpack_msg(value))
                          for key, value in values]
            else:
                values = [protocol.msg.unpack_msg(value) for value in values]
        return values

    def write_batch(self, transaction=False):
        return WriteBatch(self, transaction)
