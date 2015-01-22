import os.path
from threading import Lock

import plyvel

from onitu.utils import u


class Databases(object):
    class OpenError(Exception):
        pass

    class NotExistError(Exception):
        pass

    def __init__(self, working_dir):
        self._databases = {}
        self._names = []
        self._working_dir = working_dir
        self._lock = Lock()

    def __contains__(self, uid):
        return 0 <= uid < len(self._names)

    def get_db(self, name):
        return self._databases[name]

    def get_name(self, uid):
        uid = int(uid)
        if uid not in self:
            raise IndexError('Database with uid {} does not exist'.format(uid))
        return self._names[uid]

    def get(self, uid):
        return self.get_db(self.get_name(uid))

    def connect(self, name, prefix=None, create=False):
        with self._lock:
            try:
                name = os.path.join(self._working_dir, name)
                if name not in self._databases:
                    self._databases[name] = plyvel.DB(name,
                                                      create_if_missing=create)
                    self._names.append(name)
                if prefix:
                    db = self._databases[name]
                    name = u'{}/{}'.format(name, u(prefix))
                    if name not in self._databases:
                        self._databases[name] = db.prefixed_db(prefix)
                        self._names.append(name)
                return self._names.index(name)
            except plyvel.IOError as e:
                raise Databases.OpenError(*e.args)
            except plyvel.Error as e:
                raise Databases.NotExistError(*e.args)

    def list_dbs(self):
        return list(self._names)

    def close(self, name=None):
        if name:
            db = self.get_db(name)
            if not hasattr(db, 'prefix'):
                db.close()
        else:
            for db in self._databases.values():
                if not hasattr(db, 'prefix'):
                    db.close()
