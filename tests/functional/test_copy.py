from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop, CounterLoop
from utils.files import generate, checksum

launcher = None
loop = None


def setup_module(module):
    global launcher, loop
    launcher = Launcher()
    entries = Entries()
    entries.add('local_storage', 'rep1')
    entries.add('local_storage', 'rep2')
    # Driver should create its own directory
    entries.save('entries.json')
    loop = CounterLoop(2)
    launcher.on_driver_started(loop.check, 'rep1')
    launcher.on_driver_started(loop.check, 'rep2')
    launcher()


def teardown_module(module):
    launcher.kill()


def test_simple_copy():
    global loop
    loop.run(timeout=2)
    loop = BooleanLoop()
    launcher.on_end_transfer(loop.stop, 'rep1', 'rep2', 1)
    generate('test/driver_rep1/foo', 100)
    loop.run(timeout=5)
    launcher.quit()
    launcher.wait()
    assert(checksum('test/driver_rep1/foo') ==
           checksum('test/driver_rep2/foo'))
