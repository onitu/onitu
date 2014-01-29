import os.path
from os import unlink
from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop, CounterLoop
from utils.files import generate, checksum
from utils.tempdirs import TempDirs
from utils.benchmark import Benchmark
from utils.timer import Timer

launcher = None
dirs = TempDirs()
rep1, rep2 = dirs.create(), dirs.create()
json_file = 'bench_copy.json'


def launch_onitu():
    global launcher
    entries = Entries()
    entries.add('local_storage', 'rep1', {'root': rep1})
    entries.add('local_storage', 'rep2', {'root': rep2})
    entries.save(json_file)
    loop = CounterLoop(3)
    launcher = Launcher(json_file)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    loop.run(timeout=5)


def stop_onitu():
    launcher.kill()
    unlink(json_file)


class BenchmarkSimpleCopy(Benchmark):
    def setup(self):
        launch_onitu()

    def teardown(self):
        stop_onitu()

    def copy_file(self, filename, size, timeout=5):
        loop = BooleanLoop()
        launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        generate(os.path.join(rep1, filename), size)
        with Timer() as t:
            loop.run(timeout=5)
        assert(checksum(os.path.join(rep1, filename)) ==
               checksum(os.path.join(rep2, filename)))
        return t.msecs

    def test_small_copy(self):
        total = 0.
        for i in range(100):
            total += self.copy_file('small{}'.format(i), 100)
        return total

    def test_medium_copy(self):
        total = 0.
        for i in range(10):
            total += self.copy_file('medium{}'.format(i), 1000)
        return total

    def test_big_copy(self):
        self.copy_file('big', 10000)

if __name__ == '__main__':
    bench = BenchmarkSimpleCopy()
    bench.run()
    print bench.get_results()
