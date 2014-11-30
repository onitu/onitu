# -*- coding: utf-8 -*-

import pytest

from tests.utils.targetdriver import TargetDriver, if_feature
from tests.utils.testdriver import TestDriver

d_target, d_test = None, None


def get_services():
    global d_target, d_test
    d_target, d_test = TargetDriver(u'®ép1'), TestDriver(u'®èp2')
    return d_target, d_test


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


@if_feature.copy_file_from_onitu
def test_copy_from_onitu(module_launcher):
    module_launcher.copy_file('default', u'ùñï©∅ð€ 1', 10, d_test, d_target)


@if_feature.copy_file_to_onitu
def test_copy_from_d_test(module_launcher):
    module_launcher.copy_file('default', u'ùñï©∅ð€ 2', 10, d_target, d_test)


@if_feature.del_file_to_onitu
def test_delete_from_d_target(module_launcher):
    module_launcher.create_file('default', u'ùñï©∅ð€ 3')
    module_launcher.delete_file('default', u'ùñï©∅ð€ 3', d_target, d_test)


@if_feature.del_file_from_onitu
def test_delete_from_d_test(module_launcher):
    module_launcher.create_file('default', u'ùñï©∅ð€ 4')
    module_launcher.delete_file('default', u'ùñï©∅ð€ 4', d_test, d_target)


@if_feature.move_file_to_onitu
def test_move_from_d_target(module_launcher):
    module_launcher.create_file('default', u'ùñï©∅ð€ 5')
    module_launcher.move_file(
        'default', u'ùñï©∅ð€ 5', u'mºˇ€Ð 1', d_target, d_test
    )


@if_feature.move_file_from_onitu
def test_move_from_d_test(module_launcher):
    module_launcher.create_file('default', u'ùñï©∅ð€ 6')
    module_launcher.move_file(
        'default', u'ùñï©∅ð€ 6', u'mºˇ€Ð 2', d_test, d_target
    )
