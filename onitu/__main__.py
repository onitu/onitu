#!/usr/bin/env python
"""The main entry point. Invoke as `python -m onitu'.

"""
import sys
from onitu.core import Core


if __name__ == '__main__':
    core = Core(*sys.argv[1:])
    sys.exit(core.launch())
