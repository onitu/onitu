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


def test_deletion_from_rep1(module_launcher):
    copy_file(module_launcher, 'to_delete', 100)
    loop = CounterLoop(2)
    module_launcher.on_file_deleted(
        loop.check, driver='rep1', filename='to_delete'
    )
    module_launcher.on_deletion_completed(
        loop.check, driver='rep2', filename='to_delete'
    )
    rep1.unlink('to_delete')
    loop.run(timeout=5)
    assert not rep2.exists('to_delete')


def test_deletion_from_rep2(module_launcher):
    copy_file(module_launcher, 'to_delete', 100)
    loop = CounterLoop(2)
    module_launcher.on_file_deleted(
        loop.check, driver='rep2', filename='to_delete'
    )
    module_launcher.on_deletion_completed(
        loop.check, driver='rep1', filename='to_delete'
    )
    rep2.unlink('to_delete')
    loop.run(timeout=5)
    assert not rep1.exists('to_delete')


def test_delete_dir(module_launcher):
    rep1.mkdir('dir')
    copy_file(module_launcher, 'dir/foo', 100)
    copy_file(module_launcher, 'dir/bar', 100)
    loop = CounterLoop(4)
    module_launcher.on_file_deleted(
        loop.check, driver='rep1', filename='dir/foo'
    )
    module_launcher.on_file_deleted(
        loop.check, driver='rep1', filename='dir/bar'
    )
    module_launcher.on_deletion_completed(
        loop.check, driver='rep2', filename='dir/foo'
    )
    module_launcher.on_deletion_completed(
        loop.check, driver='rep2', filename='dir/bar'
    )
    rep1.rmdir('dir')
    loop.run(timeout=5)
    assert not rep2.exists('dir/foo')
    assert not rep2.exists('dir/bar')
