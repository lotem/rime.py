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
        SELECT phrase, freq, kwds, p_id FROM %(prefix)s_g1, %(prefix)s_keys k, %(prefix)s_phrases p 
        WHERE length = :length AND kwds = :kwds AND k.id = k_id AND p_id = p.id
        ORDER BY freq DESC;
        """ % prefix_args
        self.QUERY_G2_SQL = """
        SELECT freq, kwds, p1_id, p2_id FROM %(prefix)s_g2, %(prefix)s_keys k, %(prefix)s_phrases p1, %(prefix)s_phrases p2 
        WHERE length = :length AND kwds = :kwds AND k.id = k_id AND p1_id = p1.id AND p2_id = p2.id
        ORDER BY freq DESC;
        """ % prefix_args
        self.UPDATE_G1_SQL = """
        UPDATE %(prefix)s_g1 SET freq = freq + 1 
        WHERE k_id IN (SELECT id FROM %(prefix)s_keys WHERE kwds = :kwds) AND p_id = :p_id;
        """ % prefix_args
        self.G2_EXIST_SQL = """
        SELECT freq FROM %(prefix)s_g2 
        WHERE k_id = :k_id AND p1_id = :p1_id AND p2_id = :p2_id;
        """ % prefix_args
        self.UPDATE_G2_SQL = """
        UPDATE %(prefix)s_g2 SET freq = freq + 1 
        WHERE k_id = :k_id AND p1_id = :p1_id AND p2_id = :p2_id;
        """ % prefix_args
        self.ADD_G2_SQL = """
        INSERT INTO %(prefix)s_g2 VALUES (:k_id, :p1_id, :p2_id, 1);
        """ % prefix_args
        self.QUERY_KEY_SQL = """
        SELECT id FROM %(prefix)s_keys WHERE length = :length AND kwds = :kwds;
        """ % prefix_args
        self.ADD_KEY_SQL = """
        INSERT INTO %(prefix)s_keys VALUES (NULL, :length, :kwds);
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
        r = [(x[0], x[2:]) for x in DB.__conn.execute (self.QUERY_G2_SQL, args).fetchall ()]
        return r

    def update_unigram (self, a):
        #print 'update_unigram:', a
        if DB.read_only:
            return
        args = {'kwds' : a[2], 'p_id' : a[3]}
        DB.__conn.execute (self.UPDATE_G1_SQL, args)
        DB.flush ()

    def update_bigram (self, a, b):
        #print 'update_bigram:', a, b
        if DB.read_only:
            return
        kwds = u' '.join ([a[2], b[2]])
        args = {'length' : len (kwds), 'kwds' : kwds} 
        while True:
            r = DB.__conn.execute (self.QUERY_KEY_SQL, args).fetchone ()
            if r:
                break
            DB.__conn.execute (self.ADD_KEY_SQL, args)
        args = {'k_id' : r[0], 'p1_id' : a[3], 'p2_id' : b[3]}
        if DB.__conn.execute (self.G2_EXIST_SQL, args).fetchone ():
            DB.__conn.execute (self.UPDATE_G2_SQL, args)
        else:
            DB.__conn.execute (self.ADD_G2_SQL, args)
        DB.flush ()

