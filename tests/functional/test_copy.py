import os.path
from os import unlink
from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop, CounterLoop
from utils.files import generate, checksum
from utils.tempdirs import TempDirs

launcher = None
loop = None
dirs = TempDirs()
rep1, rep2 = dirs.create(), dirs.create()
json_file = 'test_copy.json'


def setup_module(module):
    global launcher, loop
    entries = Entries()
    entries.add('local_storage', 'rep1', {'root': rep1})
    entries.add('local_storage', 'rep2', {'root': rep2})
    entries.save(json_file)
    loop = CounterLoop(2)
    launcher = Launcher(json_file)
    launcher.on_driver_started(loop.check, 'rep1')
    launcher.on_driver_started(loop.check, 'rep2')
    launcher()


def teardown_module(module):
    launcher.kill()
    unlink(json_file)


def test_simple_copy():
    global loop
    loop.run(timeout=2)
    loop = BooleanLoop()
    launcher.on_end_transfer(loop.stop, 'rep1', 'rep2', 1)
    generate(os.path.join(rep1, 'foo'), 100)
    loop.run(timeout=5)
    launcher.quit()
    launcher.wait()
    assert(checksum(os.path.join(rep1, 'foo')) ==
           checksum(os.path.join(rep2, 'foo')))
