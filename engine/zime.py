# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

__all__ = (
    "ZimeEngine",
)

import ibus
import os

import session
import processor
from storage import DB

class ZimeEngine(ibus.EngineBase):

    def __init__(self, conn, object_path):
        super(ZimeEngine, self).__init__(conn, object_path)
        self.__page_size = DB.read_setting(u'Option/PageSize') or 5
        self.__lookup_table = ibus.LookupTable(self.__page_size)
        self.__backend = session.Switcher(self)

    def process_key_event(self, keyval, keycode, mask):
        return self.__backend.process_key_event(keyval, mask)

    def commit_string(self, s):
        #logger.debug(u'commit: [%s]' % s)
        super(ZimeEngine, self).commit_text(ibus.Text(s))

    def update_preedit(self, s, start=0, end=0):
        #logger.debug(u'preedit: [%s]' % s)
        if not s:
            super(ZimeEngine, self).hide_preedit_text()
            return
        length = len(s)
        attrs = ibus.AttrList()
        attrs.append(ibus.AttributeUnderline(ibus.ATTR_UNDERLINE_SINGLE, 0, length))
        if start < end:
            attrs.append(ibus.AttributeBackground(ibus.RGB(255, 255, 128), start, end))
            attrs.append(ibus.AttributeForeground(ibus.RGB(0, 0, 0), start, end))
        t = ibus.Text(s, attrs)
        super(ZimeEngine, self).update_preedit_text(t, length, True)

    def update_aux(self, s, start=0, end=0):
        #logger.debug(u'aux: [%s]' % s)
        if not s:
            super(ZimeEngine, self).hide_auxiliary_text()
            return
        length = len(s)
        attrs = ibus.AttrList()
        if start < end:
            attrs.append(ibus.AttributeBackground(ibus.RGB(255, 255, 128), start, end))
            attrs.append(ibus.AttributeForeground(ibus.RGB(0, 0, 0), start, end))
        t = ibus.Text(s, attrs)
        super(ZimeEngine, self).update_auxiliary_text(t, True)

    def update_candidates(self, candidates):
        self.__lookup_table.clean()
        self.__lookup_table.show_cursor(False)
        if not candidates:
            self.hide_lookup_table()
        else:
            for c in candidates:
                self.__lookup_table.append_candidate(ibus.Text(c[0]))
            self.update_lookup_table(self.__lookup_table, True, True)
    
    def page_up(self):
        if self.__lookup_table.page_up():
            self.update_lookup_table(self.__lookup_table, True, True)
            return True
        return False

    def page_down(self):
        if self.__lookup_table.page_down():
            self.update_lookup_table(self.__lookup_table, True, True)
            return True
        return False

    def cursor_up(self):
        if self.__lookup_table.cursor_up():
            self.update_lookup_table(self.__lookup_table, True, True)
            return True
        return False

    def cursor_down(self):
        if self.__lookup_table.cursor_down():
            self.update_lookup_table(self.__lookup_table, True, True)
            return True
        return False

    def get_candidate_cursor_pos(self):
        index = self.__lookup_table.get_cursor_pos()
        return index

    def get_candidate_index(self, index):
        if index >= self.__page_size:
            return -1
        return index + self.__lookup_table.get_current_page_start()

