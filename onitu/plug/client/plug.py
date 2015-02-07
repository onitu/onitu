import uuid
import threading

import zmq
import zmq.auth

from logbook import Logger

from onitu.utils import b, pack_obj, pack_msg, unpack_msg
from .escalator import Escalator
from .exceptions import _HandlerException
from .metadata import MetadataWrapper, metadata_serializer
from .folder import FolderWrapper, folder_serializer
from .heartbeat import HeartBeat


class PlugProxy(object):
    def __init__(self):
        self.unserializers = {
            'metadata': self.metadata_unserialize,
            'folder': self.folder_unserialize
        }
        self._handlers = {}
        self.context = zmq.Context.instance()
        self.logger = None
        self.requests_socket = None
        self.handlers_socket = None
        self.heartbeat_socket = None
        self.requests_lock = None
        self.options = {}
        self.service_db = Escalator(self)
        self.serv_identity = None
        self.heartbeat = None
        self._stop = threading.Event()

    def initialize(self, setup, auth=True, keys=()):
        identity = b(uuid.uuid4().hex)

        self.name = setup['name']
        self.logger = Logger(self.name)

        self.requests_lock = threading.Lock()

        self.requests_socket = self.context.socket(zmq.REQ)
        self.requests_socket.identity = identity
        self.handlers_socket = self.context.socket(zmq.REQ)
        self.handlers_socket.identity = identity

        if auth:
            server_key, client_key = keys
            pub_key, priv_key = zmq.auth.load_certificate(client_key)
            server_key, _ = zmq.auth.load_certificate(server_key)
            self.requests_socket.curve_publickey = pub_key
            self.requests_socket.curve_secretkey = priv_key
            self.requests_socket.curve_serverkey = server_key
            self.handlers_socket.curve_publickey = pub_key
            self.handlers_socket.curve_secretkey = priv_key
            self.handlers_socket.curve_serverkey = server_key

        self.requests_socket.connect(setup['requests_addr'])
        self.handlers_socket.connect(setup['handlers_addr'])

        conf = setup['service']
        msg = b'start' + pack_msg(self.name, conf)
        self.requests_socket.send_multipart((b'', msg))
        self.handlers_socket.send_multipart((b'', b'ready'))
        self.serv_identity, _ = self.requests_socket.recv_multipart()

        self.logger.info('Started')
        self.logger.info('Server identity - {}', self.serv_identity)

        self.options.update(conf.get('options', {}))

        self.folders = FolderWrapper.get_folders(self)

        self.heartbeat = HeartBeat(identity + b'client', self.close, setup['hb_addr'])
        self.heartbeat.start()

    def close(self):
        self.logger.info('Disconnecting')
        self._stop.set()
        if self.heartbeat:
            self.heartbeat.stop()
        if self.serv_identity is not None:
            try:
                with self.requests_lock:
                    self.requests_socket.send_multipart((b'', b'stop'))
            except zmq.ZMQError:
                pass
            self.requests_socket.close()
            self.handlers_socket.close()

    def metadata_unserialize(self, m):
        return MetadataWrapper(self, *m)

    def folder_unserialize(self, f):
        return FolderWrapper(*f)

    def listen(self):
        poller = zmq.Poller()
        poller.register(self.handlers_socket, zmq.POLLIN)
        while not self._stop.is_set():
            try:
                p = dict(poller.poll(1000))
            except zmq.ZMQError:
                return
            if p.get(self.handlers_socket) != zmq.POLLIN:
                continue
            _, msg = self.handlers_socket.recv_multipart()
            msg = unpack_msg(msg)
            self.logger.debug('handler {}', msg)
            cmd = self._handlers.get(msg[0], None)
            args = msg[1:]
            args = [self.unserializers.get(ser, lambda x: x)(arg)
                    for (ser, arg) in args]
            try:
                status = 0
                if cmd:
                    resp = cmd(*args)
                else:
                    resp = None
            except _HandlerException as e:
                status = e.status_code
                resp = e.args
            resp = status, resp
            self.handlers_socket.send_multipart((self.serv_identity,
                                                 pack_obj(resp)))

    def request(self, msg):
        with self.requests_lock:
            self.requests_socket.send_multipart((self.serv_identity, msg))
            _, resp = self.requests_socket.recv_multipart()
            return resp

    def handler(self, name=None):
        def decorator(h):
            self._handlers[name if name is not None else h.__name__] = h
            return h
        return decorator

    def get_metadata(self, filename, folder):
        self.logger.debug('get_metadata {} {}', filename, folder)
        m = self.request(pack_msg('get_metadata', filename,
                                  folder_serializer(folder)))
        metadata = self.metadata_unserialize(unpack_msg(m))
        return metadata

    def update_file(self, metadata):
        self.logger.debug('update_file {}', metadata.filename)
        m = metadata_serializer(metadata)
        self.request(pack_msg('update_file', m))

    def delete_file(self, metadata):
        self.logger.debug('delete_file {}', metadata.filename)
        m = metadata_serializer(metadata)
        self.request(pack_msg('delete_file', m))

    def move_file(self, old_metadata, new_filename):
        self.logger.debug('move_file {} to {}',
                          old_metadata.filename, new_filename)
        old_m = metadata_serializer(old_metadata)
        self.request(pack_msg('move_file', old_m, new_filename))

    @property
    def folders_to_watch(self):
        return tuple(folder for folder in self.folders.values()
                     if not any(f.contains(folder.path)
                                for f in self.folders.values()))

    def get_folder(self, filename):
        folder = None
        for candidate in self.folders.values():
            if candidate.contains(filename):
                if folder:
                    if folder.contains(candidate.path):
                        folder = candidate
                else:
                    folder = candidate
        return folder

    def list(self, folder, path=''):
        self.logger.debug('list {} in {}', folder, path)
        r = self.request(pack_msg('list', folder_serializer(folder), path))
        return unpack_msg(r)

    def exists(self, folder, path):
        self.logger.debug('exists {} in {}', folder, path)
        r = self.request(pack_msg('exists', folder_serializer(folder), path))
        return unpack_msg(r)
