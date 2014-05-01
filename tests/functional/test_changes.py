from os import unlink

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import CounterLoop

launchers = [None, None]
reps = [{'rep1': LocalStorageDriver('rep1'),
         'rep2': TargetDriver('rep2')},
        {'rep1': LocalStorageDriver('rep1'),
         'rep2': TargetDriver('rep2')}]
json_files = ['test_changes.json', 'test_changes_session.json']


def setup_module(module):
    for i, session in enumerate([False, True]):
        setup = Setup(session=session)
        setup.add(reps[i]['rep1'])
        setup.add(reps[i]['rep2'])
        setup.add_rule(Rule().match_path('/').sync(reps[i]['rep1'].name,
                                                   reps[i]['rep2'].name))
        setup.save(json_files[i])
        launchers[i] = Launcher(json_files[i])


def teardown_module(module):
    for launcher, json_file in zip(launchers, json_files):
        launcher.kill()
        unlink(json_file)
    for r in reps:
        for rep in r.values():
            rep.close()


def launcher_startup(launcher):
    loop = CounterLoop(3)
    launcher.on_referee_started(loop.check)
    launcher.on_plug_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    loop.run(timeout=5)


def launch_with_files(launcher, reps, prefix, n, size, delete=True):
    launcher.unset_all_events()
    files = ['{}{}'.format(prefix, i) for i in range(n)]

    try:
        for filename in files:
            reps['rep1'].generate(filename, size)

        loop = CounterLoop(n)
        for filename in files:
            launcher.on_transfer_ended(
                loop.check, d_from='rep1', d_to='rep2', filename=filename
            )

        launcher_startup(launcher)
        loop.run(timeout=(10 + n // 5))
        for filename in files:
            assert (reps['rep1'].checksum(filename) ==
                    reps['rep2'].checksum(filename))
    finally:
        launcher.kill()
        if delete:
            for filename in files:
                try:
                    for rep in reps.values():
                        rep.unlink(filename)
                except:
                    pass


def test_changes_one_file():
    launch_with_files(launchers[0], reps[0], 'one', 1, 100)


def test_changes_few_files():
    launch_with_files(launchers[0], reps[0], 'few', 10, 100)


def test_changes_many_files():
    launch_with_files(launchers[0], reps[0], 'many', 100, 10)


def test_updating_files():
    launch_with_files(launchers[1], reps[1], 'up', 10, 100, False)
    launch_with_files(launchers[1], reps[1], 'up', 10, 100)
