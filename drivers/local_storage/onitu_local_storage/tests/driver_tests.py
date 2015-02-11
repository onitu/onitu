import pytest

from tests.utils.testdriver import TestDriver
from tests.utils.loop import CounterLoop, BooleanLoop

from . import Driver


def get_services():
    return Driver('rep1'), TestDriver('rep2', speed_bump=1)


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def test_move_file_not_watched(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    d_target.generate('to_move1', 10)

    loop = CounterLoop(1)
    module_launcher.on_transfer_ended(
        loop.check, d_to=d_test, filename='moved1'
    )
    d_target.rename('to_move1', d_target.path('default', 'moved1'))
    loop.run(5)


def test_move_dir_not_watched(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    d_target.mkdir('to_move2')
    d_target.generate('to_move2/foo', 10)
    d_target.generate('to_move2/bar', 10)
    d_target.generate('to_move2/lol', 10)

    loop = CounterLoop(3)
    module_launcher.on_transfer_ended(
        loop.check, d_to=d_test, filename='moved2/foo'
    )
    module_launcher.on_transfer_ended(
        loop.check, d_to=d_test, filename='moved2/bar'
    )
    module_launcher.on_transfer_ended(
        loop.check, d_to=d_test, filename='moved2/lol'
    )
    d_target.rename('to_move2', d_target.path('default', 'moved2'))
    loop.run(5)


def test_create_and_move_file(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')

    loop = BooleanLoop()
    module_launcher.on_move_completed(
        loop.stop, driver=d_test, src='to_move3', dest='moved3'
    )
    module_launcher.on_transfer_ended(
        loop.stop, d_to=d_test, filename='moved3'
    )

    d_target.generate(d_target.path('default', 'to_move3'), 100)
    d_target.rename(
        d_target.path('default', 'to_move3'),
        d_target.path('default', 'moved3')
    )

    loop.run(5)

    assert not d_test.exists(d_test.path('default', 'to_move3'))
    assert d_test.exists(d_test.path('default', 'moved3'))
    assert d_target.checksum(d_target.path('default', 'moved3')) == \
        d_test.checksum(d_test.path('default', 'moved3'))


def test_create_and_move_file_during_transfer(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')

    loop = BooleanLoop()
    module_launcher.on_move_completed(
        loop.stop, driver=d_test, src='to_move3', dest='moved3'
    )
    module_launcher.on_transfer_ended(
        loop.stop, d_to=d_test, filename='moved3'
    )

    intermediate_loop = BooleanLoop()
    module_launcher.on_transfer_started(
        intermediate_loop.stop, d_to=d_test, filename='to_move3'
    )

    d_target.generate(d_target.path('default', 'to_move3'), 100)
    intermediate_loop.run(2)
    d_target.rename(
        d_target.path('default', 'to_move3'),
        d_target.path('default', 'moved3')
    )

    loop.run(5)

    assert not d_test.exists(d_test.path('default', 'to_move3'))
    assert d_test.exists(d_test.path('default', 'moved3'))
    assert d_target.checksum(d_target.path('default', 'moved3')) == \
        d_test.checksum(d_test.path('default', 'moved3'))
