"""
Start the Referee.

Launch it as : `python -m onitu.referee`
"""

from .referee import Referee

if __name__ == '__main__':
    referee = Referee()
    referee.listen()
