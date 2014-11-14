import os

import pytest

from .driver import load_driver


_driver_name = os.environ.get('ONITU_TEST_DRIVER', 'test')
TargetDriver, TargetFeatures = load_driver(_driver_name)


def has_feature(feature_name):
    return getattr(TargetFeatures, feature_name, False)


class IfFeature(object):
    def __getattr__(self, name):
        reason = 'Driver {} does not support feature {}'.format(_driver_name,
                                                                name)
        return pytest.mark.skipif(not has_feature(name), reason=reason)


if_feature = IfFeature()
