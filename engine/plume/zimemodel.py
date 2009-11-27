# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import re

def _get (c, k):
    for i in range (len (c)):
        if c[i][0] == k:
            return c[i][1]
        if c[i][0] > k:
            r = []
            c.insert (i, (k, r))
            return r
    r = []
    c.append ((k, r))
    return r

class Model:
    MAX_PHRASE_LENGTH = 10
    CONVERT, ERROR = 1, -1
    def __init__ (self, schema):
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
        self.__max_keyword_length = int (schema.get_config_value (u'MaxKeywordLength') or u'7')
        get_rules = lambda f, key: [f (r.split ()) for r in schema.get_config_list (key)]
        compile_repl_pattern = lambda x: (re.compile (x[0]), x[1])
        #self.__split_rules = get_rules (tuple, u'SplitRule')
        spelling_rules = get_rules (compile_repl_pattern, u'SpellingRule')
        fuzzy_rules = get_rules (compile_repl_pattern, u'FuzzyRule')
        self.__db = schema.get_db ()
        keywords = self.__db.list_keywords ()
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
    def __is_keyword (self, k):
        return k in self.__keywords
    def __translate_keyword (self, k):
        if k in self.__keywords:
            return self.__keywords[k] if self.__use_keyword_mapping else k
        else:
            return k
    def query (self, ctx):
        # segmentation
        n = len (ctx.input)
        m = 0
        p = [0]
        a = [[None] * j for j in range (n + 1)]
        j = 1
        while j <= n:
            if j < n and ctx.input[j] in self.__delimiter:
                d = 1
            else:
                d = 0
            ok = False
            for i in p:
                if i >= j:
                    continue
                s = u''.join (ctx.input[i:j])
                if self.__is_keyword (s):
                    ok = True
                    a[j + d][i] = self.__translate_keyword (s)
            if ok:
                m = max (m, j + d)
                p.append (j + d)
            j += d + 1
        if m != n:
            ctx.state = Model.ERROR
            ctx.sel = [(m, n, None)]
            ctx.cand = []
            return
        ctx.state = Model.CONVERT
        ctx.sel = []
        ctx.cand = []
        # path finding
        b = [n]
        c = {}
        for i in reversed (p):
            ok = False
            for j in b:
                if i < j and a[j][i]:
                    ok = True
                    for k in b:
                        if not (j == k or j < k and (j, k) in c):
                            continue
                        if (i, k) in c:
                            paths = c[(i, k)]
                        else:
                            paths = []
                            c[(i, k)] = paths
                        for path in c[(j, k)] if j < k else ([], ):
                            if len (path) < Model.MAX_PHRASE_LENGTH:
                                # path being an array of strings
                                new_path = [a[j][i]] + path
                                paths.append (new_path)  
                                r = self.__db.lookup_phrase (new_path)
                                if r:
                                    cc = _get (_get (ctx.cand, i), k)
                                    cc += r
            if ok:
                b.append (i)
        # debug
        #for x in ctx.cand:
        #    for y in x[1]:
        #        print '(%d, %d) [%s]' % (x[0], y[0], u''.join (ctx.input[x[0]:y[0]]))
        #        for z in y[1]:
        #            print z[0], 
        #        print
    def train (self, ctx):
        pass
