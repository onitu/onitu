import sys

from logbook.queues import ZeroMQHandler

from client import start

if __name__ == '__main__':
    with ZeroMQHandler('tcp://127.0.0.1:5000').applicationbound():
        start(*sys.argv[1:])
