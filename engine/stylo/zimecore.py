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
        self.prompt_pos = -1
        self.preedit = [u'']
        self.candidates = [None]
        self.selection = []
        self.aux = None
    def clear (self):
        self.__reset ()
        self.__cb.update_ui ()
    def is_empty (self):
        return not self.keywords or self.keywords == [u'']
    def update_keywords (self):
        self.__model.update (self)
        if self.schema.is_auto_prompt ():
            self.__set_cursor (self.prompt_pos)
        else:
            self.__set_cursor (-1)
        self.__cb.update_ui ()
    def select (self, s):
        self.__set_cursor (self.cursor + s[1])
        self.__model.select (self, s)
        self.__cb.update_ui ()
    def __set_cursor (self, pos, wrap=False):
        n = len (self.keywords)
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
        if self.aux:
            if callable (self.aux):
                return self.aux (self.cursor)
            else:
                return self.aux
        k = self.cursor
        if k < len (self.keywords) - 1 or self.schema.is_auto_prompt ():
            return self.keywords[k]
        return u''
    def get_candidates (self):
        k = self.cursor
        if k >= len (self.candidates):
            return None
        return self.candidates[k]
    def delete_phrase (self, cand):
        self.__model.delete_phrase (self, cand)
        self.__cb.update_ui ()

