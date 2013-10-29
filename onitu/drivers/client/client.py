from onitu.api.plug import Plug
import socket
from threading import Thread
import struct

protocol = {
    'RC': '256sll',
    'WF': '256sll',
    'NF': '256s256s'
}

class Client:
    def __init__(self, socket=None):
        self.socket = socket
        self.commands = []

plug = Plug()
plug.client = Client()

def send_cmd(opcode, *args):
    fmt = '2s' + protocol[opcode]
    s = struct.pack(fmt, opcode, *args)
    plug.client.socket.send(s)
    print(s)
    print(struct.unpack(fmt, s))

@plug.handler()
def read_chunk(filename, offset, size):
    send_cmd('RC', filename, offset, size)
    #return plug.client.commands.pop()
    return ''

@plug.handler()
def write_chunk(filename, offset, chunk):
    send_cmd('WC', filename, offset, size)

@plug.handler()
def new_file(metadatas):
    send_cmd('NF', metadatas['path'], metadatas['filename'])

def client_handler():
    while True:
        data = plug.client.socket.recv(1024)
        if not data:
            break
        plug.client.commands.append(data)

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)
    port = int(plug.options['port'])
    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serv.bind(('', port))
    serv.listen(1)
    print "Starting client's driver on port {}".format(port)
    plug.client.socket, _ = serv.accept()
    client_thread = Thread(None, client_handler, 'client')
    client_thread.start()
    print(plug.handlers['read_chunk']('tutu', 0, 512))
    plug.join()
