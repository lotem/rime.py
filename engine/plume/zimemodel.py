# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import re

class Entry:
    def __init__ (self, u, i, j, prob=0.0, next=None):
        self.u = u
        self.i = i
        self.j = j
        self.prob = prob
        self.next = next
    def get_word (self):
        return self.u[0] if self.u else u''
    def get_uid (self):
        return self.u[2] if self.u else 0
    def get_ufreq (self):
        return self.u[4] if self.u else 0
    def get_all (self):
        w = []
        s = self
        while s:
            w.append (s)
            s = s.next
        return w
    def get_phrase (self):
        return u''.join ([e.get_word () for e in self.get_all ()])
    def __unicode__ (self):
        return u'<%s (%d, %d) %f%s>' % \
            (self.get_word (), self.i, self.j, self.prob, (u' => [%s]' % self.next.get_word ()) if self.next else u'')

class Model:

    PENALTY = 1e-3

    def __init__ (self, schema):
        self.__max_key_length = int (schema.get_config_value (u'MaxKeyLength') or u'3')
        self.__max_keyword_length = int (schema.get_config_value (u'MaxKeywordLength') or u'7')
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
        get_rules = lambda f, key: [f (r.split ()) for r in schema.get_config_list (key)]
        compile_repl_pattern = lambda x: (re.compile (x[0]), x[1])
        #self.__split_rules = get_rules (tuple, u'SplitRule')
        self.__divide_rules = get_rules (compile_repl_pattern, u'DivideRule')
        spelling_rules = get_rules (compile_repl_pattern, u'SpellingRule')
        fuzzy_rules = get_rules (compile_repl_pattern, u'FuzzyRule')
        self.__db = schema.get_db ()
        keywords = self.__db.list_keywords ()
        def apply_spelling_rule (m, r):
            return (r[0].sub (r[1], m[0], 1), m[1])
        d = dict ([reduce (apply_spelling_rule, spelling_rules, (k, frozenset ([k]))) for k in keywords])
        akas = dict ()
        def add_aka (s, x):
            if s in akas:
                a = akas[s]
            else:
                a = akas[s] = []
            if x not in a:
                a.append (x)
        def del_aka (s, x):
            if s in akas:
                a = akas[s]
            else:
                a = akas[s] = []
            if x in a:
                a.remove (x)
            if not a:
                del akas[s]
        def apply_fuzzy_rule (d, r):
            dd = dict (d)
            for x in d:
                if not r[0].search (x):
                    continue
                y = r[0].sub (r[1], x, 1)
                if y == x:
                    continue
                if y not in dd:
                    dd[y] = d[x]
                    add_aka (dd[y], y)
                else:
                    del_aka (dd[y], y)
                    dd[y] |= d[x]
                    add_aka (dd[y], y)
            return dd
        for k in d:
            add_aka (d[k], k)
        self.__fuzzy_map = reduce (apply_fuzzy_rule, fuzzy_rules, d)
        kw = dict ()
        for s in akas:
            k = akas[s][0]
            for x in akas[s]:
                kw[x] = k
        self.__keywords = kw

    def __is_keyword (self, k):
        return k in self.__keywords

    def __translate_keyword (self, k):
        if k in self.__keywords:
            return self.__keywords[k]
        else:
            return k

    def query (self, ctx):
        # segmentation
        n = len (ctx.input)
        m = 0
        p = []
        a = [[None] * j for j in range (n + 1)]
        q = [0]
        def allow_divide (i, j, s):
            flag = True
            for k in p:
                if not a[j][k]:
                    if flag and a[i][k]:
                        return True
                    else:
                        continue
                lw = u''.join (ctx.input[k:j])
                for r in self.__divide_rules:
                    m = r[0].search (lw)
                    if m and r[0].sub (r[1], lw, 1) == s:
                        return True
                flag = False
            return False
        while q:
            i = q.pop (0)
            if i == n:
                p.append (i)
                break
            ok = False
            for j in range (min (n + 1, i + self.__max_keyword_length)):
                s = u''.join (ctx.input[i:j])
                if not self.__is_keyword (s):
                    continue
                if j + 1 < n and ctx.input[j + 1] in self.__delimiter:
                    t = j + 1
                else:
                    t = j
                #print i, t, s
                if t not in q:
                    q.append (t)
                    m = max (m, t)
                elif not allow_divide (i, t, s):
                    continue
                a[t][i] = self.__translate_keyword (s)
                ok = True
            if ok:
                p.append (i)
            q.sort ()
        if m != n:
            ctx.err = Entry (None, m, n)
            ctx.cand = []
            ctx.sugg = []
            return
        # lookup phrases
        b = []
        d = [[] for i in range (n)]
        c = [[None for j in range (n + 1)] for i in range (n)]
        unig = {}
        big = {}
        queries = {}
        total, utotal = [x + 0.1 for x in self.__db.lookup_freq_total ()]
        to_prob = lambda x: (x + 0.1) / total
        def fetch_big (id):
            r = self.__db.lookup_bigram (id)
            s = big[id] = {}
            for x in r:
                s[x[0]] = to_prob (x[1])
        def add_phrase (x, i, j):
            #print 'add_phrase:', x[0], x[1], i, j
            uid = x[2]
            prob = to_prob (x[3])
            unig[uid] = prob
            if uid not in big:
                fetch_big (uid)
            if not c[i][j]:
                c[i][j] = []
            e = Entry (x, i, j, prob)
            c[i][j].append (e)
        def match_key (x, i, j, k):
            if not k:
                add_phrase (x, i, j)
                return
            if j == n:
                return
            for y in d[j]:
                if k[0] in self.__fuzzy_map[y[1]]:
                    match_key (x, i, y[0], k[1:])
        def make_keys (i, k, length):
            if length == 0 or i == n:    
                return [(i, k)]
            return [(i, k)] + reduce (lambda x, y: x + y, [make_keys (z[0], k + [z[1]], length - 1) for z in d[i]])
        def lookup (i, j, k):
            key = u' '.join (k)
            if key in queries:
                r = queries[key]
            else:
                r = queries[key] = self.__db.lookup_phrase (k)
            for x in r:
                okey = x[1].split ()
                if len (okey) <= self.__max_key_length:
                    add_phrase (x, i, j)
                else:
                    match_key (x, i, j, okey[self.__max_key_length:])
        # path finding
        for i in reversed (p):
            ok = i == n
            for j in b:
                if i < j and a[j][i]:
                    ok = True
                    e = (j, a[j][i])
                    d[i].append (e)
                    keys = make_keys (e[0], [e[1]], self.__max_key_length)
                    for t, k in keys:
                        lookup (i, t, k)
            if ok:
                b.append (i)
            else:
                a[i] = [None for j in range (len (a[i]))]
        queries = None
        """
        print 'c:'
        for i in range (len (c)):
            for j in range (len (c[i])):
                if c[i][j]:
                    print u''.join (ctx.input[i:j])
                    for z in c[i][j]:
                        print z[0][0],
                    print
        """
        sugg = [None for i in range (n + 1)]
        for j in b:
            next = None
            for i in range (j):
                if c[i][j]:
                    for x in c[i][j]:
                        if j == n:
                            pass
                        else:
                            prob = x.prob * sugg[j].prob * Model.PENALTY
                            uid = x.get_uid ()
                            if uid in big:
                                if next is None:
                                    next = set ()
                                    for k in range (j + 1, n + 1):
                                        if c[j][k]:
                                            for y in c[j][k]:
                                                next.add (y.get_uid ())
                                succ = set (big[uid].keys ()) & next
                                if succ:
                                    #TODO: 
                                    print 'big!'
                            x.prob = prob
                        if not sugg[i] or x.prob > sugg[i].prob:
                            sugg[i] = x
        ctx.cand = c
        ctx.sugg = sugg
        #for x in sugg: print unicode (x)

    def train (self, ctx):
        # TODO
        return
        p = ctx.last_phrase
        a = [x for s in ctx.sel for x in s[2][1]]
        for x in a:
            if p:
                self.__db.update_bigram (p, x)
            p = x
            self.__db.update_unigram (x)
        ctx.last_phrase = p
        self.__db.update_freq_total (len (a))

