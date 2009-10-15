#!/usr/bin/env python

from ibus import keysyms
from ibus import modifier
from ibus import ascii

from zimedb import DB

class KeyEvent:
    def __init__ (self, keycode, mask):
        self.keycode = keycode
        self.mask = mask
    def get_char (self):
        return unichr (self.keycode)

class Schema:
    def __init__ (self, name):
        self.__name = name
        self.__db = DB (name)
    def get_name (self):
        return self.__name
    def get_db (self):
        return self.__db
    def get_parser_name (self):
        # TODO: read config values
        return 'grouping'
    def get_in_place_prompt (self):
        # TODO: read config values
        return 1

class Parser:
    __parsers = dict ()
    @classmethod
    def register (cls, name, parser_class):
        cls.__parsers[name] = parser_class
    @classmethod
    def create (cls, schema):
        return cls.__parsers[schema.get_parser_name ()] (schema)
    def __init__ (self, schema):
        self.__schema = schema

class Model:
    def __init__ (self, schema):
        self.__db = schema.get_db ()
        self.__in_place_prompt = schema.get_in_place_prompt ()
    def update (self, ctx):
        m = 0
        while m < min (len (ctx.keywords), len (ctx.kwd)) and ctx.keywords[m] == ctx.kwd[m]:
            m += 1
        self.__invalidate_selections (ctx, m, len (ctx.kwd))
        del ctx.kwd[m:]
        for i in range (len (ctx.cand)):
            del ctx.cand[i][m - i:]
        del ctx.cand[m:]
        del ctx.sugg[m + 1:]
        for k in ctx.keywords[m:len (ctx.keywords) - self.__in_place_prompt]:
            ctx.kwd.append (k)
            ctx.cand.append ([])
            ctx.sugg.append (None)
            n = len (ctx.kwd)
            for i in range (max (0, n - 4), n):
                r = self.__db.lookup (ctx.kwd[i:])
                for x in r:
                    if n - i == 4 and self.__concatenated (ctx, i, x):
                        continue
                    self.__add_candidate (ctx, i, n - i, x)
        self.__update_sugguestions (ctx)
    def select (self, ctx, sel):
        self.__invalidate_selections (ctx, sel[0], sel[1])
        ctx.selection.append (sel)
        self.__update_sugguestions (ctx)
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
                    self.__add_candidate (ctx, i, j + 2, (y[0] + x[0][-1], min (y[1], x[1])))
                    ok = True
            if ok:
                return True
        return False
    def __invalidate_selections (self, ctx, start, end):
        for s in ctx.selection:
            if s[0] < end and s[1] > start:
                ctx.selection.remove (s)
    def __update_sugguestions (self, ctx):
        print "__update_sugguestions:", ctx.selection
        for k in range (1, len (ctx.sugg)):
            if ctx.sugg[k]:
                continue
            for i in range (k):
                if not ctx.sugg[i]:
                    continue
                c = ctx.cand[i]
                j = k - i - 1
                if j >= len (c) or len (c[j]) == 0:
                    continue
                x = c[j][0]
                w = ctx.sugg[i][2] + 1 + 1.0 / (x[1] + 1)
                if not ctx.sugg[k] or w < ctx.sugg[k][2]:
                    ctx.sugg[k] = (i, x[0], w)
        k = len (ctx.sugg) - 1
        while k > 0 and not ctx.sugg[k]:
            k -= 1
        r = ctx.keywords[k:]
        t = ctx.sugg[k]
        split_words = lambda x: x.split () if u' ' in x else list (x)
        while t[0] != -1:
            r = split_words(t[1]) + r
            t = ctx.sugg[t[0]]
        ctx.preedit = r
        s = ctx.get_preedit ()
        ctx.candidates = [[(x[0], (pos, length, x))
                           for length in range (len (ctx.cand[pos]), 0, -1)
                           for x in ctx.cand[pos][length - 1] 
                           if not s.startswith (x[0], pos)] 
                          for pos in range (len (ctx.cand))]

class Context:
    def __init__ (self, callback, model):
        self.__cb = callback
        self.__model = model
        self.clear ()
    def clear (self):
        self.keywords = [u'']
        self.cursor = 0
        self.aux_string = u''
        self.kwd = []
        self.cand = []
        self.sugg = [(-1, u'', 0)]
        self.preedit = [u'']
        self.candidates = [None]
        self.selection = []
        self.__cb.update_ui (self)
    def is_empty (self):
        return not self.keywords
    def update_keywords (self):
        self.cursor = len (self.keywords) - 1
        self.__model.update (self)
        self.__cb.update_ui (self)
    def select (self, index):
        s = self.get_candidates ()[index][1]
        self.__model.select (self, s)
        self.__cb.update_ui (self)
    def set_cursor (self, pos):
        if pos == -1:
            pos += len (self.keywords)
        self.cursor = pos
        self.__cb.update_ui (self)
    def move_cursor (self, offset):
        self.cursor = (self.cursor + offset) % len (self.keywords)
        self.__cb.update_ui (self)
    def get_preedit (self):
        return u''.join (self.preedit)
    def get_aux_string (self):
        return self.aux_string
    def get_candidates (self):
        k = self.cursor
        if k >= len (self.candidates):
            return None
        return self.candidates[k]

class Engine:
    def __init__ (self, frontend, name):
        self.__frontend = frontend
        self.__schema = Schema (name)
        self.__model = Model (self.__schema)
        self.__parser = Parser.create (self.__schema)
        self.__ctx = Context (self, self.__model)
    def process_key_event (self, event):
        if self.__parser.process (event, self.__ctx):
            return True
        if self.__ctx.is_empty ():
            return False
        if event.keycode == keysyms.Home:
            self.__ctx.set_cursor (0)
            return True
        if event.keycode == keysyms.End or event.keycode == keysyms.Escape:
            self.__ctx.set_cursor (-1)
            return True
        if event.keycode == keysyms.Left:
            self.__ctx.move_cursor (-1)
            return True
        if event.keycode == keysyms.Right or event.keycode == keysyms.Tab:
            self.__ctx.move_cursor (1)
            return True
        candidates = self.__ctx.get_candidates ()
        if event.keycode == keysyms.Page_Up or event.keycode == keysyms.Up:
            if candidates and self.__frontend.page_up ():
                return True
            return True
        if event.keycode == keysyms.Page_Down or event.keycode == keysyms.Down:
            if candidates and self.__frontend.page_down ():
                return True
            return True
        if event.keycode >= keysyms._1 and event.keycode <= keysyms._9:
            if candidates:
                index = self.__frontend.get_candidate_index (event.keycode - keysyms._1)
                self.__ctx.select (index)
            return True
        if event.keycode == keysyms.BackSpace:
            k = self.__ctx.keywords
            if len (k) < 1:
                return False
            if k[-1]:
                k[-1] = u''
            else:
                if len (k) < 2:
                    return False
                del k[-2]
            self.__ctx.update_keywords ()
            return True
        if event.keycode in (keysyms.space, keysyms.Return):
            self.__frontend.commit_string (self.__ctx.get_preedit ())
            self.__ctx.clear ()
            return True
        return True
    def update_ui (self, ctx):
        k = 0
        for x in ctx.preedit[:ctx.cursor]:
            k += len (x)
        ll = len (ctx.preedit[ctx.cursor])
        self.__frontend.update_preedit (ctx.get_preedit (), k, k + ll)
        self.__frontend.update_aux_string (ctx.get_aux_string ())
        self.__frontend.update_candidates (ctx.get_candidates ())
        

