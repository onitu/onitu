import signal
import socket

import sh
from logbook import Processor, NestedSetup
from logbook.queues import ZeroMQSubscriber

from logs import logs


class Launcher(object):
    def __init__(self, entries='entries.json', background=True):
        self.entries = entries
        self.bg = background
        self.events = []
        self.process = None

    def set_event(self, triggers, action):
        event = (triggers, action)
        self.events.append(event)
        return event

    def unset_event(self, event):
        self.events.remove(event)

    def quit(self):
        self.process.signal(signal.SIGINT)

    def kill(self):
        self.process.signal(signal.SIGTERM)

    def wait(self):
        self.process.wait()

    def _process_record(self, record):
        # We could speed-up things using a hash-table
        for triggers, action in self.events:
            for channel, message in triggers:
                if record.channel == channel and record.message == message:
                    triggers.remove((channel, message))
                    if len(triggers) == 0:
                        self.unset_event((triggers, action))
                        action()
                    break

    def __call__(self):
        # Find an open port for the logs
        # (that's a race condition, deal with it)
        tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmpsock.bind(('localhost', 0))
        log_uri = 'tcp://{}:{}'.format(*tmpsock.getsockname())
        tmpsock.close()

        handlers = [
            Processor(self._process_record),
        ]
        self.subscriber = ZeroMQSubscriber(log_uri, multi=True)
        self.subscriber.dispatch_in_background(setup=NestedSetup(handlers))

        self.process = sh.python(
            '-m', 'onitu',
            '--entries', self.entries,
            '--log-uri', log_uri,
            _bg=self.bg,
        )

        return self.process

    def _on_event(self, name):
        log_triggers = logs[name]

        def caller(action, **kwargs):
            triggers = set(
                (
                    channel.format(**kwargs),
                    message.format(**kwargs)
                )
                for (channel, message) in log_triggers
            )
            self.set_event(triggers, action)

        return caller

    def __getattr__(self, name):
        if name.startswith('on_'):
            return self._on_event(name[3:])
        return super(Launcher, self).__getattr__(name)


def launch(*args, **kwargs):
    return Launcher(*args, **kwargs)()
