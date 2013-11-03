#!/usr/bin/env python2

import zmq
from time import sleep
from threading import Thread
import os.path

host, port = '127.0.0.1', 43364

context = zmq.Context()
req = context.socket(zmq.REQ)
rep = context.socket(zmq.REP)
req.connect('tcp://{}:{}'.format(host, port))

def rep_handler():
    while True:
        msg = rep.recv_multipart()
        print 'msg', msg
        try:
            cmd = msg[0]
            if cmd == 'read_chunk':
                _, filename, offset, size = msg
                offset = int(offset)
                size = int(size)
                try:
                    with open(filename, 'rb') as f:
                        f.seek(offset)
                        rep.send_multipart(('ok', f.read(size)))
                except:
                    rep.send_multipart(('ko', 'file not found', filename))
            elif cmd == 'write_chunk':
                _, filename, offset, chunk = msg
                offset = int(offset)
                dirname = os.path.dirname(filename)
                mode = 'rb+'
                if not os.path.exists(filename):
                    if dirname and not os.path.exists(dirname):
                        os.makedirs(dirname)
                    mode = 'wb+'
                with open(filename, mode) as f:
                    f.seek(offset)
                    f.write(chunk)
                rep.send_multipart(('ok',))
            else:
                rep.send_multipart(('ok',))
        except:
            rep.send_multipart(('ko',))
rep_thread = Thread(None, rep_handler, 'rep')

req.send_multipart(('connect',))
_, port2 = req.recv_multipart()
rep.connect('tcp://{}:{}'.format(host, port2))
rep_thread.start()

while True:
    req.send_multipart(('hello world', 'tutu'))
    resp = req.recv_multipart()
    print 'resp', resp
    sleep(1)
