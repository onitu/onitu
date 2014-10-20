import sys
import uuid

import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
from circus.client import CircusClient

from logbook import Logger
from onitu.escalator.client import Escalator
from onitu.utils import get_circusctl_endpoint
from .broker import Broker

GRACEFUL_TIMEOUT = 1.


# class Majordomo(HeartBeatBroker):
class Majordomo(Broker):
    handlers = {}

    def __init__(self, session, keys_directory, server_key):
        super(Majordomo, self).__init__()
        self.session = session
        self.logger = Logger('Majordomo')
        self.escalator = Escalator(session)

        self.keys_directory = keys_directory
        self.server_key = server_key
        self.auth = ThreadAuthenticator(zmq.Context.instance())
        self.circus_client = CircusClient(endpoint=get_circusctl_endpoint(
            self.session))
        self.nb_remotes = 0
        self.remote_names = {}

        self.logger.info('Started')

    def bind(self, frontend_req_uri, frontend_rep_uri):
        self.auth.start()
        self.auth.configure_curve(domain='*', location=self.keys_directory)

        self.frontend.req.curve_server = True
        self.frontend.rep.curve_server = True
        pub_key, priv_key = zmq.auth.load_certificate(self.server_key)
        self.frontend.req.curve_publickey = pub_key
        self.frontend.req.curve_secretkey = priv_key
        self.frontend.rep.curve_publickey = pub_key
        self.frontend.rep.curve_secretkey = priv_key

        super(Majordomo, self).bind(frontend_req_uri, frontend_rep_uri,
                                    'tcp://127.0.0.1', 'tcp://127.0.0.1')
        self.logger.info('Starting listening on {} and {}',
                         frontend_req_uri, frontend_rep_uri)

    def new_remote(self, src_id):
        dest_id = uuid.uuid4().hex
        self.nb_remotes += 1
        name = 'remote-{}'.format(self.nb_remotes)
        self.remote_names[src_id] = name
        self.escalator.put('entry:{}:driver'.format(name), 'remote_driver')
        self.escalator.put('entry:{}:options'.format(name), {
            'id': dest_id,
            'remote_id': src_id,
            'remote_uri': 'tcp://127.0.0.1:{}'.format(
                self.backend.rep_port),
            'handlers_uri': 'tcp://127.0.0.1:{}'.format(
                self.backend.req_port)
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
                         self.session,
                         name),
                "copy_env": True,
                "start": True,
                "graceful_timeout": GRACEFUL_TIMEOUT
            }
        }
        self.circus_client.call(query)

    def close_remote(self, src_id):
        name = self.remote_names.get(src_id)
        if name is not None:
            del self.remote_names[src_id]
            query = {
                "command": 'rm',
                "properties": {
                    "name": name
                }
            }
            self.circus_client.call(query)

    def stop(self):
        self.auth.stop()


@Majordomo.handle('f-req')
def majordomo_handle_socket(majordomo, relay, msg):
    if not msg.dest_id and msg.content == b'start':
        return majordomo.new_remote(msg.src_id)
    elif not msg.dest_id and msg.content == b'stop':
        return majordomo.close_remote(msg.src_id)
    return Broker.get_handler(relay.name)(majordomo, relay, msg)
