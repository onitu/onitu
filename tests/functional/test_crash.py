from os import unlink

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import CounterLoop, BooleanLoop

launcher = None
reps = {'rep1': LocalStorageDriver('rep1'),
        'rep2': TargetDriver('rep2')}
json_file = 'test_crash.json'


def setup_module(module):
    global launcher
    launcher = Launcher(json_file)


def teardown_module(module):
    unlink(json_file)
    for rep in reps.values():
        rep.close()


def launcher_startup():
    loop = CounterLoop(3)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    loop.run(timeout=5)


def crash(filename, d_from, d_to):
    launcher.unset_all_events()
    try:
        setup = Setup(session=True)
        setup.add(*reps['rep1'].setup)
        setup.add(*reps['rep2'].setup)
        setup.save(json_file)

        start_loop = BooleanLoop()
        end_loop = CounterLoop(2)
        launcher.on_transfer_started(
            start_loop.stop, d_from=d_from, d_to=d_to, filename=filename
        )
        launcher.on_transfer_restarted(
            end_loop.check, d_from=d_from, d_to=d_to, filename=filename
        )
        launcher.on_transfer_ended(
            end_loop.check, d_from=d_from, d_to=d_to, filename=filename
        )

        reps[d_from].generate(filename, 1000)
        launcher_startup()
        start_loop.run(timeout=10)
        launcher.kill()

        launcher_startup()
        end_loop.run(timeout=10)

        assert reps[d_from].checksum(filename) == reps[d_to].checksum(filename)
    finally:
        try:
            for rep in reps.values():
                rep.unlink(filename)
        except:
            pass
        launcher.kill()


def test_crash_rep1_to_rep2():
    crash('crash_1', 'rep1', 'rep2')


def test_crash_rep2_to_rep1():
    crash('crash_2', 'rep2', 'rep1')
