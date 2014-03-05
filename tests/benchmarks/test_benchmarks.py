import time
from os import unlink
from random import randint

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup
from tests.utils.loop import BooleanLoop, CounterLoop
from tests.utils.driver import LocalStorageDriver
from tests.utils.benchmark import Benchmark, BenchmarkData
from tests.utils.timer import Timer

SMALL = 1024 * 1024
MEDIUM = SMALL * 10
BIG = MEDIUM * 10


class BenchmarkSimpleCopy(Benchmark):
    def launch_onitu(self):
        self.launcher = None
        self.json_file = 'bench_copy.json'
        self.rep1 = LocalStorageDriver('rep1')
        self.rep2 = LocalStorageDriver('rep2')
        setup = Setup()
        setup.add(*self.rep1.setup)
        setup.add(*self.rep2.setup)
        setup.save(self.json_file)
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
        self.rep1.close()
        self.rep2.close()

    def setup(self):
        self.launch_onitu()

    def teardown(self):
        self.stop_onitu()

    def copy_file(self, filename, size, timeout=10):
        self.launcher.unset_all_events()
        loop = BooleanLoop()
        self.launcher.on_transfer_ended(
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
        )
        self.rep1.generate(filename, size)
        with Timer() as t:
            loop.run(timeout=timeout)
        assert (self.rep1.checksum(filename) == self.rep2.checksum(filename))
        return t.msecs

    def test_small(self):
        total = BenchmarkData('test_small', 'Copy 30 times a 1M file')
        for i in range(30):
            try:
                t = self.copy_file('small{}'.format(i), SMALL)
                total.add_result(t)
            except BaseException as e:
                self._log('Error in test_small')
                self._log(e)
        return total

    def test_medium(self):
        total = BenchmarkData('test_medium', 'Copy 10 times a 10M file')
        for i in range(10):
            try:
                t = self.copy_file('medium{}'.format(i), MEDIUM)
                total.add_result(t)
            except BaseException as e:
                self._log('Error in test_medium')
                self._log(e)
        return total

    def test_big(self):
        total = BenchmarkData('test_big', 'Copy 2 times a 100M file')
        for i in range(2):
            try:
                t = self.copy_file('big{}'.format(i), BIG)
                total.add_result(t)
            except BaseException as e:
                self._log('Error in test_big')
                self._log(e)
        return total


class TestBenchmark(Benchmark):
    def setup(self):
        print('welcome in the global setup')
        self.test = 0

    def test_nosetup(self):
        print('no setup for this test, just a sleep')
        print('this is the test {}'.format(self.test))
        time.sleep(1)

    def setup_withsetup(self):
        print('setup the var test to 3')
        self.test = 3

    def test_withsetup(self):
        print('there is a setup for this test, the test is {}'
              .format(self.test))

    def teardown_withsetup(self):
        print('teardown, reset value of test to 1')
        self.test = 1

    def test_youhou(self):
        test = BenchmarkData('YOUHOU', 'this test launch 30 tests')
        for i in range(30):
            test.add_result(randint(0, 1000))
        return test

    def test_zorglub(self):
        print('eviv bulgroz')
        print('the test is {}'.format(self.test))
        test = BenchmarkData('zorglub', 'this test took 9999 ms')
        test.add_result(9999)
        return test


def test_demo_benchmark():
    t = TestBenchmark()
    t.run()
    print('{:=^28}'.format(' demo benchmark '))
    t.display()


def test_copy_benchmark():
    t = BenchmarkSimpleCopy(verbose=True)
    t.run()
    print('{:=^28}'.format(' copy benchmark '))
    t.display()
