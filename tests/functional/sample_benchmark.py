import time
from random import randint
from utils.benchmark import Benchmark, BenchmarkData


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

if __name__ == '__main__':
    t = TestBenchmark()
    t.run()
    t.display()
    print(t.get_results())
