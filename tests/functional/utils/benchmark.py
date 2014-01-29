from timer import Timer


class Benchmark():
    def __init__(self,
                 prefix='test_',
                 each=1,
                 num_format='%.4g',
                 verbose=False
                 ):
        self._prefix = prefix
        self._each = each
        self._num_format = num_format
        self._results = {}

    def _log(self, msg):
        if self._verbose:
            print (msg)

    def run(self):
        """All functions whose name starts with prefix.
        Run setup at the beginning of the run.
        Run setup_each at the beginning of each test.
        Run teardown at the end of the tests.
        """
        try:
            self._run_function('setup')
            tests = self._collect_tests()
            for t in tests:
                self._run_test(t)
        finally:
            self._run_function('teardown')

    def _run_function(self, name):
        try:
            return getattr(self, name)()
        except:
            pass

    def _run_test(self, name):
        setup_test = name.replace(self._prefix, 'setup_')
        teardown_test = name.replace(self._prefix, 'teardown_')
        self._run_function(setup_test)
        try:
            with Timer() as t:
                res = self._run_function(name)
            duration = res if res else t.msecs
            self._results[name] = duration
        except Exception as e:
            self._log('The test is skipped because it raised an exception')
            self._log(e)
        finally:
            self._run_function(teardown_test)

    def _collect_tests(self):
        return [t for t in dir(self) if t.startswith(self._prefix)]

    def display(self):
        pass

    def upload_results(self):
        """upload the results to a codespeed instance
        Https://github.com/tobami/codespeed/
        """
        pass

    def get_results(self):
        """return a dictionnary with the results of all tests.
        The key is the test's name and the value is the time.
        """
        return self._results

if __name__ == '__main__':
    import time

    class TestBenchmark(Benchmark):
        def setup(self):
            print ('welcome in the global setup')
            self.test = 0

        def test_nosetup(self):
            print ('no setup for this test, just a sleep')
            print ('this is the test {}'.format(self.test))
            time.sleep(1)

        def setup_withsetup(self):
            print ('setup the test')
            self.test = 3

        def test_withsetup(self):
            print ('there is a setup for this test, the test is {}'
                   .format(self.test))

        def teardown_withsetup(self):
            print ('teardown, reset value')
            self.test = 1

        def test_zorglub(self):
            print ('eviv bulgroz')
            print ('the test is {}'.format(self.test))
            return 9999

    t = TestBenchmark()
    t.run()
    print t.get_results()
