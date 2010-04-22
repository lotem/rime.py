#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import os
import ibus
from ibus import keysyms
from ibus import modifier

import zimeengine
import zimeparser
from zimedb import DB

def _initialize():
    zimeparser.register_parsers()
    # initialize DB 
    IBUS_ZIME_LOCATION = os.getenv('IBUS_ZIME_LOCATION')
    HOME_PATH = os.getenv('HOME')
    db_path = os.path.join(HOME_PATH, '.ibus', 'zime')
    user_db = os.path.join(db_path, 'zime.db')
    if not os.path.exists(user_db):
        sys_db = IBUS_ZIME_LOCATION and os.path.join(IBUS_ZIME_LOCATION, 'data', 'zime.db')
        if sys_db and os.path.exists(sys_db):
            DB.open(sys_db, read_only=True)
            return
        else:
            if not os.path.isdir(db_path):
                os.makedirs(db_path)
    DB.open(user_db)

_initialize()

class TestEngine:

    def __init__(self, schema):
        self.__lookup_table = ibus.LookupTable()
        self.__backend = zimeengine.SchemaChooser(self, schema)

    def process_key_event(self, keycode, mask):
        print "process_key_event: '%s'(%x), %08x" % (keysyms.keycode_to_name(keycode), keycode, mask)
        return self.__backend.process_key_event(keycode, mask)

    def commit_string(self, s):
        print u'commit: [%s]' % s

    def update_preedit(self, s, start, end):
        print u'preedit: [%s[%s]%s]' % (s[:start], s[start:end], s[end:])
        if not s:
            #super(ZimeEngine, self).hide_preedit_text()
            return
        preedit_attrs = ibus.AttrList()
        length = len(s)
        preedit_attrs.append(ibus.AttributeBackground(ibus.RGB(255, 255, 128), 0, start))
        preedit_attrs.append(ibus.AttributeForeground(ibus.RGB(0, 0, 0), 0, start))
        preedit_attrs.append(ibus.AttributeBackground(ibus.RGB(0, 0, 0), start, end))
        preedit_attrs.append(ibus.AttributeForeground(ibus.RGB(255, 255, 128), start, end))
        preedit_attrs.append(ibus.AttributeBackground(ibus.RGB(255, 255, 128), end, length))
        preedit_attrs.append(ibus.AttributeForeground(ibus.RGB(0, 0, 0), end, length))
        #super(ZimeEngine, self).update_preedit_text(ibus.Text(s, preedit_attrs), length, True)

    def update_aux_string(self, s):
        print u'aux: [%s]' % s
        if not s:
            #super(ZimeEngine, self).hide_auxiliary_text()
            return
        #super(ZimeEngine, self).update_auxiliary_text(ibus.Text(s), True)

    def update_candidates(self, candidates):
        self.__lookup_table.clean()
        self.__lookup_table.show_cursor(False)
        if not candidates:
            #self.hide_lookup_table()
            pass
        else:
            for c in candidates:
                self.__lookup_table.append_candidate(ibus.Text(c[0]))
            #self.update_lookup_table(self.__lookup_table, True, True)
            self.__candidates = candidates
            self.__update_lookup_table()

    def __update_lookup_table(self):
        start = self.__lookup_table.get_current_page_start()
        end = start + self.__lookup_table.get_page_size()
        cursor_pos = start + self.__lookup_table.get_cursor_pos_in_current_page()
        c = self.__candidates
        for i in range(len(c)):
            if i < start:
                continue
            if i >= end:
                break
            print u'candidate: %d%s %s' % (i + 1, u'*' if i == cursor_pos else u'.', c[i][0])
            
    def page_up(self):
        if self.__lookup_table.page_up():
            print u'page_up.'
            #self.update_lookup_table(self.__lookup_table, True, True)
            self.__update_lookup_table()
            return True
        return False

    def page_down(self):
        if self.__lookup_table.page_down():
            print u'page_down.'
            #self.update_lookup_table(self.__lookup_table, True, True)
            self.__update_lookup_table()
            return True
        return False

    def cursor_up(self):
        if self.__lookup_table.cursor_up():
            print u'cursor_up.'
            #self.update_lookup_table(self.__lookup_table, True, True)
            self.__update_lookup_table()
            return True
        return False

    def cursor_down(self):
        if self.__lookup_table.cursor_down():
            print u'cursor_down.'
            #self.update_lookup_table(self.__lookup_table, True, True)
            self.__update_lookup_table()
            return True
        return False

    def get_candidate_index(self, index):
        index += self.__lookup_table.get_current_page_start()
        print u'index = %d' % index
        return index

    def get_candidate_cursor_pos(self):
        index = self.__lookup_table.get_cursor_pos()
        print u'candidate_cursor_pos = %d' % index
        return index

    def test(self, string):
        name = ''
        is_name = False
        for c in string:
            if c == '{':
                name = ''
                is_name = True
            elif c == '}':
                is_name = False
                self.process_key_event(keysyms.name_to_keycode(name), 0)
            elif is_name:
                name += c
            else:
                self.process_key_event(ord(c), 0)

def main():
    # test schema chooser menu
    #e.process_key_event(keysyms.grave, modifier.CONTROL_MASK)  # Ctrl+grave
    #e.test('2')

    #e = TestEngine(u'Zhuyin')
    #e.test('rm/3rm/3u.3gp6zj/ {Escape}2k7al {Tab}{Return}')

    #e = TestEngine(u'Pinyin')
    #e.test("pinyin-shuru'fa' ")
    #e.test('henanquan{Home}{Tab} ')

    #e = TestEngine(u'ComboPinyin')
    #e.process_key_event(keysyms.r, 0)
    #e.process_key_event(keysyms.j, 0)
    #e.process_key_event(keysyms.k, 0)
    #e.process_key_event(keysyms.l, 0)
    #e.process_key_event(keysyms.r, modifier.RELEASE_MASK)
    #e.process_key_event(keysyms.j, modifier.RELEASE_MASK)
    #e.process_key_event(keysyms.k, modifier.RELEASE_MASK)
    #e.process_key_event(keysyms.l, modifier.RELEASE_MASK)
    #e.process_key_event(keysyms.space, 0)
    #e.process_key_event(keysyms.space, modifier.RELEASE_MASK)

    #e = TestEngine(u'Jyutping')
    #e.test('jyuhomindeoicangjatheizaugwodikjatzi')
    #e.test('fanhoifongziganbunsamgikci')

    pass

if __name__ == "__main__":
    main()
