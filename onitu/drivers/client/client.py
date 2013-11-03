from onitu.api.plug import Plug
import socket
from threading import Thread
import struct
import zmq

plug = Plug()
context = zmq.Context()
plug.rep = context.socket(zmq.REP)
plug.req = context.socket(zmq.REQ)

@plug.handler()
def read_chunk(filename, offset, size):
    plug.req.send_multipart(('read_chunk', filename, str(offset), str(size)))
    resp = plug.req.recv_multipart()
    if resp[0] != 'ok':
        raise FileNotFoundError(filename)
    return resp[1]

@plug.handler()
def write_chunk(filename, offset, chunk):
    plug.req.send_multipart(('write_chunk', filename, str(offset), chunk))
    plug.req.recv_multipart()

def rep_handler():
    while True:
        msg = plug.rep.recv_multipart()
        if msg[0] == 'connect':
            plug.rep.send_multipart(('accept', plug.options['port2']))
        elif msg[0] == 'file_updated':
            _, filename, size, last_update = msg
            metadata = plug.get_metadata(filename)
            metadata.size = int(size)
            metadata.last_update = float(last_update)
            plug.update_file(metadata)
            plug.rep.send_multipart(('ok',))
        else:
            plug.rep.send_multipart(('ko', 'cmd not found', msg[0]))

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)
    port, port2 = plug.options['port'], plug.options['port2']
    plug.rep.bind('tcp://*:{}'.format(port))
    plug.req.bind('tcp://*:{}'.format(port2))
    print "Starting client's driver on port {}".format(port)
    rep_thread = Thread(None, rep_handler, 'rep')
    rep_thread.start()
    plug.join()
