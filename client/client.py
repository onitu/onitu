#!/usr/bin/env python2

import zmq
from time import sleep
from threading import Thread

host, port = '127.0.0.1', 43364

context = zmq.Context()
req = context.socket(zmq.REQ)
rep = context.socket(zmq.REP)
req.connect('tcp://{}:{}'.format(host, port))

def rep_handler():
    while True:
        print(rep.recv())
        rep.send('ok')
rep_thread = Thread(None, rep_handler, 'rep')

req.send_multipart(('connect',))
port2 = req.recv()
rep.connect('tcp://{}:{}'.format(host, port2))
rep_thread.start()

while True:
    req.send_multipart(('hello world', 'tutu'))
    resp = req.recv()
    print resp
    sleep(1)
