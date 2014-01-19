import sh
import signal


LOG_END_TRANSFER = "{driver} - Worker: Transfer for file {fid}" \
                   " from {other} successful"
LOG_DRIVER_STARTED = "{driver} - Worker: Listening for orders from" \
                     " the Referee..."


class Launcher(object):
    def __init__(self, ini='onitu.ini', background=True):
        self.prog = ini
        self.bg = background
        self.events = []
        self.process = None

    def set_event(self, line, action):
        event = line, action
        self.events.append(event)
        return event

    def unset_event(self, event):
        self.events.remove(event)

    @staticmethod
    def log_end_transfer(d_from, d_to, fid):
        return LOG_END_TRANSFER.format(driver=d_to, other=d_from, fid=fid)

    @staticmethod
    def log_driver_started(driver):
        return LOG_DRIVER_STARTED.format(driver=driver)

    def quit(self):
        self.process.signal(signal.SIGINT)

    def kill(self):
        self.process.signal(signal.SIGKILL)

    def wait(self):
        self.process.wait()

    def _process_line(self, line, stdin, process):
        for e_line, action in self.events:
            if e_line in line:
                action()

    def __call__(self, wait=False):
        self.process = sh.circusd(self.prog, _bg=self.bg,
                                  _err=self._process_line)
        if (wait):
            self.wait()
        return self.process

    def _on_event(self, name):
        log_func = getattr(self, 'log_{}'.format(name))

        def caller(action, *args, **kwargs):
            line = log_func(*args, **kwargs)
            self.set_event(line, action)

        return caller

    def __getattr__(self, name):
        if name.startswith('on_'):
            return self._on_event(name[3:])
        return super(Launcher, self).__getattr__(name)


def launch(*args, **kwargs):
    return Launcher(*args, **kwargs)()
