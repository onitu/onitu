import threading

import zmq
import msgpack

from onitu.plug import Plug, DriverError, ServiceError
from .remote import Remote
from .serializers import serializers

plug = Plug()

remote_socket, handlers_socket = None, None
exceptions_status = {1: DriverError, 2: ServiceError}
handlers_lock = threading.Lock()


def cmd_handler(name, *args_serializers):
    @plug.handler(name)
    def handler(*args):
        with handlers_lock:
            msg = [name] + [(ser, serializers.get(ser, lambda x: x)(arg))
                            for (ser, arg) in zip(args_serializers, args)]
            handlers_socket.send_multipart((plug.options['remote_id'],
                                            msgpack.packb(msg)))
            plug.logger.debug('===={}====', msg)
            _, resp = handlers_socket.recv_multipart()
            status, resp = msgpack.unpackb(resp)
            if status:
                E = exceptions_status.get(status, DriverError)
                raise E(*resp)
            plug.logger.debug('RESP {}', resp)
            return resp
    return handler


start_upload = cmd_handler('start_upload', 'metadata')
upload_chunk = cmd_handler('upload_chunk', 'metadata', None, None)
end_upload = cmd_handler('end_upload', 'metadata')
abort_upload = cmd_handler('abort_upload', 'metadata')
get_chunk = cmd_handler('get_chunk', 'metadata', None, None)
delete_file = cmd_handler('delete_file', 'metadata')
move_file = cmd_handler('move_file', 'metadata', 'metadata')


def start():
    global remote_socket, handlers_socket

    print "Launching driver"
    print plug.options

    ctx = zmq.Context.instance()
    remote_socket = ctx.socket(zmq.REQ)
    remote_socket.identity = plug.options['id']
    remote_socket.connect(plug.options['remote_uri'])
    handlers_socket = ctx.socket(zmq.REQ)
    handlers_socket.identity = plug.options['id']
    handlers_socket.connect(plug.options['handlers_uri'])

    remote = Remote(plug, remote_socket)
    remote.start()

    plug.listen()
    remote.join()
    remote_socket.close()
    handlers_socket.close()
