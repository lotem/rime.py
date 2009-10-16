#!/usr/bin/env python

import sqlite3

class DB:

    @classmethod
    def connect (cls, db_path):
        cls.__conn = sqlite3.connect (db_path)

    QUERY_SETTING_SQL = """
    SELECT value FROM settings WHERE path = :path;
    """

    QUERY_SETTING_ITEMS_SQL = """
    SELECT path, value FROM settings WHERE path LIKE :pattern;
    """

    @classmethod
    def read_setting (cls, key):
        r = DB.__conn.execute (DB.QUERY_SETTING_SQL, {'path': key}).fetchone ()
        return r[0] if r else None

    @classmethod
    def read_setting_items (cls, key):
        r = DB.__conn.execute (DB.QUERY_SETTING_ITEMS_SQL, {'pattern': key + '%'}).fetchall ()
        return [(x[0][len (key):], x[1]) for x in r]

    def __init__ (self, name):
        self.__name = name
        self.__conf_path = 'Config/%s/' % name
        prefix = {'prefix' : self.read_config_value ('Prefix')}
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

    def lookup (self, keywords):
        klen = len (keywords)
        args = {'klen' : klen}
        for i in range (klen):
            args['k%d' % i] = keywords[i]
        r = DB.__conn.execute (self.QUERY_PHRASE_SQL[klen - 1], args).fetchall ()
        return r

