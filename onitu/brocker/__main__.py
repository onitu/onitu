import sys

from threading import Thread

from logbook.queues import ZeroMQHandler

from onitu.utils import at_exit, get_logs_uri, u

from .brocker import Brocker

if __name__ == '__main__':
    session = u(sys.argv[1])

    with ZeroMQHandler(get_logs_uri(session), multi=True).applicationbound():
        brocker = Brocker(session)

        at_exit(brocker.close)

        thread = Thread(target=brocker.start)
        thread.start()

        while thread.is_alive():
            thread.join(100)

        brocker.logger.info("Exited")
