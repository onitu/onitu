from onitu.api.plug import Plug
import socket
from threading import Thread
import struct
import zmq

#protocol = {
#    'RC': '256sll',
#    'WF': '256sll',
#    'NF': '256s256s'
#}
#
#class Client:
#    def __init__(self, socket=None):
#        self.socket = socket
#        self.commands = []

plug = Plug()
#plug.client = Client()
plug.rep = None
plug.req = None

#def send_cmd(opcode, *args):
#    fmt = '2s' + protocol[opcode]
#    s = struct.pack(fmt, opcode, *args)
#    plug.client.socket.send(s)
#    print(s)
#    print(struct.unpack(fmt, s))

@plug.handler()
def read_chunk(filename, offset, size):
    #send_cmd('RC', filename, offset, size)
    #return plug.client.commands.pop()
    plug.req.send_multipart(('read_chunk', filename, offset, size))
    return ''

@plug.handler()
def write_chunk(filename, offset, chunk):
    #send_cmd('WC', filename, offset, size)
    pass

@plug.handler()
def new_file(metadatas):
    #send_cmd('NF', metadatas['path'], metadatas['filename'])
    pass

def client_handler():
    while True:
        msg = plug.rep.recv_multipart()
        print(msg)
        cmd = msg[0]
        if cmd == 'connect':
            port = plug.options['port2']
            plug.req.bind('tcp://*:{}'.format(port))
            plug.rep.send_multipart(('channel', port))
        else:
            plug.rep.send('ok')

from time import sleep
def test_handler():
    while True:
        sleep(2)
        plug.handlers['read_chunk']('tutu', 0, 512)
        print(plug.req.recv())

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)
    port = plug.options['port']
    print "Starting client's driver on port {}".format(port)
    context = zmq.Context()
    plug.rep = context.socket(zmq.REP)
    plug.req = context.socket(zmq.REQ)
    plug.rep.bind('tcp://*:{}'.format(port))
    client_thread = Thread(None, client_handler, 'client')
    client_thread.start()
    test_thread = Thread(None, test_handler, 'test')
    test_thread.start()
    plug.join()
