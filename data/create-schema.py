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


CREATE_SETTING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    path TEXT,
    value TEXT
);
"""

CREATE_SETTING_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS setting_index ON settings (path);
"""

CLEAR_SCHEMA_SETTING_SQL = """
DELETE FROM settings WHERE path LIKE ?;
"""

ADD_SETTING_SQL = """
INSERT INTO settings VALUES (?, ?);
"""

DROP_KEYWORD_TABLE_SQL = """
DROP TABLE IF EXISTS %(prefix)s_keywords;
"""

DROP_KEYWORD_INDEX_SQL = """
DROP INDEX IF EXISTS %(prefix)s_keyword_index;
"""

DROP_PHRASES_TABLE_SQL = """
DROP TABLE IF EXISTS %(prefix)s_phrases;
"""

DROP_PHRASE_INDEX_SQL = """
DROP INDEX IF EXISTS %(prefix)s_phrase_index;
"""

CREATE_KEYWORD_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS %(prefix)s_keywords (
    keyword TEXT,
    phrase TEXT
);
"""

CREATE_KEYWORD_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS %(prefix)s_keyword_index ON %(prefix)s_keywords (keyword);
"""

CREATE_PHRASES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS %(prefix)s_phrases (
    klen INTEGER,
    k0 TEXT, 
    k1 TEXT, 
    k2 TEXT, 
    k3 TEXT,
    phrase TEXT,
    freq INTEGER,
    user_freq INTEGER,
    PRIMARY KEY (klen, k0, k1, k2, k3, phrase)
);
"""

CREATE_PHRASE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS %(prefix)s_phrase_index ON %(prefix)s_phrases (klen, k0, k1, k2, k3);
"""

QUERY_KEYWORD_SQL = """
SELECT phrase FROM %(prefix)s_keywords WHERE keyword = ?;
"""

ADD_KEYWORD_SQL = """
INSERT INTO %(prefix)s_keywords VALUES (?, ?);
"""

QUERY_PHRASE_SQL = """
SELECT freq FROM  %(prefix)s_phrases 
WHERE klen = ? AND k0 = ? AND k1 = ? AND k2 = ? AND k3 = ? AND phrase = ?;
"""

UPDATE_PHRASE_SQL = """
UPDATE %(prefix)s_phrases SET freq = ? 
WHERE klen = ? AND k0 = ? AND k1 = ? AND k2 = ? AND k3 = ? AND phrase = ?;
"""

ADD_PHRASE_SQL = """
INSERT INTO %(prefix)s_phrases VALUES (?, ?, ?, ?, ?, ?, ?, 0);
"""

usage = 'usage: %prog [options] schema-file [keyword-file [phrase-file]]'
parser = optparse.OptionParser (usage)

parser.add_option ('-d', '--db-file', dest='db_file', help='specify destination sqlite db', metavar='FILE')

parser.add_option ('-k', '--keep', action='store_true', dest='keep', default=False, help='keep existing schema data')

parser.add_option ('-v', '--verbose', action='store_true', dest='verbose', default=False, help='make lots of noice')

options, args = parser.parse_args ()

if len (args) not in range (1, 4):
    parser.error ('incorrect number of arguments')

schema_file = args[0] if len (args) > 0 else None
keyword_file = args[1] if len (args) > 1 else None
phrase_file = args[2] if len (args) > 2 else None

if not options.db_file:
    home_path = os.getenv ('HOME')
    db_path = os.path.join (home_path, '.ibus', 'zime')
    if not os.path.isdir (db_path):
        os.makedirs (db_path)
    db_file = os.path.join (db_path, 'zime.db')
else:
    db_file = options.db_file

conn = sqlite3.connect (db_file)
conn.execute (CREATE_SETTING_TABLE_SQL)
conn.execute (CREATE_SETTING_INDEX_SQL)

schema = None
prefix = None
delim = None
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
                conn.execute (CLEAR_SCHEMA_SETTING_SQL, (path, ))
                conn.execute (CLEAR_SCHEMA_SETTING_SQL, (u'Config/%s/%%' % schema, ))
        else:
            if not prefix and path == u'Config/%s/Prefix' % schema:
                prefix = value
                print >> sys.stderr, 'schema prefix: %s' % prefix
            if not delim and path == u'Config/%s/Delimiter' % schema:
                if value[0] == u'[' and value[-1] == u']':
                    delim = value[1]
                else:
                    delim = value[0]
        conn.execute (ADD_SETTING_SQL, (path, value))
    f.close ()

if not prefix:
    print >> sys.stderr, 'error: no prefix specified in schema file.'
    exit ()
prefix_args = {'prefix' : prefix}
if not options.keep:
    conn.execute (DROP_KEYWORD_INDEX_SQL % prefix_args)
    conn.execute (DROP_PHRASE_INDEX_SQL % prefix_args)
    conn.execute (DROP_KEYWORD_TABLE_SQL % prefix_args)
    conn.execute (DROP_PHRASES_TABLE_SQL % prefix_args)
conn.execute (CREATE_KEYWORD_TABLE_SQL % prefix_args)
conn.execute (CREATE_PHRASES_TABLE_SQL % prefix_args)
conn.execute (CREATE_KEYWORD_INDEX_SQL % prefix_args)
conn.execute (CREATE_PHRASE_INDEX_SQL % prefix_args)

QUERY_KEYWORD_SQL %= prefix_args
ADD_KEYWORD_SQL %= prefix_args
QUERY_PHRASE_SQL %= prefix_args
UPDATE_PHRASE_SQL %= prefix_args
ADD_PHRASE_SQL %= prefix_args

if keyword_file:
    keyword_map = set ()
    f = open (keyword_file, 'r')
    for line in f:
        x = line.strip ().decode ('utf-8')
        if not x or x.startswith (u'#'):
            continue
        try:
            (keyword, word) = x.split (None, 1)
        except:
            print >> sys.stderr, 'error: invalid format (%s) %s' % (keyword_file, x)
            exit ()
        if word.startswith (u'*'):
            word = word[1:]
        keyword_map.add ((keyword, word))
    f.close ()
    for p in keyword_map:
        conn.execute (ADD_KEYWORD_SQL, p)
    if options.verbose:
        print >> sys.stderr, '%d keyword mapping entries.' % len (keyword_map)

def add_phrase (k, phrase, freq):
    args = [len (k)] + k[:]
    while len (args) < 1 + 4:
        args.append (None)
    args.append (phrase)
    r = conn.execute (QUERY_PHRASE_SQL, args).fetchone ()
    if r:
        conn.execute (UPDATE_PHRASE_SQL, [r[0] + freq] + args)
    else:
        conn.execute (ADD_PHRASE_SQL, args + [freq])

def query_keyword (keyword):
    r = conn.execute (QUERY_KEYWORD_SQL, (keyword, )).fetchall ()
    return [x[0] for x in r]

def __split (k, phrase):
    #debug (u'__split: %s %s' % (u' '.join (k), phrase))
    if len (k) == 0 or len (phrase) == 0:
        return None
    r = filter (lambda x: phrase.startswith (x), query_keyword (k[0]))
    for w in r:
        if len (k) == 1 and len (phrase) == len (w):
            return [w]
        s = split_phrase (k[1:], phrase[len (w):])
        if s:
            return [w] + s
    return None

def split_phrase (k, phrase):
    if u' ' in phrase:
        return phrase.split ()
    else:
        return __split (k, phrase)
    
def join_phrase (words):
    delimiter = u'' if all ([len (w) == 1 for w in words]) else u' '
    return delimiter.join (words)

phrase_counter = 0

def process_phrase (keyword, phrase, freq):
    global phrase_counter
    phrase_counter += 1
    k = keyword.split (delim)
    if len (k) <= 4:
        add_phrase (k, phrase, freq)
    else:
        w = split_phrase (k, phrase)
        if not w:
            print >> sys.stderr, 'unable to parse phrase: %s => %s' % (keyword, phrase)
            #return
            exit ()
        i = 0
        while i <= len (k) - 4:
            add_phrase (k[i:i + 4], join_phrase (w[i:i + 4]), freq)
            i += 1

if phrase_file:
    f = open (phrase_file, 'r')
    for line in f:
        x = line.strip ().decode ('utf-8')
        if not x or x.startswith (u'#'):
            continue
        try:
            (phrase, freq_str, keyword) = x.split (u'\t', 2)
            freq = int (freq_str)
        except:
            print >> sys.stderr, 'error: invalid format (%s) %s' % (phrase_file, x)
            exit ()
        process_phrase (keyword, phrase, freq)
        if options.verbose and phrase_counter % 1000 == 0:
            print >> sys.stderr, '%dk phrases processed.' % (phrase_counter / 1000)
    f.close ()

conn.commit ()
conn.close ()

print >> sys.stderr, 'done.'

