import sys
import uuid

import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
from circus.client import CircusClient

from . import broker
from onitu.escalator.client import Escalator
from logbook.queues import ZeroMQHandler
from logbook import Logger

log_uri = sys.argv[1]
escalator_uri = sys.argv[2]
session = sys.argv[3]
escalator = Escalator(escalator_uri, session)


class Broker(broker.Broker):
    def __init__(self):
        super(Broker, self).__init__((20001, 20003))
        self.circus_client = CircusClient()
        self.nb_remotes = 0

    def _before_bind(self):
        super(Broker, self)._before_bind()
        self.frontend.reqs.curve_server = True
        self.frontend.reps.curve_server = True
        pub_key, priv_key = zmq.auth.load_certificate('server.key_secret')
        self.frontend.reqs.curve_publickey = pub_key
        self.frontend.reqs.curve_secretkey = priv_key
        self.frontend.reps.curve_publickey = pub_key
        self.frontend.reps.curve_secretkey = priv_key

    def _handle_socket(self, socket):
        if socket is not self.frontend.reqs:
            return super(Broker, self)._handle_socket(socket)
        from_id, to_id, msg = self._get_msg(socket)
        if not to_id and msg == b'start':
            to_id = uuid.uuid4().hex
            self.nb_remotes += 1
            name = 'remote-{}'.format(self.nb_remotes)
            escalator.put('entry:{}:driver'.format(name), 'remote_driver')
            escalator.put('entry:{}:options'.format(name), {
                'id': to_id,
                'remote_id': from_id,
                'remote_uri': 'tcp://127.0.0.1:{}'.format(
                    self.backend.reps_port),
                'handlers_uri': 'tcp://127.0.0.1:{}'.format(
                    self.backend.reqs_port)
            })
            # protect query over non-ascii identities
            query = {
                "command": 'add',
                "properties": {
                    "name": name,
                    "cmd": sys.executable,
                    "args": ('-m',
                             'onitu.drivers',
                             'remote_driver',
                             escalator_uri,
                             session,
                             name,
                             log_uri),
                    "copy_env": True,
                    "start": True
                }
            }
            self.circus_client.call(query)
            socket.send_multipart((from_id, b'', to_id))
            return
        self._handle_relay(socket, from_id, to_id, msg)


if __name__ == '__main__':
    with ZeroMQHandler(log_uri, multi=True).applicationbound():
        ctx = zmq.Context.instance()
        auth = ThreadAuthenticator(ctx)
        auth.start()
        auth.configure_curve(domain='*', location='authorized_keys')

        logger = Logger('Majordomo')
        logger.info('Started')

        broker = Broker()
        while True:
            broker.poll()

        auth.stop()
        logger.info('Exited')
