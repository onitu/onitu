from os import unlink

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop, TimeoutError

launcher = None
rep1, rep2 = LocalStorageDriver('rep1'), TargetDriver('rep2')
json_file = 'test_rules.json'


def setup_module(module):
    global launcher
    launcher = Launcher(json_file)


def teardown_module(module):
    unlink(json_file)
    rep1.close()
    rep2.close()


def launcher_startup():
    loop = CounterLoop(3)
    launcher.unset_all_events()
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    loop.run(timeout=10)
    launcher.unset_all_events()


class ShouldNotCopy(BaseException):
    pass


def test_no_rule():
    try:
        filename = 'bar'
        setup = Setup(session=True)
        setup.add(rep1)
        setup.add(rep2)
        setup.save(json_file)
        launcher_startup()

        try:
            loop = BooleanLoop()
            launcher.on_transfer_started(
                loop.stop, d_from='rep1', d_to='rep2', filename=filename
            )
            rep1.generate(filename, 10)
            loop.run(timeout=1)
        except TimeoutError:
            pass
        else:
            raise ShouldNotCopy
    finally:
        launcher.kill()


def test_path():
    try:
        directory = 'foo'
        filename = '{}/bar'.format(directory)
        setup = Setup(session=True)
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_path('/{}'.format(directory)).sync('rep2'))
        setup.save(json_file)
        launcher_startup()

        loop = BooleanLoop()
        launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        rep1.mkdir(directory)
        rep1.generate(filename, 100)
        loop.run(timeout=5)
        assert rep1.checksum(filename) == rep2.checksum(filename)
    finally:
        launcher.kill()


def test_not_mime():
    try:
        filename = 'bar.txt'
        setup = Setup(session=True)
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_mime('image/png').sync('rep2'))
        setup.save(json_file)
        launcher_startup()

        try:
            loop = BooleanLoop()
            launcher.on_transfer_started(
                loop.stop, d_from='rep1', d_to='rep2', filename=filename
            )
            rep1.generate(filename, 100)
            loop.run(timeout=1)
        except TimeoutError:
            pass
        else:
            raise ShouldNotCopy
    finally:
        launcher.kill()


def test_simple_mime():
    try:
        filename = 'bar.png'
        setup = Setup(session=True)
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_mime('image/png').sync('rep2'))
        setup.save(json_file)
        launcher_startup()

        loop = BooleanLoop()
        launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        rep1.generate(filename, 100)
        loop.run(timeout=5)
        assert rep1.checksum(filename) == rep2.checksum(filename)
    finally:
        launcher.kill()


def test_multi_mime():
    try:
        filenames = 'bar.png', 'foo.txt'
        setup = Setup(session=True)
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_mime('image/png', 'text/plain')
                       .sync('rep2'))
        setup.save(json_file)
        launcher_startup()

        for filename in filenames:
            loop = BooleanLoop()
            launcher.on_transfer_ended(
                loop.stop, d_from='rep1', d_to='rep2', filename=filename
            )
            rep1.generate(filename, 100)
            loop.run(timeout=5)
            assert rep1.checksum(filename) == rep2.checksum(filename)
    finally:
        launcher.kill()


def test_path_mime():
    try:
        directory = 'foo'
        setup = Setup(session=True)
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_path('/{}'.format(directory))
                       .match_mime('image/png').sync('rep2'))
        setup.save(json_file)
        launcher_startup()

        rep1.mkdir(directory)

        filename = 'foo/bar.png'
        loop = BooleanLoop()
        launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        rep1.generate(filename, 100)
        loop.run(timeout=5)
        assert rep1.checksum(filename) == rep2.checksum(filename)

        filenames = 'bar.png', 'foo/bar'
        for filename in filenames:
            try:
                loop = BooleanLoop()
                launcher.on_transfer_started(
                    loop.stop, d_from='rep1', d_to='rep2', filename=filename
                )
                rep1.generate(filename, 100)
                loop.run(timeout=1)
            except TimeoutError:
                pass
            else:
                raise ShouldNotCopy
    finally:
        launcher.kill()
