# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import os
import time
import ibus
from ibus import keysyms
from ibus import modifier
from ibus import ascii

from zimecore import *
from zimedb import *
import zimeparser

def __initialize ():
    zimeparser.register_parsers ()
    IBUS_ZIME_LOCATION = os.getenv ('IBUS_ZIME_LOCATION')
    HOME_PATH = os.getenv ('HOME')
    db_path = os.path.join (HOME_PATH, '.ibus', 'zime')
    user_db = os.path.join (db_path, 'plume.db')
    if not os.path.exists (user_db):
        sys_db = IBUS_ZIME_LOCATION and os.path.join (IBUS_ZIME_LOCATION, 'data', 'plume.db')
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
        self.__schema = schema = Schema (name)
        self.__parser = Parser.create (schema)
        self.__ctx = Context (self, schema)
        self.__auto_prompt = schema.get_config_value (u'AutoPrompt') in (u'yes', u'true')
        self.__punct = None
        self.__punct_key = 0
        self.__punct_rep = 0
        self.update_ui ()
    def process_key_event (self, keycode, mask):
        # disable engine when Caps Lock is on
        if mask & modifier.LOCK_MASK:
            return False
        # ignore Num Lock
        mask &= ~modifier.MOD2_MASK
        # process hotkeys
        if mask & ( \
            modifier.CONTROL_MASK | modifier.ALT_MASK | \
            modifier.SUPER_MASK | modifier.HYPER_MASK | modifier.META_MASK
            ):
            if mask & ~modifier.RELEASE_MASK == modifier.CONTROL_MASK and keycode >= keysyms._1 and keycode <= keysyms._9:
                candidates = self.__ctx.get_candidates ()
                if candidates:
                    if mask & modifier.RELEASE_MASK == 0:
                        # delete phrase
                        index = self.__frontend.get_candidate_index (keycode - keysyms._1)
                        if index >= 0 and index < len (candidates):
                            self.__ctx.delete_phrase (candidates[index][1])
                    return True
            # ignore other hotkeys
            return False
        if self.__punct:
            if keycode not in (keysyms.Shift_L, keysyms.Shift_R) and not (mask & modifier.RELEASE_MASK):
                if keycode == self.__punct_key:
                    self.__next_punct ()
                    return True
                else:
                    if keycode in (keysyms.Escape, keysyms.BackSpace):
                        # clear punct prompt
                        self.__commit_punct (commit=False)
                        return True
                    if keycode in (keysyms.space, keysyms.Return):
                        self.__commit_punct ()
                        return True
                    self.__commit_punct ()
                    # continue processing
        event = KeyEvent (keycode, mask)
        result = self.__parser.process_input (event, self.__ctx)
        if result is True:
            return True
        if result is False:
            return self.__process (event)
        return self.__handle_parser_result (result)
    def __handle_parser_result (self, result):
        if isinstance (result, Commit):
            self.__frontend.commit_string (result)
            self.__parser.clear ()
            self.__ctx.clear ()
        if isinstance (result, Prompt):
            if self.__parser.prompt:
                self.__update_preedit ()
                self.__frontend.update_aux_string (u'')
                self.__frontend.update_candidates ([])
            else:
                self.update_ui ()
            return True    
        if isinstance (result, list):
            # handle input
            if self.__is_conversion_mode ():
                if self.__ctx.is_completed ():
                    # auto-commit
                    self.__commit ()
                else:
                    return True
            self.__ctx.edit (self.__ctx.input + result, start_conversion=self.__auto_prompt)
            return True
        if isinstance (result, KeyEvent):
            # coined key event
            return self.__process (result)
        # noop
        return True
    def __next_punct (self):
        self.__punct_rep = (self.__punct_rep + 1) % len (self.__punct)
        punct = self.__punct[self.__punct_rep]
        self.__frontend.update_preedit (punct, 0, len (punct))
    def __commit_punct (self, commit=True):
        punct = self.__punct[self.__punct_rep]
        self.__punct = None
        self.__punct_key = 0
        self.__punct_rep = 0
        self.__frontend.update_preedit (u'', 0, 0)
        if commit:
            self.__frontend.commit_string (punct)
            self.__ctx.clear ()
    def __judge (self, event):
        self.__ctx.clear ()
        if event.coined:
            if not event.mask:
                self.__frontend.commit_string (event.get_char ())
            return True
        return False
    def __process (self, event):
        ctx = self.__ctx
        if ctx.is_empty ():
            if event.mask & modifier.RELEASE_MASK and self.__punct:
                return True
            if self.__handle_punct (event, commit=False):
                return True
            return self.__judge (event)
        if event.mask & modifier.RELEASE_MASK:
            return True
        edit_key = self.__parser.check_edit_key (event)
        if edit_key:
            return self.__process (edit_key)
        if event.keycode == keysyms.Escape:
            if self.__is_conversion_mode ():
                ctx.cancel_conversion ()
            elif ctx.has_error ():
                ctx.pop_input (ctx.err.i)
                ctx.edit (ctx.input, start_conversion=self.__auto_prompt)
            else:
                ctx.edit ([])
            return True
        if event.keycode == keysyms.Tab:
            ctx.end (start_conversion=True)
            return True
        if event.keycode == keysyms.Home:
            ctx.home ()
            return True
        if event.keycode == keysyms.End:
            ctx.end ()
            return True
        if event.keycode == keysyms.Left:
            ctx.left ()
            return True
        if event.keycode == keysyms.Right:
            ctx.right ()
            return True
        candidates = ctx.get_candidates ()
        if candidates:
            if event.keycode in (keysyms.minus, keysyms.comma):
                self.__frontend.page_up () and self.__select_by_cursor (candidates)
                return True
            if event.keycode in (keysyms.equal, keysyms.period):
                self.__frontend.page_down () and self.__select_by_cursor (candidates)
                return True
        if event.keycode == keysyms.Page_Up:
            if candidates and self.__frontend.page_up ():
                self.__select_by_cursor (candidates)
                return True
            return True
        if event.keycode == keysyms.Page_Down:
            if candidates and self.__frontend.page_down ():
                self.__select_by_cursor (candidates)
                return True
            return True
        if event.keycode == keysyms.Up:
            if candidates and self.__frontend.cursor_up ():
                self.__select_by_cursor (candidates)
                return True
            return True
        if event.keycode == keysyms.Down:
            if candidates and self.__frontend.cursor_down ():
                self.__select_by_cursor (candidates)
                return True
            return True
        if event.keycode >= keysyms._1 and event.keycode <= keysyms._9:
            if self.__select_by_index (candidates, event.keycode - keysyms._1):
                return True
            else:
                # auto-commit
                self.__commit ()
                return self.__judge (event)
        if event.keycode == keysyms.BackSpace:
            if self.__is_conversion_mode (assumed=bool (event.mask & modifier.SHIFT_MASK)):
                ctx.back () or self.__auto_prompt or ctx.cancel_conversion ()
            else:
                ctx.pop_input ()
                ctx.edit (ctx.input, start_conversion=self.__auto_prompt)
            return True
        if event.keycode == keysyms.space:
            if ctx.being_converted ():
                self.__confirm_current ()
            else:
                ctx.edit (ctx.input, start_conversion=True)
            return True
        if event.keycode == keysyms.Return:
            if ctx.being_converted ():
                self.__confirm_current ()
            else:
                self.__commit (raw_input=bool (event.mask & modifier.SHIFT_MASK))
            return True
        # auto-commit
        if self.__handle_punct (event, commit=True):
            return True
        return True
    def __is_conversion_mode (self, assumed=False):
        return (not self.__auto_prompt or assumed) and self.__ctx.being_converted ()
    def __handle_punct (self, event, commit):
        punct = self.__parser.check_punct (event)
        if punct:
            if event.mask & modifier.RELEASE_MASK:
                return True
            if commit:
                self.__commit ()
            if isinstance (punct, list):
                self.__punct = punct
                self.__punct_key = event.keycode
                self.__punct_rep = 0
                # prompt punct
                self.__frontend.update_preedit (punct[0], 0, len (punct[0]))
            else:
                self.__frontend.commit_string (punct)
            return True
        return False
    def __select_by_index (self, candidates, n):
        if not candidates:
            return False
        index = self.__frontend.get_candidate_index (n)
        if index >= 0 and index < len (candidates):
            self.__ctx.select (candidates[index][1])
            self.__confirm_current ()
        return True
    def __select_by_cursor (self, candidates):
        index = self.__frontend.get_candidate_cursor_pos ()
        if index >= 0 and index < len (candidates):
            self.__ctx.select (candidates[index][1])
            self.__update_preedit ()
            self.__frontend.update_aux_string (self.__ctx.get_aux_string ())
            return True
        return False
    def __confirm_current (self):
        if self.__ctx.is_completed ():
            self.__commit ()
        else:
            self.__ctx.forward ()
    def __commit (self, raw_input=False):
        s = self.__ctx.get_input_string () if raw_input else self.__ctx.get_commit_string ()
        self.__frontend.commit_string (s)
        self.__parser.clear ()
        self.__ctx.commit ()
    def __update_preedit (self):
        preedit, start, end = self.__ctx.get_preedit ()
        prompt = self.__parser.prompt
        if prompt:
            start = len (preedit)
            preedit += prompt
            end = len (preedit)
        self.__frontend.update_preedit (preedit, start, end)
    def update_ui (self):
        self.__update_preedit ()
        self.__frontend.update_aux_string (self.__ctx.get_aux_string ())
        self.__frontend.update_candidates (self.__ctx.get_candidates ())
        
class SchemaChooser:
    def __init__ (self, frontend, schema_name=None):
        self.__frontend = frontend
        self.__engine = None
        self.__deactivate ()
        self.__load_schema_list ()
        self.choose (schema_name)
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
        if c != -1:
            now = time.time ()        
            DB.update_setting (u'SchemaChooser/LastUsed/%s' % s[c], unicode (now))
            self.__deactivate ()
            self.__engine = Engine (self.__frontend, s[c])
    def __activate (self):
        self.__active = True
        self.__load_schema_list ()
        self.__frontend.update_aux_string (u'方案選單')
        self.__frontend.update_candidates (self.__schema_list)
    def __deactivate (self):
        self.__active = False
        self.__schema_list = []
    def process_key_event (self, keycode, mask):
        if not self.__engine:
            self.__frontend.update_aux_string (u'無方案')
            return False
        if not self.__active:
            # Ctrl-` calls schema chooser menu
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
            if self.__engine:
                self.__deactivate ()
                self.__engine.update_ui ()
            return True
        if keycode in (keysyms.Page_Up, keysyms.minus, keysyms.comma):
            if self.__frontend.page_up ():
                return True
            return True
        if keycode in (keysyms.Page_Down, keysyms.equal, keysyms.period):
            if self.__frontend.page_down ():
                return True
            return True
        if keycode == keysyms.Up:
            if self.__frontend.cursor_up ():
                return True
            return True
        if keycode == keysyms.Down:
            if self.__frontend.cursor_down ():
                return True
            return True
        if keycode >= keysyms._1 and keycode <= keysyms._9:
            index = self.__frontend.get_candidate_index (keycode - keysyms._1)
            self.__choose_schema_by_index (index)
            return True
        if keycode in (keysyms.space, keysyms.Return):
            index = self.__frontend.get_candidate_cursor_pos ()
            self.__choose_schema_by_index (index)
            return True    
        return True
    def __choose_schema_by_index (self, index):
        if index >= 0 and index < len (self.__schema_list):
            schema_name = self.__schema_list[index][1]
            self.choose (schema_name)

