#!/usr/bin/env python

import ibus
from ibus import keysyms

from zimedb import DB

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
        self.__auto_prompt = self.__db.read_config_value (u'AutoPrompt') == u'yes'
    def get_name (self):
        return self.__name
    def get_db (self):
        return self.__db
    def get_parser_name (self):
        return self.__parser_name
    def is_auto_prompt (self):
        return self.__auto_prompt
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
        punct_mapping = lambda (x, y): (x, [tuple (z.split (u'~', 1)) if u'~' in z else z for z in y.split ()])
        self.__punct = dict ([punct_mapping (c.split (None, 1)) for c in schema.get_config_list (u'Punct')])
    def get_schema (self):
        return self.__schema
    def check_punct (self, event):
        ch = event.get_char ()
        if ch in self.__punct:
            p = self.__punct[ch]
            if not p:
                return None
            x = p[0]
            if isinstance (x, tuple):
                y = x[0]
                p[0] = (x[1], x[0])
                return y
            else:
                return x
        return None

class Context:
    def __init__ (self, callback, model, schema):
        self.__cb = callback
        self.__model = model
        self.schema = schema
        self.__reset ()
    def __reset (self):
        self.keywords = [u'']
        self.cursor = 0
        self.kwd = []
        self.cand = []
        self.sugg = [(-1, u'', 0)]
        self.preedit = [u'']
        self.candidates = [None]
        self.selection = []
        self.aux_string = u''
    def clear (self):
        self.__reset ()
        self.__cb.update_ui ()
    def is_empty (self):
        return not self.keywords or self.keywords == [u'']
    def update_keywords (self):
        self.__set_cursor (-1)
        self.__model.update (self)
        self.__cb.update_ui ()
    def select (self, index):
        s = self.get_candidates ()[index][1]
        self.__set_cursor (self.cursor + s[1])
        self.__model.select (self, s)
        self.__cb.update_ui ()
    def __set_cursor (self, pos, wrap=False):
        n = len (self.keywords)
        if n > 1 and not self.keywords[n - 1] and self.schema.is_auto_prompt ():
            n -= 1
        if not wrap and pos >= n:
            pos = n - 1
        self.cursor = pos % n
    def set_cursor (self, pos):
        self.__set_cursor (pos)
        self.__cb.update_ui ()
    def move_cursor (self, offset):
        self.__set_cursor (self.cursor + offset, wrap=True)
        self.__cb.update_ui ()
    def get_preedit (self):
        return u''.join (self.preedit)
    def get_aux_string (self):
        if self.aux_string:
            return self.aux_string
        k = self.cursor
        if k < len (self.keywords) - 1 or self.schema.is_auto_prompt ():
            return self.keywords[k]
        return u''
    def get_candidates (self):
        k = self.cursor
        if k >= len (self.candidates):
            return None
        return self.candidates[k]

