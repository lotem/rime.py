#!/usr/bin/env python

import sqlite3
import time

class DB:

    LIMIT = 1024

    INIT_PLUME_DB_SQLS = """
    CREATE TABLE IF NOT EXISTS setting_paths (
        id INTEGER PRIMARY KEY,
        path TEXT UNIQUE
    );
    CREATE TABLE IF NOT EXISTS setting_values (
        path_id INTEGER,
        value TEXT
    );
    CREATE TABLE IF NOT EXISTS phrases (
        id INTEGER PRIMARY KEY,
        phrase TEXT UNIQUE
    );
    """
    QUERY_SETTING_SQL = """
    SELECT value FROM setting_values WHERE path_id IN (SELECT id FROM setting_paths WHERE path = :path);
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

    FLUSH_INTERVAL = 2 * 60  # 2 minutes
    __last_flush_time = 0
    __conn = None

    @classmethod
    def open(cls, db_file, read_only=False):
        if cls.__conn:
            return
        cls.__conn = sqlite3.connect(db_file)
        cls.read_only = read_only
        if not read_only:
            cls.__conn.executescript(cls.INIT_PLUME_DB_SQLS)
            cls.flush(True)

    @classmethod
    def read_setting(cls, key):
        r = cls.__conn.execute(cls.QUERY_SETTING_SQL, {'path': key}).fetchone()
        return r[0] if r else None

    @classmethod
    def read_setting_list(cls, key):
        r = cls.__conn.execute(cls.QUERY_SETTING_SQL, {'path': key}).fetchall()
        return [x[0] for x in r]

    @classmethod
    def read_setting_items(cls, key):
        r = cls.__conn.execute(cls.QUERY_SETTING_ITEMS_SQL, {'pattern': key + '%'}).fetchall()
        return [(x[0][len(key):], x[1]) for x in r]

    @classmethod
    def update_setting(cls, key, value):
        if cls.read_only:
            return False
        path = cls.__conn.execute(cls.QUERY_SETTING_PATH_SQL, {'path': key}).fetchone()
        if path:
            path_id = path[0]
        else:
            c = cls.__conn.execute(cls.ADD_SETTING_PATH_SQL, {'path': key})
            path_id = c.lastrowid
        if cls.read_setting(key) is None:
            cls.__conn.execute(cls.ADD_SETTING_VALUE_SQL, {'path_id': path_id, 'value': value})
        else:
            cls.__conn.execute(cls.UPDATE_SETTING_VALUE_SQL, {'path_id': path_id, 'value': value})
        cls.flush(True)
        return True

    @classmethod
    def flush(cls, immediate=False):
        now = time.time()
        if immediate or now - cls.__last_flush_time > cls.FLUSH_INTERVAL:
            cls.__conn.commit()
            cls.__last_flush_time = now

    def __init__(self, name):
        self.__name = name
        self.__section = '%s/' % name
        prefix_args = {'prefix' : self.read_config_value('Dict')}

        self.LIST_KEYWORDS_SQL = """
        SELECT keyword FROM %(prefix)s_keywords;
        """ % prefix_args

        self.QUERY_KEY_SQL = """
        SELECT id FROM %(prefix)s_keys WHERE ikey = :ikey;
        """ % prefix_args

        self.ADD_KEY_SQL = """
        INSERT INTO %(prefix)s_keys VALUES (NULL, :ikey);
        """ % prefix_args

        self.QUERY_STATS_SQL = """
        SELECT sfreq + ufreq AS freq, ufreq FROM %(prefix)s_stats;
        """ % prefix_args

        self.QUERY_UNIGRAM_SQL = """
        SELECT phrase, okey, u.id, sfreq + ufreq AS freq, ufreq 
        FROM %(prefix)s_unigram u, %(prefix)s_ku ku, %(prefix)s_keys k, phrases p 
        WHERE ikey = :ikey AND k.id = k_id AND u_id = u.id AND p_id = p.id
        ORDER BY freq DESC;
        """ % prefix_args

        self.QUERY_BIGRAM_SQL = """
        SELECT e1, e2, bfreq AS freq FROM %(prefix)s_bigram b , %(prefix)s_kb kb, %(prefix)s_keys k
        WHERE ikey = :ikey AND k.id = k_id AND b_id = b.rowid
        ORDER BY freq;
        """ % prefix_args

        self.QUERY_BIGRAM_BY_ENTRY_SQL = """
        SELECT e2, bfreq FROM %(prefix)s_bigram WHERE e1 = :e1;
        """ % prefix_args

        self.UPDATE_STATS_SQL = """
        UPDATE %(prefix)s_stats SET ufreq = ufreq + :n;
        """ % prefix_args

        self.INC_UFREQ_SQL = """
        UPDATE %(prefix)s_unigram SET ufreq = ufreq + 1 WHERE id = :id;
        """ % prefix_args

        self.BIGRAM_EXIST_SQL = """
        SELECT rowid FROM %(prefix)s_bigram WHERE e1 = :e1 AND e2 = :e2;
        """ % prefix_args

        self.INC_BFREQ_SQL = """
        UPDATE %(prefix)s_bigram SET bfreq = bfreq + 1 WHERE e1 = :e1 AND e2 = :e2;
        """ % prefix_args

        self.ADD_BIGRAM_SQL = """
        INSERT INTO %(prefix)s_bigram VALUES (:e1, :e2, 1);
        """ % prefix_args

        self.QUERY_KB_SQL = """
        SELECT rowid FROM %(prefix)s_kb WHERE k_id = :k_id AND b_id = :b_id;
        """ % prefix_args

        self.ADD_KB_SQL = """
        INSERT INTO %(prefix)s_kb VALUES (:k_id, :b_id);
        """ % prefix_args

        self.__pending_updates = []

    def read_config_value(self, key):
        return DB.read_setting(self.__section + key)

    def read_config_list(self, key):
        return DB.read_setting_list(self.__section + key)
        
    def list_keywords(self):
        return [x[0] for x in DB.__conn.execute(self.LIST_KEYWORDS_SQL, ()).fetchall()]

    def proceed_pending_updates(self):
        if self.__pending_updates:
            for f in self.__pending_updates:
                f()
            self.__pending_updates = []

    def cancel_pending_updates(self):
        if self.__pending_updates:
            self.__pending_updates = []

    def lookup_freq_total(self):
        self.proceed_pending_updates()
        r = DB.__conn.execute(self.QUERY_STATS_SQL).fetchone()
        return r

    def lookup_unigram(self, key):
        #print 'lookup_unigram:', key
        args = {'ikey' : key}
        r = DB.__conn.execute(self.QUERY_UNIGRAM_SQL, args).fetchmany(DB.LIMIT)
        return r

    def lookup_bigram(self, key):
        #print 'lookup_bigram:', key
        args = {'ikey' : key}
        r = DB.__conn.execute(self.QUERY_BIGRAM_SQL, args).fetchmany(DB.LIMIT)
        return r

    def lookup_bigram_by_entry(self, e):
        #print 'lookup_bigram_by_entry:', unicode(e)
        args = {'e1' : e.get_eid()}
        r = DB.__conn.execute(self.QUERY_BIGRAM_BY_ENTRY_SQL, args).fetchmany(DB.LIMIT)
        return r

    def update_freq_total(self, n):
        #print 'update_freq_total:', n
        self.__pending_updates.append(lambda: self.__update_freq_total(n))

    def __update_freq_total(self, n):
        if DB.read_only:
            return
        args = {'n' : n}
        DB.__conn.execute(self.UPDATE_STATS_SQL, args)
        DB.flush()
        
    def update_unigram(self, e):
        #print 'update_unigram:', unicode(e)
        self.__pending_updates.append(lambda: self.__update_unigram(e))

    def __update_unigram(self, e):
        if DB.read_only:
            return
        args = {'id' : e.get_eid()}
        DB.__conn.execute(self.INC_UFREQ_SQL, args)

    def update_bigram(self, a, b, get_ikeys):
        #print 'update_bigram:', unicode(a), unicode(b)
        self.__pending_updates.append(lambda: self.__update_bigram(a, b, get_ikeys))

    def __update_bigram(self, a, b, get_ikeys):
        if DB.read_only:
            return
        args = {'e1' : a.get_eid(), 'e2' : b.get_eid()}
        if DB.__conn.execute(self.BIGRAM_EXIST_SQL, args).fetchone():
            DB.__conn.execute(self.INC_BFREQ_SQL, args)
        else:
            DB.__conn.execute(self.ADD_BIGRAM_SQL, args)
            # generate ikey-bigram index
            b_id = DB.__conn.execute(self.BIGRAM_EXIST_SQL, args).fetchone()[0]
            k_ids = [self.__get_or_insert_key(k) for k in get_ikeys(a, b)]
            for k_id in k_ids:
                self.__add_kb(k_id, b_id)

    def __get_or_insert_key(self, key):
        args = {'ikey' : key}
        r = None
        while not r:
            r = DB.__conn.execute(self.QUERY_KEY_SQL, args).fetchone()
            if not r:
                DB.__conn.execute(self.ADD_KEY_SQL, args)
        return r[0]

    def __add_kb(self, k_id, b_id):
        args = {'k_id' : k_id, 'b_id' : b_id}
        if not DB.__conn.execute(self.QUERY_KB_SQL, args).fetchone():
            DB.__conn.execute(self.ADD_KB_SQL, args)
