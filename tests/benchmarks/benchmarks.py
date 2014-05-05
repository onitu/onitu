import socket
from os import unlink

import logbook
from logbook.queues import ZeroMQSubscriber

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.loop import BooleanLoop, CounterLoop
from tests.utils.driver import LocalStorageDriver
from tests.utils.benchmark import Benchmark, BenchmarkData
from tests.utils.timer import Timer
from tests.utils.files import MB

SMALL = 1 * MB
MEDIUM = 10 * MB
BIG = 100 * MB


FORMAT_STRING = (
    u'[{record.time:%H:%M:%S}] '
    u'{record.level_name}: {record.channel}: {record.message}'
)


# TODO: this function should raise an exception if something is wrong
def launcher(benchmark, num):
    if num < 1:
        benchmark.log.error("You should launch at least 1 driver")
        raise
    benchmark.launcher = None
    benchmark.json_file = 'bench_copy.json'
    benchmark.reps = []
    for i in range(num):
        name = 'rep{}'.format(i + 1)
        benchmark.reps.append(LocalStorageDriver(name))
    setup = Setup()
    for rep in benchmark.reps:
        setup.add(rep)
    rule = Rule().match_path('/')
    for rep in benchmark.reps:
        rule.sync(rep.name)
    setup.add_rule(rule)
    setup.save(benchmark.json_file)
    loop = CounterLoop(num + 1)
    benchmark.launcher = Launcher(
        setup=benchmark.json_file
        # log_setup=benchmark.log_setup,
        # log_uri=None
        # log_uri=benchmark.log_uri
    )
    benchmark.launcher.on_referee_started(loop.check)
    for i in range(num):
        benchmark.launcher.on_driver_started(
            loop.check,
            driver='rep{}'.format(i + 1)
        )
    benchmark.launcher()
    loop.run(timeout=5)


def process_record(record):
    print ("toto")
    print (record)


def get_log_uri():
        tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmpsock.bind(('localhost', 0))
        log_uri = 'tcp://{}:{}'.format(*tmpsock.getsockname())
        tmpsock.close()
        return log_uri


def get_log_setup(debug=False):
        level = logbook.DEBUG if debug else logbook.INFO
        log_setup = logbook.NestedSetup([
            logbook.NullHandler(),
            logbook.StderrHandler(
                level=level, format_string=FORMAT_STRING
            ),
            # logbook.Processor(None),
        ])
        return log_setup


class BenchmarkSimpleCopy(Benchmark):
    def launch_onitu(self):
        self.tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tmpsock.bind(('localhost', 0))
        self.log_uri = 'tcp://{}:{}'.format(*self.tmpsock.getsockname())
        self.tmpsock.close()
        # self.log_uri = get_log_uri()
        self.log_setup = get_log_setup(self.debug)
        self.subscriber = ZeroMQSubscriber(self.log_uri, multi=True)
        self.subscriber.dispatch_in_background(setup=self.log_setup)
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
            loop.stop, d_from='rep1', d_to='rep2', filename=filename
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
        for i in range(10):
            try:
                t = self.copy_file('small{}'.format(i), SMALL)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_small')
                self.log.warn(e)
        return total

    # def test_medium(self):
    #     total = BenchmarkData('test_medium', 'Copy 100 times a 10M file')
    #     for i in range(100):
    #         try:
    #             t = self.copy_file('medium{}'.format(i), MEDIUM)
    #             total.add_result(t)
    #         except BaseException as e:
    #             self.log.warn('Error in test_medium')
    #             self.log.warn(e)
    #     return total

    # def test_big(self):
    #     total = BenchmarkData('test_big', 'Copy 10 times a 100M file')
    #     for i in range(10):
    #         try:
    #             t = self.copy_file('big{}'.format(i), BIG)
    #             total.add_result(t)
    #         except BaseException as e:
    #             self.log.warn('Error in test_big')
    #             self.log.warn(e)
    #     return total


class BenchmarkMultipleCopies(Benchmark):
    def launch_onitu(self):
        self.launcher = None
        self.json_file = 'bench_multiple_copy.json'
        self.rep1 = LocalStorageDriver('rep1')
        self.rep2 = LocalStorageDriver('rep2')
        self.rep3 = LocalStorageDriver('rep3')
        setup = Setup()
        setup.add(self.rep1)
        setup.add(self.rep2)
        setup.add(self.rep3)
        setup.save(self.json_file)
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
        self.rep1.close()
        self.rep2.close()
        self.rep3.close()

    def setup(self):
        self.launch_onitu()

    def teardown(self):
        self.stop_onitu()

    def copy_file(self, filename, size, timeout=20):
        self.launcher.unset_all_events()
        loop = BooleanLoop()
        loop = CounterLoop(2)
        self.launcher.on_transfer_ended(
            loop.check, d_from='rep1', d_to='rep2', filename=filename
        )
        self.launcher.on_transfer_ended(
            loop.check, d_from='rep1', d_to='rep3', filename=filename
        )
        self.rep1.generate(filename, size)
        with Timer() as t:
            loop.run(timeout=timeout)
        assert self.rep1.checksum(filename) == self.rep2.checksum(filename)
        assert self.rep1.checksum(filename) == self.rep3.checksum(filename)
        return t.msecs

    def test_small(self):
        total = BenchmarkData('test_small', 'Copy 1000 times a 1M file')
        for i in range(1000):
            try:
                t = self.copy_file('small', SMALL)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_small')
                self.log.warn(e)
        return total

    def test_medium(self):
        total = BenchmarkData('test_medium', 'Copy 100 times a 10M file')
        for i in range(100):
            try:
                t = self.copy_file('medium', MEDIUM)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_medium')
                self.log.warn(e)
        return total

    def test_big(self):
        total = BenchmarkData('test_big', 'Copy 10 times a 100M file')
        for i in range(10):
            try:
                t = self.copy_file('big', BIG)
                total.add_result(t)
            except BaseException as e:
                self.log.warn('Error in test_big')
                self.log.warn(e)
        return total

if __name__ == '__main__':
    bench_simple = BenchmarkSimpleCopy('Bench simple copy', verbose=True)
    bench_simple.run()
    # bench_multiple = BenchmarkMultipleCopies(
    #     'Bench multiple copies',
    #     verbose=True
    # )
    # bench_multiple.run()
    print('{:=^28}'.format(' simple copy '))
    bench_simple.display()
    # print('{:=^28}'.format(' multiple copy '))
    # bench_multiple.display()
