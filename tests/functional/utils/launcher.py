import signal
import socket
from subprocess import Popen
from collections import defaultdict

import logbook
from logbook.queues import ZeroMQSubscriber

from .logs import logs


FORMAT_STRING = (
    u'[{record.time:%H:%M:%S}] '
    u'{record.level_name}: {record.channel}: {record.message}'
)


class Event(object):
    def __init__(self, triggers, action, unique):
        self.triggers = triggers
        self.state = [False] * len(triggers)
        self.action = action
        self.unique = unique


class Launcher(object):
    def __init__(self, setup='setup.json', background=True, debug=True):
        self.setup = setup
        self.bg = background
        self.debug = debug

        self.process = None
        self.event_triggers = defaultdict(set)

    def set_event(self, triggers, action, unique):
        event = Event(list(triggers), action, unique)

        for trigger in event.triggers:
            self.event_triggers[trigger].add(event)
        return event

    def unset_event(self, event):
        for trigger in event.triggers:
            self.event_triggers[trigger].remove(event)

    def unset_all_events(self):
        self.event_triggers = defaultdict(set)

    def quit(self, wait=True):
        if self.process is None:
            return

        try:
            self.process.send_signal(signal.SIGINT)
        except OSError:  # Process already exited
            self.process = None
        if wait:
            self.wait()

    def kill(self, wait=True):
        if self.process is None:
            return

        try:
            self.process.send_signal(signal.SIGTERM)
        except OSError:  # Process already exited
            self.process = None
        if wait:
            self.wait()

    def wait(self):
        if self.process is not None:
            self.process.wait()

    def _process_record(self, record):
        trigger = (record.channel, record.message)
        events = self.event_triggers.get(trigger)

        if not events:
            return

        unset_events = set()
        for event in events:
            event.state[event.triggers.index(trigger)] = True
            if all(event.state):
                if event.unique:
                    unset_events.add(event)
                event.action()
        for event in unset_events:
            self.unset_event(event)

    def __call__(self):
        # Find an open port for the logs
        # (that's a race condition, deal with it)
        tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmpsock.bind(('localhost', 0))
        log_uri = 'tcp://{}:{}'.format(*tmpsock.getsockname())
        tmpsock.close()

        level = logbook.DEBUG if self.debug else logbook.INFO
        setup = logbook.NestedSetup([
            logbook.NullHandler(),
            logbook.StderrHandler(
                level=level, format_string=FORMAT_STRING
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

        def caller(action, unique=True, **kwargs):
            triggers = set(
                (
                    channel.format(**kwargs),
                    message.format(**kwargs)
                )
                for (channel, message) in log_triggers
            )
            return self.set_event(triggers, action, unique)

        return caller

    def __getattr__(self, name):
        if name.startswith('on_'):
            return self._on_event(name[3:])
        return super(Launcher, self).__getattr__(name)


def launch(*args, **kwargs):
    return Launcher(*args, **kwargs)()
