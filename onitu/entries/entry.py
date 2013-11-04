import sys

import circus

class Entry(dict):

    def __init__(self, name, core, *args, **kwargs):
        super(Entry, self).__init__(*args, **kwargs)

        self.name = name
        self.core = core
        self._ready = False

        if 'options' in self:
            self.core.redis.hmset('drivers:{}:options'.format(self.name), self['options'])

        self._load_driver()

    @property
    def ready(self):
        return self._ready

    def _load_driver(self):
        script = 'onitu.drivers.{}'.format(self['driver_name'])

        watcher = {
            'cmd': sys.executable,
            'args': ['-m', script, self.name],
            'name': self.name,
            'start': True
        }
        self.core.circus.send_message('add', **watcher)

        self._ready = True
