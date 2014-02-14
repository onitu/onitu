import os.path
from os import unlink

import sh

from utils.launcher import Launcher
from utils.setup import Setup
from utils.loop import BooleanLoop, CounterLoop, TimeoutError
from utils.files import generate, checksum, KB, MB
from utils.tempdirs import TempDirs

launcher = None
dirs = TempDirs()
rep1, rep2 = dirs.create(), dirs.create()
json_file = 'test_copy.json'


def setup_module(module):
    global launcher
    setup = Setup()
    setup.add('local_storage', 'rep1', {'root': rep1})
    setup.add('local_storage', 'rep2', {'root': rep2})
    setup.save(json_file)
    loop = CounterLoop(3)
    launcher = Launcher(json_file)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    try:
        loop.run(timeout=5)
    except:
        teardown_module(module)
        raise


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


def test_small_copy():
    copy_file('simple', 10)


def test_regular_copy():
    copy_file('other', 100)


def test_same_copy():
    copy_file('same', 100)
    copy_file('same', 100)


def test_smaller_copy():
    copy_file('smaller', 10 * KB)
    copy_file('smaller', 1 * KB)


def test_bigger_copy():
    copy_file('bigger', 1 * KB)
    copy_file('bigger', 10 * KB)


def test_big_copy():
    copy_file('big', 10 * MB)


def test_empty_file():
    filename = 'empty'
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    sh.touch(os.path.join(rep1, filename))
    loop.run(timeout=5)
    assert os.path.getsize(os.path.join(rep2, filename)) == 0


def test_subdirectories():
    sh.mkdir('-p', os.path.join(rep1, 'sub/dir/deep/'))
    copy_file('sub/dir/deep/file', 100)


def test_multipass_copy():
    count = 10
    filename = 'multipass'

    loop = BooleanLoop()

    launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )

    generate(os.path.join(rep1, filename), 10 * KB, count)
    size = os.path.getsize(os.path.join(rep1, filename))

    for _ in range(count):
        try:
            loop.run(timeout=2)
        except TimeoutError:
            continue

        loop.restart()

        if os.path.getsize(os.path.join(rep2, filename)) == size:
            break

    assert (checksum(os.path.join(rep1, filename)) ==
            checksum(os.path.join(rep2, filename)))
