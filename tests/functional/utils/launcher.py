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
    def on_end_transfer(d_from, d_to, fid):
        return LOG_END_TRANSFER.format(driver=d_to, other=d_from, fid=fid)


    @staticmethod
    def on_driver_started(driver):
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
        self.process = sh.circusd(self.prog, _bg=self.bg, _err=self._process_line)
        if (wait):
            self.wait()
        return self.process


def launch(*args, **kwargs):
    return Launcher(*args, **kwargs)()
