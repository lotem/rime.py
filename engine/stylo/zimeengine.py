# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import os
import time
import ibus
from ibus import keysyms

from zimecore import *
from zimedb import *
from zimemodel import *
import zimeparser

def __initialize ():
    zimeparser.register_parsers ()
    home_path = os.getenv ('HOME')
    db_path = os.path.join (home_path, '.ibus', 'zime')
    if not os.path.isdir (db_path):
        os.makedirs (db_path)
    db_file = os.path.join (db_path, 'zime.db')
    DB.connect (db_file)
    print "__initialize"

__initialize ()

class Engine:
    def __init__ (self, frontend, name):
        self.__frontend = frontend
        self.__schema = Schema (name)
        self.__model = Model (self.__schema)
        self.__parser = Parser.create (self.__schema)
        self.__ctx = Context (self, self.__model)
    def process_key_event (self, keycode, mask):
        if self.__parser.process (KeyEvent (keycode, mask), self.__ctx):
            return True
        if self.__ctx.is_empty ():
            return False
        if keycode == keysyms.Home:
            self.__ctx.set_cursor (0)
            return True
        if keycode == keysyms.End or keycode == keysyms.Escape:
            self.__ctx.set_cursor (-1)
            return True
        if keycode == keysyms.Left:
            self.__ctx.move_cursor (-1)
            return True
        if keycode == keysyms.Right or keycode == keysyms.Tab:
            self.__ctx.move_cursor (1)
            return True
        candidates = self.__ctx.get_candidates ()
        if keycode == keysyms.Page_Up or keycode == keysyms.Up:
            if candidates and self.__frontend.page_up ():
                return True
            return True
        if keycode == keysyms.Page_Down or keycode == keysyms.Down:
            if candidates and self.__frontend.page_down ():
                return True
            return True
        if keycode >= keysyms._1 and keycode <= keysyms._9:
            if candidates:
                index = self.__frontend.get_candidate_index (keycode - keysyms._1)
                self.__ctx.select (index)
            return True
        if keycode == keysyms.BackSpace:
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
        if keycode in (keysyms.space, keysyms.Return):
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
        
class SchemaChooser:
    def __init__ (self, frontend, schema_name=None):
        self.__frontend = frontend
        s = DB.read_setting_items (u'Schema/')
        print 'schema:', s
        if not schema_name and len (s) > 0:
            # TODO
            #t = DB.read_setting_items (u'SchemaChooser/LastUsed/')
            schema_name = s[0][0]
        self.choose (schema_name)
    def choose (self, schema_name):
        timestamp = time.time ()        
        DB.update_setting (u'SchemaChooser/LastUsed/%s' % schema_name, unicode (timestamp))
        self.__engine = Engine (self.__frontend, schema_name)
    def process_key_event (self, keycode, mask):
        return self.__engine.process_key_event (keycode, mask)
        

