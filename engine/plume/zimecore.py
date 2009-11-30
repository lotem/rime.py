#!/usr/bin/env python

import ibus
from ibus import keysyms

from zimedb import DB
from zimemodel import Model

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

def _get (c, label):
    for x in c:
        if x[0] == label:
            return x
    return None

class Context:
    EDIT, CONVERT, ERROR = 0, 1, -1
    def __init__ (self, callback, schema):
        self.__cb = callback
        self.__model = Model (schema)
        self.schema = schema
        self.__reset ()
        self.clear_context_info ()
    def __reset (self, clearInput=True):
        self.state = Context.EDIT
        if clearInput:
            self.input = []
        self.aux = None
        self.sel = []
        self.cand = []
        self.__candidates = []
    def clear_context_info (self):
        self.last_phrase = None
    def clear (self):
        self.__reset ()
        self.__cb.update_ui ()
    def edit (self):
        self.__reset (clearInput=False)
        self.__cb.update_ui ()
    def is_empty (self):
        return not self.input
    def commit (self):
        if self.state == Context.CONVERT:
            self.__model.train (self)
        else:
            self.clear_context_info ()
        self.clear ()
    def clear_error (self):
        del self.input[self.sel[-1][0]:]
        self.sel = []
        self.edit ()
    def next (self):
        if self.state != Context.CONVERT:
            return False
        if not self.sel:
            return False
        s = self.sel.pop ()
        x = _get (self.cand, s[0])
        for y in x[1]:
            if y[0] > s[1]:
                self.__update_selection (x[0], y[0], y[1])
                return True
        # wrap
        y = x[1][0]
        self.__update_selection (x[0], y[0], y[1])
        return True
    def previous (self):
        if self.state != Context.CONVERT:
            return False
        s = self.sel.pop ()
        x = _get (self.cand, s[0])
        for y in reversed (x[1]):
            if y[0] < s[1]:
                self.__update_selection (x[0], y[0], y[1])
                return True
        self.sel.append (s)
        return False
    def start (self):
        if self.state == Context.CONVERT:
            return
        self.__model.query (self)
        if self.state == Context.CONVERT:
            self.forward ()
        elif self.state == Context.ERROR:
            self.__cb.update_ui ()
    def forward (self):
        cursor_pos = self.sel[-1][1] if self.sel else 0
        x = _get (self.cand, cursor_pos)
        y = x[1][-1]  # take the longest phrase that starts at cursor_pos
        self.__update_selection (x[0], y[0], y[1])
    def __update_selection (self, i, j, c):
        candidates = self.__model.calculate_candidates (self, c)
        if candidates:
            self.sel.append ([i, j, candidates[0][1]])
        self.__candidates = candidates
        self.__cb.update_ui ()
    def back (self):
        self.sel.pop ()
        if self.sel:
            self.sel.pop ()
            self.forward ()
        else:
            self.edit ()
    def select (self, s):
        self.sel[-1][2] = s
    def converted (self):
        return self.sel and self.sel[-1][1] == len (self.input)
    def get_preedit (self):
        if self.state == Context.EDIT:
            return u''.join (self.input), 0, 0
        if self.state == Context.ERROR:
            return u''.join (self.input), self.sel[-1][0], self.sel[-1][1]
        start = end = rest = 0
        r = []
        for s in self.sel:
            start = end
            r.append (s[2][1])
            end += len (s[2][1])
            rest = s[1]
        r.append (u''.join (self.input[rest:]))
        return u''.join (r), start, end
    def get_aux_string (self):
        if self.aux:
            if callable (self.aux):
                return self.aux (self.cursor)
            else:
                return self.aux
        if self.state == Context.CONVERT and self.sel:
            s = self.sel[-1]
            return u''.join (self.input[s[0]:s[1]])
        return u''
    def get_candidates (self):
        return self.__candidates
    def delete_phrase (self, cand):
        pass

