import signal
from subprocess import Popen, PIPE
from collections import defaultdict

import logbook
from logbook.queues import ZeroMQSubscriber

from onitu.utils import get_logs_uri, u, IS_WINDOWS

from .targetdriver import TargetDriver, if_feature
from .testdriver import TestDriver
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
            self.event_triggers[trigger].discard(event)

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
        if IS_WINDOWS:
            self._kill(signal.CTRL_C_EVENT, wait)
        else:
            self._kill(signal.SIGINT, wait)

    def kill(self, wait=True):
        self._kill(signal.SIGTERM, wait)

    def close(self):
        try:
            self.kill(wait=True)
        finally:
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

    def __call__(self, wait=True, api=False, save_setup=True,
                 stdout=False, stderr=False):
        self.start_dispatcher()

        if save_setup:
            self.setup.save()

        if wait:
            loop = CounterLoop(len(self.setup.services) + api + 1)
            self.on_referee_started(loop.check)
            if api:
                self.on_api_started(loop.check)
            for service in self.setup.services.values():
                self.on_driver_started(loop.check, driver=service.name)

        self.process = Popen(
            ('onitu', '--config-dir', self.setup.config_dir, '--setup',
             self.setup.filename, '--no-dispatcher'),
            stdout=PIPE if stdout else None,
            stderr=PIPE if stderr else None,
        )

        if wait:
            try:
                loop.run(timeout=5)
            except:
                self.close()
                raise

        return self.process

    def __del__(self):
        self.close()

    def _on_event(self, name):
        log_triggers = logs[name]

        def caller(action, unique=True, **kwargs):
            triggers = set(
                (
                    u(channel).format(**kwargs),
                    u(message).format(**kwargs)
                )
                for (channel, message) in log_triggers
            )
            return self.set_event(triggers, action, unique)

        return caller

    def __getattr__(self, name):
        if name.startswith('on_'):
            return self._on_event(name[3:])
        return self.__getattribute__(name)

    @property
    def services(self):
        return self.setup.services

    def get_services(self, *names):
        return [self.services[name] for name in names]

    def create_file(self, folder, filename, size=10):
        if if_feature.copy_file_from_onitu:
            src_driver = TestDriver
        else:
            src_driver = TargetDriver

        services = list(self.services.values())
        for i, service in enumerate(services):
            if isinstance(service, src_driver):
                src = services.pop(i)
                # we asume that all the services should receive
                # the file
                dests = services
                break

        self.copy_file(folder, filename, size, src, *dests)

    def copy_file(self, folder, filename, size, src, *dests):
        loop = CounterLoop(len(dests))
        for dest in dests:
            self.on_transfer_ended(
                loop.check, d_from=src, d_to=dest, filename=filename
            )
        src.generate(src.path(folder, filename), size)
        loop.run(timeout=10)

        checksum = src.checksum(src.path(folder, filename))

        for dest in dests:
            assert dest.checksum(dest.path(folder, filename)) == checksum

    def delete_file(self, folder, filename, src, *dests):
        loop = CounterLoop(1 + len(dests))
        self.on_file_deleted(
            loop.check, driver=src, filename=filename, folder=folder
        )
        for dest in dests:
            self.on_deletion_completed(
                loop.check, driver=dest, filename=filename
            )
        src.unlink(src.path(folder, filename))
        loop.run(timeout=5)
        for dest in dests:
            assert not dest.exists(dest.path(folder, filename))

    def move_file(self, folder, old_filename, new_filename, src, *dests):
        loop = CounterLoop(1 + len(dests))
        self.on_file_moved(
            loop.check, driver=src, src=old_filename, dest=new_filename,
            folder=folder
        )
        for dest in dests:
            self.on_move_completed(
                loop.check, driver=dest, src=old_filename, dest=new_filename
            )
        src.rename(
            src.path(folder, old_filename), src.path(folder, new_filename)
        )
        loop.run(timeout=5)
        checksum = src.checksum(src.path(folder, new_filename))
        for dest in dests:
            assert not dest.exists(dest.path(folder, old_filename))
            assert dest.checksum(dest.path(folder, new_filename)) == checksum
