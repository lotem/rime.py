#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import ibus
from ibus import keysyms
from ibus import modifier

import zimeengine

class TestEngine:

    def __init__ (self, schema):
        self.__lookup_table = ibus.LookupTable ()
        self.__backend = zimeengine.SchemaChooser (self, schema)

    def process_key_event (self, keycode, mask):
        print "process_key_event: '%s'(%x), %08x" % (keysyms.keycode_to_name (keycode), keycode, mask)
        return self.__backend.process_key_event (keycode, mask)

    def commit_string (self, s):
        print u'commit: [%s]' % s

    def update_preedit (self, s, start, end):
        print u'preedit: [%s[%s]%s]' % (s[:start], s[start:end], s[end:])
        if not s:
            #super (ZimeEngine, self).hide_preedit_text ()
            return
        preedit_attrs = ibus.AttrList ()
        length = len (s)
        preedit_attrs.append (ibus.AttributeBackground (ibus.RGB (255, 255, 128), 0, start))
        preedit_attrs.append (ibus.AttributeForeground (ibus.RGB (0, 0, 0), 0, start))
        preedit_attrs.append (ibus.AttributeBackground (ibus.RGB (0, 0, 0), start, end))
        preedit_attrs.append (ibus.AttributeForeground (ibus.RGB (255, 255, 128), start, end))
        preedit_attrs.append (ibus.AttributeBackground (ibus.RGB (255, 255, 128), end, length))
        preedit_attrs.append (ibus.AttributeForeground (ibus.RGB (0, 0, 0), end, length))
        #super (ZimeEngine, self).update_preedit_text (ibus.Text (s, preedit_attrs), length, True)

    def update_aux_string (self, s):
        print u'aux: [%s]' % s
        if not s:
            #super (ZimeEngine, self).hide_auxiliary_text ()
            return
        #super (ZimeEngine, self).update_auxiliary_text (ibus.Text (s), True)

    def update_candidates (self, candidates):
        self.__lookup_table.clean ()
        self.__lookup_table.show_cursor (False)
        if not candidates:
            #self.hide_lookup_table ()
            pass
        else:
            for c in candidates:
                self.__lookup_table.append_candidate (ibus.Text (c[0]))
            #self.update_lookup_table (self.__lookup_table, True, True)
            self.__candidates = candidates
            self.__update_lookup_table ()

    def __update_lookup_table (self):
        start = self.__lookup_table.get_current_page_start ()
        end = start + self.__lookup_table.get_page_size ()
        cursor_pos = start + self.__lookup_table.get_cursor_pos_in_current_page ()
        c = self.__candidates
        for i in range (len (c)):
            if i < start:
                continue
            if i >= end:
                break
            print u'candidate: %d%s %s' % (i + 1, u'*' if i == cursor_pos else u'.', c[i][0])
            
    def page_up (self):
        if self.__lookup_table.page_up ():
            print u'page_up.'
            #self.update_lookup_table (self.__lookup_table, True, True)
            self.__update_lookup_table ()
            return True
        return False

    def page_down (self):
        if self.__lookup_table.page_down ():
            print u'page_down.'
            #self.update_lookup_table (self.__lookup_table, True, True)
            self.__update_lookup_table ()
            return True
        return False

    def cursor_up (self):
        if self.__lookup_table.cursor_up ():
            print u'cursor_up.'
            #self.update_lookup_table (self.__lookup_table, True, True)
            self.__update_lookup_table ()
            return True
        return False

    def cursor_down (self):
        if self.__lookup_table.cursor_down ():
            print u'cursor_down.'
            #self.update_lookup_table (self.__lookup_table, True, True)
            self.__update_lookup_table ()
            return True
        return False

    def get_candidate_index (self, index):
        index += self.__lookup_table.get_current_page_start ()
        print u'index = %d' % index
        return index

    def get_candidate_cursor_pos (self):
        index = self.__lookup_table.get_cursor_pos ()
        print u'candidate_cursor_pos = %d' % index
        return index

    def test (self, string):
        name = ''
        is_name = False
        for c in string:
            if c == '{':
                name = ''
                is_name = True
            elif c == '}':
                is_name = False
                self.process_key_event (keysyms.name_to_keycode (name), 0)
            elif is_name:
                name += c
            else:
                self.process_key_event (ord (c), 0)

def main ():
    #e = TestEngine (u'Zhuyin')
    #e.test ('rm/3rm/3u.3gp6zj/ {Escape}2k7al {Tab}')
    #e.test ('5j/ cj86aup6eji6{BackSpace}ji{BackSpace}i6 ')
    #e.test ('5j/ eji6{BackSpace}{BackSpace}')
    #e.test ('5j/ cj86bp6aup6ej/4ck6eji6{Tab}{Page_Down}{Page_Up}{Tab}{Escape} ')
    #e.test ('5j/ eji62k75j/{Tab}{Page_Down}')
    #e.test ('5j/ eji62k75j/ {Left}1{Home}2{Left}1{Tab}1 ')
    #e.test ('5j/ cj86bp6aup6ej/4ck6eji6{Home}1{Home}')
    #e.test ('5j/ cj86bp6aup6ej/4ck6eji6j04njo4{Left}{Left}5{End}{BackSpace}{BackSpace}{BackSpace}{BackSpace}{BackSpace}{BackSpace}{BackSpace} ')
    #e.test ('5j/ 5. mp4{Left}2gj bj4 ')
    #e.test ('5j/ 5. mp4gj {Left}{Left}2bj4z83{Home}{Tab}{Tab}4')
    # test schema chooser menu
    #e.process_key_event (keysyms.grave, modifier.CONTROL_MASK)  # Ctrl+grave
    #e.test ('2')
    #e.process_key_event (keysyms.grave, modifier.CONTROL_MASK)  # Ctrl+grave
    #e.test ('{Page_Down}{Up}{Escape}')
    #e.process_key_event (keysyms.grave, modifier.CONTROL_MASK)  # Ctrl+grave
    #e.test ('1')
    #e.test ('g4{Tab}.=,- ')
    #e.test ('ji{Escape}ji353gji {Tab}{Escape}{Escape}')

    #e = TestEngine (u'Pinyin')
    #e.test ("pinyin-shuru'fa' ")
    #e.test ("an'an anan chang'an changang2 ")
    #e.test ('xauxin xiauxin ')
    #e.test ('pin-yim zioush hauyung ')
    #e.test ('gong{Page_Down}3chen5-tongxuo ')
    #e.test ('woshi-gong{Page_Down}3chen5-tongxuo ')
    #e.test ('zanmen-qu2-ta-jia2-zaishuo ')
    #e.test ('wozhishuo{Escape}ni')

    #e = TestEngine (u'ComboPinyin')
    #e.process_key_event (keysyms.r, 0)
    #e.process_key_event (keysyms.j, 0)
    #e.process_key_event (keysyms.k, 0)
    #e.process_key_event (keysyms.l, 0)
    #e.process_key_event (keysyms.r, modifier.RELEASE_MASK)
    #e.process_key_event (keysyms.j, modifier.RELEASE_MASK)
    #e.process_key_event (keysyms.k, modifier.RELEASE_MASK)
    #e.process_key_event (keysyms.l, modifier.RELEASE_MASK)
    #e.process_key_event (keysyms.space, 0)
    #e.process_key_event (keysyms.space, modifier.RELEASE_MASK)

    #e = TestEngine (u'Pinyin')
    #e.test ('wo! .<>[[]]""""')
    #e = TestEngine (u'Zhuyin')
    #e.test ('ji!3! >')
    #e = TestEngine (u'ComboPinyin')
    #e.test ('!')

    #e = TestEngine (u'Test')
    #e.test ('yorenyoxau2 yosiauxau yosiauxohxau ')
    #e.test ('cioqai-ni-shashou-qai-le-ya ')

    #e = TestEngine (u'Pinyin')
    #e.test ('guantasanqi-ershiyi ')
    #e.test ('wozaixiechengshipspspspspsp')
    #e.test ('woyoulailaHP')

    #from zimedb import DB
    #DB.open ('/home/lotem/.ibus/zime/zime.db', True)
    #db = DB ('Pinyin')
    #print db.list_keywords ()
    #print db.lookup_phrase ('yi yi'.split ())

    #e = TestEngine (u'Pinyin')
    #e.test ('zhunghuarenmingungheguo-vansui {Return}{Return}')
    #e.test ('aspasp {BackSpace}{Escape}')
    #e.test ('changanjiushixian {BackSpace}{BackSpace}{Tab}{Tab} {Left}{Right} ....5{Escape}')
    #e.test ('pinyim-shurufa {BackSpace} {BackSpace}{BackSpace}{BackSpace}{Escape}')
    #e.test ('pinyim-shurufa {BackSpace}{BackSpace} {BackSpace} {Escape}')
    #e.test ('wo-xihuan  ')
    #e.test ('pinyim-shurufa  ')
    #e.test ('gongchen {BackSpace}85.')
    #e.test ('renminde gongchen 2.')
    #e.test ('woshi gongchen  .')
    #e.test ('gongchen {Escape}')
    #e.test ('renminde gongchen {Escape}')
    #e.test ('woshi gongchen {Escape}')

    #e = TestEngine (u'Pinyin')
    # test fuzzy input
    #e.test ('qiujiu')
    #e.test ('chagnan')
    #e.test ('changansbssyiandejioucen')
    #e.test ('zhonghrmghg')
    #e.test ('lzsb')
    #e.test ('rminyxongychbxiuuiuiuiui {Escape} {BackSpace}{BackSpace}{BackSpace} {Home}{Tab}{Page_Down}{Page_Up}')
    #e.test ('lanzhoushaobing  lzsb {Escape}{Escape}')
    #e.test ('shishemeyisi .4ssmys {Escape}{Escape}')
    #e.test ('ruguodachangjuhuishishemexiaoguo {Home} .52.    rgdchjhshshmxg {Escape}{Escape}')
    #e.test ('shishutang {Home}{Left}.434.shishutangshaozhu 2 shishutangshzh {Home}{Escape}{Escape}')
    # a rare case: when the longest concat'd phrases fail to rank in top LIMIT, and there are not dict phrase of that length. when testing, LIMIT in Context.__update_candidate should be set to 1
    #e.test ('gongchenchong {Home} ...3gongchenchongmi {Home}')
    #"""
    #e.test ('gongchentongxue  .')
    #e.test ('renmindegongchen 2.')
    #e.test ('congmingdegongchentongxue {Left}{Left}')
    #"""
    #e.test ('gongminquanli 2;guowangquanli 3;gongmin quanli {Escape}{Escape};guowang quanli ')
    #e.test ('shishikanzhongbuzhongyong {Home}')
    #e.test ('Ubuntu9.10{Return}')
    # test Shift-Return
    #e.test ('vutuvuzhensiang')
    #e.process_key_event (keysyms.Shift_L, 0)
    #e.process_key_event (keysyms.Return, modifier.SHIFT_MASK)
    #e.process_key_event (keysyms.Return, modifier.SHIFT_MASK | modifier.RELEASE_MASK)
    #e.process_key_event (keysyms.Shift_L, modifier.RELEASE_MASK)
    # BUG: fail to recognize `[zcs]huang` due to misuse of max_keyword_length
    #e.test ('anzhuang')

    #e = TestEngine (u'TonalPinyin')
    #e.test ('biao1diao4  ')

    pass

if __name__ == "__main__":
    main ()
