#!/usr/bin/env python

import sqlite3
import time

class DB:

    CREATE_SETTING_SQLS = """
    CREATE TABLE IF NOT EXISTS setting_paths (
        id INTEGER PRIMARY KEY,
        path TEXT UNIQUE
    );
    CREATE TABLE IF NOT EXISTS setting_values (
        path_id INTEGER,
        value TEXT
    );
    """
    QUERY_SETTING_SQL = """
    SELECT value FROM setting_values WHERE path_id in (SELECT id FROM setting_paths WHERE path = :path);
    """
    QUERY_SETTING_ITEMS_SQL = """
    SELECT path, value FROM setting_paths, setting_values WHERE path LIKE :pattern AND id = path_id;
    """
    QUERY_SETTING_PATH_SQL = """
    SELECT id FROM setting_paths WHERE path = :path;
    """
    ADD_SETTING_PATH_SQL = """
    INSERT INTO setting_paths VALUES (NULL, :path);
    """
    ADD_SETTING_VALUE_SQL = """
    INSERT INTO setting_values VALUES (:path_id, :value);
    """
    UPDATE_SETTING_VALUE_SQL = """
    UPDATE setting_values SET value = :value WHERE path_id == :path_id;
    """

    FLUSH_INTERVAL = 3 * 60  # 3 minutes
    __last_flush_time = 0

    @classmethod
    def open (cls, db_file, read_only=False):
        cls.__conn = sqlite3.connect (db_file)
        cls.read_only = read_only
        if not read_only:
            cls.__conn.executescript (cls.CREATE_SETTING_SQLS)
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
        if cls.read_only:
            return False
        while True:
            path = cls.__conn.execute (cls.QUERY_SETTING_PATH_SQL, {'path': key}).fetchone ()
            if path:
                break
            else:
                cls.__conn.execute (cls.ADD_SETTING_PATH_SQL, {'path': key})
        path_id = path[0]
        if cls.read_setting (key) is None:
            cls.__conn.execute (cls.ADD_SETTING_VALUE_SQL, {'path_id': path_id, 'value': value})
        else:
            cls.__conn.execute (cls.UPDATE_SETTING_VALUE_SQL, {'path_id': path_id, 'value': value})
        cls.flush (True)
        return True

    @classmethod
    def flush (cls, immediate=False):
        now = time.time ()
        if immediate or now - cls.__last_flush_time > cls.FLUSH_INTERVAL:
            cls.__conn.commit ()
            cls.__last_flush_time = now

    def __init__ (self, name):
        self.__name = name
        self.__conf_path = 'Config/%s/' % name
        prefix_args = {'prefix' : self.read_config_value ('Prefix')}
        self.LIST_KEYWORDS_SQL = """
        SELECT kwds FROM %(prefix)s_keys WHERE length = 1;
        """ % prefix_args
        self.QUERY_G1_SQL = """
        SELECT phrase, freq, p_id FROM %(prefix)s_g1, %(prefix)s_keys k, %(prefix)s_phrases p 
        WHERE length = :length AND kwds = :kwds AND k.id = k_id AND p_id = p.id
        ORDER BY freq DESC;
        """ % prefix_args
        self.QUERY_G2_SQL = """
        SELECT freq, p1_id, p2_id FROM %(prefix)s_g2, %(prefix)s_keys k, %(prefix)s_phrases p1, %(prefix)s_phrases p2 
        WHERE length = :length AND kwds = :kwds AND k.id = k_id AND p1_id = p1.id AND p2_id = p2.id
        ORDER BY freq DESC;
        """ % prefix_args

    def read_config_value (self, key):
        return DB.read_setting (self.__conf_path + key)

    def read_config_list (self, key):
        return DB.read_setting_list (self.__conf_path + key)
        
    def list_keywords (self):
        return [x[0] for x in DB.__conn.execute (self.LIST_KEYWORDS_SQL, ()).fetchall ()]

    def lookup_phrase (self, key):
        length = len (key)
        args = {'length' : length, 'kwds' : u' '.join (key)}
        r = [tuple(x) for x in DB.__conn.execute (self.QUERY_G1_SQL, args).fetchall ()]
        return r

    def lookup_bigram (self, key):
        length = len (key)
        args = {'length' : length, 'kwds' : u' '.join (key)}
        r = [(x[0], x[1:]) for x in DB.__conn.execute (self.QUERY_G2_SQL, args).fetchall ()]
        return r

    def store (self, key, phrase):
        #print 'store:', key, phrase
        if DB.read_only:
            return False
        #klen = len (key)
        #args = {'klen' : klen, 'phrase' : phrase, 'n' : 1}
        #for i in range (4):
        #    args['k%d' % i] = key[i] if i < klen else None
        #if DB.__conn.execute (self.PHRASE_EXIST_SQL[klen - 1], args).fetchone ():
        #    DB.__conn.execute (self.UPDATE_PHRASE_SQL[klen - 1], args)
        #else:
        #    DB.__conn.execute (self.ADD_PHRASE_SQL, args)
        #DB.flush ()
        return True

    def delete (self, key, phrase, n):
        #print 'delete:', key, phrase
        if DB.read_only:
            return False
        #klen = len (key)
        #args = {'klen' : klen, 'phrase' : phrase, 'n' : -n - 1}
        #for i in range (4):
        #    args['k%d' % i] = key[i] if i < klen else None
        #DB.__conn.execute (self.UPDATE_PHRASE_SQL[klen - 1], args)
        #DB.flush ()
        return True
