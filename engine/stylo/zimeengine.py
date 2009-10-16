# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import os
import time
import ibus
from ibus import keysyms
from ibus import modifier

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
    DB.open (db_file)
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
        self.__reset ()
        self.__load_schema_list ()
        self.choose (schema_name)
    def __reset (self):
        self.__active = True
        self.__schema_list = []
        self.__engine = None
    def __load_schema_list (self):
        s = DB.read_setting_items (u'Schema/')
        #t = DB.read_setting_items (u'SchemaChooser/LastUsed/')
        # TODO: sort by time
        self.__schema_list = [(x[1], x[0]) for x in s]
    def choose (self, schema_name):
        s = [x[1] for x in self.__schema_list]
        c = -1
        if schema_name and schema_name in s:
            c = s.index (schema_name)
        elif len (s) > 0:
            c = 0
        if c == -1:
            # TODO: 
            self.__frontend.update_aux_string (u'無方案')
            print 'failed to load schema.'
            self.__reset ()
        else:
            now = time.time ()        
            DB.update_setting (u'SchemaChooser/LastUsed/%s' % s[c], unicode (now))
            self.__active = False
            self.__schema_list = []
            self.__engine = Engine (self.__frontend, s[c])
    def __activate (self):
        self.__active = True
        self.__load_schema_list ()
        self.__frontend.update_aux_string (u'方案選單')
        self.__frontend.update_candidates (self.__schema_list)
    def process_key_event (self, keycode, mask):
        if not self.__active:
            if keycode == keysyms.grave:# and mask & modifier.CONTROL_MASK:
                self.__activate ()
                return True
            return self.__engine.process_key_event (keycode, mask)
        

