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
        self.schema = schema
        self.__reset ()
    def __reset (self, keep_context=False):
        self.input = []
        self.aux = None
        self.err = None
        if not keep_context:
            self.pre = []
        self.sel = []
        self.cur = []
        self.cand = []
        self.sugg = []
        self.__candidates = []
    def clear (self):
        self.__reset ()
        self.__cb.update_ui ()
    def is_empty (self):
        return not self.input
    def commit (self):
        if self.is_completed ():
            self.__model.train (self, self.sel + self.cur)
        self.edit ([])
    def edit (self, input):
        self.__reset (keep_context=True)
        self.input = input
        self.__cb.update_ui ()
    def has_error (self):
        return self.err is not None
    def clear_error (self):
        self.edit (self.input[:self.err.i])
    def start_conversion (self):
        self.__model.query (self)
        if self.has_error ():
            self.__cb.update_ui ()
        else:
            self.end ()
    def cancel_conversion (self):
        self.edit (self.input)
    def home (self):
        if not self.being_converted ():
            return False
        self.__reset (keep_context=True)
        self.__update_candidates (0)
        return True
    def end (self):
        i = self.sel[-1].j if self.sel else 0
        p = (self.sel[-1].next if self.sel else None) or self.sugg[i]
        while p:
            s = p.get_all ()
            if not s:
                break
            p = s[-1]
            if p.j == len (self.input):
                break
            self.sel.extend (s)
            i = p.j
            p = self.sugg[i]
        self.__update_candidates (i)
    def left (self):
        if not self.cur:
            return
        i = self.cur[0].i
        j = self.cur[-1].j
        for k in range (j - 1, i, -1):
            if self.__cand_list[k]:
                self.__update_candidate_index (i, k)
                return
        self.back ()
    def right (self):
        if not self.cur:
            return
        i = self.cur[0].i
        j = self.cur[-1].j
        for k in range (j + 1, len (self.input) + 1):
            if self.__cand_list[k]:
                self.__update_candidate_index (i, k)
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
        p = (self.sel[-1].next if self.sel else None) or self.sugg[i]
        if p:
            if p.j < len (self.input):
                self.sel.append (p)
                self.__update_candidates (p.j, shortest=True)
                return True
        return False
    def forward (self):
        c = self.cur
        if c:
            self.sel.extend (c)
            self.__update_candidates (c[-1].j)
    def __update_candidates (self, i, shortest=False):
        c = self.cand
        n = len (self.input)
        r = [None for j in range (n + 1)]
        for j in range (len (c), i, -1):
            if c[i][j]:
                r[j] = c[i][j]
        # TODO: add concatenated phrases
        self.__cand_list = r
        j = i
        for k in range (i + 1, n + 1):
            if r[k]:
                j = k
                if shortest:
                    break
        self.__update_candidate_index (i, j)
    def __update_candidate_index (self, i, j):
        r = self.__candidates = [(e.get_phrase (), e) for c in self.__cand_list[j:i:-1] if c for e in c]
        if r:
            self.cur = r[0][1].get_all ()
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
    def get_input_string (self):
        return u''.join (self.input)
    def get_preedit (self):
        if self.has_error ():
            return self.get_input_string (), self.err.i, self.err.j
        start = end = rest = 0
        r = []
        for s in self.sel + self.cur:
            start = end
            w = s.get_word ()
            r.append (w)
            end += len (w)
            rest = s.j
        r.append (u''.join (self.input[rest:]))
        return u''.join (r), start, end
    def get_aux_string (self):
        if self.aux:
            return self.aux
        c = self.cur
        if c:
            return u''.join (self.input[c[0].i:c[-1].j])
        return u''
    def get_candidates (self):
        return self.__candidates
    def delete_phrase (self, e):
        pass

