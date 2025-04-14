import logging
from ssl import create_default_context

from elasticsearch import Elasticsearch

from seafes.config import seafes_config


logger = logging.getLogger('seafes')


def es_get_conn():
    context = None
    if seafes_config.cafile:
        context = create_default_context(cafile=seafes_config.cafile)

    es = Elasticsearch(['%s://%s:%s' % (seafes_config.scheme, seafes_config.host, seafes_config.port)],
                       http_auth=seafes_config.authorization, ssl_context=context, maxsize=50, timeout=30)
    return es


def es_get_status():
    """ return True if es server work normal, otherwise return false
    """
    client = es_get_conn()
    try:
        client.ping()
        alive = True
    except Exception as e:
        logger.warning(e)
        alive = False
    return alive
