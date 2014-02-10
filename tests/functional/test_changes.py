import os.path
from os import unlink

from utils.launcher import Launcher
from utils.setup import Setup
from utils.loop import CounterLoop
from utils.files import generate, checksum
from utils.tempdirs import TempDirs

launcher = None
dirs = TempDirs()
rep1, rep2 = dirs.create(), dirs.create()
json_file = 'test_changes.json'


def setup_module(module):
    global launcher
    setup = Setup()
    setup.add('local_storage', 'rep1', {'root': rep1})
    setup.add('local_storage', 'rep2', {'root': rep2})
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


def launch_with_files(prefix, n, size):
    launcher.unset_all_events()

    files = ['{}{}'.format(prefix, i) for i in range(n)]

    for filename in files:
        generate(os.path.join(rep1, filename), size)

    loop = CounterLoop(n)
    for filename in files:
        launcher.on_transfer_ended(
            loop.check, d_from='rep1', d_to='rep2', filename=filename
        )

    launcher_startup()
    loop.run(timeout=(5 + n // 10))
    for filename in files:
        assert(checksum(os.path.join(rep1, filename)) ==
               checksum(os.path.join(rep2, filename)))
    launcher.kill()


def test_changes_one_file():
    launch_with_files('one', 1, 100)


def test_changes_few_files():
    launch_with_files('few', 10, 100)


def test_changes_many_files():
    launch_with_files('many', 100, 10)


def test_updating_files():
    launch_with_files('up', 10, 100)
    launch_with_files('up', 10, 100)
