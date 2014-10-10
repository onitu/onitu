import zmq

from onitu.escalator import protocol


class WriteBatch(object):
    def __init__(self, db, transaction):
        self.db = db
        self.transaction = transaction
        self.requests = []

    def write(self):
        self.requests.insert(0, protocol.msg.format_request(protocol.cmd.BATCH,
                                                            self.db.db_uid,
                                                            self.transaction))
        with self.db.lock:
            try:
                self.db.socket.send_multipart(self.requests)
                protocol.msg.extract_response(self.db.socket.recv())
            except zmq.ZMQError:
                self.db.socket.close()
                raise protocol.status.EscalatorClosed()

        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if not self.transaction or not type:
            self.write()

    def _request(self, cmd, *args):
        self.requests.append(protocol.msg.format_request(cmd, None, *args))

    def put(self, key, value, pack=True):
        if pack:
            value = protocol.msg.pack_arg(value)
        self._request(protocol.cmd.PUT, key, value)

    def delete(self, key):
        self._request(protocol.cmd.DELETE, key)
