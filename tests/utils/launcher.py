import signal
from subprocess import Popen, PIPE
from collections import defaultdict

import logbook
from logbook.queues import ZeroMQSubscriber

from onitu.utils import get_logs_uri

from .loop import CounterLoop
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
    def __init__(self,
                 setup,
                 background=True,
                 debug=True):
        self.setup = setup
        self.bg = background
        self.debug = debug

        self.process = None
        self.dispatcher = None
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

    def _kill(self, sig, wait):
        if self.process is None:
            return

        try:
            self.process.send_signal(sig)
        except OSError:  # Process already exited
            self.process = None

        if wait:
            self.wait()

    def quit(self, wait=True):
        self._kill(signal.SIGINT, wait)

    def kill(self, wait=True):
        self._kill(signal.SIGTERM, wait)

    def close(self, clean_setup=True):
        try:
            self.kill(wait=True)
        finally:
            if clean_setup:
                self.setup.clean()

            if self.dispatcher:
                self.dispatcher.stop()
                self.dispatcher.subscriber.close()

    def wait(self):
        if self.process is not None:
            self.process.wait()

    def process_record(self, record):
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

    def start_dispatcher(self):
        if not self.dispatcher:
            logs_uri = get_logs_uri(self.setup.name)

            level = logbook.DEBUG if self.debug else logbook.INFO
            handlers = logbook.NestedSetup([
                logbook.NullHandler(),
                logbook.StderrHandler(
                    level=level, format_string=FORMAT_STRING
                ),
                logbook.Processor(self.process_record),
            ])
            subscriber = ZeroMQSubscriber(logs_uri, multi=True)
            self.dispatcher = subscriber.dispatch_in_background(setup=handlers)
        elif not self.dispatcher.running:
            self.dispatcher.start()

    def __call__(self, wait=True, api=False, save_setup=True,
                 stdout=False, stderr=False):
        self.start_dispatcher()

        if save_setup:
            self.setup.save()

        if wait:
            loop = CounterLoop(len(self.setup.entries) + api + 1)
            self.on_referee_started(loop.check)
            if api:
                self.on_api_started(loop.check)
            for entry in self.setup.entries:
                self.on_driver_started(loop.check, driver=entry.name)

        self.process = Popen(
            ('onitu', '--setup', self.setup.filename, '--no-dispatcher'),
            stdout=PIPE,
            stderr=PIPE,
        )

        if wait:
            try:
                loop.run(timeout=5)
            except:
                self.close()

        return self.process

    def __del__(self):
        self.close()

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
