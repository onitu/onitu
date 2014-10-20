import sys

import zmq

from logbook.queues import ZeroMQHandler
from onitu.utils import at_exit, get_logs_uri

from .majordomo import Majordomo

session = sys.argv[1]
frontend_req_uri = sys.argv[2]
frontend_rep_uri = sys.argv[3]
keys_dir = sys.argv[4]
server_key = sys.argv[5]


def cleanup():
    majordomo.stop()

if __name__ == '__main__':
    with ZeroMQHandler(get_logs_uri(session), multi=True).applicationbound():
        try:
            majordomo = Majordomo(session, keys_dir, server_key)
            majordomo.bind(frontend_req_uri, frontend_rep_uri)
            at_exit(cleanup)
            while True:
                majordomo.poll()
        except zmq.ZMQError as e:
            pass
        except Exception as e:
            majordomo.logger.error('{}', e)
        finally:
            majordomo.logger.info('Exited')
