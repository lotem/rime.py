# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

__all__ = (
    "ZimeEngine",
)

import ibus
import gobject

from stylo import zimecore
from stylo import zimeparser
zimeparser.register_parsers ()

#from gettext import dgettext
#_  = lambda a : dgettext ("ibus-zime", a)
_ = lambda a : a
N_ = lambda a : a


class ZimeEngine (ibus.EngineBase):

    def __init__ (self, conn, object_path):
        super (ZimeEngine, self).__init__ (conn, object_path)
        self.__lookup_table = ibus.LookupTable ()
        # TODO
        self.__engine = zimecore.Engine (self, 'zhuyin')

    def process_key_event (self, keycode, mask):
        return self.__engine.process_key_event (zimecore.KeyEvent (keycode, mask))

    def commit_string (self, s):
        #print u'commit: [%s]' % s
        super (ZimeEngine, self).commit_text (ibus.Text (s))

    def update_preedit (self, s, start, end):
        #print u'preedit: [%s]' % s
        if not s:
            super (ZimeEngine, self).hide_preedit_text ()
            return
        preedit_attrs = ibus.AttrList ()
        length = len (s)
        preedit_attrs.append (ibus.AttributeBackground (ibus.RGB (255, 255, 128), 0, start))
        preedit_attrs.append (ibus.AttributeForeground (ibus.RGB (0, 0, 0), 0, start))
        preedit_attrs.append (ibus.AttributeBackground (ibus.RGB (0, 0, 0), start, end))
        preedit_attrs.append (ibus.AttributeForeground (ibus.RGB (255, 255, 128), start, end))
        preedit_attrs.append (ibus.AttributeBackground (ibus.RGB (255, 255, 128), end, length))
        preedit_attrs.append (ibus.AttributeForeground (ibus.RGB (0, 0, 0), end, length))
        super (ZimeEngine, self).update_preedit_text (ibus.Text (s, preedit_attrs), length, True)

    def update_aux_string (self, s):
        #print u'aux: [%s]' % s
        if not s:
            super (ZimeEngine, self).hide_auxiliary_text ()
            return
        super (ZimeEngine, self).update_auxiliary_text (ibus.Text (s), True)

    def update_candidates (self, candidates):
        self.__lookup_table.clean ()
        self.__lookup_table.show_cursor (False)
        if not candidates:
            self.hide_lookup_table ()
        else:
            for c in candidates:
                self.__lookup_table.append_candidate (ibus.Text (c[0]))
            self.update_lookup_table (self.__lookup_table, True, True)
    
    def page_up (self):
        if self.__lookup_table.page_up ():
            self.update_lookup_table (self.__lookup_table, True, True)
            return True
        return False

    def page_down (self):
        if self.__lookup_table.page_down ():
            self.update_lookup_table (self.__lookup_table, True, True)
            return True
        return False

    @classmethod
    def CONFIG_VALUE_CHANGED (cls, bus, section, name, value):
        config = bus.get_config ()
        if section != "engine/Zime":
            return

    @classmethod
    def CONFIG_RELOADED (cls, bus):
        config = bus.get_config ()

