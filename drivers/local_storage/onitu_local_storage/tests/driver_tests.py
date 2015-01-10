import pytest

from tests.utils.testdriver import TestDriver
from tests.utils.loop import CounterLoop

from . import Driver


def get_services():
    return Driver('rep1'), TestDriver('rep2')


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def test_driver_move_file_not_watched(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    d_target.generate('to_move1', 10)

    loop = CounterLoop(1)
    module_launcher.on_transfer_ended(
        loop.check, d_from=d_target, d_to=d_test, filename='moved1'
    )
    d_target.rename('to_move1', d_target.path('default', 'moved1'))
    loop.run(5)


def test_driver_move_dir_not_watched(module_launcher):
    d_target, d_test = module_launcher.get_services('rep1', 'rep2')
    d_target.mkdir('to_move2')
    d_target.generate('to_move2/foo', 10)
    d_target.generate('to_move2/bar', 10)
    d_target.generate('to_move2/lol', 10)

    loop = CounterLoop(3)
    module_launcher.on_transfer_ended(
        loop.check, d_from=d_target, d_to=d_test, filename='moved2/foo'
    )
    module_launcher.on_transfer_ended(
        loop.check, d_from=d_target, d_to=d_test, filename='moved2/bar'
    )
    module_launcher.on_transfer_ended(
        loop.check, d_from=d_target, d_to=d_test, filename='moved2/lol'
    )
    d_target.rename('to_move2', d_target.path('default', 'moved2'))
    loop.run(5)
