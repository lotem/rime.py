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
    def analyze (self, ctx):
        m = 0
        while m < min (len (ctx.keywords), len (ctx.kwd)) and ctx.keywords[m] == ctx.kwd[m]:
            m += 1
        del ctx.kwd[m:]
        for i in range (len (ctx.cand)):
            del ctx.cand[i][m - i:]
        del ctx.cand[m:]
        del ctx.sugg[m + 1:]
        for k in ctx.keywords[m:]:
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
    def __update_sugguestions (self, ctx):
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

class Context:
    def __init__ (self, callback):
        self.__cb = callback
        self.clear ()
    def update (self):
        self.__cb.on_context_update (self)
    def clear (self):
        self.keywords = []
        self.cursor = -1
        self.aux = u''
        self.kwd = []
        self.cand = []
        self.sugg = [(-1, u'', 0)]
    def is_empty (self):
        return not self.keywords
    def move_cursor (self, offset):
        self.cursor = (self.cursor + offset + 1) % (len (self.keywords) + 1) - 1
    def get_preedit (self):
        i = len (self.sugg) - 1
        while i > 0 and not self.sugg[i]:
            i -= 1
        r = u' '.join (self.keywords[i:])
        s = u''
        t = self.sugg[i]
        while t[0] != -1:
            s = t[1] + s
            t = self.sugg[t[0]]
        return s + r
    def get_aux_string (self):
        return self.aux
    def get_candidates (self):
        if self.cursor == -1:
            return None
        pos = self.cursor
        s = self.get_preedit ()
        result = [x[0] for c in reversed (self.cand[pos]) 
                           for x in c 
                               if not s.startswith (x[0], pos)]
        return result

class Engine:
    def __init__ (self, frontend, name):
        self.__frontend = frontend
        self.__schema = Schema (name)
        self.__model = Model (self.__schema)
        self.__parser = Parser.create (self.__schema)
        self.__ctx = Context (self)
        self.__ctx.update ()
    def process_key_event (self, event):
        if self.__parser.process (event, self.__ctx):
            return True
        if self.__ctx.is_empty ():
            return False
        if event.keycode == keysyms.Left:
            self.__ctx.move_cursor (-1)
            self.__ctx.update ()
            return True
        if event.keycode == keysyms.Right:
            self.__ctx.move_cursor (1)
            self.__ctx.update ()
            return True
        if event.keycode == keysyms.BackSpace:
            if len (self.__ctx.keywords) < 1:
                return False
            del self.__ctx.keywords[-1]
            self.__ctx.cursor = -1
            self.__ctx.update ()
            return True
        if event.keycode in (keysyms.space, keysyms.Return):
            self.__frontend.commit_string (self.__ctx.get_preedit ())
            self.__ctx.clear ()
            self.__ctx.update ()
        return True
    def on_context_update (self, ctx):
        self.__model.analyze (ctx)
        self.__frontend.update_preedit (ctx.get_preedit ())
        self.__frontend.update_aux_string (ctx.get_aux_string ())
        self.__frontend.update_candidates (ctx.get_candidates ())

