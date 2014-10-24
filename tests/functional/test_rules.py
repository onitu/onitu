from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import TestingDriver, TargetDriver
from tests.utils.loop import BooleanLoop, TimeoutError


class ShouldNotCopy(BaseException):
    pass


def test_no_rule():
    try:
        filename = 'bar'
        rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')
        setup = Setup()
        setup.add(rep1)
        setup.add(rep2)
        launcher = Launcher(setup)
        launcher()

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
        launcher.close()


def test_path():
    try:
        directory = 'foo'
        filename = '{}/bar'.format(directory)
        rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')
        setup = Setup()
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_path('/{}'.format(directory)).sync('rep2'))
        launcher = Launcher(setup)
        launcher()

        loop = BooleanLoop()
        launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        rep1.mkdir(directory)
        rep1.generate(filename, 100)
        loop.run(timeout=5)
        assert rep1.checksum(filename) == rep2.checksum(filename)
    finally:
        launcher.close()


def test_not_mime():
    try:
        filename = 'bar.txt'
        rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')
        setup = Setup()
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_mime('image/png').sync('rep2'))
        launcher = Launcher(setup)
        launcher()

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
        launcher.close()


def test_simple_mime():
    try:
        filename = 'bar.png'
        rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')
        setup = Setup()
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_mime('image/png').sync('rep2'))
        launcher = Launcher(setup)
        launcher()

        loop = BooleanLoop()
        launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        rep1.generate(filename, 100)
        loop.run(timeout=5)
        assert rep1.checksum(filename) == rep2.checksum(filename)
    finally:
        launcher.close()


def test_multi_mime():
    try:
        filenames = 'bar.png', 'foo.txt'
        rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')
        setup = Setup()
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_mime('image/png', 'text/plain')
                       .sync('rep2'))
        launcher = Launcher(setup)
        launcher()

        for filename in filenames:
            loop = BooleanLoop()
            launcher.on_transfer_ended(
                loop.stop, d_from='rep1', d_to='rep2', filename=filename
            )
            rep1.generate(filename, 100)
            loop.run(timeout=5)
            assert rep1.checksum(filename) == rep2.checksum(filename)
    finally:
        launcher.close()


def test_path_mime():
    try:
        directory = 'foo'
        rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')
        setup = Setup()
        setup.add(rep1)
        setup.add(rep2)
        setup.add_rule(Rule().match_path('/{}'.format(directory))
                       .match_mime('image/png').sync('rep2'))
        launcher = Launcher(setup)
        launcher()

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
        launcher.close()
