# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

split_phrase = lambda x: x.split () if u' ' in x else list (x)
join_phrase = lambda w: (u'' if all ([len (x) == 1 for x in w]) else u' ').join (w)

class Model:
    def __init__ (self):
        pass
    def update (self, ctx):
        #print 'update:', ctx.keywords
        db = ctx.schema.get_db ()
        m = 0
        while m < min (len (ctx.keywords), len (ctx.kwd)) and ctx.keywords[m] == ctx.kwd[m]:
            m += 1
        self.__invalidate_selections (ctx, m, len (ctx.kwd))
        del ctx.kwd[m:]
        for i in range (len (ctx.cand)):
            del ctx.cand[i][m - i:]
        del ctx.cand[m:]
        del ctx.sugg[m + 1:]
        for k in ctx.keywords[m:len (ctx.keywords) - 1]:
            ctx.kwd.append (k)
            ctx.cand.append ([])
            ctx.sugg.append (None)
            n = len (ctx.kwd)
            for i in range (max (0, n - 4), n):
                r = db.lookup (ctx.kwd[i:])
                for x in r:
                    x = (split_phrase (x[0]) if n - i > 1 else [x[0]], x[1], x[2])
                    if n - i == 4 and self.__concatenated (ctx, i, x):
                       continue
                    self.__add_candidate (ctx, i, n - i, x)
        self.__calculate (ctx)
    def select (self, ctx, s):
        self.__invalidate_selections (ctx, s[0], s[0] + s[1])
        ctx.selection.append (s)
        for i in range (s[0] + 1, len (ctx.sugg)):
            ctx.sugg[i] = None
        self.__calculate (ctx)
    def __add_candidate (self, ctx, pos, length, x):
        c = ctx.cand[pos]
        if length > len (c):
            c += [[] for i in range (length - len (c))]
        c[length - 1].append (x)
    def __concatenated (self, ctx, pos, x):
        for i in range (pos):
            c = ctx.cand[i]
            j = pos + 3 - i - 1
            if j >= len (c):
                continue
            ok = False
            for y in c[j]:
                if y[0][-3:] == x[0][:3]:
                    self.__add_candidate (ctx, i, j + 2, (y[0] + [x[0][-1]], min (y[1], x[1]), min (y[2], x[2])))
                    ok = True
            if ok:
                return True
        return False
    def __invalidate_selections (self, ctx, start, end):
        if start >= end:
            return
        for s in ctx.selection:
            if s[0] < end and s[0] + s[1] > start:
                ctx.selection.remove (s)
    def __calculate (self, ctx):
        # update suggestion
        Free, Fixed = 0, 1
        sel = [Free] * len (ctx.kwd)
        for s in ctx.selection:
            for i in range (s[0], s[1] - 1):
                sel[i] = Fixed
            sel[s[0] + s[1] - 1] = s
        def update_sugg (ctx, k, i, x):
            # formula
            if x[2] >= 0:
                w = ctx.sugg[i][2] + 0.5 + 1.0 / (x[1] + x[2] + 1)
            else:
                w = ctx.sugg[i][2] + 0.5 + 1.0 / (x[1] + 1)
            if not ctx.sugg[k] or w < ctx.sugg[k][2]:
                ctx.sugg[k] = (i, x[0], w)
        start = 0
        for k in range (1, len (ctx.sugg)):
            s = sel[k - 1]
            if s == Fixed:
                pass
            elif s == Free:
                if ctx.sugg[k]:
                    continue
                for i in range (start, k):
                    if not ctx.sugg[i]:
                        continue
                    c = ctx.cand[i]
                    j = k - i
                    if j > len (c) or len (c[j - 1]) == 0:
                        continue
                    x = c[j - 1][0]
                    update_sugg (ctx, k, i, x)
            else:
                i, j, x = s[:]
                start = i + j
                if ctx.sugg[k]:
                    continue
                if ctx.sugg[i]:
                    update_sugg (ctx, k, i, x)
        # update preedit
        k = len (ctx.sugg) - 1
        while k > 0 and not ctx.sugg[k]:
            k -= 1
        r = ctx.keywords[k:]
        t = ctx.sugg[k]
        # last phrase's start pos
        ctx.prompt_pos = t[0] if r == [u''] else len (ctx.keywords) - 1
        while t[0] != -1:
            r = t[1] + r
            t = ctx.sugg[t[0]]
        ctx.preedit = r
        # update candidates
        ctx.candidates = []
        for pos in range (len (ctx.cand)):
            c = ctx.cand[pos]
            a = []
            for length in range (len (c), 0, -1):
                for x in c[length - 1]:
                    if x[2] < 0:
                        continue
                    y = u''.join (x[0])
                    if length >= 4 and any ([t[0].startswith (y) for t in a]): 
                        continue
                    a.append ((y, (pos, length, x)))
            ctx.candidates.append (a)
    def learn (self, ctx):
        db = ctx.schema.get_db ()
        k = len (ctx.sugg) - 1
        while k > 0 and not ctx.sugg[k]:
            k -= 1
        r = []
        s = k
        t = ctx.sugg[k]
        while t[0] != -1:
            r = [t[1]] + r
            s = t[0]
            t = ctx.sugg[s]
        flatten = lambda ls, x: ls + x
        self.__memorize (db, ctx.kwd[:k], reduce (flatten, r, []))
        i = j = 0
        w = []
        def check_new_word ():
            if len (w) in range (2, 4) and i - j < k:
                self.__memorize (db, ctx.kwd[j:i], reduce (flatten, w, []))
        for x in r:
            if len (x) == 1:
                w.append (x)
            else:
                check_new_word ()
                w = []
                j = i + len (x)
            i += len (x)
        check_new_word ()
    def __memorize (self, db, keywords, words):
        #print '__memorize:', keywords, words
        if len (keywords) <= 4:
            db.store (keywords, join_phrase (words))
        else:
            for i in range (len (keywords) - 4 + 1):
                db.store (keywords[i:i+4], join_phrase (words[i:i+4]))
    def delete_phrase (self, ctx, c):
        db = ctx.schema.get_db ()
        keywords = ctx.kwd[c[0]:c[0] + c[1]]
        words = c[2][0]
        if len (keywords) <= 4:
            db.delete (keywords, join_phrase (words), c[2][2])
        else:
            for i in range (len (keywords) - 4 + 1):
                db.delete (keywords[i:i+4], join_phrase (words[i:i+4]), c[2][2])
        # update context
        j = 0
        for i in range (len (ctx.kwd) - c[0] + 1):
            if ctx.kwd[i:i + c[0]] == keywords:
                j = i
                break
        del ctx.kwd[j:]
        self.update (ctx)
