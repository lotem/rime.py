# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import re

class Entry:
    def __init__ (self, u, i, j, prob=1.0, use_count=0, next=None):
        self.u = u
        self.i = i
        self.j = j
        self.prob = prob
        self.use_count = use_count
        self.next = next
    def get_word (self):
        return self.u[0] if self.u else u''
    def get_uid (self):
        return self.u[2] if self.u else 0
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
        return u'<%s (%d, %d) %g%s>' % \
            (self.get_word (), self.i, self.j, self.prob, (u' => %s' % self.next.get_phrase ()) if self.next else u'')

class Model:

    PENALTY = 1e-4

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

    def segmentation (self, input):
        n = len (input)
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
                lw = u''.join (input[k:j])
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
                s = u''.join (input[i:j])
                if not self.__is_keyword (s):
                    continue
                if j < n and input[j] in self.__delimiter:
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
        if m < n:
            p.append (m)
        b = []
        d = []
        # path finding
        for i in reversed (p):
            ok = i == m
            for j in b:
                if i < j and a[j][i]:
                    ok = True
                    d = [k for k in d if k >= j]
            if ok:
                b.append (i)
                d.append (i)
            else:
                a[i] = [None for j in range (len (a[i]))]
        b.reverse ()
        d.reverse ()
        return m, n, a, b, d

    def query (self, ctx):
        m, n, a, b, d = ctx.seg
        # lookup words
        edges = [[] for i in range (m)]
        c = [[None for j in range (m + 1)] for i in range (m + 1)]
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
        def add_word (x, i, j):
            #print 'add_word:', x[0], x[1], i, j
            uid = x[2]
            prob = to_prob (x[3])
            unig[uid] = prob
            if uid not in big:
                fetch_big (uid)
            if not c[i][j]:
                c[i][j] = []
            e = Entry (x, i, j, prob, x[4])
            c[i][j].append (e)
        def match_key (x, i, j, k):
            if not k:
                add_word (x, i, j)
                return
            if j == m:
                return
            for y in edges[j]:
                if k[0] in self.__fuzzy_map[y[1]]:
                    match_key (x, i, y[0], k[1:])
        def make_keys (i, k, length):
            if length == 0 or i == m:    
                return [(i, k)]
            return [(i, k)] + reduce (lambda x, y: x + y, [make_keys (z[0], k + [z[1]], length - 1) for z in edges[i]])
        def lookup (i, j, k):
            key = u' '.join (k)
            if key in queries:
                r = queries[key]
            else:
                r = queries[key] = self.__db.lookup_phrase (k)
            for x in r:
                okey = x[1].split ()
                if len (okey) <= self.__max_key_length:
                    add_word (x, i, j)
                else:
                    match_key (x, i, j, okey[self.__max_key_length:])
        # traverse
        visited = []
        for i in reversed (b):
            for j in visited:
                if i < j and a[j][i]:
                    ok = True
                    e = (j, a[j][i])
                    edges[i].append (e)
                    keys = make_keys (e[0], [e[1]], self.__max_key_length)
                    for t, k in keys:
                        lookup (i, t, k)
            visited.append (i)
        queries = None
        # last committed word's data goes to ctx.phrase[-1] and ctx.pred[-1]
        if ctx.pre:
            add_word (ctx.pre.u, -1, 0)
        # calculate sentence prediction
        pred = [None for i in range (m + 1 + 1)]
        for j in reversed (b):
            next = None
            for i in range (-1, j):
                if c[i][j]:
                    for x in c[i][j]:
                        if j == m:
                            pass
                        else:
                            x.prob *= pred[j].prob * Model.PENALTY
                            # make phrases
                            uid = x.get_uid ()
                            if uid in big:
                                if next is None:
                                    # all phrases that starts at j, grouped by uid
                                    next = dict ()
                                    for k in range (j + 1, m + 1):
                                        if c[j][k]:
                                            for y in c[j][k]:
                                                v = y.get_uid ()
                                                if v in next:
                                                    next[v].append (y)
                                                else:
                                                    next[v] = [y]
                                for v in big[uid]:
                                    if v in next:
                                        for y in next[v]:
                                            prob = big[uid][v] / unig[v] * y.prob
                                            e = Entry (x.u, i, j, prob, min (x.use_count, y.use_count), y)
                                            #print 'made phrase:', unicode (e)
                                            # save phrase
                                            k = e.get_all ()[-1].j
                                            if c[i][k]:
                                                c[i][k].append (e)
                                            else:
                                                c[i][k] = [e]
                                            # update pred[i] with concat'd phrases
                                            if not pred[i] or e.prob > pred[i].prob:
                                                pred[i] = e
                        # update pred[i] with the current word
                        if not pred[i] or x.prob > pred[i].prob:
                            pred[i] = x
        ctx.phrase = c
        ctx.pred = pred
        """
        print 'phrase:'
        for i in range (len (c)):
            for j in range (len (c[i])):
                if c[i][j]:
                    print i, j, u''.join (ctx.input[i:j])
                    for z in c[i][j]:
                        print z.get_phrase (),
                    print
        print 'pred:'
        for x in pred: print unicode (x)
        """

    def train (self, ctx, s):
        last = None
        for e in s:
            if last:
                self.__db.update_bigram (last, e)
            last = e
            self.__db.update_unigram (e)
        self.__db.update_freq_total (len (s))
        ctx.pre = Entry (last.u, -1, 0) if last else None

    def make_candidate_list (self, ctx, i, j):
        c = ctx.phrase
        m = ctx.seg[0]
        if i >= m:
            return []
        r = [[] for k in range (m + 1)]
        p = []
        if j == 0:
            j = m
            while j > i and not c[i][j]:
                j -= 1
        # info about the last phrase selected
        prev_table = dict ()
        prev = ctx.sel[-1] if ctx.sel else ctx.pre
        if prev:
            #print 'prev:', prev.get_phrase ()
            prev_award = 1.0
            prev_uid = prev.get_uid ()
            for x in c[prev.i][prev.j]:
                if x.get_uid () == prev_uid:
                    prev_award = ctx.pred[x.j].prob / x.prob
                    break
            for y in c[prev.i][prev.j:]:
                if y:
                    for x in y:
                        if x.next and x.get_uid () == prev_uid:
                            prev_table[id (x.next)] = x.prob * prev_award
        def adjust (e):
            if id (e) not in prev_table:
                return e
            prob = prev_table[id (e)]
            return Entry (e.u, e.i, e.j, prob, e.use_count, e.next)
        #print 'range:', u''.join (ctx.input[i:j])
        for k in range (j, i, -1):
            if c[i][k]:
                for x in c[i][k]:
                    e = adjust (x)
                    if e.next:
                        #print "concat'd phrase:", e.get_phrase (), e.prob
                        p.append ((k, e))
                    else:
                        r[k].append (e)
        phrase_cmp = lambda a, b: -cmp (a[1].prob, b[1].prob)
        p.sort (cmp=phrase_cmp)
        LIMIT = 3
        for x in p[:LIMIT]:
            r[x[0]].append (x[1])
        if not r[j]:
            for x in p:
                if x[0] == j:
                    r[j].append (x[1])
                    break
            #print 'supplemented:', r[j][0].get_phrase ()
        cand_cmp = lambda a, b: -cmp (a.use_count + a.prob, b.use_count + b.prob)
        return [(e.get_phrase (), e) for s in reversed (r) if s for e in sorted (s, cand_cmp)]
