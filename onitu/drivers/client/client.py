from onitu.api.plug import Plug
import socket
from threading import Thread
import struct
import zmq

plug = Plug()
context = zmq.Context()
plug.rep = context.socket(zmq.REP)
plug.req = context.socket(zmq.REQ)

#@plug.handler()
#def read_chunk(filename, offset, size):
#    return ''

#@plug.handler()
#def write_chunk(filename, offset, chunk):
#    pass

#@plug.handler()
#def new_file(metadatas):
#    pass

def rep_handler():
    while True:
        msg = plug.rep.recv_multipart()
        if msg[0] == 'connect':
            plug.rep.send(plug.options['port2'])
        else:
            plug.rep.send('ok')
        print msg

from time import sleep
def test_handler():
    while True:
        plug.req.send('toto')
        print plug.req.recv()
        sleep(2)

def start(*args, **kwargs):
    plug.launch(*args, **kwargs)
    port, port2 = plug.options['port'], plug.options['port2']
    plug.rep.bind('tcp://*:{}'.format(port))
    plug.req.bind('tcp://*:{}'.format(port2))
    print "Starting client's driver on port {}".format(port)
    rep_thread = Thread(None, rep_handler, 'rep')
    rep_thread.start()
    test_thread = Thread(None, test_handler, 'test')
    test_thread.start()
    plug.join()
