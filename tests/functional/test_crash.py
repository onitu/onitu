from os import unlink

from utils.launcher import Launcher
from utils.setup import Setup
from utils.driver import LocalStorageDriver, TargetDriver
from utils.loop import CounterLoop, BooleanLoop

launcher = None
reps = {'rep1': LocalStorageDriver('rep1'),
        'rep2': TargetDriver('rep2')}
json_file = 'test_crash.json'


def setup_module(module):
    global launcher
    setup = Setup(session=True)
    setup.add(*reps['rep1'].setup)
    setup.add(*reps['rep2'].setup)
    setup.save(json_file)
    launcher = Launcher(json_file)


def teardown_module(module):
    launcher.kill()
    unlink(json_file)
    for rep in reps.values():
        rep.close()


def launcher_startup():
    launcher.kill()
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
    reps[d_from].generate(filename, 1000)
    launcher_startup()
    loop.run(timeout=10)
    launcher.kill()

    launcher.unset_all_events()
    loop = CounterLoop(2)
    launcher.on_transfer_restarted(
        loop.check, d_from=d_from, d_to=d_to, filename=filename
    )
    launcher.on_transfer_ended(
        loop.check, d_from=d_from, d_to=d_to, filename=filename
    )
    launcher_startup()
    loop.run(timeout=10)

    assert reps[d_from].checksum(filename) == reps[d_to].checksum(filename)
    launcher.kill()


def test_crash_rep1_to_rep2():
    crash('crash_1', 'rep1', 'rep2')


def test_crash_rep2_to_rep1():
    crash('crash_2', 'rep2', 'rep1')
