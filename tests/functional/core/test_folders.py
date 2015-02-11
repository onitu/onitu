from tests.utils.testdriver import TestDriver
from tests.utils.loop import BooleanLoop


def test_folders(setup, launcher):
    A = TestDriver('A', folders={
        'foo': 'foo',
        'lol': 'lol',
        'bar': 'bar',
    })
    B = TestDriver('B', folders={
        'foo': 'Foo',
        'lol': 'Lol'
    })
    C = TestDriver('C', folders={
        'foo': 'foo',
        'bar': 'bar'
    })

    setup.add(A)
    setup.add(B)
    setup.add(C)

    try:
        launcher()

        launcher.copy_file('foo', 'test1', 10, A, B, C)
        launcher.copy_file('bar', 'test2', 10, C, A)
        launcher.copy_file('lol', 'test3', 10, B, A)

        launcher.move_file('foo', 'test1', 'moved1', B, A, C)
        launcher.move_file('bar', 'test2', 'moved2', A, C)
        launcher.move_file('lol', 'test3', 'moved3', A, B)

        launcher.delete_file('foo', 'moved1', A, B, C)
        launcher.delete_file('bar', 'moved2', A, C)
        launcher.delete_file('lol', 'moved3', B, A)
    finally:
        launcher.close()


def test_mode(setup, launcher):
    R = TestDriver('R', folders={'dir': {'path': 'dir', 'mode': 'r'}})
    W = TestDriver('W', folders={'dir': {'path': 'dir', 'mode': 'w'}})
    RW = TestDriver('RW', folders={'dir': {'path': 'dir', 'mode': 'rw'}})

    setup.folders = {'dir': {}}

    setup.add(R)
    setup.add(W)
    setup.add(RW)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.copy_file('dir', 'test1', 10, R, W, RW)
        launcher.copy_file('dir', 'test2', 10, RW, W)

        loop.restart()

        launcher.on_event_source_ignored_mode(
            loop.stop, service='W', folder='dir', filename='test3', mode='w'
        )
        launcher.copy_file('dir', 'test3', 10, W)

        loop.run(timeout=1)
        loop.restart()

        launcher.on_event_service_ignored_mode(
            loop.stop, service='R', folder='dir', filename='test4', mode='r'
        )
        launcher.copy_file('dir', 'test4', 10, RW, W)

        loop.run(timeout=1)
    finally:
        launcher.close()


def test_size(setup, launcher):
    A = TestDriver('A', folders={
        'dir': 'dir',
    })
    B = TestDriver('B', folders={
        'dir': 'dir',
    })

    setup.folders = {
        'dir': {
            'file_size': {
                'min': 3,
                'max': 10
            }
        }
    }
    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.on_event_folder_ignored_size(
            loop.stop, folder='dir', filename='test1', size=1
        )
        launcher.copy_file('dir', 'test1', 1, A)
        loop.run(timeout=1)

        launcher.copy_file('dir', 'test3', 5, A, B)
        launcher.copy_file('dir', 'test4', 10, A, B)

        loop.restart()
        launcher.on_event_folder_ignored_size(
            loop.stop, folder='dir', filename='test5', size=11
        )
        launcher.copy_file('dir', 'test5', 11, A)
        loop.run(timeout=1)

        loop.restart()
        launcher.on_event_folder_ignored_size(
            loop.stop, folder='dir', filename='test6', size=12
        )
        launcher.copy_file('dir', 'test6', 12, A)
        loop.run(timeout=1)
    finally:
        launcher.close()


def test_blacklist(setup, launcher):
    A = TestDriver('A', folders={
        'dir': 'dir',
    })
    B = TestDriver('B', folders={
        'dir': 'dir',
    })

    setup.folders = {
        'dir': {
            'blacklist': [
                'foo/*',
            ],
        }
    }

    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.on_event_folder_ignored_blacklisted(
            loop.stop, folder='dir', filename='foo/test'
        )
        launcher.copy_file('dir', 'foo/test', 10, A)
        loop.run(timeout=1)

        launcher.copy_file('dir', 'foo', 10, A, B)
        launcher.copy_file('dir', 'toto', 10, A, B)
    finally:
        launcher.close()


def test_whitelist(setup, launcher):
    A = TestDriver('A', folders={
        'dir': 'dir',
    })
    B = TestDriver('B', folders={
        'dir': 'dir',
    })

    setup.folders = {
        'dir': {
            'whitelist': [
                'foo/*',
            ],
        }
    }

    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.copy_file('dir', 'foo/test', 10, A, B)

        launcher.on_event_folder_ignored_not_whitelisted(
            loop.stop, folder='dir', filename='foo'
        )
        launcher.copy_file('dir', 'foo', 10, A)
        loop.run(timeout=1)

        launcher.on_event_folder_ignored_not_whitelisted(
            loop.stop, folder='dir', filename='toto'
        )
        launcher.copy_file('dir', 'toto', 10, A)
        loop.run(timeout=1)
    finally:
        launcher.close()


def test_mimetypes(setup, launcher):
    A = TestDriver('A', folders={
        'dir': 'dir',
    })
    B = TestDriver('B', folders={
        'dir': 'dir',
    })

    setup.folders = {
        'dir': {
            'mimetypes': [
                'application/json',
            ],
        }
    }

    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.copy_file('dir', 'test.json', 10, A, B)

        launcher.on_event_folder_ignored_mimetype(
            loop.stop, folder='dir', filename='test.js',
            mimetype='application/javascript'
        )
        launcher.copy_file('dir', 'test.js', 10, A)
        loop.run(timeout=1)
    finally:
        launcher.close()


def test_rename(setup, launcher):
    A = TestDriver('A', folders={
        'dir': 'dir',
    })
    B = TestDriver('B', folders={
        'dir': 'dir',
    })

    setup.folders = {
        'dir': {
            'blacklist': [
                'foo/*',
            ],
        }
    }

    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.on_event_folder_ignored_blacklisted(
            loop.stop, folder='dir', filename='foo/test'
        )
        launcher.copy_file('dir', 'foo/test', 10, A)
        loop.run(timeout=1)

        loop = BooleanLoop()
        launcher.on_transfer_ended(loop.stop, d_to=B, filename='bar/test')
        A.rename(A.path('dir', 'foo/test'), B.path('dir', 'bar/test'))
        loop.run(1)

        assert not A.exists(A.path('dir', 'foo/test'))
        assert not B.exists(B.path('dir', 'foo/test'))
        assert A.exists(A.path('dir', 'bar/test'))
        assert B.exists(B.path('dir', 'bar/test'))
    finally:
        launcher.close()


def test_update_size_from_source(setup, launcher):
    A = TestDriver('A', folders={
        'dir': 'dir',
    })
    B = TestDriver('B', folders={
        'dir': 'dir',
    })

    setup.folders = {
        'dir': {
            'file_size': {
                'min': 5,
            }
        }
    }
    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.on_event_folder_ignored_size(
            loop.stop, folder='dir', filename='test', size=3
        )
        launcher.copy_file('dir', 'test', 3, A)
        loop.run(timeout=1)

        launcher.copy_file('dir', 'test', 10, A, B)
    finally:
        launcher.close()


def test_update_size_from_other_service(setup, launcher):
    A = TestDriver('A', folders={
        'dir': 'dir',
    })
    B = TestDriver('B', folders={
        'dir': 'dir',
    })

    setup.folders = {
        'dir': {
            'file_size': {
                'min': 5,
            }
        }
    }
    setup.add(A)
    setup.add(B)

    try:
        launcher()

        loop = BooleanLoop()

        launcher.on_event_folder_ignored_size(
            loop.stop, folder='dir', filename='test', size=3
        )
        launcher.copy_file('dir', 'test', 3, A)
        loop.run(timeout=1)

        launcher.copy_file('dir', 'test', 10, B, A)
    finally:
        launcher.close()


def test_move_to_another_folder(setup, launcher):
    A = TestDriver('A', folders={
        'foo': 'foo',
        'bar': 'bar',
    })
    B = TestDriver('B', folders={
        'foo': 'Foo',
        'bar': 'Bar'
    })

    setup.add(A)
    setup.add(B)

    try:
        launcher()

        launcher.copy_file('foo', 'test', 10, A, B)

        loop = BooleanLoop()
        launcher.on_move_completed(
            loop.stop, driver=B, src='test', dest='test'
        )
        A.rename('foo/test', 'bar/test')
        loop.run()
    finally:
        launcher.close()


def test_move_to_non_existing_folder(setup, launcher):
    A = TestDriver('A', folders={
        'foo': 'foo',
    })
    B = TestDriver('B', folders={
        'foo': 'Foo',
    })

    setup.add(A)
    setup.add(B)

    try:
        launcher()

        launcher.copy_file('foo', 'test', 10, A, B)

        loop = BooleanLoop()
        launcher.on_deletion_completed(
            loop.stop, driver=B, filename='test'
        )
        A.rename('foo/test', 'bar/test')
        loop.run()
    finally:
        launcher.close()
