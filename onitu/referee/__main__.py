"""
Start the Referee.

Launch it as : `python -m onitu.referee`
"""

from logbook.queues import ZeroMQHandler

from .referee import Referee

if __name__ == '__main__':
    with ZeroMQHandler('tcp://127.0.0.1:5000', multi=True).applicationbound():
        referee = Referee()
        referee.listen()
