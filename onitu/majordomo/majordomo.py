import sys
import uuid

import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
from circus.client import CircusClient

from logbook import Logger
from onitu.escalator.client import Escalator
from onitu.utils import get_circusctl_endpoint, unpack_msg
from .broker import Broker
from .heartbeat import HeartBeatBroker

GRACEFUL_TIMEOUT = 1.


class Majordomo(HeartBeatBroker):
    handlers = {}

    def __init__(self, session, auth, keys_directory, server_key):
        super(Majordomo, self).__init__()
        self.session = session
        self.logger = Logger('Majordomo')
        self.escalator = Escalator(session)

        if auth:
            self.keys_directory = keys_directory
            self.server_key = server_key
            self.auth = ThreadAuthenticator(zmq.Context.instance())
        else:
            self.auth = None

        self.circus_client = CircusClient(endpoint=get_circusctl_endpoint(
            self.session))
        self.remote_names = {}

        self.logger.info('Started')

    def bind(self, frontend_req_uri, frontend_rep_uri):
        if self.auth:
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

    def new_remote(self, src_id, msg):
        service, conf = unpack_msg(msg)
        dest_id = uuid.uuid4().hex
        self.remote_names[src_id] = service
        self.escalator.put('service:{}:driver'.format(service),
                           'remote_driver')
        options = conf.get('options', {})
        options.update({
            'id': dest_id,
            'remote_id': src_id,
            'remote_uri': 'tcp://127.0.0.1:{}'.format(
                self.backend.rep_port),
            'handlers_uri': 'tcp://127.0.0.1:{}'.format(
                self.backend.req_port)
        })
        self.escalator.put('service:{}:options'.format(service),
                           options)
        self.escalator.put('services',
                           self.escalator.get('services') + (service,))
        folders = conf.get('folders', {})
        self.escalator.put(u'service:{}:folders'.format(service),
                           list(folders.keys()))
        for name, options in folders.items():
            if type(options) != dict:
                path = options
                options = {}
            else:
                path = options.pop('path', '/')
            self.escalator.put(u'service:{}:folder:{}:path'.format(service,
                                                                   name),
                               path)
            self.escalator.put(u'service:{}:folder:{}:options'.format(service,
                                                                      name),
                               options)
        query = {
            "command": 'add',
            "properties": {
                "name": service,
                "cmd": sys.executable,
                "args": ('-m',
                         'onitu.service',
                         self.session,
                         'remote_driver',
                         service),
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
        if self.auth:
            self.auth.stop()


@Majordomo.handle('f-req')
def majordomo_handle_socket(majordomo, relay, msg):
    if not msg.dest_id and msg.content.startswith(b'start'):
        return majordomo.new_remote(msg.src_id, msg.content[5:])
    elif not msg.dest_id and msg.content == b'stop':
        return majordomo.close_remote(msg.src_id)
    return Broker.get_handler(relay.name)(majordomo, relay, msg)
