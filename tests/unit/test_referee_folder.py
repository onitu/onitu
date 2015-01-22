from logbook import Logger
from onitu.referee.folder import Folder


def test_init_size():

    f = Folder('folder', {}, Logger(), {})

    assert f._to_bytes(10) == 10
    assert f._to_bytes(15.3) == 15

    assert f._to_bytes(0) == 0
    assert f._to_bytes(None) is None
    assert f._to_bytes('') is None
    assert f._to_bytes('toto') is None
    assert f._to_bytes('2toto') is None

    assert f._to_bytes('10') == 10
    assert f._to_bytes('  10 ') == 10
    assert f._to_bytes('10B') == 10
    assert f._to_bytes('10o') == 10

    assert f._to_bytes('10 000') == 10000
    assert f._to_bytes('10000') == 10000
    assert f._to_bytes(' 10 000') == 10000

    assert f._to_bytes('15k') == 15000
    assert f._to_bytes('15 k') == 15000
    assert f._to_bytes(' 15 k ') == 15000
    assert f._to_bytes('15K') == 15000
    assert f._to_bytes('15ko') == 15000
    assert f._to_bytes('15Kb') == 15000

    assert f._to_bytes('11m') == 11000000
    assert f._to_bytes('11 Mb') == 11000000
    assert f._to_bytes(' 11MB') == 11000000

    assert f._to_bytes('123 456.0 Mo') == 123456000000

    assert f._to_bytes('7.5g') == 7500000000
    assert f._to_bytes('7.5 G') == 7500000000
    assert f._to_bytes('7.5go') == 7500000000
    assert f._to_bytes('7.5 Gb') == 7500000000

    assert f._to_bytes('42t') == 42000000000000
    assert f._to_bytes('42 Tb') == 42000000000000
    assert f._to_bytes('42 to') == 42000000000000

    assert f._to_bytes('3P') == 3000000000000000
    assert f._to_bytes('3 pb') == 3000000000000000
    assert f._to_bytes('3 Po') == 3000000000000000

    assert f._to_bytes('2 Ki') == 2048
    assert f._to_bytes('2ki') == 2048
    assert f._to_bytes('6mi') == 6291456
    assert f._to_bytes('  7  GI') == 7516192768
    assert f._to_bytes('13Ti') == 14293651161088
    assert f._to_bytes('1 000 Pi') == 1125899906842624000


def test_no_size():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {},
            {'filename': '', 'size': val, 'mimetype': ''},
            '')

    assert do_test(0) is True
    assert do_test(42) is True


def test_min_size():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {'file_size': {'min': 1024}},
            {'filename': '', 'size': val, 'mimetype': ''},
            '')

    assert do_test(0) is False
    assert do_test(42) is False
    assert do_test(1023) is False
    assert do_test(1024) is True
    assert do_test(2048) is True


def test_max_size():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {'file_size': {'max': 1024}},
            {'filename': '', 'size': val, 'mimetype': ''},
            '')

    assert do_test(0) is True
    assert do_test(42) is True
    assert do_test(1023) is True
    assert do_test(1024) is True
    assert do_test(2048) is False


def test_min_and_max_size():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {'file_size': {'min': 100, 'max': 200}},
            {'filename': '', 'size': val, 'mimetype': ''},
            '')

    assert do_test(0) is False
    assert do_test(42) is False
    assert do_test(123) is True
    assert do_test(250) is False


def test_no_mimetype():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {},
            {'filename': '', 'size': 0, 'mimetype': val},
            '')

    assert do_test('application/json') is True
    assert do_test('image/png') is True


def test_mimetypes():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {'mimetypes': ['application/json',
                           'image/*',
                           'application/vnd.oasis.opendocument.*',
                           '*/ogg']},
            {'filename': '', 'size': 0, 'mimetype': val},
            '')

    assert do_test('application/json') is True
    assert do_test('application/javascript') is False

    assert do_test('image/jpeg') is True
    assert do_test('image/gif') is True
    assert do_test('image/png') is True
    assert do_test('image/svg+xml') is True

    assert do_test('application/x-iso9660-image') is False
    assert do_test('application/x-msdownload') is False
    assert do_test('application/xml') is False
    assert do_test('text/html') is False
    assert do_test('video/x-msvideo') is False

    assert do_test('application/vnd.oasis.opendocument.spreadsheet') is True
    assert do_test('application/vnd.oasis.opendocument.text') is True
    assert do_test('application/msword') is False
    assert do_test('application/vnd.openxmlformats-'
                   'officedocument.wordprocessingml.document') is False
    assert do_test('application/vnd.ms-excel') is False

    assert do_test('audio/ogg') is True
    assert do_test('video/ogg') is True
    assert do_test('audio/x-flac') is False
    assert do_test('audio/mpeg') is False
    assert do_test('video/mpeg') is False


def test_no_blacklist():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {},
            {'filename': val, 'size': 0, 'mimetype': ''},
            '')

    assert do_test('foo.jpg') is True


def test_blacklist():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {'blacklist': ['foo.jpg',
                           'dir/*',
                           '*.mp3',
                           't?t?']},
            {'filename': val, 'size': 0, 'mimetype': ''},
            '')

    assert do_test('foo.jpg') is False
    assert do_test('foo.png') is True

    assert do_test('dir/bar') is False
    assert do_test('dir') is True

    assert do_test('bar.mp3') is False
    assert do_test('foo/bar/lol.mp3') is False

    assert do_test('toto') is False
    assert do_test('titi') is False
    assert do_test('tuto') is False
    assert do_test('tototo') is True


def test_no_whitelist():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {},
            {'filename': val, 'size': 0, 'mimetype': ''},
            '')

    assert do_test('foo.jpg') is True


def test_whitelist():
    f = Folder('folder', {}, Logger(), {})

    def do_test(val):
        return f.assert_options(
            {'whitelist': ['foo.jpg',
                           'dir/*',
                           '*.mp3',
                           't?t?']},
            {'filename': val, 'size': 0, 'mimetype': ''},
            '')

    assert do_test('foo.jpg') is True
    assert do_test('foo.png') is False

    assert do_test('dir/bar') is True
    assert do_test('dir') is False

    assert do_test('bar.mp3') is True
    assert do_test('foo/bar/lol.mp3') is True

    assert do_test('toto') is True
    assert do_test('titi') is True
    assert do_test('tuto') is True
    assert do_test('tototo') is False
