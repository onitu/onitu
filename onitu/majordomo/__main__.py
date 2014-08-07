import sys

import zmq

from logbook.queues import ZeroMQHandler
from onitu.utils import at_exit

from .majordomo import Majordomo

log_uri = sys.argv[1]
escalator_uri = sys.argv[2]
session = sys.argv[3]


def cleanup():
    majordomo.stop()

if __name__ == '__main__':
    with ZeroMQHandler(log_uri, multi=True).applicationbound():
        try:
            majordomo = Majordomo(log_uri, escalator_uri, session,
                                  'authorized_keys', 'server.key_secret')
            majordomo.bind()
            at_exit(cleanup)
            while True:
                majordomo.poll()
        except zmq.ZMQError as e:
            pass
        except Exception as e:
            majordomo.logger.error('{}', e)
        finally:
            majordomo.logger.info('Exited')
