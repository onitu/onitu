import os.path
from os import unlink

from utils.launcher import Launcher
from utils.setup import Setup
from utils.loop import CounterLoop, BooleanLoop
from utils.files import generate, checksum
from utils.tempdirs import TempDirs

launcher = None
dirs = TempDirs()
reps = {'rep1': dirs.create(), 'rep2': dirs.create()}
json_file = 'test_crash.json'


def setup_module(module):
    global launcher
    setup = Setup()
    setup.add('local_storage', 'rep1', {'root': reps['rep1']})
    setup.add('local_storage', 'rep2', {'root': reps['rep2']})
    setup.save(json_file)
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


def crash(filename, d_from, d_to):
    loop = BooleanLoop()
    launcher.on_transfer_started(
        loop.stop, d_from=d_from, d_to=d_to, filename=filename
    )
    generate(os.path.join(reps[d_from], filename), 1000)
    launcher_startup()
    loop.run(timeout=5)
    launcher.kill()

    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from=d_from, d_to=d_to, filename=filename
    )
    launcher_startup()
    loop.run(timeout=5)

    assert(checksum(os.path.join(reps[d_from], filename)) ==
           checksum(os.path.join(reps[d_to], filename)))
    launcher.kill()


def test_crash_rep1_to_rep2():
    crash('crash_1', 'rep1', 'rep2')


def test_crash_rep2_to_rep1():
    crash('crash_2', 'rep2', 'rep1')
