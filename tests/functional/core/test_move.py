import pytest

from tests.utils.testdriver import TestDriver
from tests.utils.loop import BooleanLoop, CounterLoop

rep1, rep2 = TestDriver('rep1'), TestDriver('rep2')


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def copy_file(module_launcher, filename, size):
    module_launcher.unset_all_events()
    loop = BooleanLoop()
    module_launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    rep1.generate(filename, size)
    loop.run(timeout=10)
    assert rep2.exists(filename)


def test_move_from_rep1(module_launcher):
    copy_file(module_launcher, 'to_move1', 100)
    loop = CounterLoop(2)
    module_launcher.on_file_moved(
        loop.check, driver='rep1', src='to_move1', dest='moved1'
    )
    module_launcher.on_move_completed(
        loop.check, driver='rep2', src='to_move1', dest='moved1'
    )
    rep1.rename('to_move1', 'moved1')
    loop.run(timeout=5)
    assert not rep2.exists('to_move1')
    assert rep2.exists('moved1')


def test_move_from_rep2(module_launcher):
    copy_file(module_launcher, 'to_move2', 100)
    loop = CounterLoop(2)
    module_launcher.on_file_moved(
        loop.check, driver='rep2', src='to_move2', dest='moved2'
    )
    module_launcher.on_move_completed(
        loop.check, driver='rep1', src='to_move2', dest='moved2'
    )
    rep2.rename('to_move2', 'moved2')
    loop.run(timeout=5)
    assert not rep1.exists('to_move2')
    assert rep1.exists('moved2')


def test_move_in_subdirs(module_launcher):
    rep1.mkdir('test/with/subdirs/')
    copy_file(module_launcher, 'test/with/subdirs/foo', 100)
    loop = CounterLoop(2)
    module_launcher.on_file_moved(
        loop.check, driver='rep1',
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar'
    )
    module_launcher.on_move_completed(
        loop.check, driver='rep2',
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar'
    )
    rep1.mkdir('test/to/other/dir')
    rep1.rename('test/with/subdirs/foo', 'test/to/other/dir/bar')
    loop.run(timeout=5)
    assert not rep2.exists('test/with/subdirs/foo')
    assert rep2.exists('test/to/other/dir/bar')


def test_move_dir_from_rep1(module_launcher):
    rep1.mkdir('dir')
    copy_file(module_launcher, 'dir/foo', 100)
    copy_file(module_launcher, 'dir/bar', 100)
    loop = CounterLoop(4)
    module_launcher.on_file_moved(
        loop.check, driver='rep1', src='dir/foo', dest='other/foo'
    )
    module_launcher.on_file_moved(
        loop.check, driver='rep1', src='dir/bar', dest='other/bar'
    )
    module_launcher.on_move_completed(
        loop.check, driver='rep2', src='dir/foo', dest='other/foo'
    )
    module_launcher.on_move_completed(
        loop.check, driver='rep2', src='dir/bar', dest='other/bar'
    )
    rep1.rename('dir', 'other')
    loop.run(timeout=5)
    assert not rep2.exists('dir/foo')
    assert not rep2.exists('dir/bar')
    assert rep2.exists('other/foo')
    assert rep2.exists('other/bar')
