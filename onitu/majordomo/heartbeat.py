import zmq

from .broker import Broker


class HeartBeatBroker(Broker):
    handlers = {}

    def __init__(self):
        super(HeartBeatBroker, self).__init__()
        ctx = zmq.Context.instance()
        self.heartbeat = ctx.socket(zmq.REP)
        self.relay(self.heartbeat, 'heartbeat')

    def bind(self, *args, **kwargs):
        super(HeartBeatBroker, self).bind(*args, **kwargs)
        self.heartbeat.bind('tcp://*:20005')


@HeartBeatBroker.handle('heartbeat')
def _heartbeat(broker, relay, msg):
    print('ping', msg.src_id)
    relay.src.send(b'pong')
