#!/usr/bin/env python2

import entries

entries = entries.Entries()
entries.add('local_storage')
entries.add('local_storage', 'tutu & toto')
entries.add('local_storage', 'tutu toto')
entries.add('useless')
entries.add('useless')

print entries.json
