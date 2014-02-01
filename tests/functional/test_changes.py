import os.path
from os import unlink

import sh

from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop, CounterLoop, TimeoutError
from utils.files import generate, checksum
from utils.tempdirs import TempDirs

launcher = None
dirs = TempDirs()
rep1, rep2 = dirs.create(), dirs.create()
json_file = 'test_changes.json'


def setup_module(module):
    global launcher
    entries = Entries()
    entries.add('local_storage', 'rep1', {'root': rep1})
    entries.add('local_storage', 'rep2', {'root': rep2})
    entries.save(json_file)
    #loop = CounterLoop(3)
    launcher = Launcher(json_file)
    #launcher.on_referee_started(loop.check)
    #launcher.on_driver_started(loop.check, driver='rep1')
    #launcher.on_driver_started(loop.check, driver='rep2')
    #launcher()
    #try:
    #    loop.run(timeout=5)
    #except:
    #    teardown_module(module)
    #    raise


def teardown_module(module):
    launcher.kill()
    unlink(json_file)
    dirs.delete()


def copy_file(filename, size):
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    generate(os.path.join(rep1, filename), size)
    loop.run(timeout=5)
    assert(checksum(os.path.join(rep1, filename)) ==
           checksum(os.path.join(rep2, filename)))


def test_changes_on_launch():
    filename = 'foo'
    generate(os.path.join(rep1, filename), 100)

    launch_loop = CounterLoop(3)
    launcher.on_referee_started(launch_loop.check)
    launcher.on_driver_started(launch_loop.check, driver='rep1')
    launcher.on_driver_started(launch_loop.check, driver='rep2')

    copy_loop = BooleanLoop()
    launcher.on_transfer_ended(
        copy_loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )

    launcher()
    launch_loop.run(timeout=5)
    copy_loop.run(timeout=5)
    assert(checksum(os.path.join(rep1, filename)) ==
           checksum(os.path.join(rep2, filename)))
