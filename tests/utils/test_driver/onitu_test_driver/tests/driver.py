import zmq

from onitu.utils import _get_uri

from tests.utils import driver


class Driver(driver.Driver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        super(Driver, self).__init__('test', *args, **options)
        self.context = zmq.Context.instance()
        self.req_socket = self.context.socket(zmq.REQ)
        self.notif_socket = self.context.socket(zmq.PUSH)

    def connect(self, session):
        self.session = session
        self.req_socket.connect(self.get_uri('requests'))
        self.notif_socket.connect(self.get_uri('notifs'))

    def close(self):
        self.req_socket.close(linger=0)
        self.notif_socket.close(linger=0)

    def get_uri(self, name):
        return _get_uri(self.session, u':tests:{}:{}'.format(self.name, name))

    def mkdir(self, subdirs):
        pass

    def rmdir(self, path):
        self._notif('rmdir', path)

    def write(self, filename, content):
        self._notif('write', filename, content)

    def generate(self, filename, size):
        self._notif('generate', filename, size)

    def exists(self, filename):
        return self._request('exists', filename)

    def unlink(self, filename):
        self._notif('delete', filename)

    def rename(self, source, target):
        self._notif('move', source, target)

    def checksum(self, filename):
        return self._request('checksum', filename)

    def _notif(self, name, *args):
        try:
            self.notif_socket.send_json({'type': name, 'args': args})
        except zmq.ZMQError:
            return

    def _request(self, name, *args):
        try:
            self.req_socket.send_json({'type': name, 'args': args})
            return self.req_socket.recv_json().get('response')
        except zmq.ZMQError:
            return


class DriverFeatures(driver.DriverFeatures):
    pass
