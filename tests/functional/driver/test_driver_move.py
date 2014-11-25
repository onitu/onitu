import pytest

from tests.utils.targetdriver import TargetDriver, if_feature
from tests.utils.testdriver import TestDriver
from tests.utils.loop import BooleanLoop, CounterLoop

def get_entries():
    return TargetDriver('rep1'), TestDriver('rep2')


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def copy_file(launcher, filename, size, src, dest):
    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from=src.name, d_to=dest.name, filename=filename
    )
    src.generate(filename, size)
    loop.run(timeout=10)
    assert dest.exists(filename)


def init_file(launcher, filename, size):
    d_target, d_test = launcher.get_entries('rep1', 'rep2')
    if if_feature.copy_file_from_onitu:
        copy_file(launcher, filename, size, d_test, d_target)
    else:
        copy_file(launcher, filename, size, d_target, d_test)


def move_file(launcher, old_filename, new_filename, size, src, dest):
    init_file(launcher, old_filename, size)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver=src.name, src=old_filename, dest=new_filename
    )
    launcher.on_move_completed(
        loop.check, driver=dest.name, src=old_filename, dest=new_filename
    )
    src.rename(old_filename, new_filename)
    loop.run(timeout=5)
    assert not dest.exists(old_filename)
    assert dest.exists(new_filename)
    assert src.checksum(new_filename) == dest.checksum(new_filename)


@if_feature.move_file_from_onitu
def test_driver_move_from_onitu(module_launcher):
    d_target, d_test = module_launcher.get_entries('rep1', 'rep2')
    move_file(module_launcher, 'move1', 'moved1', 100, d_test, d_target)


@if_feature.move_file_to_onitu
def test_driver_move_to_onitu(module_launcher):
    d_target, d_test = module_launcher.get_entries('rep1', 'rep2')
    move_file(module_launcher, 'move2', 'moved2', 100, d_target, d_test)
