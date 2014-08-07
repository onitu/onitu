import sys
import uuid

import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
from circus.client import CircusClient

from logbook import Logger
from onitu.escalator.client import Escalator
from . import broker


class Majordomo(broker.Broker):
    def __init__(self, log_uri, escalator_uri, session,
                 keys_directory, server_key):
        super(Majordomo, self).__init__()
        self.log_uri = log_uri
        self.escalator_uri = escalator_uri
        self.session = session
        self.logger = Logger('Majordomo')
        self.escalator = Escalator(escalator_uri, session)

        self.keys_directory = keys_directory
        self.server_key = server_key
        self.auth = ThreadAuthenticator(zmq.Context.instance())
        self.circus_client = CircusClient()
        self.nb_remotes = 0

        self.logger.info('Started')

    def bind(self, frontend_ports=(20001, 20003)):
        self.auth.start()
        self.auth.configure_curve(domain='*', location=self.keys_directory)

        self.frontend.reqs.curve_server = True
        self.frontend.reps.curve_server = True
        pub_key, priv_key = zmq.auth.load_certificate(self.server_key)
        self.frontend.reqs.curve_publickey = pub_key
        self.frontend.reqs.curve_secretkey = priv_key
        self.frontend.reps.curve_publickey = pub_key
        self.frontend.reps.curve_secretkey = priv_key

        super(Majordomo, self).bind(frontend_ports)

    def _handle_socket(self, socket):
        if socket is not self.frontend.reqs:
            return super(Majordomo, self)._handle_socket(socket)
        from_id, to_id, msg = self._get_msg(socket)
        if not to_id and msg == b'start':
            to_id = uuid.uuid4().hex
            self.nb_remotes += 1
            name = 'remote-{}'.format(self.nb_remotes)
            self.escalator.put('entry:{}:driver'.format(name), 'remote_driver')
            self.escalator.put('entry:{}:options'.format(name), {
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
                             self.escalator_uri,
                             self.session,
                             name,
                             self.log_uri),
                    "copy_env": True,
                    "start": True
                }
            }
            self.circus_client.call(query)
            return
        self._handle_relay(socket, from_id, to_id, msg)

    def stop(self):
        self.auth.stop()
