# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import re

class Entry:
    def __init__(self, e, i, j, prob=1.0, use_count=0, next=None):
        self.e = e
        self.i = i
        self.j = j
        self.prob = prob
        self.use_count = use_count
        self.next = next
    def get_word(self):
        return self.e[0] if self.e else u''
    def get_okey(self):
        return self.e[1] if self.e else u''
    def get_eid(self):
        return self.e[2] if self.e else 0
    def get_all(self):
        w = []
        s = self
        while s:
            w.append(s)
            s = s.next
        return w
    def get_phrase(self):
        return u''.join([e.get_word() for e in self.get_all()])
    def partof(self, other):
        if self.use_count != other.use_count:
            return False
        a, b = self, other
        while a and b and a.get_eid() == b.get_eid():
            a, b = a.next, b.next
        return not a
    def __unicode__(self):
        return u'<%s (%d, %d) %g%s>' % \
            (self.get_word(), self.i, self.j, self.prob, (u' => %s' % self.next.get_phrase()) if self.next else u'')

class SpellingCollisionError:
    def __init__(self, rule, vars):
        self.rule = rule
        self.vars = vars
    def __str__(self):
        return 'spelling collision detected in %s: %s' % (self.rule, repr(self.vars))

class SpellingAlgebra:

    def __init__(self, report_errors=True):
        self.__report_errors = report_errors

    def calculate(self, mapping_rules, fuzzy_rules, spelling_rules, alternative_rules, keywords):

        akas = dict()

        def add_aka(s, x):
            if s in akas:
                a = akas[s]
            else:
                a = akas[s] = []
            if x not in a:
                a.append(x)

        def del_aka(s, x):
            if s in akas:
                a = akas[s]
            else:
                a = akas[s] = []
            if x in a:
                a.remove(x)
            if not a:
                del akas[s]

        def transform(x, r):
            return r[0].sub(r[1], x, 1)

        def apply_fuzzy_rule(d, r):
            dd = dict(d)
            for x in d:
                if not r[0].search(x):
                    continue
                y = transform(x, r)
                if y == x:
                    continue
                if y not in dd:
                    dd[y] = d[x]
                    add_aka(dd[y], y)
                else:
                    del_aka(dd[y], y)
                    dd[y] |= d[x]
                    add_aka(dd[y], y)
            return dd

        def apply_alternative_rule(d, r):
            for x in d.keys():
                if not r[0].search(x):
                    continue
                y = transform(x, r)
                if y == x:
                    continue
                if y not in d:
                    d[y] = d[x]
                elif self.__report_errors:
                    raise SpellingCollisionError('AlternativeRule', (x, d[x], y, d[y]))
            return d

        io_map = dict()
        for okey in keywords:
            ikey = reduce(transform, mapping_rules, okey)
            s = frozenset([okey])
            if ikey in io_map:
                io_map[ikey] |= s
            else:
                io_map[ikey] = s
        for ikey in io_map:
            add_aka(io_map[ikey], ikey)
        io_map = reduce(apply_fuzzy_rule, fuzzy_rules, io_map)

        oi_map = dict()
        ikeys = []
        spellings = []
        for okeys in akas:
            ikey = akas[okeys][0]
            ikeys.append(ikey)
            for x in akas[okeys]:
                spellings.append((x, ikey))
            for k in okeys:
                if k in oi_map:
                    a = oi_map[k]
                else:
                    a = oi_map[k] = []
                a.append(ikey)
        akas = None

        # remove non-ikey keys
        io_map = dict([(k, io_map[k]) for k in ikeys])

        spelling_map = dict()
        for s, ikey in spellings:
            t = reduce(transform, spelling_rules, s)
            if t not in spelling_map:
                spelling_map[t] = ikey
            elif self.__report_errors:
                raise SpellingCollisionError('SpellingRule', (s, ikey, t, spelling_map[t]))
        spelling_map = reduce(apply_alternative_rule, alternative_rules, spelling_map)

        return spelling_map, io_map, oi_map

class ContextInfo:

    def __init__(self):
        self.m = 0
        self.n = 0
        self.e = []
        self.q = {}
        self.unig = {}
        self.big = {}
        self.cand = []
        self.pred = [None]
        self.last = None

class Model:

    PENALTY = 1e-4
    LIMIT = 256
    MAX_CONCAT_PHRASE = 3

    def __init__(self, schema):
        self.__max_key_length = int(schema.get_config_value(u'MaxKeyLength') or u'2')
        self.__max_keyword_length = int(schema.get_config_value(u'MaxKeywordLength') or u'7')
        self.__delimiter = schema.get_config_char_sequence(u'Delimiter') or u' '
        get_rules = lambda f, key: [f(r.split()) for r in schema.get_config_list(key)]
        compile_repl_pattern = lambda x: (re.compile(x[0]), x[1])
        mapping_rules = get_rules(compile_repl_pattern, u'MappingRule')
        fuzzy_rules = get_rules(compile_repl_pattern, u'FuzzyRule')
        spelling_rules = get_rules(compile_repl_pattern, u'SpellingRule')
        alternative_rules = get_rules(compile_repl_pattern, u'AlternativeRule')
        self.__split_rules = get_rules(compile_repl_pattern, u'SplitRule')
        self.__divide_rules = get_rules(compile_repl_pattern, u'DivideRule')
        self.__db = schema.get_db()
        keywords = self.__db.list_keywords()
        sa = SpellingAlgebra(report_errors=False)
        self.__keywords, self.__io_map, self.__oi_map = sa.calculate(mapping_rules, 
                                                                     fuzzy_rules, 
                                                                     spelling_rules, 
                                                                     alternative_rules, 
                                                                     keywords)

    def __is_keyword(self, k):
        return k in self.__keywords

    def __translate_keyword(self, k):
        if k in self.__keywords:
            return self.__keywords[k]
        else:
            return k

    def create_context_info(self):
        return ContextInfo()

    def __segmentation(self, input):
        n = len(input)
        m = 0
        a = [[None] * j for j in range(n + 1)]
        p = []
        q = [0]
        def allow_divide(i, j, s):
            flag = True
            for k in p:
                if not a[j][k]:
                    if flag and a[i][k]:
                        return True
                    else:
                        continue
                lw = u''.join(input[k:j])
                for r in self.__divide_rules:
                    m = r[0].search(lw)
                    if m and r[0].sub(r[1], lw, 1) == s:
                        return True
                flag = False
            return False
        while q:
            i = q.pop(0)
            if i == n:
                p.append(i)
                break
            # TODO: implement split rules
            ok = False
            beyond_delimiter = False
            for j in range(i + 1, n + 1):
                if beyond_delimiter:
                    break
                s = u''.join(input[i:j])
                if len (s) > self.__max_keyword_length:
                    break
                #print j, s
                if not self.__is_keyword(s):
                    continue
                if j < n and input[j] in self.__delimiter:
                    t = j + 1
                    beyond_delimiter = True
                else:
                    t = j
                #print i, t, s
                if t not in q:
                    q.append(t)
                    m = max(m, t)
                elif not allow_divide(i, t, s):
                    continue
                a[t][i] = self.__translate_keyword(s)
                ok = True
            if ok:
                p.append(i)
            q.sort()
        if m < n:
            p.append(m)
        b = []
        d = []
        e = [[] for i in range(m + 1)]
        # path finding
        for i in reversed(p):
            ok = i == m
            for j in b:
                if i < j and a[j][i]:
                    ok = True
                    d = [k for k in d if k >= j]
                    e[i].append((j, a[j][i]))
            if ok:
                b.append(i)
                d.append(i)
            else:
                a[i] = [None for j in range(len(a[i]))]
        b.reverse()
        d.reverse()
        return m, n, b, d, e

    def query(self, ctx):
        m, n, b, d, e = self.__segmentation(ctx.input)
        prev_e = ctx.info.e
        ctx.info.m = m
        ctx.info.n = n
        ctx.info.b = b
        ctx.info.d = d
        ctx.info.e = e
        # find the start position of altered input
        diff = 0
        while diff < m and diff < len(prev_e) and prev_e[diff] == e[diff]:
            diff += 1
        # clear unconfirmed selection
        i = ctx.confirmed
        s = ctx.sel
        while i > 0 and s[i - 1].j > diff:
            i -= 1
        del ctx.sel[i:]
        ctx.confirmed = i
        self.__lookup_candidates(ctx.info, diff)
        self.__calculate_prediction(ctx.info)

    def __lookup_candidates(self, info, diff):
        m = info.m
        b = info.b
        e = info.e
        c = info.cand
        unig = info.unig
        big = info.big
        total, utotal = [x + 0.1 for x in self.__db.lookup_freq_total()]
        to_prob = lambda x: (x + 0.1) / total
        def make_keys(i, k, length):
            if length == 0 or i == m:    
                return [(i, k)]
            keys = sum([make_keys(jw, k + [kw], length - 1) for jw, kw in e[i]], [])
            return [(i, k)] + keys
        def lookup(k):
            key = u' '.join(k)
            if key in info.q:
                return info.q[key]
            result = info.q[key] = self.__db.lookup_unigram(key)
            for x in result:
                prob = to_prob(x[3])
                unig[x[2]] = prob
            if len(k) >= min(2, self.__max_key_length):
                for x in self.__db.lookup_bigram(key):
                    if x[0] in big:
                        s = big[x[0]]
                    else:
                        s = big[x[0]] = {}
                    s[x[1]] = to_prob(x[2])
            return result
        def add_word(x, i, j):
            #print 'add_word:', i, j, x[0], x[1]
            use_count = x[4]
            e = Entry(x, i, j, 1.0, use_count)
            if not c[i][j]:
                a = c[i][j] = []
            else:
                a = c[i][j]
            a.append(e)
        def match_key(x, i, j, k):
            if not k:
                if j > diff:
                    add_word(x, i, j)
                return
            if j == m:
                return
            for jw, kw in e[j]:
                if k[0] in self.__io_map[kw]:
                    match_key(x, i, jw, k[1:])
        def judge(x, i, j):
            okey = x[1].split()
            if len(okey) <= self.__max_key_length:
                if j > diff:
                    add_word(x, i, j)
            else:
                match_key(x, i, j, okey[self.__max_key_length:])
        # clear invalidated candidates
        for i in range(diff):
            c[i][diff + 1:] = [None for j in range(diff + 1, m + 1)]
        c[diff:] = [[None for j in range(m + 1)] for i in range(diff, m + 1)]
        # last committed word goes to array index -1
        if info.last:
            c[-1][0] = [info.last]
            if not info.q:
                r = self.__db.lookup_bigram_by_entry(info.last)
                if r:
                    eid = info.last.get_eid()
                    if eid in big:
                        s = big[eid]
                    else:
                        s = big[eid] = {}
                    for x in r:
                        s[x[0]] = to_prob(x[1])
        # traverse
        for i in b:
            for jw, kw in e[i]:
                for j, k in make_keys(jw, [kw], self.__max_key_length - 1):
                    if j <= diff and len(k) < self.__max_key_length:
                        continue
                    #print 'lookup:', i, j, k
                    for x in lookup(k):
                        judge(x, i, j)

    def __calculate_prediction(self, info):
        m = info.m
        b = info.b
        c = info.cand
        f = [[None for j in range(m + 1)] for i in range(m + 1)]
        info.fraz = f
        unig = info.unig
        big = info.big
        # index m should be left empty; index -1 is reserved for the last committed word
        pred = [None for i in range(m + 1 + 1)]
        info.pred = pred
        def update_pred(i, e):
            if not pred[i] or e.prob > pred[i].prob:
                pred[i] = e
        def succ_phrases(j):
            '''returns succeeding phrases starting with position j, grouped by eid'''
            succ = dict()
            for k in range(j + 1, m + 1):
                if c[j][k]:
                    for x in c[j][k][:Model.LIMIT]:
                        eid = x.get_eid()
                        if eid in succ:
                            succ[eid].append(x)
                        else:
                            succ[eid] = [x]
                if f[j][k]:
                    for x in f[j][k]:
                        eid = x.get_eid()
                        if eid in succ:
                            succ[eid].append(x)
                        else:
                            succ[eid] = [x]
            return succ
        # traverse
        for j in reversed(b):
            succ = None
            for i in range(-1, j):
                if c[i][j]:
                    for x in c[i][j]:
                        # calculate prob
                        if i == -1:
                            pass
                        elif j == m:
                            x.prob = unig[x.get_eid()]
                        else:
                            x.prob = unig[x.get_eid()] * pred[j].prob * Model.PENALTY
                        update_pred(i, x)
                        if j == m:
                            continue
                        # try making phrases
                        eid = x.get_eid()
                        if eid in big:
                            if succ is None:
                                succ = succ_phrases(j)
                            for v in big[eid]:
                                if v in succ:
                                    for y in succ[v]:
                                        prob = big[eid][v] / unig[v] * y.prob
                                        e = Entry(x.e, i, j, prob, min(x.use_count, y.use_count), y)
                                        #print "concat'd phrase:", unicode(e)
                                        # save phrase
                                        k = e.get_all()[-1].j
                                        if f[i][k]:
                                            f[i][k].append(e)
                                        else:
                                            f[i][k] = [e]
                                        # update pred[i] with concat'd phrases
                                        update_pred(i, e)

    def train(self, ctx, s):
        def g(ikeys, okey, depth):
            if not okey or depth >= self.__max_key_length:
                return ikeys
            r = []
            for x in ikeys:
                if okey[0] not in self.__oi_map:
                    return []
                for y in self.__oi_map[okey[0]]:
                    r.append(x + [y])
            return g(r, okey[1:], depth + 1)
        def f(a, b):
            okey = a.get_okey().split() + b.get_okey().split()
            return [u' '.join(ikey) for ikey in g([[]], okey, 0)]
        last = None
        for e in s:
            if last:
                self.__db.update_bigram(last, e, f)
            last = e
            self.__db.update_unigram(e)
        self.__db.update_freq_total(len(s))
        ctx.info = self.create_context_info()
        ctx.info.last = Entry(last.e, -1, 0, last.prob, last.use_count + 1) if last else None

    def make_candidate_list(self, ctx, i, j):
        m = ctx.info.m
        c = ctx.info.cand
        f = ctx.info.fraz
        pred = ctx.info.pred
        if i >= m:
            return []
        if j == 0:
            j = m
            while j > i and not c[i][j] and not f[i][j]:
                j -= 1
        # info about the previously selected phrase
        prev_table = dict()
        prev = ctx.sel[-1] if ctx.sel else ctx.info.last
        if prev:
            #print 'prev:', prev.get_phrase()
            prev_award = 1.0
            prev_eid = prev.get_eid()
            for x in c[prev.i][prev.j]:
                if x.get_eid() == prev_eid:
                    prev_award = pred[x.j].prob / x.prob
                    break
            for y in c[prev.i][prev.j:]:
                if y:
                    for x in y[:Model.LIMIT]:
                        if x.next and x.get_eid() == prev_eid:
                            prev_table[id(x.next)] = x.prob * prev_award
        def adjust(e):
            if id(e) not in prev_table:
                return e
            prob = prev_table[id(e)]
            return Entry(e.e, e.i, e.j, prob, e.use_count, e.next)
        r = [[] for k in range(m + 1)]
        p = []
        #print 'range:', u''.join(ctx.input[i:j])
        for k in range(j, i, -1):
            if c[i][k]:
                for x in c[i][k]:
                    e = adjust(x)
                    r[k].append(e)
            if f[i][k]:
                for x in f[i][k]:
                    e = adjust(x)
                    #print "concat'd phrase:", e.get_phrase(), e.prob
                    if not any([e.partof(ex) for kx, ex in p]):
                        p.append((k, e))
        phrase_cmp = lambda a, b: -cmp(a[1].prob, b[1].prob)
        p.sort(cmp=phrase_cmp)
        for k, e in p[:Model.MAX_CONCAT_PHRASE]:
            r[k].append(e)
        if not r[j]:
            for kx, ex in p:
                if kx == j:
                    r[j].append(ex)
                    break
            #print 'supplemented:', r[j][0].get_phrase()
        cand_cmp = lambda a, b: -cmp(a.use_count + a.prob, b.use_count + b.prob)
        ret = []
        for s in reversed(r):  # longer words come first
            if s:
                phrases = set()
                for e in sorted(s, cand_cmp):
                    p = e.get_phrase()
                    # ignore less freqently used phrases with identical representation
                    if p not in phrases:
                        phrases.add(p)
                        ret.append((p, e))
        return ret
