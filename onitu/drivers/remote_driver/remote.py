import threading

import zmq
import msgpack

from .serializers import metadata_serializer, metadata_unserialize

remote_commands = {}


def remote_command(name=None):
    def decorator(f):
        remote_commands[name if name is not None else f.__name__] = f
        return f
    return decorator


class Remote(threading.Thread):
    def __init__(self, plug, socket):
        threading.Thread.__init__(self)
        self.plug = plug
        self.socket = socket

    def run(self):
        self.socket.send_multipart((self.plug.options['remote_id'],
                                    self.plug.name))
        while True:
            try:
                req_id, msg = self.socket.recv_multipart()
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break
            msg = msgpack.unpackb(msg, use_list=False)
            print 'Recv', msg, 'from', req_id
            command = remote_commands.get(msg[0], None)
            if command:
                command(self.plug, self.socket, *msg[1:])
            else:
                self.socket.send_multipart((req_id, b'ko'))


@remote_command()
def get_metadata(plug, remote_socket, filename):
    metadata = plug.get_metadata(filename)
    m = msgpack.packb(metadata_serializer(metadata))
    remote_socket.send_multipart((plug.options['remote_id'], m))


@remote_command()
def update_file(plug, remote_socket, m):
    metadata = metadata_unserialize(plug, m)
    plug.update_file(metadata)
    remote_socket.send_multipart((plug.options['remote_id'], b''))


@remote_command()
def delete_file(plug, remote_socket, m):
    metadata = metadata_unserialize(plug, m)
    plug.delete_file(metadata)
    remote_socket.send_multipart((plug.options['remote_id'], b''))


@remote_command()
def move_file(plug, remote_socket, old_m, new_filename):
    old_metadata = metadata_unserialize(plug, old_m)
    plug.move_file(old_metadata, new_filename)
    remote_socket.send_multipart((plug.options['remote_id'], b''))


@remote_command()
def metadata_write(plug, remote_socket, m):
    metadata = metadata_unserialize(plug, m)
    metadata.write()
    remote_socket.send_multipart((plug.options['remote_id'], b''))
