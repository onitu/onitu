import pytest

from .driver import load_driver_module, load_driver
from . import env


TargetModule = load_driver_module(env.driver)
TargetDriver, TargetFeatures = load_driver(env.driver)


def has_feature(feature_name):
    return getattr(TargetFeatures, feature_name, False)


class IfFeature(object):
    def __getattr__(self, name):
        reason = 'Driver {} does not support feature {}'.format(env.driver,
                                                                name)
        return pytest.mark.skipif(not has_feature(name), reason=reason)


if_feature = IfFeature()
