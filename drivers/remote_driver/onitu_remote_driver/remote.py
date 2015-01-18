import threading

import zmq

from onitu.plug.folder import Folder
from onitu.utils import b, pack_obj, pack_msg, unpack_msg
from .serializers import metadata_serializer, metadata_unserialize
from .serializers import folder_serializer, folder_unserialize

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
        self.socket.send_multipart((b(self.plug.options['remote_id']),
                                    b''))
        while True:
            try:
                req_id, msg = self.socket.recv_multipart()
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break
            msg = unpack_msg(msg)
            command = remote_commands.get(msg[0], None)
            if command:
                command(self.plug, self.socket, *msg[1:])
            else:
                self.socket.send_multipart((req_id, b'ko'))


@remote_command()
def get_metadata(plug, remote_socket, filename, folder):
    folder = folder_unserialize(plug, folder)
    metadata = plug.get_metadata(filename, folder)
    m = pack_obj(metadata_serializer(metadata))
    remote_socket.send_multipart((b(plug.options['remote_id']), m))


@remote_command()
def update_file(plug, remote_socket, m):
    metadata = metadata_unserialize(plug, m)
    plug.update_file(metadata)
    remote_socket.send_multipart((b(plug.options['remote_id']), b''))


@remote_command()
def delete_file(plug, remote_socket, m):
    metadata = metadata_unserialize(plug, m)
    plug.delete_file(metadata)
    remote_socket.send_multipart((b(plug.options['remote_id']), b''))


@remote_command()
def move_file(plug, remote_socket, old_m, new_filename):
    old_metadata = metadata_unserialize(plug, old_m)
    plug.move_file(old_metadata, new_filename)
    remote_socket.send_multipart((b(plug.options['remote_id']), b''))


@remote_command()
def metadata_write(plug, remote_socket, m):
    metadata = metadata_unserialize(plug, m)
    metadata.write()
    remote_socket.send_multipart((b(plug.options['remote_id']), b''))

@remote_command()
def get_folder(plug, remote_socket, folder):
    folder = Folder.get(plug, folder)
    f = pack_obj(folder_serializer(folder))
    remote_socket.send_multipart((b(plug.options['remote_id']), f))

@remote_command()
def get_folders(plug, remote_socket):
    folders = Folder.get_folders(plug)
    f = pack_obj({name:folder_serializer(value)
                  for (name, value) in folders.items()})
    remote_socket.send_multipart((b(plug.options['remote_id']), f))

@remote_command()
def list(plug, remote_socket, folder, path):
    folder = folder_unserialize(plug, folder)
    r = pack_obj(plug.list(folder, path))
    remote_socket.send_multipart((b(plug.options['remote_id']), r))

@remote_command()
def exists(plug, remote_socket, folder, path):
    folder = folder_unserialize(plug, folder)
    r = pack_obj(plug.exists(folder, path))
    remote_socket.send_multipart((b(plug.options['remote_id']), r))

@remote_command()
def escalator(plug, remote_socket, method, args, kwargs):
    actions = {
        'get': plug.entry_db.get,
        'exists': plug.entry_db.exists,
        'put': plug.entry_db.put,
        'delete': plug.entry_db.delete,
        'range': plug.entry_db.range
    }
    if method == 'batch':
        transaction = kwargs.get('transaction')
        requests = kwargs.get('requests')
        with plug.entry_db.write_batch(transaction) as batch:
            for (cmd, args, kwargs) in requests:
                if cmd == 'put':
                    batch.put(*args, **kwargs)
                elif cmd == 'delete':
                    batch.delete(*args, **kwargs)
        remote_socket.send_multipart((b(plug.options['remote_id']),
                                      pack_obj(None)))
        return
    action = actions.get(method)
    if action is None:
        remote_socket.send_multipart((b(plug.options['remote_id']), b''))
    else:
        try:
            resp = action(*args, **kwargs)
        except Exception as e:
            remote_socket.send_multipart((b(plug.options['remote_id']),
                                          pack_msg(0, e.args)))
        else:
            remote_socket.send_multipart((b(plug.options['remote_id']),
                                          pack_msg(1, resp)))