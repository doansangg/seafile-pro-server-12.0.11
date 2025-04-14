#!coding: UTF_8

import os
import sys
import logging
import logging.handlers
import subprocess

from seafes.config import seafes_config

def _expand(v):
    return v[0] if isinstance(v, list) else v

def get_result_set_hits(result):
    hits = result.__getattr__('hits')
    if isinstance(hits, dict):
        hits = hits['hits']

    # In ES 1.4.0 the returned fields values are like {field1: [value1], field2: [value2], ...}
    for entry in hits:
        fields = entry.get('fields', {})
        for k, v in fields.copy().items():
            fields[k] = _expand(v)

    return hits


def run(argv, cwd=None, env=None, suppress_stdout=False, suppress_stderr=False):
    """Run a program and wait it to finish, and return its exit code. The
    standard output of this program is suppressed.
    """
    with open(os.devnull, 'w') as devnull:
        if suppress_stdout:
            stdout = devnull
        else:
            stdout = sys.stdout

        if suppress_stderr:
            stderr = devnull
        else:
            stderr = sys.stderr

        proc = subprocess.Popen(argv,
                                cwd=cwd,
                                stdout=stdout,
                                stderr=stderr,
                                env=env)

        return proc.wait()


def do_dict_config(level, stream):
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'seafes': {
                'format': '[%(asctime)s] %(message)s',
            },
        },
        'handlers': {
            'seafes': {
                'level': level,
                'class': 'logging.StreamHandler',
                'stream': stream,
                'formatter': 'seafes',
            },
        },
        'loggers': {
            'seafes': {
                'handlers': ['seafes'],
                'level': level,
                'propagate': False
            },
        }
    }

    # Make sure that dictConfig is available
    # This was added in Python 2.7/3.2
    try:
        from logging.config import dictConfig
    except ImportError:
        from django.utils.dictconfig import dictConfig

    dictConfig(LOGGING)

def init_logging(args):
    level = args.loglevel

    if level == 'debug':
        level = logging.DEBUG
    elif level == 'info':
        level = logging.INFO
    elif level == 'warning':
        level = logging.WARNING
    else:
        if seafes_config.debug:
            level = logging.DEBUG
        else:
            level = logging.INFO

    try:
        # set boto3 log level
        import boto3
        boto3.set_stream_logger(level=logging.WARNING)
    except:
        pass

    # do_dict_config(level, args.logfile)
    seafile_log_to_stdout = os.getenv('SEAFILE_LOG_TO_STDOUT', 'false') == 'true'
    if seafile_log_to_stdout or args.logfile == sys.stdout:
        formatter = '[seafes] [%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(message)s'
        stream = sys.stdout
        kw = {
        #'format': '[%(asctime)s] %(message)s',
            'format': formatter,
            'datefmt': '%Y-%m-%d %H:%M:%S',
            # 'datefmt': '%m/%d/%Y %H:%M:%S',
            'level': level,
            'stream': stream
        }

        logging.basicConfig(**kw)
    else:
        log_file = str(args.logfile.name)
        handler = logging.handlers.TimedRotatingFileHandler(log_file, when='W0', interval=1, backupCount=3)
        handler.setLevel(level)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s: %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logging.root.setLevel(level)
        logging.root.addHandler(handler)


    logging.getLogger('oss_util').setLevel(logging.WARNING)
    logging.getLogger('elasticsearch').setLevel(logging.ERROR)
    logging.getLogger('elastic_transport').setLevel(logging.ERROR)
    logging.getLogger('elasticsearch.trace').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    if seafes_config.debug:
        logging.debug('debug flag turned on')
