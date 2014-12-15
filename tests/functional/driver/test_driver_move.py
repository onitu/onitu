import pytest

from tests.utils.targetdriver import TargetDriver, if_feature
from tests.utils.testdriver import TestDriver


def get_services():
    return TargetDriver('rep1'), TestDriver('rep2')


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


@if_feature.move_file_from_onitu
def test_driver_move_from_onitu(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    module_launcher.create_file('default', 'move1')
    module_launcher.move_file('default', 'move1', 'moved1', d_test, d_target)


@if_feature.move_file_to_onitu
def test_driver_move_to_onitu(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    module_launcher.create_file('default', 'move2')
    module_launcher.move_file('default', 'move2', 'moved2', d_target, d_test)
