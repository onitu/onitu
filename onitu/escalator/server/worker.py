from threading import Thread

import zmq

from onitu.escalator import protocol
from onitu.utils import u


class Multipart(list):
    pass


class Worker(Thread):

    def __init__(self, databases, uri, logger, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)

        self.context = zmq.Context.instance()
        self.uri = uri
        self.logger = logger
        self.socket = None

        self.databases = databases

        self.db_commands = {
            protocol.cmd.CREATE: self.create,
            protocol.cmd.CONNECT: self.connect
        }

        self.commands = {
            protocol.cmd.GET: self.get,
            protocol.cmd.EXISTS: self.exists,
            protocol.cmd.PUT: self.put,
            protocol.cmd.DELETE: self.delete,
            protocol.cmd.RANGE: self.range,
            protocol.cmd.BATCH: self.batch
        }

        self.batch_commands = {
            protocol.cmd.PUT: self.put,
            protocol.cmd.DELETE: self.delete
        }

    def run(self):
        self.socket = self.context.socket(zmq.REP)
        self.socket.connect(self.uri)

        try:
            while True:
                cmd, uid, args = protocol.msg.extract_request(
                    self.socket.recv()
                )
                try:
                    if cmd in self.db_commands:
                        db = None
                    else:
                        db = self.databases.get(uid)
                except Exception:
                    resp = protocol.msg.format_response(
                        uid, status=protocol.status.NO_DB)
                else:
                    if db:
                        resp = self.handle_cmd(db, self.commands, cmd, args)
                    else:
                        resp = self.handle_cmd(
                            None, self.db_commands, cmd, args
                        )
                if isinstance(resp, Multipart):
                    self.socket.send_multipart(resp)
                else:
                    self.socket.send(resp)
        except zmq.ZMQError:
            pass
        except RuntimeError:
            pass
        finally:
            self.socket.close(linger=0)

    def handle_cmd(self, db, commands, cmd, args):
        cb = commands.get(cmd)
        if cb:
            try:
                resp = cb(db, *args) if db is not None else cb(*args)
            except TypeError as e:
                self.logger.warning("Invalid arguments: {}", e)
                resp = protocol.msg.format_response(
                    cmd, status=protocol.status.INVALID_ARGS)
        else:
            self.logger.warning("Command not found: {}", cmd)
            resp = protocol.msg.format_response(
                cmd, status=protocol.status.CMD_NOT_FOUND)
        return resp

    def create(self, name):
        return self.connect(name, None, True)

    def connect(self, name, prefix, create):
        name = u(name)
        try:
            uid = self.databases.connect(name, prefix, create)
            resp = protocol.msg.format_response(uid, status=protocol.status.OK)
        except self.databases.NotExistError as e:
            self.logger.warning("No such database: {}", name)
            resp = protocol.msg.format_response(
                name, status=protocol.status.DB_NOT_FOUND)
        except Exception as e:
            self.logger.warning("Error opening database '{}': {}", name, e)
            resp = protocol.msg.format_response(
                name, status=protocol.status.DB_ERROR)
        return resp

    def get(self, db, key):
        value = db.get(key)
        if value is None:
            return protocol.msg.format_response(
                key, status=protocol.status.KEY_NOT_FOUND)
        return protocol.msg.format_response(value)

    def exists(self, db, key):
        value = db.get(key)
        return protocol.msg.format_response(value is not None)

    def put(self, db, key, value):
        db.put(key, value)
        return protocol.msg.format_response()

    def delete(self, db, key):
        db.delete(key)
        return protocol.msg.format_response()

    def range(self, db,
              prefix, start, stop,
              include_start, include_stop,
              include_key, include_value,
              reverse):
        values = Multipart(protocol.msg.pack_arg(v) for v in
                           db.iterator(prefix=prefix,
                                       start=start,
                                       stop=stop,
                                       include_start=include_start,
                                       include_stop=include_stop,
                                       include_key=include_key,
                                       include_value=include_value,
                                       reverse=reverse))
        values.insert(0, protocol.msg.format_response())
        return values

    def batch(self, db, transaction):
        with db.write_batch(transaction=transaction) as wb:
            while self.socket.get(zmq.RCVMORE):
                cmd, _, args = protocol.msg.extract_request(self.socket.recv())
                self.handle_cmd(wb, self.batch_commands, cmd, args)
        return protocol.msg.format_response()
