from onitu.api.plug import Plug
import socket
from threading import Thread

plug = Plug()
plug.client = None

@plug.handler()
def read_chunk(filename, offset, size):
    return ''

@plug.handler()
def write_chunk(filename, offset, chunk):
    return -1

@plug.handler()
def new_file(metadatas):
    pass

def client_handler():
    while True:
        data = plug.client.recv(1024)
        if not data:
            break
        print(data)

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)
    port = int(plug.options['port'])
    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serv.bind(('', port))
    serv.listen(1)
    print "Starting client's driver on port {}".format(port)
    plug.client, _ = serv.accept()
    client_thread = Thread(None, client_handler, 'client')
    client_thread.start()
    print(plug.handlers)
    plug.join()
