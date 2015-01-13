import pytest

from tests.utils.targetdriver import TargetDriver, if_feature
from tests.utils.testdriver import TestDriver


def get_services():
    return TargetDriver('rep1'), TestDriver('rep2')


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


@if_feature.del_file_from_onitu
def test_driver_del_from_onitu(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    module_launcher.create_file('default', 'del1')
    module_launcher.delete_file('default', 'del1', d_test, d_target)


@if_feature.del_file_to_onitu
def test_driver_del_to_onitu(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    module_launcher.create_file('default', 'del2')
    module_launcher.delete_file('default', 'del2', d_target, d_test)
