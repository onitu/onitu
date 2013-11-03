from referee import Referee

if __name__ == '__main__':
    try:
        referee = Referee()
        referee.listen()
    finally:
        exit()
