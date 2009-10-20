#!/usr/bin/env python

import sqlite3
import time

class DB:

    CREATE_SETTING_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS settings (
        path TEXT,
        value TEXT
    );
    """
    CREATE_SETTING_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS setting_index ON settings (path);
    """
    QUERY_SETTING_SQL = """
    SELECT value FROM settings WHERE path = :path;
    """
    QUERY_SETTING_ITEMS_SQL = """
    SELECT path, value FROM settings WHERE path LIKE :pattern;
    """
    ADD_SETTING_SQL = """
    INSERT INTO settings VALUES (:path, :value);
    """
    UPDATE_SETTING_SQL = """
    UPDATE settings SET value = :value WHERE path == :path;
    """

    FLUSH_INTERVAL = 5 * 60  # 5 minutes
    __last_flush_time = 0

    @classmethod
    def open (cls, db_file):
        cls.__conn = sqlite3.connect (db_file)
        cls.__conn.execute (cls.CREATE_SETTING_TABLE_SQL)
        cls.__conn.execute (cls.CREATE_SETTING_INDEX_SQL)
        cls.flush (True)

    @classmethod
    def read_setting (cls, key):
        r = cls.__conn.execute (cls.QUERY_SETTING_SQL, {'path': key}).fetchone ()
        return r[0] if r else None

    @classmethod
    def read_setting_list (cls, key):
        r = cls.__conn.execute (cls.QUERY_SETTING_SQL, {'path': key}).fetchall ()
        return [x[0] for x in r]

    @classmethod
    def read_setting_items (cls, key):
        r = cls.__conn.execute (cls.QUERY_SETTING_ITEMS_SQL, {'pattern': key + '%'}).fetchall ()
        return [(x[0][len (key):], x[1]) for x in r]

    @classmethod
    def update_setting (cls, key, value):
        if cls.read_setting (key) is None:
            cls.__conn.execute (cls.ADD_SETTING_SQL, {'path': key, 'value': value})
        else:
            cls.__conn.execute (cls.UPDATE_SETTING_SQL, {'path': key, 'value': value})
        cls.flush (True)

    @classmethod
    def flush (cls, immediate=False):
        now = time.time ()
        if immediate or now - cls.__last_flush_time > cls.FLUSH_INTERVAL:
            cls.__conn.commit ()
            cls.__last_flush_time = now

    def __init__ (self, name):
        self.__name = name
        self.__conf_path = 'Config/%s/' % name
        prefix = {'prefix' : self.read_config_value ('Prefix')}
        self.LIST_KEYWORDS_SQL = """
        SELECT DISTINCT keyword FROM %(prefix)s_keywords;
        """ % prefix
        self.QUERY_KEYWORD_SQL = """
        SELECT phrase FROM %(prefix)s_keywords WHERE keyword = :keyword;
        """ % prefix
        self.ADD_KEYWORD_SQL = """
        INSERT INTO %(prefix)s_keywords VALUES (:keyword, :phrase);
        """ % prefix
        self.QUERY_PHRASE_SQL = (
        """
        SELECT phrase, sum(freq) AS total FROM
        (
        SELECT phrase, freq FROM %(prefix)s_phrases 
        WHERE klen = 1 AND k0 = :k0 AND k1 IS NULL AND k2 IS NULL AND k3 IS NULL
        UNION 
        SELECT phrase, 0 AS freq FROM %(prefix)s_keywords 
        WHERE keyword = :k0
        )
        GROUP BY phrase
        ORDER BY total DESC;
        """ % prefix,
        """
        SELECT phrase, freq FROM %(prefix)s_phrases 
        WHERE klen = 2 AND k0 = :k0 AND k1 = :k1 AND k2 IS NULL AND k3 IS NULL
        ORDER BY freq DESC;
        """ % prefix,
        """
        SELECT phrase, freq FROM %(prefix)s_phrases 
        WHERE klen = 3 AND k0 = :k0 AND k1 = :k1 AND k2 = :k2 AND k3 IS NULL
        ORDER BY freq DESC;
        """ % prefix,
        """
        SELECT phrase, freq FROM %(prefix)s_phrases 
        WHERE klen = 4 AND k0 = :k0 AND k1 = :k1 AND k2 = :k2 AND k3 = :k3
        ORDER BY freq DESC;
        """ % prefix
        )
        self.UPDATE_PHRASE_SQL = """
        UPDATE %(prefix)s_phrases SET freq = ? 
        WHERE klen = :klen AND k0 = :k0 AND k1 = :k1 AND k2 = :k2 AND k3 = :k3 AND phrase = :phrase;
        """ % prefix
        self.ADD_PHRASE_SQL = """
        INSERT INTO %(prefix)s_phrases VALUES (:klen, :k0, :k1, :k2, :k3, :phrase, :freq);
        """ % prefix

    def read_config_value (self, key):
        return DB.read_setting (self.__conf_path + key)

    def read_config_list (self, key):
        return DB.read_setting_list (self.__conf_path + key)
        
    def list_keywords (self):
        return [x[0] for x in DB.__conn.execute (self.LIST_KEYWORDS_SQL, ()).fetchall ()]

    def lookup (self, key):
        klen = len (key)
        args = {'klen' : klen}
        for i in range (klen):
            args['k%d' % i] = key[i]
        r = DB.__conn.execute (self.QUERY_PHRASE_SQL[klen - 1], args).fetchall ()
        return r

