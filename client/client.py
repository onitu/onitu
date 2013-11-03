#!/usr/bin/env python2

import zmq
from time import sleep
from threading import Thread
import os.path
import pyinotify

host, port = '127.0.0.1', 43364
root = 'files'

if not os.path.exists(root):
    os.makedirs(root)

context = zmq.Context()
req = context.socket(zmq.REQ)
rep = context.socket(zmq.REP)
req.connect('tcp://{}:{}'.format(host, port))

nowatch_files = set()

class Watcher(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        return self.handle(event)

    def process_IN_CLOSE_WRITE(self, event):
        return self.handle(event)

    def handle(self, event):
        filename = os.path.normpath(os.path.relpath(event.pathname, '.'))
        if not filename in nowatch_files:
            filename = os.path.normpath(os.path.relpath(filename, root))
            print filename
            req.send_multipart(('file_updated',
                                filename,
                                str(os.path.getsize(event.pathname)),
                                str(os.path.getmtime(event.pathname))))
            print req.recv_multipart()
        else:
            nowatch_files.remove(filename)

manager = pyinotify.WatchManager()
notifier = pyinotify.ThreadedNotifier(manager, Watcher())
notifier.start()
mask = pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE
manager.add_watch(root, mask, rec=True)

req.send_multipart(('connect',))
_, port2 = req.recv_multipart()
rep.connect('tcp://{}:{}'.format(host, port2))

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
                if '..' in filename:
                    raise IOError
                filename = os.path.join(root, filename)
                with open(filename, 'rb') as f:
                    f.seek(offset)
                    rep.send_multipart(('ok', f.read(size)))
            except:
                rep.send_multipart(('ko', 'file not found', filename))
        elif cmd == 'write_chunk':
            _, filename, offset, chunk = msg
            if '..' in filename:
                raise IOError
            filename = os.path.join(root, filename)
            nowatch_files.add(filename)
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
