import os.path
from os import unlink

import pytest

from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import CounterLoop, BooleanLoop
from utils.files import generate, checksum
from utils.tempdirs import TempDirs

launcher = None
dirs = TempDirs()
rep1, rep2 = dirs.create(), dirs.create()
json_file = 'test_crash.json'


def setup_module(module):
    global launcher
    entries = Entries()
    entries.add('local_storage', 'rep1', {'root': rep1})
    entries.add('local_storage', 'rep2', {'root': rep2})
    entries.save(json_file)
    launcher = Launcher(json_file)


def teardown_module(module):
    launcher.kill()
    unlink(json_file)
    dirs.delete()


def launcher_startup():
    loop = CounterLoop(3)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    loop.run(timeout=5)


@pytest.mark.xfail
def test_crach():
    filename = 'crash'

    loop = BooleanLoop()
    launcher.on_transfer_started(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    launcher_startup()
    generate(os.path.join(rep1, filename), 1000)
    loop.run(timeout=5)
    launcher.kill()

    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    launcher_startup()
    loop.run(timeout=5)

    assert(checksum(os.path.join(rep1, filename)) ==
           checksum(os.path.join(rep2, filename)))
    launcher.kill()
    launcher.wait()
