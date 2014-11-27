from tests.utils.loop import BooleanLoop, CounterLoop
from tests.utils.targetdriver import TargetDriver, if_feature


def copy_file(launcher, filename, size, src, dest):
    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from=src.name, d_to=dest.name, filename=filename
    )
    src.generate(filename, size)
    loop.run(timeout=10)
    assert dest.exists(filename)


def init_file(launcher, filename, size, src, dest):
    if isinstance(src, TargetDriver):
        d_target, d_test = src, dest
    else:
        d_test, d_target = dest, src

    if if_feature.copy_file_from_onitu:
        copy_file(launcher, filename, size, d_test, d_target)
    else:
        copy_file(launcher, filename, size, d_target, d_test)


def delete_file(launcher, filename, size, src, dest):
    init_file(launcher, filename, size, src, dest)
    loop = CounterLoop(2)
    launcher.on_file_deleted(
        loop.check, driver=src.name, filename=filename
    )
    launcher.on_deletion_completed(
        loop.check, driver=dest.name, filename=filename
    )
    src.unlink(filename)
    loop.run(timeout=5)
    assert not dest.exists(filename)


def move_file(launcher, old_filename, new_filename, size, src, dest):
    init_file(launcher, old_filename, size, src, dest)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver=src.name, src=old_filename, dest=new_filename
    )
    launcher.on_move_completed(
        loop.check, driver=dest.name, src=old_filename, dest=new_filename
    )
    src.rename(old_filename, new_filename)
    loop.run(timeout=5)
    assert not dest.exists(old_filename)
    assert dest.exists(new_filename)
    assert src.checksum(new_filename) == dest.checksum(new_filename)
