from onitu.referee.folder import Folder


def check_size(size, length):
        folder = Folder('folder', (), None,
                        file_size={'min': size, 'max': size})
        assert folder.min_size == length
        assert folder.max_size == length


def test_init_size():
    check_size(10, 10)
    check_size(15.3, 15)

    check_size(0, 0)
    check_size(None, None)
    check_size('', None)
    check_size('toto', None)
    check_size('2toto', None)

    check_size('10', 10)
    check_size('  10 ', 10)
    check_size('10B', 10)
    check_size('10o', 10)

    check_size('10 000', 10000)
    check_size('10000', 10000)
    check_size(' 10 000', 10000)

    check_size('15k', 15000)
    check_size('15 k', 15000)
    check_size(' 15 k ', 15000)
    check_size('15K', 15000)
    check_size('15ko', 15000)
    check_size('15Kb', 15000)

    check_size('11m', 11000000)
    check_size('11 Mb', 11000000)
    check_size(' 11MB', 11000000)

    check_size('123 456.0 Mo', 123456000000)

    check_size('7.5g', 7500000000)
    check_size('7.5 G', 7500000000)
    check_size('7.5go', 7500000000)
    check_size('7.5 Gb', 7500000000)

    check_size('42t', 42000000000000)
    check_size('42 Tb', 42000000000000)
    check_size('42 to', 42000000000000)

    check_size('3P', 3000000000000000)
    check_size('3 pb', 3000000000000000)
    check_size('3 Po', 3000000000000000)

    check_size('2 Ki', 2048)
    check_size('2ki', 2048)
    check_size('6mi', 6291456)
    check_size('  7  GI', 7516192768)
    check_size('13Ti', 14293651161088)
    check_size('1 000 Pi', 1125899906842624000)


def test_no_size():
    folder = Folder('folder', (), None, file_size=None)

    assert folder.check_size(0) is True
    assert folder.check_size(42) is True


def test_min_size():
    folder = Folder('folder', (), None,
                    file_size={'min': 1024})

    assert folder.check_size(0) is False
    assert folder.check_size(42) is False
    assert folder.check_size(1023) is False
    assert folder.check_size(1024) is True
    assert folder.check_size(2048) is True


def test_max_size():
    folder = Folder('folder', (), None,
                    file_size={'max': 1024})

    assert folder.check_size(0) is True
    assert folder.check_size(42) is True
    assert folder.check_size(1023) is True
    assert folder.check_size(1024) is True
    assert folder.check_size(2048) is False


def test_min_and_max_size():
    folder = Folder('folder', (), None,
                    file_size={'min': 100, 'max': 200})

    assert folder.check_size(0) is False
    assert folder.check_size(42) is False
    assert folder.check_size(123) is True
    assert folder.check_size(250) is False


def test_no_mimetype():
    folder = Folder('folder', (), None, mimetypes=None)

    assert folder.check_mimetype('application/json') is True
    assert folder.check_mimetype('image/png') is True


def test_mimetypes():
    folder = Folder('folder', (), None, mimetypes=(
        'application/json',
        'image/*',
        'application/vnd.oasis.opendocument.*',
        '*/ogg',
    ))

    assert folder.check_mimetype('application/json') is True
    assert folder.check_mimetype('application/javascript') is False

    assert folder.check_mimetype('image/jpeg') is True
    assert folder.check_mimetype('image/gif') is True
    assert folder.check_mimetype('image/png') is True
    assert folder.check_mimetype('image/svg+xml') is True

    assert folder.check_mimetype('application/x-iso9660-image') is False
    assert folder.check_mimetype('application/x-msdownload') is False
    assert folder.check_mimetype('application/xml') is False
    assert folder.check_mimetype('text/html') is False
    assert folder.check_mimetype('video/x-msvideo') is False

    assert folder.check_mimetype(
        'application/vnd.oasis.opendocument.spreadsheet') is True
    assert folder.check_mimetype(
        'application/vnd.oasis.opendocument.text') is True
    assert folder.check_mimetype('application/msword') is False
    assert folder.check_mimetype(
        'application/vnd.openxmlformats-'
        'officedocument.wordprocessingml.document') is False
    assert folder.check_mimetype('application/vnd.ms-excel') is False

    assert folder.check_mimetype('audio/ogg') is True
    assert folder.check_mimetype('video/ogg') is True
    assert folder.check_mimetype('audio/x-flac') is False
    assert folder.check_mimetype('audio/mpeg') is False
    assert folder.check_mimetype('video/mpeg') is False
