#!/usr/bin/env python
# -*- coding: utf-8 -*-

# zhuyin -> tonal pinyin conversion

import re

tr_from = u'''ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙㄧㄨㄩㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦˊˇˋ˙'''
tr_to = u'''bpmfdtnlgkhjqxZCSrzcsiuYaoeEIAOUMNKGR2345'''

def tr (x):
    return u''.join ([tr_to[tr_from.index (c)] if c in tr_from else c for c in x])

rules = [
    ('Z', 'zh'),
    ('C', 'ch'),
    ('S', 'sh'),
    ('Y', 'yu'),
    ('E', 'eh'),
    ('I', 'ai'),
    ('A', 'ei'),
    ('O', 'ao'),
    ('U', 'ou'),
    ('M', 'an'),
    ('N', 'en'),
    ('K', 'ang'),
    ('G', 'eng'),
    ('R', 'er'),
    (r'ien(g?)', r'in\1'),
    (r'yueng', r'iong'),
    (r'(i|yu)eh', r'\1e'),
    (r'^i([aeou])', r'y\1'),
    (r'^i', r'yi'),
    (r'^u([aeio])', r'w\1'),
    (r'^u', r'wu'),
    (r'^([jqx])yu', r'\1u'),
    (r'ueng', r'ong'),
    (r'uen', r'un'),
    (r'uei', r'ui'),
    (r'iou', r'iu'),
    (r'^([nl])yue', r'\1ue'),
    (r'^([nl])yu', r'\1v'),
    (r'^([zcs]h?|r)([2345]|$)', r'\1i\2'),
    (r'([a-z])$', r'\g<1>1'),
]

def convert (x):
    print 'convert:', x
    y = tr (x)
    for (k, v) in rules: 
        y = re.sub (k, v, y)
    return y

def process (input_file, output_file, column):
    input = open (input_file)
    output = open (output_file, 'w')
    s = None
    for line in input:
        p = line.rstrip ().decode ('utf-8').split (None, 2)
        r = [u' '.join ([convert (w) for w in p[col].split ()]) if col == column else p[col] for col in range (len (p))]
        if r == s:
            continue
        s = r
        print >>output, u'\t'.join (r).encode ('utf-8')
    output.close ()
    input.close ()

process ('zhuyin-keywords.txt', 'tonal-pinyin-keywords.txt', 0)
process ('zhuyin-phrases.txt', 'tonal-pinyin-phrases.txt', 2)
