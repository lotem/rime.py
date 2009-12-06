# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import re

def _get (c, k, create=True):
    for i in range (len (c)):
        if c[i][0] == k:
            return c[i][1]
        if c[i][0] > k:
            r = []
            if create:
                c.insert (i, (k, r))
            return r
    r = []
    if create:
        c.append ((k, r))
    return r

class Model:
    MAX_PHRASE_LENGTH = 10
    CONVERT, ERROR = 1, -1
    PENALTY = 1e-3
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
        cand = []
        unig = {}
        big = {}
        total, utotal = [x + 0.1 for x in self.__db.lookup_freq_total ()]
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
                                #print 'debug:', new_path
                                paths.append (new_path)  
                                r = self.__db.lookup_bigram (new_path)
                                if r:
                                    for x in r:
                                        if x[1] in big:
                                            ss = big[x[1]] 
                                        else:
                                            ss = big[x[1]] = {}
                                        ss[x[2]] = (x[0] + 0.1) / total
                                r = self.__db.lookup_phrase (new_path)
                                if r:
                                    for x in r:
                                        prob = (x[3] + 0.1) / total
                                        unig[x[1]] = prob
                                        e = (x[0], [(x[1], x[2])], prob, x[4] + 1, 0)
                                        s = _get (_get (cand, i), k)
                                        s.append (e)
                                        if k == n:
                                            continue
                                        succ = big[x[1]] if x[1] in big else {}
                                        opt = (u'', [], 0.0)
                                        for y in _get (_get (cand, k, False), n, False):
                                            u = y[1][0][0]
                                            if u in succ:
                                                prob = succ[u] / unig[u] * y[2]
                                                ufreq = min (e[3], y[3])
                                                rank = 1
                                            else:
                                                prob = e[2] * y[2] * Model.PENALTY
                                                ufreq = max (1, min (e[3], y[3]) - 1)
                                                rank = 2
                                            if prob > opt[2]:
                                                opt = (e[0] + y[0], e[1] + y[1], prob, ufreq, max (e[4], y[4], rank)) 
                                        if opt[1]:
                                            s = _get (_get (cand, i), n)
                                            s.append (opt)
            if ok:
                b.append (i)
        ctx.cand = cand 
        ctx.unig = unig
        ctx.big = big
    def __adjust (self, x, ctx):
        """ajust candidate order in regard to the previously selected phrase"""
        if ctx.sel:
            prev = ctx.sel[-1][2]
        else:
            return x
        u = prev[1][0][0]
        if u not in ctx.big:
            return x
        succ = ctx.big[u]
        a = x[1][0][0]
        if a not in succ:
            return x
        award = succ[a] / ctx.unig[a] / ctx.unig[u] / Model.PENALTY;
        return x[:2] + (x[2] * award, ) + x[3:]
    def calculate_candidates (self, ctx, c):
        result = []
        count = 3
        rank = 2
        order_by_prob_desc = lambda a, b: -cmp (a[2] + a[3], b[2] + b[3])
        for t in sorted ([self.__adjust (x, ctx) for x in c], cmp=order_by_prob_desc):
            r = t[4]
            if r > rank or any ([x[0] == t[0] for x in result]):
                continue
            rank = 1
            if r > 0:
                if count == 0:
                    continue
                count -= 1
            #print t[0], t
            result.append ((t[0], t))
        return result
    def train (self, ctx):
        p = ctx.last_phrase
        a = [x for s in ctx.sel for x in s[2][1]]
        for x in a:
            if p:
                self.__db.update_bigram (p, x)
            p = x
            self.__db.update_unigram (x)
        ctx.last_phrase = p
        self.__db.update_freq_total (len (a))

