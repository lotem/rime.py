#!/usr/bin/env python

import ibus
from ibus import keysyms

from zimedb import DB
from zimemodel import *

class KeyEvent:
    def __init__ (self, keycode, mask, coined=False):
        self.keycode = keycode
        self.mask = mask
        self.coined = coined
    def get_char (self):
        return unichr (self.keycode)
    def __str__ (self):
        return "<KeyEvent: '%s'(%x), %08x>" % (keysyms.keycode_to_name (self.keycode), self.keycode, self.mask)

class Schema:
    def __init__ (self, name):
        self.__name = name
        self.__db = DB (name)
        self.__parser_name = self.__db.read_config_value (u'Parser')
    def get_name (self):
        return self.__name
    def get_db (self):
        return self.__db
    def get_parser_name (self):
        return self.__parser_name
    def get_config_value (self, key):
        return self.__db.read_config_value (key)
    def get_config_char_sequence (self, key):
        r = self.__db.read_config_value (key)
        if r and r.startswith (u'[') and r.endswith (u']'):
            return r[1:-1]
        return r
    def get_config_list (self, key):
        return self.__db.read_config_list (key)

class Parser:
    __parsers = dict ()
    @classmethod
    def register (cls, name, parser_class):
        cls.__parsers[name] = parser_class
    @classmethod
    def get_parser_class (cls, parser_name):
        return cls.__parsers[parser_name]
    @classmethod
    def create (cls, schema):
        return cls.get_parser_class (schema.get_parser_name ()) (schema)
    def __init__ (self, schema):
        self.__schema = schema
        punct_mapping = lambda (x, y): (x, (0, y.split (u' ')) if u' ' in y else \
                                           (2, y.split (u'~', 1)) if u'~' in y else \
                                           (1, y))
        self.__punct = dict ([punct_mapping (c.split (None, 1)) for c in schema.get_config_list (u'Punct')])
        key_mapping = lambda (x, y): (keysyms.name_to_keycode (x), keysyms.name_to_keycode (y))
        self.__edit_keys = dict([key_mapping (c.split (None, 1)) for c in schema.get_config_list (u'EditKey')])
    def get_schema (self):
        return self.__schema
    def check_punct (self, event):
        ch = event.get_char ()
        if ch in self.__punct:
            p = self.__punct[ch]
            if p[0] == 1:
                return p[1]
            elif p[0] == 2:
                x = p[1]
                x[:] = x[::-1]
                return x[-1]
            else:
                return p[1]
        return None
    def check_edit_key (self, event):
        if not event.coined and event.keycode in self.__edit_keys:
            return KeyEvent (self.__edit_keys[event.keycode], 0, coined=True)
        return None

class Context:
    def __init__ (self, callback, schema):
        self.__cb = callback
        self.__model = Model (schema)
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
        self.__auto_delimit = schema.get_config_value (u'AutoDelimit') in (u'yes', u'true')
        #self.schema = schema
        self.__reset ()
    def __reset (self, keep_context=False):
        self.input = []
        self.aux = None
        self.err = None
        if not keep_context:
            self.pre = None
        self.sel = []
        self.cur = []
        self.phrase = []
        self.pred = []
        self.__candidates = []
        self.seg = 0, 0
        self.__prompt = (u'', [0])
    def clear (self):
        self.__reset ()
        self.__cb.update_ui ()
    def is_empty (self):
        return not self.input
    def commit (self):
        if self.is_completed ():
            self.__model.train (self, self.sel + self.cur)
            self.edit ([])
        else:
            self.clear ()
    def edit (self, input):
        self.__reset (keep_context=True)
        self.input = input
        if input:
            s = self.seg = self.__model.segmentation (input)
            n, m = s[:2]
            if m != n:
                self.err = Entry (None, m, n)
            self.__calculate_prompt_string (input, s[4], n, m)
        self.__cb.update_ui ()
    def has_error (self):
        return self.err is not None
    def clear_error (self):
        self.edit (self.input[:self.err.i])
    def start_conversion (self):
        if self.has_error ():
            self.__cb.update_ui ()
        else:
            self.__model.query (self)
            self.end ()
    def cancel_conversion (self):
        self.edit (self.input)
    def home (self):
        if not self.being_converted ():
            return False
        self.sel = []
        self.__update_candidates (0)
        return True
    def end (self):
        i = self.sel[-1].j if self.sel else (-1 if self.pre else 0)
        p = (self.sel[-1].next if self.sel else None) or self.pred[i]
        while p:
            s = p.get_all ()
            if s[0].i < 0:
                del s[0]
            if s:
                p = s[-1]
                if p.j == len (self.input):
                    break
                self.sel.extend (s)
            i = p.j
            p = self.pred[i]
        self.__update_candidates (i)
    def left (self):
        if not self.cur:
            return
        i = self.cur[0].i
        j = self.cur[-1].j
        for k in range (j - 1, i, -1):
            if self.phrase[i][k]:
                self.__update_candidates (i, k)
                return
        self.back ()
    def right (self):
        if not self.cur:
            return
        i = self.cur[0].i
        j = self.cur[-1].j
        for k in range (j + 1, len (self.input) + 1):
            if self.phrase[i][k]:
                self.__update_candidates (i, k)
                return
        self.forth ()
    def back (self):
        if not self.being_converted ():
            return False
        if self.sel:
            e = self.sel.pop ()
            self.__update_candidates (e.i)
            return True
        return False
    def forth (self):
        if not self.being_converted ():
            return False
        i = self.cur[0].i
        p = (self.sel[-1].next if self.sel else None) or self.pred[i]
        if p and p.j < len (self.input):
            self.sel.append (p)
            i = p.j
            j = 0
            for k in range (i + 1, len (self.input) + 1):
                if self.phrase[i][k]:
                    j = k
                    break
            self.__update_candidates (i, j)
            return True
        return False
    def forward (self):
        c = self.cur
        if c:
            self.sel.extend (c)
            self.__update_candidates (c[-1].j)
    def __update_candidates (self, i, j=0):
        #print '__update_candidates:', i, j
        self.__candidates = self.__model.make_candidate_list (self, i, j)
        if self.__candidates:
            self.cur = self.__candidates[0][1].get_all ()
        else:
            err_pos = self.cur[-1].i if self.cur else 0
            self.err = Entry (None, err_pos, len (self.input))
            self.cur = []
        self.__cb.update_ui ()
    def select (self, e):
        self.cur = e.get_all ()
    def being_converted (self):
        return bool (self.cur)
    def is_completed (self):
        return self.cur and self.cur[-1].j == len (self.input)
    def __calculate_prompt_string (self, s, d, n, m):
        if n == 0:
            return
        t = [i for i in range (n + 1)]
        p = s
        if self.__auto_delimit:
            p = []
            c = 0
            for i in range (n):
                if i > 0 and i in d and s[i - 1] not in self.__delimiter:
                    p.append (self.__delimiter[0])
                    c += 1
                p.append (s[i])
                t[i] = i + c
            t[-1] = n + c
        self.__prompt = (u''.join (p), t)
    def get_preedit (self):
        if self.is_empty ():
            return u'', 0, 0
        if self.has_error ():
            p, t = self.__prompt
            return p, t[self.err.i], t[self.err.j]
        r = []
        rest = 0
        start = 0
        for s in self.sel:
            w = s.get_word ()
            r.append (w)
            start += len (w)
            rest = s.j
        end = start
        for s in self.cur:
            w = s.get_word ()
            r.append (w)
            end += len (w)
            rest = s.j
        if rest < len (self.input):
            p, t = self.__prompt
            #if r:
            #    r.append (u' ')
            r.append (p[t[rest]:])
        return u''.join (r), start, end
    def get_commit_string (self):
        if self.is_completed ():
            return u''.join ([s.get_word () for s in self.sel + self.cur])
        else:
            return u''.join (self.input)
    def get_aux_string (self):
        if self.aux:
            return self.aux
        c = self.cur
        if c:
            p, t = self.__prompt
            return p[t[c[0].i]:t[c[-1].j]].rstrip (self.__delimiter)
        return u''
    def get_candidates (self):
        return self.__candidates
    def delete_phrase (self, e):
        pass

