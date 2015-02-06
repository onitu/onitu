from circus.client import CircusClient

from onitu.utils import get_circusctl_endpoint

from tests.utils.testdriver import TestDriver
from tests.utils.loop import BooleanLoop, CounterLoop


def test_abort_if_no_source(setup, launcher):
    A = TestDriver('A', speed_bump=True)
    B = TestDriver('B', speed_bump=True)

    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.on_transfer_started(loop.stop, d_to='B', filename='test')

        A.generate(A.path('default', 'test'), 20)

        loop.run(timeout=1)

        A.unlink(A.path('default', 'test'), notify=False)

        loop.restart()
        launcher.on_transfer_aborted(loop.stop, d_to='B', filename='test')
        loop.run(timeout=10)
    finally:
        launcher.close()


def test_work_if_secondary_source(setup, launcher):
    A = TestDriver('A')
    B = TestDriver('B', speed_bump=True)
    C = TestDriver('C')

    setup.add(A)
    setup.add(B)
    setup.add(C)

    circus = CircusClient(endpoint=get_circusctl_endpoint(setup.name))

    try:
        launcher()

        circus.call({
            'command': "stop",
            'properties': {
                'name': 'B',
                'waiting': True
            }
        })

        launcher.copy_file('default', 'test', 20, A, C)

        loop = BooleanLoop()

        launcher.on_transfer_started(loop.stop, d_to='B', filename='test')

        circus.call({
            'command': "start",
            'properties': {
                'name': 'B',
                'waiting': True
            }
        })

        loop.run(timeout=1)

        A.unlink(A.path('default', 'test'), notify=False)

        loop.restart()
        launcher.on_transfer_ended(loop.stop, d_to='B', filename='test')
        loop.run(timeout=10)
    finally:
        launcher.close()


def test_velocity(setup, launcher):
    A = TestDriver('A', velocity=0.1)
    B = TestDriver('B', velocity=0.4)
    C = TestDriver('C', velocity=0.8)
    D = TestDriver('D', velocity=0.7)

    setup.add(A)
    setup.add(B)
    setup.add(C)
    setup.add(D)

    circus = CircusClient(endpoint=get_circusctl_endpoint(setup.name))

    try:
        launcher()

        circus.call({
            'command': "stop",
            'properties': {
                'name': 'A',
                'waiting': True
            }
        })

        launcher.copy_file('default', 'test', 20, B, C, D)

        loop = CounterLoop(2)

        launcher.on_source_selected(loop.check, source='C')
        launcher.on_transfer_ended(loop.check, d_to='A', filename='test')

        circus.call({
            'command': "start",
            'properties': {
                'name': 'A',
                'waiting': True
            }
        })

        loop.run(timeout=2)
    finally:
        launcher.close()
