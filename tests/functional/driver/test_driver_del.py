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


def delete_file(launcher, filename, size, src, dest):
    init_file(launcher, filename, size)
    loop = CounterLoop(2)
    launcher.on_file_deleted(
        loop.check, driver=src.name, filename=filename
    )
    launcher.on_deletion_completed(
        loop.check, driver=dest.name, filename=filename
    )
    src.unlink(filename)
    loop.run(timeout=5)
    assert not dest.exists(filename)


@if_feature.del_file_from_onitu
def test_driver_del_from_onitu(module_launcher):
    d_target, d_test = module_launcher.get_entries('rep1', 'rep2')
    delete_file(module_launcher, 'del1', 100, d_test, d_target)


@if_feature.del_file_to_onitu
def test_driver_del_to_onitu(module_launcher):
    d_target, d_test = module_launcher.get_entries('rep1', 'rep2')
    delete_file(module_launcher, 'del2', 100, d_target, d_test)
