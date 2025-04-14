import redis
import logging

logger = logging.getLogger('seafes')


def get_mq(mq_type, server, port, password):
    backend = mq_type
    if backend == 'REDIS':
        rdp = redis.ConnectionPool(host=server, port=port,
                                   password=password, retry_on_timeout=True, decode_responses=True)
        mq = redis.StrictRedis(connection_pool=rdp)
        try:
            mq.ping()
        except Exception as e:
            logger.error("Redis server can't be connected: host %s, port %s, error %s",
                         server, port, e)
        finally:
            # python redis is a client, each operation tries to connect and retry exec
            return mq
    else:
        logger.error("Unsupported MessageQueue Type")
