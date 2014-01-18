from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import EventLoop
from utils.files import generate, checksum

launcher = None
loop = EventLoop()


def setup_module(module):
    global launcher, circus
    launcher = Launcher()
    entries = Entries()
    entries.add('local_storage', 'rep1')
    entries.add('local_storage', 'rep2')
    # Driver should create its own directory
    entries.save('entries.json')
    launcher.set_event(launcher.on_driver_started('rep1'), loop.stop)
    launcher()


def teardown_module(module):
    launcher.quit()


def test_simple_copy():
    loop.run()
    launcher.set_event(launcher.on_end_transfer('rep1', 'rep2', 1),
                       launcher.quit)
    generate('test/driver_rep1/foo', 100)
    launcher.wait()
    assert(checksum('test/driver_rep1/foo') ==
           checksum('test/driver_rep2/foo'))
