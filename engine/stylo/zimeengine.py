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
    IBUS_ZIME_LOCATION = os.getenv ('IBUS_ZIME_LOCATION')
    HOME_PATH = os.getenv ('HOME')
    db_path = os.path.join (HOME_PATH, '.ibus', 'zime')
    user_db = os.path.join (db_path, 'zime.db')
    if not os.path.exists (user_db):
        sys_db = IBUS_ZIME_LOCATION and os.path.join (IBUS_ZIME_LOCATION, 'data', 'zime.db')
        if sys_db and os.path.exists (sys_db):
            DB.open (sys_db, read_only=True)
            return
        else:
            if not os.path.isdir (db_path):
                os.makedirs (db_path)
    DB.open (user_db)

__initialize ()

class Engine:
    def __init__ (self, frontend, name):
        self.__frontend = frontend
        self.__schema = Schema (name)
        self.__parser = Parser.create (self.__schema)
        self.__model = Model ()
        self.__ctx = Context (self, self.__model, self.__schema)
        self.update_ui ()
    def process_key_event (self, keycode, mask):
        # disable engine when Caps Lock is on
        if mask & modifier.LOCK_MASK:
            return False
        # ignore Num Lock
        mask &= ~modifier.MOD2_MASK
        # ignore hotkeys
        if mask & (modifier.SHIFT_MASK | \
            modifier.CONTROL_MASK | modifier.ALT_MASK | \
            modifier.SUPER_MASK | modifier.HYPER_MASK | modifier.META_MASK
            ):
            return False
        if self.__parser.process (KeyEvent (keycode, mask), self.__ctx):
            return True
        if self.__ctx.is_empty ():
            return False
        if mask & modifier.RELEASE_MASK:
            return True
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
        if keycode in (keysyms.Page_Up, keysyms.Up, keysyms.minus, keysyms.comma):
            if candidates and self.__frontend.page_up ():
                return True
            return True
        if keycode in (keysyms.Page_Down, keysyms.Down, keysyms.equal, keysyms.period):
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
            self.__model.learn (self.__ctx)
            self.__ctx.clear ()
            return True
        return True
    def update_ui (self):
        ctx = self.__ctx
        start = 0
        for x in ctx.preedit[:ctx.cursor]:
            start += len (x)
        end = start + len (ctx.preedit[ctx.cursor])
        self.__frontend.update_preedit (ctx.get_preedit (), start, end)
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
        t = dict ()
        for x in DB.read_setting_items (u'SchemaChooser/LastUsed/'):
            t[x[0]] = float (x[1])
        last_used_time = lambda a: t[a[0]] if a[0] in t else 0.0
        self.__schema_list = [(x[1], x[0]) for x in sorted (s, key=last_used_time, reverse=True)]
    def choose (self, schema_name):
        s = [x[1] for x in self.__schema_list]
        c = -1
        if schema_name and schema_name in s:
            c = s.index (schema_name)
        elif len (s) > 0:
            c = 0
        if c == -1:
            self.__frontend.update_aux_string (u'無方案')
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
            if keycode == keysyms.grave and mask & modifier.CONTROL_MASK:
                self.__activate ()
                return True
            return self.__engine.process_key_event (keycode, mask)
        # ignore hotkeys
        if mask & (modifier.SHIFT_MASK | \
            modifier.CONTROL_MASK | modifier.ALT_MASK | \
            modifier.SUPER_MASK | modifier.HYPER_MASK | modifier.META_MASK
            ):
            return False
        if mask & modifier.RELEASE_MASK:
            return True
        # schema chooser menu
        if keycode == keysyms.Escape:
            self.__active = False
            if self.__engine:
                self.__engine.update_ui ()
            return True
        if keycode == keysyms.Page_Up or keycode == keysyms.Up:
            if self.__frontend.page_up ():
                return True
            return True
        if keycode == keysyms.Page_Down or keycode == keysyms.Down:
            if self.__frontend.page_down ():
                return True
            return True
        if keycode >= keysyms._1 and keycode <= keysyms._9:
            index = self.__frontend.get_candidate_index (keycode - keysyms._1)
            if index < len (self.__schema_list):
                schema_name = self.__schema_list[index][1]
                self.choose (schema_name)
            return True
        return True
        

