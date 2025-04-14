import os
import pymysql
import logging
import configparser

pymysql.install_as_MySQLdb()


logger = logging.getLogger('seafes')

class db(object):
    def __init__(self):
        # read seafile conf for init db
        if 'SEAFILE_CENTRAL_CONF_DIR' in os.environ:
            confdir = os.environ['SEAFILE_CENTRAL_CONF_DIR']
        else:
            confdir = os.environ['SEAFILE_CONF_DIR']
        if not confdir:
            logger.critical("seafile config dir is not set")
            raise RuntimeError("seafile config dir is not set")
        seafile_conf_file = os.path.join(confdir, 'seafile.conf')

        self.cur = None
        self.load_config(seafile_conf_file)
        self.connection()

    def load_config(self, config_file):
        seaf_conf = configparser.ConfigParser()
        seaf_conf.read(config_file)
        backend = seaf_conf.get('database', 'type')
        if backend == 'mysql':
            self.db_server = 'localhost'
            self.db_port = 3306
            if not seaf_conf.has_option('database', 'user') or \
               not seaf_conf.has_option('database', 'password') or \
               not seaf_conf.has_option('database', 'db_name'):
                logger.critical("Invalid mysql config file")
                raise RuntimeError("Invalid mysql config file")

            if seaf_conf.has_option('database', 'host'):
                self.db_server = seaf_conf.get('database', 'host')
            if seaf_conf.has_option('database', 'port'):
                self.db_port =seaf_conf.getint('database', 'port')
            self.db_username = seaf_conf.get('database', 'user')
            self.db_passwd = seaf_conf.get('database', 'password')
            self.db_name = seaf_conf.get('database', 'db_name')
        else:
            logger.critical("Unknown Database backend: %s" % backend)
            raise RuntimeError("Unknown Database backend: %s" % backend)

    def connection(self):
        # use seafile conf to connection seafile database
        conn = pymysql.connect(host=self.db_server, port=self.db_port,
                               user=self.db_username, passwd=self.db_passwd,
                               db=self.db_name)
        self.cur = conn.cursor()

    def query(self, cmd, param=None):
        if param:
            self.cur.execute(cmd, param)
        else:
            self.cur.execute(cmd)
        return self.cur.fetchall()


db = db()
