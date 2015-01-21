import os
import json
import shutil
from passlib.hash import sha256_crypt as passwordhash

from onitu.utils import TMPDIR, b, get_random_string

from .launcher import Launcher


class Setup(object):
    def __init__(self, folders=None, api=None, users=None):
        self.services = {}
        if folders is None:
            folders = {}
        self.folders = folders

        if api is None:
            api = {"host": "localhost", "port": 3862}
        self.api = api

        if users is None:
            users = {}
        self.users = users

        self._json = None

        self.name = get_random_string(15)
        self.config_dir = os.path.join(TMPDIR, "onitu-{}".format(self.name))
        self.filename = os.path.join(self.config_dir, "setup.json")

        os.makedirs(self.config_dir)

    def add(self, service):
        service.connect(self.name)
        self.services[service.name] = service

        for folder in service.folders.keys():
            if folder not in self.folders:
                self.folders[folder] = {}

        return self

    def add_user(self, user, pwd, roles):
        self.users[user] = {"passhash": passwordhash.encrypt(pwd),
                            "roles": roles}

    def clean(self, services=True):
        if services:
            for service in self.services.values():
                service.close()

        shutil.rmtree(self.config_dir)

    @property
    def dump(self):
        setup = {}
        if self.name:
            setup['name'] = self.name
        setup['services'] = {name: e.dump for name, e in self.services.items()}
        setup['folders'] = self.folders
        setup['api'] = self.api
        setup['users'] = self.users
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
