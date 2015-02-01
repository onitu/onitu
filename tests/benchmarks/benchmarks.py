import socket
from os import unlink, devnull

import logbook
from logbook.queues import ZeroMQSubscriber

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup
from tests.utils.loop import BooleanLoop, CounterLoop
from tests.utils.driver import LocalStorageDriver
from tests.utils.benchmark import Benchmark, BenchmarkData
from tests.utils.timer import Timer
from tests.utils.units import MB

SMALL = 1 * MB
MEDIUM = 10 * MB
BIG = 100 * MB


FORMAT_STRING = (
    u'[{record.time:%H:%M:%S}] '
    u'{record.level_name}: {record.channel}: {record.message}'
)


# TODO: this function should raise an exception if something is wrong

def setup_debug(benchmark):
    benchmark.tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    benchmark.tmpsock.bind(('localhost', 0))
    benchmark.log_uri = 'tcp://{}:{}'.format(*benchmark.tmpsock.getsockname())
    benchmark.tmpsock.close()
    benchmark.level = logbook.DEBUG if benchmark.verbose else logbook.INFO
    benchmark.log_setup = logbook.NestedSetup([
        logbook.NullHandler(),
        logbook.StderrHandler(
            level=benchmark.level, format_string=FORMAT_STRING
        ),
        logbook.FileHandler(devnull),
        logbook.Processor(benchmark.launcher.process_record),
    ])
    benchmark.subscriber = ZeroMQSubscriber(benchmark.log_uri, multi=True)
    benchmark.subscriber.dispatch_in_background(setup=benchmark.log_setup)
    benchmark.launcher(benchmark.log_uri)


def setup_config(benchmark, num):
    benchmark.json_file = '{}.json'.format(benchmark.name.replace(' ', '_'))
    benchmark.reps = []
    for i in range(num):
        name = 'rep{}'.format(i + 1)
        benchmark.reps.append(LocalStorageDriver(name))
    setup = Setup()
    for rep in benchmark.reps:
        setup.add(rep)
    setup.save(benchmark.json_file)


def launcher(benchmark, num):
    if num < 1:
        benchmark.log.error("You should launch at least 1 driver")
        raise
    benchmark.launcher = None
    setup_config(benchmark, num)
    loop = CounterLoop(num + 1)
    benchmark.launcher = Launcher(
        setup=benchmark.json_file
    )
    benchmark.launcher.on_referee_started(loop.check)
    for i in range(num):
        benchmark.launcher.on_driver_started(
            loop.check,
            driver='rep{}'.format(i + 1)
        )
    setup_debug(benchmark)
    loop.run(timeout=5)


class BenchmarkSimpleCopy(Benchmark):
    def launch_onitu(self):
        launcher(self, 2)

    def stop_onitu(self):
        self.launcher.kill()
        unlink(self.json_file)
        for rep in self.reps:
            rep.close()

    def setup(self):
        self.launch_onitu()

    def teardown(self):
        self.stop_onitu()

    def copy_file(self, filename, size, timeout=10):
        self.launcher.unset_all_events()
        loop = BooleanLoop()
        self.launcher.on_transfer_ended(
            loop.stop, d_to='rep2', filename=filename
        )
        self.reps[0].generate(filename, size)
        with Timer() as t:
            loop.run(timeout=timeout)
        assert (
            self.reps[0].checksum(filename) == self.reps[1].checksum(filename)
        )
        return t.msecs

    def test_small(self):
        total = BenchmarkData('test_small', 'Copy 1000 times a 1M file')
        for i in range(1000):
            try:
                t = self.copy_file('small{}'.format(i), SMALL)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_small')
                self.log.warn(e)
        return total

    def test_medium(self):
        total = BenchmarkData('test_medium', 'Copy 100 times a 10M file')
        for i in range(100):
            try:
                t = self.copy_file('medium{}'.format(i), MEDIUM)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_medium')
                self.log.warn(e)
        return total

    def test_big(self):
        total = BenchmarkData('test_big', 'Copy 10 times a 100M file')
        for i in range(10):
            try:
                t = self.copy_file('big{}'.format(i), BIG)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_big')
                self.log.warn(e)
        return total


class BenchmarkMultipleCopies(Benchmark):
    def launch_onitu(self):
        launcher(self, 3)

    def stop_onitu(self):
        self.launcher.kill()
        unlink(self.json_file)
        for rep in self.reps:
            rep.close()

    def setup(self):
        self.launch_onitu()

    def teardown(self):
        self.stop_onitu()

    def copy_file(self, filename, size, timeout=20):
        self.launcher.unset_all_events()
        loop = CounterLoop(2)
        self.launcher.on_transfer_ended(
            loop.check, d_to='rep2', filename=filename
        )
        self.launcher.on_transfer_ended(
            loop.check, d_to='rep3', filename=filename
        )
        self.reps[0].generate(filename, size)
        with Timer() as t:
            loop.run(timeout=timeout)
        assert (
            self.reps[0].checksum(filename) == self.reps[1].checksum(filename)
        )
        assert (
            self.reps[0].checksum(filename) == self.reps[2].checksum(filename)
        )
        return t.msecs

    def test_small(self):
        total = BenchmarkData('test_small', 'Copy 1000 times a 1M file')
        for i in range(1000):
            try:
                t = self.copy_file('small{}'.format(i), SMALL)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_small')
                self.log.warn(e)
        return total

    def test_medium(self):
        total = BenchmarkData('test_medium', 'Copy 100 times a 10M file')
        for i in range(100):
            try:
                t = self.copy_file('medium{}'.format(i), MEDIUM)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_medium')
                self.log.warn(e)
        return total

    def test_big(self):
        total = BenchmarkData('test_big', 'Copy 10 times a 100M file')
        for i in range(10):
            try:
                t = self.copy_file('big{}'.format(i), BIG)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_big')
                self.log.warn(e)
        return total

if __name__ == '__main__':
    bench_simple = BenchmarkSimpleCopy('BENCH_SIMPLE_COPY', verbose=True)
    bench_simple.run()
    bench_multiple = BenchmarkMultipleCopies(
        'BENCH_MULTIPLE_COPIES',
        verbose=True
    )
    bench_multiple.run()
    print('{:=^28}'.format(' simple copy '))
    bench_simple.display()
    print('{:=^28}'.format(' multiple copies '))
    bench_multiple.display()
