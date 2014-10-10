from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import CounterLoop, BooleanLoop


def test_startup():
    json_file = 'test_startup.json'

    rep1, rep2 = LocalStorageDriver('rep1'), TargetDriver('rep2')

    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
    setup.save(json_file)

    launcher = Launcher(json_file)
    loop = CounterLoop(3)

    try:
        launcher.on_referee_started(loop.check)
        launcher.on_driver_started(loop.check, driver='rep1')
        launcher.on_driver_started(loop.check, driver='rep2')
        launcher()

        loop.run(timeout=2)
    finally:
        launcher.quit()
        setup.clean()


def test_no_setup():
    json_file = 'non_existing_setup.json'
    launcher = Launcher(json_file)
    loop = BooleanLoop()

    try:
        launcher.on_setup_not_existing(loop.stop, setup=json_file)
        launcher()
        launcher.wait()  # We should add a timeout

        assert launcher.process.returncode == 1
        assert not loop.condition()
    finally:
        launcher.quit()


def test_invalid_setup():
    json_file = 'invalid_setup.json'
    setup = Setup()
    setup.json = '{"foo": bar}'
    setup.save(json_file)
    launcher = Launcher(json_file)
    loop = BooleanLoop()

    try:
        launcher.on_setup_invalid(loop.stop, setup=json_file)
        launcher()
        launcher.wait()  # We should add a timeout

        assert launcher.process.returncode == 1
        assert not loop.condition()
    finally:
        launcher.quit()
        setup.clean()
