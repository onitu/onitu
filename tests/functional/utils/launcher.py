import signal
import socket
from subprocess import Popen

import logbook
from logbook.queues import ZeroMQSubscriber

from .logs import logs


FORMAT_STRING = (
    u'[{record.time:%H:%M:%S}] '
    u'{record.level_name}: {record.channel}: {record.message}'
)


class Launcher(object):
    def __init__(self, setup='setup.json', background=True):
        self.setup = setup
        self.bg = background
        self.process = None

        self.events = {}
        self.event_triggers = {}

    def set_event(self, name, triggers, action):
        event = {
            'triggers': list(triggers),
            'state': [False] * len(triggers),
            'action': action,
        }

        self.events[name] = event

        for trigger in triggers:
            self.event_triggers[trigger] = event

    def unset_event(self, name):
        for trigger in self.events[name]['triggers']:
            del self.event_triggers[trigger]
        del self.events[name]

    def unset_all_events(self):
        self.events = {}
        self.event_triggers = {}

    def quit(self, wait=True):
        if self.process is None:
            return

        try:
            self.process.send_signal(signal.SIGINT)
        except OSError: # Process already exited
            self.process = None
        if wait:
            self.wait()

    def kill(self, wait=True):
        if self.process is None:
            return

        try:
            self.process.send_signal(signal.SIGTERM)
        except OSError: # Process already exited
            self.process = None
        if wait:
            self.wait()

    def wait(self):
        if self.process is not None:
            self.process.wait()

    def _process_record(self, record):
        trigger = (record.channel, record.message)
        event = self.event_triggers.get(trigger)

        if not event:
            return

        event['state'][event['triggers'].index(trigger)] = True

        if all(event['state']):
            event['state'] = [False] * len(event['triggers'])
            event['action']()

    def __call__(self):
        # Find an open port for the logs
        # (that's a race condition, deal with it)
        tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmpsock.bind(('localhost', 0))
        log_uri = 'tcp://{}:{}'.format(*tmpsock.getsockname())
        tmpsock.close()

        setup = logbook.NestedSetup([
            logbook.NullHandler(),
            logbook.StderrHandler(
                level=logbook.INFO, format_string=FORMAT_STRING
            ),
            logbook.Processor(self._process_record),
        ])
        self.subscriber = ZeroMQSubscriber(log_uri, multi=True)
        self.subscriber.dispatch_in_background(setup=setup)

        self.process = Popen(('python', '-m', 'onitu',
                              '--setup', self.setup,
                              '--log-uri', log_uri))

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
            self.set_event(name, triggers, action)

        return caller

    def __getattr__(self, name):
        if name.startswith('on_'):
            return self._on_event(name[3:])
        return super(Launcher, self).__getattr__(name)


def launch(*args, **kwargs):
    return Launcher(*args, **kwargs)()
