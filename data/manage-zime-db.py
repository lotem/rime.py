#! /usr/bin/env python

try:
    import psyco
    psyco.full()
    print 'psyco activated.'
except:
    pass

import os
import sys
import optparse
import sqlite3
import re

def debug(*what):
    print >> sys.stderr, u'[DEBUG]: ', u' '.join(map(unicode, what))

CREATE_DICT_SQLS = """
CREATE TABLE IF NOT EXISTS %(prefix)s_stats (
    sfreq INTEGER,
    ufreq INTEGER
);
CREATE TABLE IF NOT EXISTS %(prefix)s_unigram (
    id INTEGER PRIMARY KEY,
    p_id INTEGER,
    okey TEXT,
    sfreq INTEGER,
    ufreq INTEGER
);
CREATE TABLE IF NOT EXISTS %(prefix)s_bigram (
    e1 INTEGER,
    e2 INTEGER,
    bfreq INTEGER,
    PRIMARY KEY (e1, e2)
);
INSERT INTO %(prefix)s_stats VALUES (0, 0);
CREATE UNIQUE INDEX IF NOT EXISTS %(prefix)s_entry_idx ON %(prefix)s_unigram (p_id, okey);
CREATE TABLE IF NOT EXISTS %(prefix)s_keywords (
    keyword TEXT
);
CREATE TABLE IF NOT EXISTS %(prefix)s_keys (
    id INTEGER PRIMARY KEY,
    ikey TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS %(prefix)s_ku (
    k_id INTEGER,
    u_id INTEGER,
    PRIMARY KEY (k_id, u_id)
);
CREATE TABLE IF NOT EXISTS %(prefix)s_kb (
    k_id INTEGER,
    b_id INTEGER,
    PRIMARY KEY (k_id, b_id)
);
"""

DROP_DICT_SQLS = """
DROP INDEX IF EXISTS %(prefix)s_entry_idx;
DROP TABLE IF EXISTS %(prefix)s_unigram;
DROP TABLE IF EXISTS %(prefix)s_bigram;
DROP TABLE IF EXISTS %(prefix)s_stats;
DROP TABLE IF EXISTS %(prefix)s_keywords;
DROP TABLE IF EXISTS %(prefix)s_keys;
DROP TABLE IF EXISTS %(prefix)s_ku;
DROP TABLE IF EXISTS %(prefix)s_kb;
"""

CLEAR_SETTING_VALUE_SQL = """
DELETE FROM setting_values WHERE path_id IN (SELECT id FROM setting_paths WHERE path LIKE :path);
"""

CLEAR_SETTING_PATH_SQL = """
DELETE FROM setting_paths WHERE path LIKE :path;
"""

QUERY_SCHEMA_LIST_SQL = """
SELECT substr(path, length('SchemaList/') + 1), value FROM setting_paths p 
LEFT JOIN setting_values v ON p.id = v.path_id 
WHERE path LIKE 'SchemaList/%';
"""

QUERY_DICT_PREFIX_SQL = """
SELECT substr(path, 1, length(path) - length('/Dict')), value 
FROM setting_paths p LEFT JOIN setting_values v ON p.id = v.path_id 
WHERE path LIKE '%/Dict';
"""

QUERY_PHRASE_SQL = """
SELECT id FROM phrases WHERE phrase = :phrase;
"""

ADD_PHRASE_SQL = """
INSERT INTO phrases VALUES (NULL, :phrase);
"""

ADD_UNIGRAM_SQL = """
INSERT INTO %(prefix)s_unigram VALUES (NULL, :p_id, :okey, 0, :freq);
"""

QUERY_UNIGRAM_SQL = """
SELECT id FROM %(prefix)s_unigram WHERE p_id = :p_id AND okey = :okey;
"""

QUERY_UNIGRAM_SQL = """
SELECT u.id FROM %(prefix)s_unigram u LEFT JOIN phrases p ON p_id = p.id 
WHERE phrase = :phrase AND okey = :okey;
"""

QUERY_USER_FREQ_SQL = """
SELECT phrase, ufreq, okey
FROM %(prefix)s_unigram u, phrases p 
WHERE ufreq > 0 AND p_id = p.id
"""

QUERY_USER_GRAM_SQL = """
SELECT p1.phrase, p2.phrase, bfreq, u1.okey, u2.okey
FROM %(prefix)s_bigram b, %(prefix)s_unigram u1, %(prefix)s_unigram u2, phrases p1, phrases p2
WHERE bfreq > 0 AND e1 = u1.id AND e2 = u2.id AND u1.p_id = p1.id AND u2.p_id = p2.id
"""

INC_USER_FREQ_SQL = """
UPDATE %(prefix)s_unigram SET ufreq = ufreq + :n WHERE id = :id;
"""

QUERY_KEY_SQL = """
SELECT id FROM %(prefix)s_keys WHERE ikey = :ikey;
"""

ADD_KEY_SQL = """
INSERT INTO %(prefix)s_keys VALUES (NULL, :ikey);
"""

UPDATE_STATS_SQL = """
UPDATE %(prefix)s_stats SET ufreq = ufreq + :freq;
"""

INC_UFREQ_SQL = """
UPDATE %(prefix)s_unigram SET ufreq = ufreq + :freq WHERE id = :id;
"""

BIGRAM_EXIST_SQL = """
SELECT rowid FROM %(prefix)s_bigram WHERE e1 = :e1 AND e2 = :e2;
"""

INC_BFREQ_SQL = """
UPDATE %(prefix)s_bigram SET bfreq = bfreq + :n WHERE e1 = :e1 AND e2 = :e2;
"""

ADD_BIGRAM_SQL = """
INSERT INTO %(prefix)s_bigram VALUES (:e1, :e2, 1);
"""

QUERY_KB_SQL = """
SELECT rowid FROM %(prefix)s_kb WHERE k_id = :k_id AND b_id = :b_id;
"""

ADD_KB_SQL = """
INSERT INTO %(prefix)s_kb VALUES (:k_id, :b_id);
"""

def clear_schema_setting(path):
    cur.execute(CLEAR_SETTING_VALUE_SQL, {'path' : path})
    cur.execute(CLEAR_SETTING_PATH_SQL, {'path' : path})

def get_or_insert_key(key):
    args = {'ikey' : u' '.join(key)}
    r = None
    while not r:
        r = cur.execute(QUERY_KEY_SQL, args).fetchone()
        if not r:
            cur.execute(ADD_KEY_SQL, args)
    return r[0]

def get_or_insert_phrase(phrase):
    args = {'phrase' : phrase}
    r = None
    while not r:
        r = cur.execute(QUERY_PHRASE_SQL, args).fetchone()
        if not r:
            cur.execute(ADD_PHRASE_SQL, args)
    return r[0]

def inc_userfreq(phrase, okey, freq, prefix_args):

    def add_phrase(args):
        cur.execute(ADD_UNIGRAM_SQL, args)
        # generate index for the new phrase
        key_ids = [get_or_insert_key(k) for k in g([[]], okey.split(), 0)]
        if not key_ids:
            print >> sys.stderr, 'failed index generation for phrase [%s] %s.' % (okey, phrase)
        for k_id in key_ids:
            add_ku(k_id, u_id)

    # increment userfreq in table *_unigram
    p_id = get_or_insert_phrase(phrase)
    args = {'p_id' : p_id, 'okey' : okey, 'freq' : freq}
    r = cur.execute(QUERY_UNIGRAM_SQL % prefix_args, args).fetchone()
    if not r:
        print >> sys.stderr, 'INFO: introducing new phrase', phrase, okey
        add_phrase(args)
        r = cur.execute(QUERY_UNIGRAM_SQL, args).fetchone()
    elif freq > 0:
        cur.execute(INC_UFREQ_SQL, args)

    # update userfreq total in table *_stats
    if freq > 0:
        cur.execute(UPDATE_STATS_SQL % prefix_args, {'freq': freq})

    print >> sys.stderr, 'DEBUG: restored userfreq', phrase, okey, freq

def inc_usergram(phrase1, okey1, phrase2, okey2, freq, prefix_args):
    print >> sys.stderr, 'TODO: restore usergram', phrase1, okey1, phrase2, okey2, freq
    pass


usage = 'usage: %prog [options] [command]'
parser = optparse.OptionParser(usage)

parser.add_option('-c', '--compact', action='store_true', dest='compact', default=False, help='compact db file')
parser.add_option('-d', '--db-file', dest='db_file', help='specify destination sqlite db', metavar='FILE')

parser.add_option('-l', '--list', action='store_true', dest='list_schema', default=False, help='show schema list (default command)')
parser.add_option('-k', '--kill', dest='kill_schema', help='delete schema and associated dict', metavar='Schema')
parser.add_option('-s', '--save', dest='save_dict', help='save user data from specified dict', metavar='dict')
parser.add_option('-r', '--restore', dest='restore_dict', help='restore user data into specified dict', metavar='dict')

options, args = parser.parse_args()

if len(args) != 0:
    parser.error('incorrect number of arguments')

if not options.db_file:
    home_path = os.getenv('HOME') or os.getenv('USERPROFILE')
    db_path = os.path.join(home_path, '.ibus', 'zime')
    if not os.path.isdir(db_path):
        os.makedirs(db_path)
    db_file = os.path.join(db_path, 'zime.db')
else:
    db_file = options.db_file

if not os.path.exists(db_file):
    print >> sys.stderr, 'cannot locate db file: %s' % db_file
    exit(-1)
conn = sqlite3.connect(db_file)
cur = conn.cursor()

# retrieve schema list and associated dict names
schema_list = cur.execute(QUERY_SCHEMA_LIST_SQL).fetchall()
schemas = set([x[0] for x in schema_list])
prefixes = set()
prefix_map = dict()
for (schema, prefix) in cur.execute(QUERY_DICT_PREFIX_SQL).fetchall():
    prefixes.add(prefix)
    prefix_map[schema] = prefix


def list_schema():
    print u'# schemas installed in %s:' % db_file
    print u'%-20s %-20s %s' % (u'#<SCHEMA>', u'<DICT>', u'<NAME>')
    for (schema, label) in schema_list:
        prefix = prefix_map[schema] if schema in prefix_map else u'--'
        print u"%-20s %-20s %s" % (schema, prefix, label)


def kill_schema(schema):
    if schema not in schemas:
        print >> sys.stderr, u'non-existing schema: %s' % schema
        return
    clear_schema_setting(u'SchemaList/%s' % schema)
    clear_schema_setting(u'SchemaChooser/%s/%%' % schema)
    clear_schema_setting(u'%s/%%' % schema)
    if schema not in prefix_map:
        print >> sys.stderr, u'warning: no dict associated with schema: %s' % schema
    else:
        prefix = prefix_map[schema]
        no_longer_needed = True
        for s, p in prefix_map.iteritems():
            if p == prefix and s != schema:
                no_longer_needed = False
                break
        if no_longer_needed:
            print >> sys.stderr, u'dict %s associated with %s is no longer needed; dropped...' % (prefix, schema)
            cur.executescript(DROP_DICT_SQLS % {'prefix' : prefix})
    if options.compact:
        cur.execute("""VACUUM;""")
    conn.commit()
    print >> sys.stderr, u'schema %s has been removed.' % schema


def save_dict(prefix):
    if prefix not in prefixes:
        print >> sys.stderr, u'non-existing dict: %s' % prefix
        return

    filename_prefix = prefix.replace(u'_', u'-')
    prefix_args = {'prefix' : prefix}

    userfreq_file = "%s-userfreq.txt" % filename_prefix
    out = open(userfreq_file, "w")
    r = cur.execute(QUERY_USER_FREQ_SQL % prefix_args).fetchall()
    for x in r:
        print >> out, (u"%s\t%d\t%s" % tuple(x)).encode('utf-8')
    out.close()
    print >> sys.stderr, '%d records saved to %s' % (len(r), userfreq_file)

    usergram_file = "%s-usergram.txt" % filename_prefix
    out = open(usergram_file, "w")
    r = cur.execute(QUERY_USER_GRAM_SQL % prefix_args).fetchall()
    for x in r:
        print >> out, (u"%s\t%s\t%d\t%s\t%s" % tuple(x)).encode('utf-8')
    out.close()
    print >> sys.stderr, '%d records saved to %s' % (len(r), usergram_file)
    

def restore_dict(prefix):
    if prefix not in prefixes:
        print >> sys.stderr, u'non-existing dict: %s' % prefix
        return

    filename_prefix = prefix.replace(u'_', u'-')
    prefix_args = {'prefix' : prefix}

    userfreq_file = "%s-userfreq.txt" % filename_prefix
    for line in open(userfreq_file):
        x = line.strip().decode('utf-8').lstrip(u'\ufeff')
        if not x or x.startswith(u'#'):
            continue
        try:
            ll = x.split(u'\t', 2)
            (phrase, freq_str, okey) = ll
            freq = int(freq_str)
            if u' ' in phrase:
                phrase = phrase.replace(u' ', '')
        except:
            print >> sys.stderr, 'error: invalid format (%s) %s' % (userfreq_file, x)
            exit()
        inc_userfreq(phrase, okey, freq, prefix_args)

    usergram_file = "%s-usergram.txt" % filename_prefix
    for line in open(usergram_file):
        x = line.strip().decode('utf-8').lstrip(u'\ufeff')
        if not x or x.startswith(u'#'):
            continue
        try:
            ll = x.split(u'\t', 4)
            (phrase1, phrase2, freq_str, okey1, okey2) = ll
            freq = int(freq_str)
            if u' ' in phrase1:
                phrase1 = phrase1.replace(u' ', '')
            if u' ' in phrase2:
                phrase2 = phrase2.replace(u' ', '')
        except:
            print >> sys.stderr, 'error: invalid format (%s) %s' % (usergram_file, x)
            exit()
        inc_usergram(phrase1, okey1, phrase2, okey2, freq, prefix_args)

    if options.compact:
        cur.execute("""VACUUM;""")
    conn.commit()
    print >> sys.stderr, 'done.'


if options.kill_schema:
    kill_schema(options.kill_schema)
elif options.save_dict:
    save_dict(options.save_dict)
elif options.restore_dict:
    restore_dict(options.restore_dict)
else:
    list_schema()

conn.close()
