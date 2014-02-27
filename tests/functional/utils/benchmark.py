from .timer import Timer
from codespeed_client import Client


class BenchmarkData():
    def __init__(self, description, unit="ms"):
        self.description = description
        self.unit = unit
        self._results = []

    def add_result(self, result):
        print(self.description, 'add one result', result)
        self._results.append(result)

    def average(self):
        return self.sum() / len(self)

    def max(self):
        return max(self._results)

    def min(self):
        return min(self._results)

    def sum(self):
        return sum(self._results)

    def __len__(self):
        return len(self._results)

    def __str__(self):
        return str(self._results)


class Benchmark():
    def __init__(self,
                 prefix='test_',
                 each=1,
                 num_format='.4f',
                 verbose=False
                 ):
        self._prefix = prefix
        self._each = each
        self._num_format = num_format
        self._results = {}
        self._verbose = verbose

    def _log(self, msg):
        if self._verbose:
            print('BENCHMARKS: ' + msg)

    def run(self, *args):
        """All functions whose name starts with prefix.
        Run setup at the beginning of the run.
        Run setup_each at the beginning of each test.
        Run teardown at the end of the tests.
        """
        try:
            self._run_function('setup', *args)
            tests = self._collect_tests()
            for t in tests:
                self._run_test(t)
        except BaseException as e:
            self._log('Fatal exception. Benchmark shutdown.')
            self._log(e)
        except:
            print 'cest la mort'
        finally:
            self._run_function('teardown')

    def _run_function(self, name, *args):
        try:
            self._log('Run function {}'.format(name))
            return getattr(self, name)(*args)
        except:
            pass

    def _run_test(self, name):
        setup_test = name.replace(self._prefix, 'setup_')
        teardown_test = name.replace(self._prefix, 'teardown_')
        try:
            self._run_function(setup_test)
            with Timer() as t:
                res = self._run_function(name)
            if res:
                r = res
            else:
                r = BenchmarkData(None)
                r.add_result(t.msecs)
            self._results[name] = r
        except BaseException as e:
            self._log('The test is skipped because it raised an exception')
            self._log(e)
        finally:
            self._run_function(teardown_test)

    # TODO: fix this function
    def _run_test_loop(self, name):
        total = {
            'description': None,
            'unit': 'ms',
            'results': {}
        }
        for i in self._each:
            total['results'][i] = self._run_test(name)

    def _collect_tests(self):
        return [t for t in dir(self) if t.startswith(self._prefix)]

    def display(self):
        for k in self._results.keys():
            res = self._results[k]
            print('{:-^28}'.format(k))
            if res.description:
                print(res.description)
            print('{} times'.format(len(res)))
            print('Total: {:{f}} {}'
                  .format(res.sum(), res.unit, f=self._num_format))
            print('Min: {:{f}} {}'
                  .format(res.min(), res.unit, f=self._num_format))
            print('Max: {:{f}} {}'
                  .format(res.max(), res.unit, f=self._num_format))
            print('Average: {:{f}} {}'
                  .format(res.average(), res.unit, f=self._num_format))

    def upload_results(self,
                       name,
                       host,
                       environment,
                       project,
                       commitid,
                       branch
                       ):
        """upload the results to a codespeed instance
        Https://github.com/tobami/codespeed/
        """
        # kwargs list: environment, project, benchmark, branch, commitid,
        # result_date, result_value, max, min,
        # std_dev, revision_date, executable,

        # kwargs passed to constructor are defaults
        client = Client(
            host,
            environment=environment,
            project=project,
            commitid=commitid,
            branch=branch
        )

        # kwargs passed to add_result overwrite defaults
        for result in self._results:
            n = '{}-{}'.format(name.replace(' ', '_'),
                               result[len(self._prefix):])
            res = self._results[result] / 1000
            client.add_result(
                benchmark=n,
                result_value=res
            )

        # upload all results in one request
        client.upload_results()

    def get_results(self):
        """return a dictionnary with the results of all tests.
        The key is the test's name and the value is the time.
        """
        return self._results
