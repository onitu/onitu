from collections import namedtuple

import zmq

Relay = namedtuple('Relay', ['src', 'dest', 'name'])


class Interface(object):
    def __init__(self):
        ctx = zmq.Context.instance()
        self.req = ctx.socket(zmq.ROUTER)
        self.rep = ctx.socket(zmq.ROUTER)

    def bind(self, req_uri, rep_uri):
        self.req_port = self._bind_socket(self.req, req_uri)
        self.rep_port = self._bind_socket(self.rep, rep_uri)

    @staticmethod
    def _bind_socket(socket, uri):
        _, _, netloc = uri.partition('://')
        _, _, port = netloc.partition(':')
        if not port:
            port = socket.bind_to_random_port(uri)
        else:
            port = int(port)
            socket.bind(uri)
        return port


class Message(namedtuple('Message', ['src_id', 'dest_id', 'content'])):
    @classmethod
    def from_tuple(cls, t):
        src_id, _, dest_id, content = t
        return cls(src_id, dest_id, content)

    def to_tuple(self):
        return (self.src_id, b'', self.dest_id, self.content)

    def reverse(self):
        return type(self)(self.dest_id, self.src_id, self.content)


class Broker(object):
    handlers = {}

    def __init__(self):
        self.frontend = Interface()
        self.backend = Interface()

        self._poller = zmq.Poller()
        self._relays_by_name = {}
        self._relays_by_src = {}

        self.relay(self.frontend.req, 'f-req', self.backend.rep, 'b-rep')
        self.relay(self.backend.req, 'b-req', self.frontend.rep, 'f-rep')

    def _add_relay(self, relay):
        self._relays_by_name[relay.name] = relay
        self._relays_by_src[relay.src] = relay
        self._poller.register(relay.src, zmq.POLLIN)

    def relay(self, src, src_name, dest=None, dest_name=None):
        self._add_relay(Relay(src, dest, src_name))
        if dest is not None:
            self._add_relay(Relay(dest, src, dest_name))

    @classmethod
    def handle(cls, name):
        def decorator(f):
            cls.handlers[name] = f
            return f
        return decorator

    def bind(self, frontend_req_uri, frontend_rep_uri,
             backend_req_uri, backend_rep_uri):
        self.frontend.bind(frontend_req_uri, frontend_rep_uri)
        self.backend.bind(backend_req_uri, backend_rep_uri)

    @classmethod
    def get_handler(cls, name):
        h = cls.handlers.get(name)
        if h is not None:
            return h
        for base in cls.__bases__:
            try:
                h = base.get_handler(name)
                if h is not None:
                    return h
            except AttributeError:
                pass
        return cls._handle_msg

    def _handle_msg(self, relay, msg):
        if relay.dest:
            relay.dest.send_multipart(msg.reverse().to_tuple())

    def poll(self):
        for socket, t in self._poller.poll():
            if t == zmq.POLLIN:
                msg = Message.from_tuple(socket.recv_multipart())
                relay = self._relays_by_src[socket]
                handler = self.get_handler(relay.name)
                handler(self, relay, msg)


@Broker.handle('f-rep')
@Broker.handle('b-rep')
def broker_handle_rep(broker, relay, msg):
    if not msg.dest_id and msg.content == b'ready':
        return
    return broker._handle_msg(relay, msg)
