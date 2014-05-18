from .timer import Timer
from logbook import Logger
from codespeed_client import Client


class BenchmarkData():
    def __init__(self, title, description, unit="ms"):
        self.title = title
        self.description = description
        self.unit = unit
        self._results = []
        self._num_format = '.4f'

    def add_result(self, result):
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
        text = []
        text.append('{:-^28}'.format(self.title))
        if self.description:
            text.append(self.description)
        text.append('run {} times'.format(len(self)))
        text.append('Total:\t\t{:{f}} {}'
                    .format(self.sum(), self.unit, f=self._num_format))
        text.append('Min:\t\t{:{f}} {}'
                    .format(self.min(), self.unit, f=self._num_format))
        text.append('Max:\t\t{:{f}} {}'
                    .format(self.max(), self.unit, f=self._num_format))
        text.append('Average:\t{:{f}} {}'
                    .format(self.average(), self.unit, f=self._num_format))
        return '\n'.join(text)

    def get(self):
        return {
            'title': self.title,
            'desc': self.description,
            'unit': self.unit,
            'results': self._results
        }


class Benchmark():
    def __init__(self,
                 name,
                 prefix='test_',
                 num_format='.4f',
                 verbose=False,
                 log_uri=None
                 ):
        self.name = name
        self._prefix = prefix
        self._num_format = num_format
        self._results = {}
        self.log = Logger(self.name)
        self.verbose = verbose

    def run(self, *args):
        """All functions whose name starts with prefix.
        Run setup at the beginning of the run.
        Run setup_each at the beginning of each test.
        Run teardown at the end of the tests.
        """
        try:
            self._run_function_exn('setup', *args)
            tests = self._collect_tests()
            for t in tests:
                self._run_test(t)
        except BaseException as e:
            self.log.error('Fatal exception. Benchmark shutdown.')
            self.log.error(e)
            raise e
        finally:
            self._run_function('teardown')

    def _run_function_exn(self, name, *args):
        self.log.debug('Run function {}'.format(name))
        return getattr(self, name)(*args)

    def _run_function(self, name, *args):
        try:
            self.log.debug('Run function {}'.format(name))
            return getattr(self, name)(*args)
        except BaseException as e:
            self.log.warn(
                'The test is skipped because it raised an exception'
            )
            self.log.warn(e)

    def _run_env(self, name, *args):
        try:
            self.log.debug('Run function {}'.format(name))
            return getattr(self, name)(*args)
        except AttributeError as e:
            self.log.debug('The function {} does not exist'.format(name))
        except BaseException as e:
            self.log.warn(
                'The test is skipped because {} raised an exception'
                .format(name)
            )
            self.log.warn(e)

    def _run_test(self, name):
        setup_test = name.replace(self._prefix, 'setup_')
        teardown_test = name.replace(self._prefix, 'teardown_')
        try:
            self._run_env(setup_test)
            with Timer() as t:
                res = self._run_function(name)
            if res:
                r = res
            else:
                r = BenchmarkData(name, None)
                r.add_result(t.msecs)
            self._results[name] = r
        except BaseException as e:
            self.log.warn('The test is skipped because it raised an exception')
            self.log.warn(e)
        finally:
            self._run_env(teardown_test)

    def execute(self, name):
        return self._run_test(name)

    def _collect_tests(self):
        return [t for t in dir(self) if t.startswith(self._prefix)]

    def display(self):
        for k in self._results.keys():
            res = self._results[k]
            print(res)

    # TODO: fix codespeed
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
        return {k: r.get() for k, r in self._results.items()}
