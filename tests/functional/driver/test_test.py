from tests.utils.targetdriver import TargetDriver, if_feature


@if_feature.copy_file_from_onitu
def test_toto():
    print(TargetDriver.__name__)
