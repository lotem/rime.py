#! /usr/bin/env python

try:
    import psyco
    psyco.full ()
    print 'psyco activated.'
except:
    pass

import os
import sys
import optparse
import sqlite3
import re

def debug (*what):
    print >> sys.stderr, u'[DEBUG]: ', u' '.join (map (unicode, what))


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

CREATE_DICT_SQLS = """
CREATE TABLE IF NOT EXISTS %(prefix)s_keys (
    id INTEGER PRIMARY KEY,
    length INTEGER,
    kwds TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS %(prefix)s_g0 (
    sfreq INTEGER,
    ufreq INTEGER
);
INSERT INTO %(prefix)s_g0 VALUES (0, 0);
CREATE TABLE IF NOT EXISTS %(prefix)s_g1 (
    id INTEGER PRIMARY KEY,
    k_id INTEGER,
    p_id INTEGER,
    sfreq INTEGER,
    ufreq INTEGER
);
CREATE TABLE IF NOT EXISTS %(prefix)s_g2 (
    k_id INTEGER,
    u1_id INTEGER,
    u2_id INTEGER,
    freq INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS %(prefix)s_g1_idx ON %(prefix)s_g1 (k_id, p_id);
CREATE UNIQUE INDEX IF NOT EXISTS %(prefix)s_g2_idx ON %(prefix)s_g2 (k_id, u1_id, u2_id);
"""

DROP_DICT_SQLS = """
DROP INDEX IF EXISTS %(prefix)s_g1_idx;
DROP INDEX IF EXISTS %(prefix)s_g2_idx;
DROP TABLE IF EXISTS %(prefix)s_keys;
DROP TABLE IF EXISTS %(prefix)s_g0;
DROP TABLE IF EXISTS %(prefix)s_g1;
DROP TABLE IF EXISTS %(prefix)s_g2;
"""

CLEAR_SETTING_VALUE_SQL = """
DELETE FROM setting_values WHERE path_id IN (SELECT id FROM setting_paths WHERE path LIKE :path);
"""
CLEAR_SETTING_PATH_SQL = """
DELETE FROM setting_paths WHERE path LIKE :path;
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

QUERY_PHRASE_SQL = """
SELECT id FROM phrases WHERE phrase = :phrase;
"""

ADD_PHRASE_SQL = """
INSERT INTO phrases VALUES (NULL, :phrase);
"""

usage = 'usage: %prog [options] schema-file [keyword-file [phrase-file]]'
parser = optparse.OptionParser (usage)

parser.add_option ('-d', '--db-file', dest='db_file', help='specify destination sqlite db', metavar='FILE')

parser.add_option ('-k', '--keep', action='store_true', dest='keep', default=False, help='keep existing schema data')

parser.add_option ('-v', '--verbose', action='store_true', dest='verbose', default=False, help='make lots of noice')

options, args = parser.parse_args ()

if len (args) < 1:
    parser.error ('incorrect number of arguments')

schema_file = args[0] if len (args) > 0 else None

if not options.db_file:
    home_path = os.getenv ('HOME')
    db_path = os.path.join (home_path, '.ibus', 'zime')
    if not os.path.isdir (db_path):
        os.makedirs (db_path)
    db_file = os.path.join (db_path, 'plume.db')
else:
    db_file = options.db_file

conn = sqlite3.connect (db_file)
conn.executescript (INIT_PLUME_DB_SQLS)

schema = None
prefix = None
delim = None

def get_or_insert_setting_path (path):
    args = {'path' : path}
    while True:
        r = conn.execute (QUERY_SETTING_PATH_SQL, args).fetchone ()
        if r:
            break
        else:
            conn.execute (ADD_SETTING_PATH_SQL, args)
    return r[0]

def clear_schema_setting (path):
    conn.execute (CLEAR_SETTING_VALUE_SQL, {'path' : path})
    conn.execute (CLEAR_SETTING_PATH_SQL, {'path' : path})

if schema_file:
    equal_sign = re.compile (ur'\s*=\s*')
    f = open (schema_file, 'r')
    for line in f:
        x = line.strip ().decode ('utf-8')
        if not x or x.startswith (u'#'):
            continue
        try:
            (path, value) = equal_sign.split (x, 1)
        except:
            print >> sys.stderr, 'error parsing (%s) %s' % (schema_file, x)
            exit ()
        if not schema:
            m = re.match (ur'Schema/(\w+)', path)
            if m:
                schema = m.group (1)
                print >> sys.stderr, 'processing schema: %s' % schema
                clear_schema_setting (path)
                clear_schema_setting (u'Config/%s/%%' % schema)
        else:
            if not prefix and path == u'Config/%s/Prefix' % schema:
                prefix = value
                print >> sys.stderr, 'dict prefix: %s' % prefix
            if not delim and path == u'Config/%s/Delimiter' % schema:
                if value[0] == u'[' and value[-1] == u']':
                    delim = value[1]
                else:
                    delim = value[0]
        path_id = get_or_insert_setting_path (path)
        conn.execute (ADD_SETTING_VALUE_SQL, {'path_id' : path_id, 'value' : value})
    f.close ()

if not prefix:
    print >> sys.stderr, 'error: no prefix specified in schema file.'
    exit ()
prefix_args = {'prefix' : prefix}
if not options.keep:
    conn.executescript (DROP_DICT_SQLS % prefix_args)
    conn.executescript (CREATE_DICT_SQLS % prefix_args)

QUERY_KEY_SQL = """
SELECT id FROM %(prefix)s_keys WHERE kwds = :kwds;
""" % prefix_args

ADD_KEY_SQL = """
INSERT INTO %(prefix)s_keys VALUES (NULL, :length, :kwds);
""" % prefix_args

INC_G0_SQL = """
UPDATE %(prefix)s_g0 SET sfreq = sfreq + :freq;
""" % prefix_args

INC_G1_SQL = """
UPDATE %(prefix)s_g1 SET sfreq = sfreq + :freq WHERE k_id = :k_id AND p_id = :p_id;
""" % prefix_args

QUERY_G1_SQL = """
SELECT sfreq FROM %(prefix)s_g1 WHERE k_id = :k_id AND p_id = :p_id;
""" % prefix_args

ADD_G1_SQL = """
INSERT INTO %(prefix)s_g1 VALUES (NULL, :k_id, :p_id, :freq, 0);
""" % prefix_args

INC_G2_SQL = """
UPDATE %(prefix)s_g2 SET freq = freq + :freq WHERE k_id = :k_id AND u1_id = :u1_id AND u2_id = :u2_id;
""" % prefix_args

QUERY_G2_SQL = """
SELECT freq FROM %(prefix)s_g2 WHERE k_id = :k_id AND u1_id = :u1_id AND u2_id = :u2_id;
""" % prefix_args

ADD_G2_SQL = """
INSERT INTO %(prefix)s_g2 VALUES (:k_id, :u1_id, :u2_id, :freq);
""" % prefix_args

def get_or_insert_key (kwds):
    length = len (kwds.split ())
    args = {'length' : length, 'kwds' : kwds}
    r = None
    while not r:
        r = conn.execute (QUERY_KEY_SQL, args).fetchone ()
        if not r:
            conn.execute (ADD_KEY_SQL, args)
    return r[0]

def get_or_insert_phrase (phrase):
    args = {'phrase' : phrase}
    r = None
    while not r:
        r = conn.execute (QUERY_PHRASE_SQL, args).fetchone ()
        if not r:
            conn.execute (ADD_PHRASE_SQL, args)
    return r[0]

def inc_g0 (freq):
    args = {'freq' : freq}
    conn.execute (INC_G0_SQL, args)

def inc_g1 (k_id, p_id, freq):
    args = {'k_id' : k_id, 'p_id' : p_id, 'freq' : freq}
    if conn.execute (QUERY_G1_SQL, args).fetchone ():
        if freq > 0:
            conn.execute (INC_G1_SQL, args)
    else:
        conn.execute (ADD_G1_SQL, args)

def inc_g2 (k_id, u1_id, u2_id, freq):
    args = {'k_id' : k_id, 'u1_id' : u1_id, 'u2_id' : u2_id, 'freq' : freq}
    if conn.execute (QUERY_G2_SQL, args).fetchone ():
        if freq > 0:
            conn.execute (INC_G2_SQL, args)
    else:
        conn.execute (ADD_G2_SQL, args)

phrase_counter = 0
last_kwds = None
last_key_id = 0

def process_phrase (kwds, phrase, freq):
    global phrase_counter, last_kwds, last_key_id
    phrase_counter += 1
    phrase_id = get_or_insert_phrase (phrase)
    if kwds == last_kwds:
        key_id = last_key_id
    else:
        key_id = get_or_insert_key (kwds)
        last_kwds = kwds
        last_key_id = key_id
    inc_g1 (key_id, phrase_id, freq)
    inc_g0 (freq)

for phrase_file in args[1:]:
    f = open (phrase_file, 'r')
    for line in f:
        x = line.strip ().decode ('utf-8')
        if not x or x.startswith (u'#'):
            continue
        try:
            ll = x.split (u'\t', 2)
            if len (ll) == 3:
                (phrase, freq_str, kwds) = ll
                freq = int (freq_str)
            else:
                (kwds, phrase) = ll
                if phrase.startswith (u'*'):
                    phrase = phrase[1:]
                freq = 0
        except:
            print >> sys.stderr, 'error: invalid format (%s) %s' % (phrase_file, x)
            exit ()
        process_phrase (kwds, phrase, freq)
        if options.verbose and phrase_counter % 1000 == 0:
            print >> sys.stderr, '%dk phrases imported from %s.' % (phrase_counter / 1000, phrase_file)
    f.close ()

conn.commit ()
conn.close ()

print >> sys.stderr, 'done.'

