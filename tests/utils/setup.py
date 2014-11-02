import os
import random
import string
import json

from plyvel import destroy_db

from onitu.utils import TMPDIR, b

from .launcher import Launcher


class Setup(object):
    def __init__(self):
        self.services = {}

        self._json = None

        self.name = ''.join(
            random.sample(string.ascii_letters + string.digits, 20)
        )
        self.filename = os.path.join(TMPDIR, "{}.json".format(self.name))

    def add(self, service):
        service.connect(self.name)
        self.services[service.name] = service
        return self

    def clean(self, services=True):
        if services:
            for service in self.services.values():
                service.close()

        try:
            os.unlink(self.filename)
            destroy_db(u'dbs/{}'.format(self.name))
        except (OSError, IOError):
            pass

    @property
    def dump(self):
        setup = {}
        if self.name:
            setup['name'] = self.name
        setup['services'] = {name: e.dump for name, e in self.services.items()}
        return setup

    @property
    def json(self):
        if not self._json:
            self._json = json.dumps(self.dump, indent=2, ensure_ascii=False)

        return self._json

    @json.setter
    def json(self, content):
        self._json = content

    def save(self):
        print('Setup:')
        print(self.json)

        with open(self.filename, 'wb+') as f:
            f.write(b(self.json))

    def get_launcher(self):
        return Launcher(self)
