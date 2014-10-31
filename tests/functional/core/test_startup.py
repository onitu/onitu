import json

from tests.utils.setup import Rule
from tests.utils.testdriver import TestDriver

from onitu.utils import u


def test_startup(setup, launcher):
    rep1, rep2 = TestDriver('rep1'), TestDriver('rep2')

    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))

    try:
        launcher()
        assert not launcher.process.poll()
    finally:
        launcher.close()


def test_no_setup(setup, launcher):
    try:
        with open(u(setup.filename)):
            pass
    except IOError as e:
        error = "Can't process setup file '{}' : {}".format(setup.filename, e)

    try:
        launcher(wait=False, stderr=True, save_setup=False)
        launcher.wait()

        assert launcher.process.returncode == 1
        assert error in launcher.process.stderr.read().decode()
    finally:
        launcher.close()


def test_invalid_setup(setup, launcher):
    setup.json = '{"foo": bar}'

    try:
        json.loads(setup.json)
    except ValueError as e:
        error = "Error parsing '{}' : {}".format(setup.filename, e)

    try:
        launcher(wait=False, stderr=True)
        launcher.wait()

        assert launcher.process.returncode == 1
        assert error in launcher.process.stderr.read().decode()
    finally:
        launcher.close()
