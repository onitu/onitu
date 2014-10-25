import os
import hashlib
import zmq

from threading import Thread, Event

from onitu.plug import Plug
from onitu.utils import _get_uri
from onitu.escalator.client import EscalatorClosed

plug = Plug()

files = set()


def read(metadata):
    return metadata.extra.get('content', '')


def write(metadata, content):
    files.add(metadata.filename)
    if type(content) == type(u''):
        content = content.encode()
    metadata.extra['content'] = content
    metadata.write()


def delete(metadata):
    if 'content' in metadata.extra:
        del metadata.extra['content']
        metadata.write()

    files.discard(metadata.filename)


def move(old_metadata, new_metadata):
    write(new_metadata, read(old_metadata))
    delete(old_metadata)


@plug.handler()
def get_chunk(metadata, offset, size):
    plug.logger.debug("get_chunk called")
    return read(metadata)[offset:offset + size]


@plug.handler()
def start_upload(metadata):
    plug.logger.debug("start_upload called")
    write(metadata, '')


@plug.handler()
def restart_upload(metadata, offset):
    plug.logger.debug("restart_upload called")


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    plug.logger.debug("upload_chunk called")

    content = read(metadata)
    content = content[:offset] + chunk + content[offset + len(chunk):]
    write(metadata, content)


@plug.handler()
def end_upload(metadata):
    plug.logger.debug("end_upload called")


@plug.handler()
def abort_upload(metadata):
    plug.logger.debug("abort_upload called")


@plug.handler()
def upload_file(metadata, content):
    plug.logger.debug("upload_file called")
    write(metadata, content)


@plug.handler()
def get_file(metadata):
    plug.logger.debug("get_file called")
    return read(metadata)


@plug.handler()
def delete_file(metadata):
    plug.logger.debug("delete_file called")
    delete(metadata)


@plug.handler()
def move_file(old_metadata, new_metadata):
    plug.logger.debug("move_file called")
    move(old_metadata, new_metadata)


@plug.handler()
def set_chunk_size(chunk_size):
    plug.logger.debug("set_chunk_size called")


@plug.handler()
def close():
    plug.logger.debug("close called")


class Watcher(Thread):
    def __init__(self, *args, **kwargs):
        super(Watcher, self).__init__(*args, **kwargs)
        self.context = zmq.Context.instance()

        self.ready = Event()

        self.pull_socket = None
        self.req_socket = None
        self.rep_socket = None

        self.handlers = {
            'write': self.handle_write,
            'generate': self.handle_generate,
            'exists': self.handle_exists,
            'delete': self.handle_delete,
            'move': self.handle_move,
            'rmdir': self.handle_rmdir,
            'checksum': self.handle_checksum,
        }

    def get_uri(self, name):
        return _get_uri(plug.session, ':tests:{}:{}'.format(plug.name, name))

    def run(self):
        try:
            self.pull_socket = self.context.socket(zmq.PULL)
            self.pull_socket.bind(self.get_uri('notifs'))

            self.req_socket = self.context.socket(zmq.REQ)
            self.req_socket.connect(self.get_uri('get_notifs'))

            self.rep_socket = self.context.socket(zmq.REP)
            self.rep_socket.bind(self.get_uri('requests'))

            self.notifs()
            self.ready.set()

            poller = zmq.Poller()
            poller.register(self.pull_socket, zmq.POLLIN)
            poller.register(self.rep_socket, zmq.POLLIN)

            while True:
                for socket, _ in poller.poll():
                    if socket == self.pull_socket:
                        self.pull_socket.recv()
                        self.notifs()
                    elif socket == self.rep_socket:
                        self.request()
        except (zmq.ZMQError, EscalatorClosed):
            pass
        finally:
            if self.rep_socket:
                self.rep_socket.close(linger=0)
            if self.pull_socket:
                self.pull_socket.close(linger=0)
            if self.req_socket:
                self.req_socket.close(linger=0)

    def notifs(self):
        self.req_socket.send(b'')
        for notif in self.req_socket.recv_json():
            self.handle(notif)

    def request(self):
        request = self.rep_socket.recv_json()
        response = self.handle(request)
        self.rep_socket.send_json({'response': response})

    def handle(self, event):
        handler = self.handlers[event['type']]
        return handler(*event['args'])

    def handle_write(self, filename, content):
        metadata = plug.get_metadata(filename)
        metadata.size = len(content)
        write(metadata, content)
        plug.update_file(metadata)

    def handle_generate(self, filename, size):
        content = os.urandom(size)
        self.handle_write(filename, content)

    def handle_exists(self, filename):
        return filename in files

    def handle_delete(self, filename):
        metadata = plug.get_metadata(filename)
        delete(metadata)
        plug.delete_file(metadata)

    def handle_move(self, source, target):
        if source not in files:
            # We are probably trying to move a dir
            for filename in list(files):
                if filename.startswith(source):
                    new_filename = filename.replace(source, target, 1)
                    self.handle_move(filename, new_filename)

        old_metadata = plug.get_metadata(source)
        plug.move_file(old_metadata, target)
        # We must get the metadata after notifying the Plug
        # as Plug.move_file will create the Metadata
        new_metadata = plug.get_metadata(target)
        move(old_metadata, new_metadata)

    def handle_rmdir(self, path):
        for filename in list(files):
            if filename.startswith(path):
                self.handle_delete(filename)

    def handle_checksum(self, filename):
        metadata = plug.get_metadata(filename)
        content = read(metadata)
        h = hashlib.md5()
        h.update(content)
        return h.hexdigest()


def start():
    watcher = Watcher()
    watcher.daemon = True
    watcher.start()
    watcher.ready.wait()
    plug.listen()
