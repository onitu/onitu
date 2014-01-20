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


def test_startup():
    global loop
    loop.run(timeout=2)


def gen_test_copy(filename, size, fileids=[]):
    if not filename in fileids:
        fileids.append(filename)
    fileid = fileids.index(filename) + 1
    def test():
        loop = BooleanLoop()
        launcher.on_end_transfer(loop.stop, 'rep1', 'rep2', fileid)
        generate(os.path.join(rep1, filename), size)
        loop.run(timeout=5)
        assert(checksum(os.path.join(rep1, filename)) ==
               checksum(os.path.join(rep2, filename)))
    return test


test_simple_copy = gen_test_copy('foo', 100)
test_other_copy = gen_test_copy('bar', 100)
test_bigger_copy = gen_test_copy('foo', 1000)
test_smaller_copy = gen_test_copy('foo', 10)


def test_end():
    launcher.quit()
    launcher.wait()
