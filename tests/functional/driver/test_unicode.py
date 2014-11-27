# -*- coding: utf-8 -*-

import pytest

from tests.utils.targetdriver import TargetDriver, if_feature
from tests.utils.testdriver import TestDriver
from tests.utils.helpers import copy_file, move_file, delete_file

d_target, d_test = None, None


def get_entries():
    global d_target, d_test
    d_target, d_test = TargetDriver(u'®ép1'), TestDriver(u'®èp2')
    return d_target, d_test


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


@if_feature.copy_file_from_onitu
def test_copy_from_onitu(module_launcher):
    copy_file(module_launcher, u'ùñï©∅ð€ 1', 100, d_test, d_target)


@if_feature.copy_file_to_onitu
def test_copy_from_d_test(module_launcher):
    copy_file(module_launcher, u'ùñï©∅ð€ 2', 100, d_target, d_test)


def test_delete_from_d_target(module_launcher):
    delete_file(module_launcher, u'ùñï©∅ð€ 3', 100, d_target, d_test)


def test_delete_from_d_test(module_launcher):
    delete_file(module_launcher, u'ùñï©∅ð€ 4', 100, d_target, d_test)


def test_move_from_d_target(module_launcher):
    move_file(module_launcher, u'ùñï©∅ð€ 5', u'mºˇ€Ð 1', 100, d_target, d_test)


def test_move_from_d_test(module_launcher):
    move_file(module_launcher, u'ùñï©∅ð€ 6', u'mºˇ€Ð 2', 100, d_test, d_target)
