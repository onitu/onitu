import os.path
from os import unlink

from utils.launcher import Launcher
from utils.setup import Setup
from utils.loop import CounterLoop
from utils.files import generate, checksum
from utils.tempdirs import TempDirs

launchers = [None, None]
dirs = TempDirs()
reps = [{'rep1': dirs.create(), 'rep2': dirs.create()},
        {'rep1': dirs.create(), 'rep2': dirs.create()}]
json_files = ['test_changes.json', 'test_changes_session.json']


def setup_module(module):
    for i, session in enumerate([False, True]):
        setup = Setup(session=session)
        setup.add('local_storage', 'rep1', {'root': reps[i]['rep1']})
        setup.add('local_storage', 'rep2', {'root': reps[i]['rep2']})
        setup.save(json_files[i])
        launchers[i] = Launcher(json_files[i])


def teardown_module(module):
    for launcher, json_file in zip(launchers, json_files):
        launcher.kill()
        unlink(json_file)
    dirs.delete()


def launcher_startup(launcher):
    loop = CounterLoop(3)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    loop.run(timeout=5)


def launch_with_files(launcher, reps, prefix, n, size, delete=True):
    launcher.unset_all_events()
    files = ['{}{}'.format(prefix, i) for i in range(n)]

    try:
        for filename in files:
            generate(os.path.join(reps['rep1'], filename), size)

        loop = CounterLoop(n)
        for filename in files:
            launcher.on_transfer_ended(
                loop.check, d_from='rep1', d_to='rep2', filename=filename
            )

        launcher_startup(launcher)
        loop.run(timeout=(5 + n // 10))
        for filename in files:
            assert(checksum(os.path.join(reps['rep1'], filename)) ==
                   checksum(os.path.join(reps['rep2'], filename)))
    finally:
        launcher.kill()
        if delete:
            for filename in files:
                try:
                    for n in ('rep1', 'rep2'):
                        unlink(os.path.join(reps[n], filename))
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
