from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import TestingDriver, TargetDriver
from tests.utils.loop import CounterLoop, BooleanLoop

# We use chunks of size 1 to slow down the transfers. This way, we have
# more chances to stop a transfer before its completion
rep1 = TestingDriver('rep1', speed_bump=True)
rep2 = TargetDriver('rep2', speed_bump=True)
setup = None


def setup_module(module):
    global setup
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))


def teardown_module(module):
    setup.clean()


def crash(filename, source, target):
    launcher = Launcher(setup)

    try:
        start_loop = BooleanLoop()
        end_loop = CounterLoop(2)
        launcher.on_transfer_started(
            start_loop.stop,
            d_from=source.name, d_to=target.name,
            filename=filename
        )
        launcher.on_transfer_restarted(
            end_loop.check,
            d_from=source.name, d_to=target.name,
            filename=filename
        )
        launcher.on_transfer_ended(
            end_loop.check,
            d_from=source.name, d_to=target.name,
            filename=filename
        )

        source.generate(filename, 100)
        launcher()
        start_loop.run(timeout=10)
        launcher.kill()

        launcher()
        end_loop.run(timeout=10)

        assert source.checksum(filename) == target.checksum(filename)
    finally:
        try:
            source.unlink(filename)
            target.unlink(filename)
        except:
            pass
        launcher.close(clean_setup=False)


def test_crash_rep1_to_rep2():
    crash('crash_1', rep1, rep2)


def test_crash_rep2_to_rep1():
    crash('crash_2', rep2, rep1)
