#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import os
import ibus
from ibus import keysyms
from ibus import modifier

import session

class ZimeTester:

    def __init__(self, schema):
        self.__lookup_table = ibus.LookupTable()
        self.__backend = session.Switcher(self, schema)

    def process_key_event(self, keycode, mask):
        print "process_key_event: '%s'(%x), %08x" % (keysyms.keycode_to_name(keycode), keycode, mask)
        return self.__backend.process_key_event(keycode, mask)

    def commit_string(self, s):
        print u'commit: [%s]' % s

    def update_preedit(self, s, start=0, end=0):
        if start < end:
            print u'preedit: [%s[%s]%s]' % (s[:start], s[start:end], s[end:])
        else:
            print u'preedit: [%s]' % s
        if not s:
            #super(ZimeEngine, self).hide_preedit_text()
            return
        #super(ZimeEngine, self).update_preedit_text(ibus.Text(s), length, True)

    def update_aux(self, s, start=0, end=0):
        if start < end:
            print u'aux: [%s[%s]%s]' % (s[:start], s[start:end], s[end:])
        else:
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

    #e = ZimeTester(u'Zhuyin')
    #e.test('rm/3rm/3u.3gp6zj/ {Escape}2k7al {Tab}{Return}')

    e = ZimeTester(u'Pinyin')
    #e.test('jiong ')
    e.test("pinyin-shuru'fa'{Left}")
    #e.test('henanquan{Home}{Tab} ')
    #e.test('hezhinan{Home}. 23qianwanghezhinan')  # 河之南 vs. 和指南
    #e.test('henanhenanquan{Tab} {Tab}{Tab}')

    #e = ZimeTester(u'ComboPinyin')
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

    #e = ZimeTester(u'Jyutping')
    #e.test('jyuhomindeoicangjatheizaugwodikjatzi')
    #e.test('fanhoifongziganbunsamgikci')

    #e = ZimeTester(u'TonalPinyin')
    #e.test('pkucn.com')
    #e.test('3.14wo1.0')

    pass

if __name__ == "__main__":
    main()
