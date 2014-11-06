from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import TestingDriver, TargetDriver
from tests.utils.loop import BooleanLoop
from tests.utils.files import KB, MB

launcher, setup = None, None
rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')


def setup_module(module):
    global launcher, setup
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
    launcher = Launcher(setup)
    launcher()


def teardown_module(module):
    launcher.close()


def copy_file(filename, size):
    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    rep1.generate(filename, size)
    loop.run(timeout=10)
    assert rep1.checksum(filename) == rep2.checksum(filename)


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
    copy_file('empty', 0)


def test_subdirectories():
    rep1.mkdir('sub/dir/deep/')
    copy_file('sub/dir/deep/file', 100)
