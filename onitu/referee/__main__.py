"""
Start the Referee.

Launch it as : `python -m onitu.referee`
"""

import sys

from threading import Thread

from logbook.queues import ZeroMQHandler

from onitu.utils import at_exit

from .referee import Referee

if __name__ == '__main__':
    with ZeroMQHandler(sys.argv[1], multi=True).applicationbound():
        referee = Referee(sys.argv[2])

        at_exit(referee.close)

        # We run Referee.listen in another thread in order
        # to be able to interrupt it gently in the end
        thread = Thread(target=referee.listen)
        thread.start()

        while thread.is_alive():
            thread.join(100)

        referee.logger.info("Exited")
