import zmq


class Broker(object):

    class Interface(object):
        def __init__(self):
            ctx = zmq.Context.instance()
            self.reqs = ctx.socket(zmq.ROUTER)
            self.reps = ctx.socket(zmq.ROUTER)

        def bind(self, protocol='tcp', addr='*', ports=(None, None)):
            self.reqs_port = self._bind_socket(self.reqs,
                                               protocol,
                                               addr,
                                               ports[0])
            self.reps_port = self._bind_socket(self.reps,
                                               protocol,
                                               addr,
                                               ports[1])

        @staticmethod
        def _bind_socket(socket, protocol, addr, port):
            if port is None:
                port = socket.bind_to_random_port('{}://{}'.format(protocol,
                                                                   addr))
            else:
                socket.bind('{}://{}:{}'.format(protocol, addr, port))
            return port

    def __init__(self, frontend_ports, backend_ports=(None, None),
                 frontend_addr='*', backend_addr='*',
                 frontend_protocol='tcp', backend_protocol='tcp'):
        self.frontend = self.Interface()
        self.backend = self.Interface()
        self._before_bind()
        self.frontend.bind(frontend_protocol,
                           frontend_addr,
                           frontend_ports)
        self.backend.bind(backend_protocol,
                          backend_addr,
                          backend_ports)

        self.poller = zmq.Poller()
        self.poller.register(self.frontend.reqs, zmq.POLLIN)
        self.poller.register(self.frontend.reps, zmq.POLLIN)
        self.poller.register(self.backend.reqs, zmq.POLLIN)
        self.poller.register(self.backend.reps, zmq.POLLIN)

        self.relays = {
            self.frontend.reqs: self.backend.reps,
            self.backend.reqs: self.frontend.reps,
            self.frontend.reps: self.backend.reqs,
            self.backend.reps: self.frontend.reqs
        }
        self.logs = {
            self.frontend.reqs: 'F-REQ',
            self.backend.reqs: 'B-REQ',
            self.frontend.reps: 'F-REP',
            self.backend.reps: 'B-REP'
        }

    def _before_bind(self):
        pass

    def _get_msg(self, socket):
        print self.logs.get(socket, 'ERROR')
        from_id, _, to_id, msg = socket.recv_multipart()
        print '--', from_id, to_id, msg
        return from_id, to_id, msg

    def _handle_socket(self, socket):
        from_id, to_id, msg = self._get_msg(socket)
        if not to_id and msg == b'ready':
            return
        self._handle_relay(socket, from_id, to_id, msg)

    def _handle_relay(self, socket, from_id, to_id, msg):
        to = self.relays.get(socket, None)
        if to:
            to.send_multipart((to_id, b'', from_id, msg))

    def poll(self):
        for socket, t in self.poller.poll():
            if t == zmq.POLLIN:
                self._handle_socket(socket)
