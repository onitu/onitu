import zmq

from threading import Thread

from tests.utils.testdriver import TestDriver

from onitu.utils import _get_uri


class NotifThread(Thread):
    def __init__(self, context, uri, *args, **kwargs):
        super(NotifThread, self).__init__(*args, **kwargs)

        self.context = context
        self.uri = uri

        self.notifs = []

    def run(self):
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(self.uri)

        try:
            while True:
                self.socket.recv()
                self.socket.send_json(list(self.notifs))
                self.notifs = []
        except zmq.ZMQError:
            return
        finally:
            self.socket.close()


class Driver(TestDriver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        super(Driver, self).__init__('test', *args, **options)
        self.context = zmq.Context()

    @property
    def root(self):
        return self.options['root']

    def connect(self, session):
        self.session = session

        self.push_socket = self.context.socket(zmq.PUSH)
        self.push_socket.connect(self._get_uri('notifs'))

        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.connect(self._get_uri('requests'))

        uri = self._get_uri('get_notifs')
        self.notif_thread = NotifThread(self.context, uri)
        self.notif_thread.start()

    def _get_uri(self, name):
        return _get_uri(self.session, ':tests:{}:{}'.format(self.name, name))

    def close(self):
        self.push_socket.close(linger=0)
        self.req_socket.close(linger=0)
        self.context.term()

    def mkdir(self, subdirs):
        pass

    def rmdir(self, path):
        self._request('rmdir', path)

    def write(self, filename, content):
        self._notif('write', filename, content)

    def generate(self, filename, size):
        self._notif('generate', filename, size)

    def exists(self, filename):
        return self._request('exists', filename)

    def unlink(self, filename):
        self._notif('delete', filename)

    def rename(self, source, target):
        self._request('move', source, target)

    def checksum(self, filename):
        return self._request('checksum', filename)

    def _request(self, name, *args):
        try:
            self.req_socket.send_json({'type': name, 'args': args})
            return self.req_socket.recv_json().get('response')
        except zmq.ZMQError:
            return

    def _notif(self, name, *args):
        try:
            self.notif_thread.notifs.append({'type': name, 'args': args})
            if len(self.notif_thread.notifs) == 1:
                self.push_socket.send(b'')
        except zmq.ZMQError:
            return
