import json

from tests.utils.setup import Rule
from tests.utils.driver import TestingDriver, TargetDriver


def test_startup(launcher):
    rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')

    launcher.setup.add(rep1)
    launcher.setup.add(rep2)
    launcher.setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))

    try:
        launcher()
        assert not launcher.process.poll()
    finally:
        launcher.close()


def test_no_setup(launcher):
    error = (
        "Can't process setup file '{setup}' : "
        "[Errno 2] No such file or directory: '{setup}'"
        .format(setup=launcher.setup.filename)
    )

    try:
        launcher(wait=False, stderr=True, save_setup=False)
        launcher.wait()

        assert launcher.process.returncode == 1
        assert error in launcher.process.stderr.read().decode()
    finally:
        launcher.close()


def test_invalid_setup(launcher):
    launcher.setup.json = '{"foo": bar}'

    try:
        json.loads(launcher.setup.json)
    except ValueError as e:
        error = "Error parsing '{}' : {}".format(launcher.setup.filename, e)

    try:
        launcher(wait=False, stderr=True)
        launcher.wait()

        assert launcher.process.returncode == 1
        assert error in launcher.process.stderr.read().decode()
    finally:
        launcher.close()
