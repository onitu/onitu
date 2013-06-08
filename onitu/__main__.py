#!/usr/bin/env python
"""The main entry point. Invoke as `python -m onitu'.

"""
import sys
from .core import Core


if __name__ == '__main__':
    core = Core()
    sys.exit(core.run())
