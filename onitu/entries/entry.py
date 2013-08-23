import sys

import circus

class Entry(dict):

    def __init__(self, id, core, *args, **kwargs):
        super(Entry, self).__init__(*args, **kwargs)

        self.id = id
        self.core = core
        self._ready = False

        if 'options' in self:
            self.core.redis.hmset('onitu:options:{}'.format(self.id), self['options'])

        self._load_driver()

    @property
    def ready(self):
        return self._ready

    def _load_driver(self):
        try:
            script = 'onitu.drivers.{name}'.format(name=self['driver_name'])

            watcher = {
                'cmd': sys.executable,
                'args': ['-m', script, self.id],
                'name': self.id,
                'start': True
            }
            self.core.circus.send_message('add', **watcher)

            self._ready = True

        except (ImportError, AttributeError) as e:
            print("Impossible to load driver {} :".format(self['driver_name']), e)
