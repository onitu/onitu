# -*- coding: utf-8 -*-

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import TestingDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop

launcher, setup = None, None
rep1, rep2 = TestingDriver(u'®ép1'), TargetDriver(u'®èp2')


def setup_module(module):
    global launcher, setup
    setup = Setup()
    setup.name += u'¡æəˇ'
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
    launcher = Launcher(setup)
    launcher()


def teardown_module(module):
    launcher.close()


def copy_file(filename, source, target):
    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from=source.name, d_to=target.name, filename=filename
    )
    source.generate(filename, 1)
    loop.run(timeout=10)
    assert source.exists(filename)
    assert target.exists(filename)


def delete_file(filename, source, target):
    copy_file(filename, source, target)

    loop = CounterLoop(2)
    launcher.on_file_deleted(
        loop.check, driver=source.name, filename=filename
    )
    launcher.on_deletion_completed(
        loop.check, driver=target.name, filename=filename
    )
    source.unlink(filename)
    loop.run(timeout=5)
    assert not source.exists(filename)
    assert not target.exists(filename)


def move_file(filename, dest, source, target):
    copy_file(filename, source, target)

    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver=source.name, src=filename, dest=dest
    )
    launcher.on_move_completed(
        loop.check, driver=target.name, src=filename, dest=dest
    )
    source.rename(filename, dest)
    loop.run(timeout=5)
    assert not source.exists(filename)
    assert not target.exists(filename)
    assert source.exists(dest)
    assert target.exists(dest)


def test_copy_from_rep1():
    copy_file(u'ùñï©∅ð€ 1', rep1, rep2)


def test_copy_from_rep2():
    copy_file(u'ùñï©∅ð€ 2', rep2, rep1)


def test_delete_from_rep1():
    delete_file(u'ùñï©∅ð€ 3', rep1, rep2)


def test_delete_from_rep2():
    delete_file(u'ùñï©∅ð€ 4', rep1, rep2)


def test_move_from_rep1():
    move_file(u'ùñï©∅ð€ 5', u'mºˇ€Ð 1', rep1, rep2)


def test_move_from_rep2():
    move_file(u'ùñï©∅ð€ 6', u'mºˇ€Ð 2', rep2, rep1)
