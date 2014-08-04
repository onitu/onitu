import threading
import random

import zmq

from onitu.plug import Plug

plug = Plug()


class Thread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        ctx = zmq.Context.instance()
        remote_socket = ctx.socket(zmq.REQ)
        remote_socket.identity = plug.options['id']
        remote_socket.connect(plug.options['remote_uri'])
        handlers_socket = ctx.socket(zmq.REQ)
        handlers_socket.identity = plug.options['id']
        handlers_socket.connect(plug.options['handlers_uri'])

        pouet = random.randrange(100)
        n = 0

        remote_socket.send_multipart((b'', b'ready'))
        while True:
            req_id, msg = remote_socket.recv_multipart()
            print 'Recv', msg, 'from', req_id
            resp = 'ok-{}-{}'.format(pouet, n).encode()
            remote_socket.send_multipart((req_id, resp))
            n += 1


def start():
    print "Launching driver"
    print plug.options

    thread = Thread()
    thread.start()

    plug.listen()

"""
import threading

import msgpack

from onitu.api import Plug

plug = Plug()

def metadata_serializer(m):
    props = [getattr(m, p) for p in m.PROPERTIES]
    return m.fid, props, m.extra

def metadata_unserialize(m):
    fid, (filename, size, owners, uptodate), extra = m
    metadata = plug.get_metadata(filename)
    metadata.size = size
    metadata.owners = owners
    metadata.uptodate = uptodate
    metadata.extra = extra
    return metadata

def cmd_handler(name, *args_serializers):
    args_serializers = [ser if ser is not None else lambda x: x
                        for ser in args_serializers]

    @plug.handler(name)
    def handler(*args):
        msg = [name] + [ser(arg) for (ser, arg) in zip(args_serializers, args)]
        handlers_socket.send_multipart(client_identity, msgpack.packb(msg))
        # plug.logger.debug('{}', msg)
        _, resp = handlers_socket.recv_multipart()
        # plug.logger.debug('RESP {}', resp)
        return resp
    return handler


start_upload = cmd_handler('start_upload', metadata_serializer)
upload_chunk = cmd_handler('upload_chunk', metadata_serializer, None, None)
end_upload = cmd_handler('end_upload', metadata_serializer)
abort_upload = cmd_handler('abort_upload', metadata_serializer)
get_chunk = cmd_handler('get_chunk', metadata_serializer, None, None)


class ClientThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._running = True
        #ctx = zmq.Context.instance()
        #self.socket = ctx.socket(zmq.REP)
        #self.socket.bind('tcp://*:{}'.format(clients_port))
        self.socket = client_reqs

    def run(self):
        cmds = {
            'metadata write': self.metadata_write,
            'update_file': self.update_file,
            'get_metadata': self.get_metadata
        }
        while True:
            try:
                _, msg = self.socket.recv_multipart()
                msg = msgpack.unpackb(msg, use_list=False)
                # plug.logger.debug('MSG {}', msg)
                cmd = cmds.get(msg[0], None)
                if cmd:
                    cmd(*msg[1:])
                else:
                    self.socket.send_multipart(client_identity, b'ko')
            except zmq.ContextTerminated:
                break

    def metadata_write(self, m):
        metadata = metadata_unserialize(m)
        metadata.write()
        # print(metadata, metadata_serializer(metadata))
        self.socket.send_multipart(client_identity, b'ok')

    def update_file(self, m):
        metadata = metadata_unserialize(m)
        plug.update_file(metadata)
        self.socket.send_multipart(client_identity, b'ok')

    def get_metadata(self, filename):
        # print(filename)
        msg = msgpack.packb(metadata_serializer(plug.get_metadata(filename)))
        self.socket.send_multipart(client_identity, msg)

    def stop(self):
        self.socket.close()


def start():
    global handlers_socket
    #ctx = zmq.Context.instance()
    #handlers_socket = ctx.socket(zmq.REQ)
    #handlers_socket.bind('tcp://*:{}'.format(handlers_port))
    client = ClientThread()
    client.start()
    plug.listen()
    handlers_socket.close()
    client_reqs.close()
    client.stop()
"""
