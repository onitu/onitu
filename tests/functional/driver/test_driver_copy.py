import pytest

from tests.utils.targetdriver import TargetDriver, if_feature
from tests.utils.testdriver import TestDriver
from tests.utils.loop import BooleanLoop

d_target, d_test = TargetDriver('target'), TestDriver('test')
rep1, rep2 = d_target, d_test


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
    assert src.checksum(filename) == dest.checksum(filename)


@if_feature.copy_file_from_onitu
def test_driver_copy_from_onitu(module_launcher):
    copy_file(module_launcher, 'cpy1', 100, d_test, d_target)


@if_feature.copy_file_to_onitu
def test_driver_copy_to_onitu(module_launcher):
    copy_file(module_launcher, 'cpy2', 100, d_target, d_test)
