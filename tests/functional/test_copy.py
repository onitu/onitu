from utils import Launcher
from utils.entries import Entries
from utils.files import generate, checksum
from time import sleep

launcher = None


def setup_module(module):
    global launcher, circus
    launcher = Launcher(directory='../..')
    entries = Entries()
    entries.add('local_storage', 'rep1')
    entries.add('local_storage', 'rep2')
    # Driver should create its own directory
    entries.save('entries.json')
    launcher()


def teardown_module(module):
    launcher.kill()


def test_simple_copy():
    sleep(1)
    launcher.set_event(launcher.on_end_transfer('rep1', 'rep2', 1), launcher.quit)
    generate('test/driver_rep1/foo', 100)
    launcher.wait()
    assert(checksum('test/driver_rep1/foo') ==
           checksum('test/driver_rep2/foo'))
