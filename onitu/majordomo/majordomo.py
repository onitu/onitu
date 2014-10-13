import sys
import uuid

import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
from circus.client import CircusClient

from logbook import Logger
from onitu.escalator.client import Escalator
from .broker import Broker


class Majordomo(Broker):
    handlers = {}

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
        self.remote_names = {}

        self.logger.info('Started')

    def bind(self, frontend_req_uri='tcp://*:20001',
             frontend_rep_uri='tcp://*:20003'):
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

    def stop(self):
        self.auth.stop()


def majordomo_new_remote(m, src_id):
    dest_id = uuid.uuid4().hex
    m.nb_remotes += 1
    name = 'remote-{}'.format(m.nb_remotes)
    m.remote_names[src_id] = name
    m.escalator.put('entry:{}:driver'.format(name), 'remote_driver')
    m.escalator.put('entry:{}:options'.format(name), {
        'id': dest_id,
        'remote_id': src_id,
        'remote_uri': 'tcp://127.0.0.1:{}'.format(
            m.backend.rep_port),
        'handlers_uri': 'tcp://127.0.0.1:{}'.format(
            m.backend.req_port)
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
                     m.escalator_uri,
                     m.session,
                     name,
                     m.log_uri),
            "copy_env": True,
            "start": True
        }
    }
    m.circus_client.call(query)


def majordomo_close_remote(m, src_id):
    name = m.remote_names.get(src_id)
    if name is not None:
        del m.remote_names[src_id]
        query = {
            "command": 'rm',
            "properties": {
                "name": name
            }
        }
        m.circus_client.call(query)


@Majordomo.handle('f-req')
def _handle_socket(m, relay, msg):
    if not msg.dest_id and msg.content == b'start':
        return majordomo_new_remote(m, msg.src_id)
    elif not msg.dest_id and msg.content == b'stop':
        return majordomo_close_remote(m, msg.src_id)
    return Broker.get_handler(relay.name)(m, relay, msg)
