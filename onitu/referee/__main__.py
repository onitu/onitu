from referee import Referee
from logbook import StderrHandler, catch_exceptions

if __name__ == '__main__':
    referee = Referee()
    referee.listen()
