"""
Start the Referee.

Launch it as : `python -m onitu.referee`
"""

import sys

from logbook.queues import ZeroMQHandler

from .referee import Referee

if __name__ == '__main__':
    with ZeroMQHandler(sys.argv[1], multi=True).applicationbound():
        referee = Referee()
        referee.listen()
