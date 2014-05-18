import time
from random import randint

from tests.utils.benchmark import Benchmark, BenchmarkData


class TestBenchmark(Benchmark):
    def setup(self):
        print('welcome in the global setup')
        self.test = 0

    def test_nosetup(self):
        """This test should take more than 1 second and print 0"""
        print('no setup for this test, just a sleep')
        print('this is the test {}'.format(self.test))
        time.sleep(1)

    def setup_withsetup(self):
        print('setup the var test to 3')
        self.test = 3

    def test_withsetup(self):
        """This test should print 3"""
        print('there is a setup for this test, the test is {}'
              .format(self.test))
        test = BenchmarkData('withsetup', 'This test should carry the value 3')
        test.add_result(self.test)
        return test

    def teardown_withsetup(self):
        print('teardown, reset value of test to 9999')
        self.test = 9999

    def test_loop(self):
        """Generate 30 values between 0 and 1000 and feed the
        benchmark with the values."""
        test = BenchmarkData('Loop', 'this test launch 30 tests')
        for i in range(30):
            test.add_result(randint(0, 1000))
        return test

    def test_zorglub(self):
        print('eviv bulgroz')
        print('the test is {}'.format(self.test))
        test = BenchmarkData(
            'zorglub',
            'this test took 9999 days',
            unit='days'
        )
        test.add_result(self.test)
        return test


def test_benchmark():
    t = TestBenchmark('TestBenchmark', verbose=True)
    t.run()
    print('{:=^28}'.format(' Test benchmark '))
    t.display()
    results = t.get_results()
    nosetup = results['test_nosetup']
    withsetup = results['test_withsetup']
    loop = results['test_loop']
    zorglub = results['test_zorglub']
    assert(len(nosetup['results']) == 1)
    assert(nosetup['results'][0] >= 1000.)
    assert(nosetup['desc'] is None)
    assert(nosetup['unit'] == 'ms')
    assert(withsetup['results'][0] == 3)
    assert(len(loop['results']) == 30)
    for r in loop['results']:
        assert(r >= 0 and r <= 1000)
    assert(zorglub['desc'] == 'this test took 9999 days')
    assert(zorglub['results'][0] == 9999)
    assert(zorglub['unit'] == 'days')
