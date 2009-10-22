#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from ibus import keysyms
from ibus import modifier

from zimecore import *

class RomanParser (Parser):
    def __init__ (self, schema):
        self.__alphabet = schema.get_config_char_sequence (u'Alphabet') or u'abcdefghijklmnopqrstuvwxyz'
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
        self.__max_keyword_length = int (schema.get_config_value (u'MaxKeywordLength') or u'7')
        get_rules = lambda f, key: [f (r.split ()) for r in schema.get_config_list (key)]
        compile_repl_pattern = lambda x: (re.compile (x[0]), x[1])
        self.__split_rules = get_rules (tuple, u'SplitRule')
        spelling_rules = get_rules (compile_repl_pattern, u'SpellingRule')
        fuzzy_rules = get_rules (compile_repl_pattern, u'FuzzyRule')
        db = schema.get_db ()
        keywords = db.list_keywords ()
        self.__use_keyword_mapping = bool (spelling_rules or fuzzy_rules)
        if self.__use_keyword_mapping:
            def apply_spelling_rule (m, r):
                return (r[0].sub (r[1], m[0], 1), m[1])
            d = dict ([reduce (apply_spelling_rule, spelling_rules, (k, k)) for k in keywords])
            def apply_fuzzy_rule (d, r):
                dd = dict (d)
                for x in d:
                    y = r[0].sub (r[1], x, 1)
                    if y not in dd:
                        dd[y] = d[x]
                return dd
            self.__keywords = reduce (apply_fuzzy_rule, fuzzy_rules, d)
        else:
            self.__keywords = set (keywords)
        self.__clear ()
    def __clear (self):
        self.__input = []
    def __is_empty (self):
        return len (self.__input) == 0
    def __is_keyword (self, s):
        return s in self.__keywords
    def __parse (self, ctx):
        k = []
        remainder = u''
        i = 0
        n = len (self.__input)
        while i < n:
            keyword = None
            split_rule_index = 0
            for j in range (min (n, i + self.__max_keyword_length), i, -1):
                s = u''.join (self.__input[i:j])
                if j < n:
                    split = False
                    for t in range (split_rule_index, len (self.__split_rules)):
                        r = self.__split_rules[t]
                        if self.__input[j - 1] in r[0] and self.__input[j] in r[1]:
                            split_rule_index = t + 1
                            split = True
                            break
                    if split:
                        continue
                if self.__is_keyword (s):
                    keyword = s
                    k.append (s) 
                    delim = None
                    if j < len (self.__input) and self.__input[j] in self.__delimiter:
                        delim = self.__input[j]
                        i = j + 1
                    else:
                        i = j
                    k.append (delim)
                    break
                split_rule_index = 0
            if not keyword:
                remainder = u''.join (self.__input[i:])
                break
        ctx.aux_string = u''.join ([self.__delimiter[0] if x is None else x for x in k] + [remainder])
        if self.__use_keyword_mapping:
            ctx.keywords = [self.__keywords[x] for x in k[::2]] + [remainder]
        else:
            ctx.keywords = k[::2] + [remainder]
        #print 'parse result:', ctx.keywords
        ctx.update_keywords ()
    def process (self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return True
        if event.keycode == keysyms.BackSpace:
            if self.__is_empty ():
                return False
            self.__input.pop ()
            self.__parse (ctx)
            return True
        if event.keycode in (keysyms.space, keysyms.Return):
            self.__clear ()
            return False
        ch = event.get_char ()
        if ch in self.__alphabet or not self.__is_empty () and ch in self.__delimiter:
            self.__input.append (ch)
            self.__parse (ctx)
            return True
        return False

class ComboParser (Parser):
    pass

class GroupingParser (Parser):
    def __init__ (self, schema):
        self.__key_groups = schema.get_config_value (u'KeyGroups').split ()
        self.__code_groups = schema.get_config_value (u'CodeGroups').split ()
        self.__group_count = len (self.__key_groups)
        self.clear ()
    def clear (self):
        self.__slots = [u''] * self.__group_count
        self.__cursor = 0
    def process (self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return True
        if event.keycode == keysyms.BackSpace:
            if self.__is_empty ():
                return False
            j = self.__group_count - 1
            while j > 0 and not self.__slots[j]:
                j -= 1
            self.__slots[j] = u''
            while j > 0 and not self.__slots[j]:
                j -= 1
            self.__cursor = j
            ctx.keywords[-1] = u''.join (self.__slots)
            ctx.update_keywords ()
            return True
        if ctx.cursor < len (ctx.keywords) - 1:
            return False
        if event.keycode == keysyms.space:
            if self.__is_empty ():
                return False
            self.clear ()
            ctx.keywords.append (u'')
            ctx.update_keywords ()
            return True
        ch = event.get_char ()
        k = self.__cursor
        while ch not in self.__key_groups[k]:
            k += 1
            if k >= self.__group_count:
                k = 0
            if k == self.__cursor:
                return not self.__is_empty ()
        idx = self.__key_groups[k].index (ch)
        self.__slots[k] = self.__code_groups[k][idx]
        ctx.keywords[-1] = u''.join (self.__slots)
        k += 1
        if k >= self.__group_count:
            self.clear ()
            ctx.keywords.append (u'')
        else:
            self.__cursor = k
        ctx.update_keywords ()
        return True
    def __is_empty (self):
        return not any (self.__slots)

def register_parsers ():
    Parser.register ('roman', RomanParser)
    Parser.register ('combo', ComboParser)
    Parser.register ('grouping', GroupingParser)

