import os.path
from os import unlink
from sys import argv
from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop, CounterLoop
from utils.files import generate, checksum
from utils.tempdirs import TempDirs
from utils.benchmark import Benchmark
from utils.timer import Timer

SMALL = 1024 * 1024
MEDIUM = SMALL * 10
BIG = MEDIUM * 10


class BenchmarkSimpleCopy(Benchmark):
    def launch_onitu(self):
        self.launcher = None
        self.json_file = 'bench_copy.json'
        self.dirs = TempDirs()
        self.rep1, self.rep2 = self.dirs.create(), self.dirs.create()
        entries = Entries()
        entries.add('local_storage', 'rep1', {'root': self.rep1})
        entries.add('local_storage', 'rep2', {'root': self.rep2})
        entries.save(self.json_file)
        loop = CounterLoop(3)
        self.launcher = Launcher(self.json_file)
        self.launcher.on_referee_started(loop.check)
        self.launcher.on_driver_started(loop.check, driver='rep1')
        self.launcher.on_driver_started(loop.check, driver='rep2')
        self.launcher()
        loop.run(timeout=5)

    def stop_onitu(self):
        self.launcher.kill()
        unlink(self.json_file)

    def setup(self):
        self.launch_onitu()

    def teardown(self):
        self.stop_onitu()

    def copy_file(self, filename, size, timeout=5):
        loop = BooleanLoop()
        self.launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        generate(os.path.join(self.rep1, filename), size)
        with Timer() as t:
            loop.run(timeout=5)
        assert(checksum(os.path.join(self.rep1, filename)) ==
               checksum(os.path.join(self.rep2, filename)))
        return t.msecs

    def test_small(self):
        total = 0.
        for i in range(1000):
            total += self.copy_file('small', SMALL)
        return total

    def test_medium(self):
        total = 0.
        for i in range(100):
            total += self.copy_file('medium', MEDIUM)
        return total

    def test_big(self):
        total = 0.
        for i in range(10):
            self.copy_file('big', BIG)
        return total


class BenchmarkMultipleCopy(Benchmark):
    def launch_onitu(self):
        self.launcher = None
        self.json_file = 'bench_multiple_copy.json'
        self.dirs = TempDirs()
        self.rep1 = self.dirs.create()
        self.rep2 = self.dirs.create()
        self.rep3 = self.dirs.create()
        entries = Entries()
        entries.add('local_storage', 'rep1', {'root': self.rep1})
        entries.add('local_storage', 'rep2', {'root': self.rep2})
        entries.add('local_storage', 'rep3', {'root': self.rep3})
        entries.save(self.json_file)
        loop = CounterLoop(4)
        self.launcher = Launcher(self.json_file)
        self.launcher.on_referee_started(loop.check)
        self.launcher.on_driver_started(loop.check, driver='rep1')
        self.launcher.on_driver_started(loop.check, driver='rep2')
        self.launcher.on_driver_started(loop.check, driver='rep3')
        self.launcher()
        loop.run(timeout=5)

    def stop_onitu(self):
        self.launcher.kill()
        unlink(self.json_file)

    def setup(self):
        self.launch_onitu()

    def teardown(self):
        self.stop_onitu()

    def copy_file(self, filename, size, timeout=5):
        loop = CounterLoop(2)
        self.launcher.on_transfer_ended(
            loop.check, d_from='rep1', d_to='rep2', filename=filename
        )
        self.launcher.on_transfer_ended(
            loop.check, d_from='rep1', d_to='rep3', filename=filename
        )
        generate(os.path.join(self.rep1, filename), size)
        with Timer() as t:
            loop.run(timeout=5)
        assert(checksum(os.path.join(self.rep1, filename)) ==
               checksum(os.path.join(self.rep2, filename)))
        assert(checksum(os.path.join(self.rep1, filename)) ==
               checksum(os.path.join(self.rep3, filename)))
        return t.msecs

    def test_small(self):
        total = 0.
        for i in range(1000):
            total += self.copy_file('small', SMALL)
        return total

    def test_medium(self):
        total = 0.
        for i in range(100):
            total += self.copy_file('medium', MEDIUM)
        return total

    def test_big(self):
        total = 0.
        for i in range(10):
            self.copy_file('big', BIG)
        return total

if __name__ == '__main__':
    bench_simple = BenchmarkSimpleCopy(verbose=True)
    bench_simple.run()
    bench_multiple = BenchmarkMultipleCopy(verbose=True)
    bench_multiple.run()
    print(('{:=^28}'.format(' simple copy ')))
    bench_simple.display()
    print(('{:=^28}'.format(' multiple copy ')))
    bench_multiple.display()
    if len(argv) >= 7 and argv[1] in ('-u', '--upload'):
        host = argv[2]
        environment = argv[3]
        project = argv[4]
        commitid = argv[5]
        branch = argv[6]
        bench_simple.upload_results(
            'copy single destination',
            host,
            environment,
            project,
            commitid,
            branch
        )
        bench_multiple.upload_results(
            'copy mutiple destinations',
            host,
            environment,
            project,
            commitid,
            branch
        )
