#!/usr/bin/env python

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
        return self.__db.read_config_value ('Parser')
    def get_in_place_prompt (self):
        parser = self.__db.read_config_value ('Parser')
        return 0 if parser == 'roman' else 1

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

class Context:
    def __init__ (self, callback, model):
        self.__cb = callback
        self.__model = model
        self.clear ()
    def clear (self):
        self.keywords = [u'']
        self.cursor = 0
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
        self.cursor += s[1]
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
        return u''
    def get_candidates (self):
        k = self.cursor
        if k >= len (self.candidates):
            return None
        return self.candidates[k]

