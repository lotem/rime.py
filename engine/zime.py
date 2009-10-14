# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

__all__ = (
    "ZimeEngine",
)

import ibus
import gobject

from stylo import zimecore
from stylo import zimeparser

#from gettext import dgettext
#_  = lambda a : dgettext ("ibus-zime", a)
_ = lambda a : a
N_ = lambda a : a


class ZimeEngine (ibus.EngineBase):

    def __init__ (self, conn, object_path):
        super (ZimeEngine, self).__init__ (conn, object_path)
        # TODO
        self.__engine = zimecore.Engine (self, 'zhuyin')

    def process_key_event (self, keycode, mask):
        return self.__engine.process_key_event (zimecore.KeyEvent (keycode, mask))

    def commit_string (self, s):
        #print u'commit: [%s]' % s
        super (ZimeEngine, self).commit_text (ibus.Text (s))

    def update_preedit (self, s):
        #print u'preedit: [%s]' % s
        if not s:
            super (ZimeEngine, self).hide_preedit_text ()
            return
        preedit_attrs = ibus.AttrList ()
        attr = ibus.AttributeUnderline (ibus.ATTR_UNDERLINE_SINGLE, 0, len (s))
        preedit_attrs.append (attr)
        super (ZimeEngine, self).update_preedit_text (ibus.Text (s, preedit_attrs), len (s), True)

    def update_aux_string (self, s):
        #print u'aux: [%s]' % s
        if not s:
            super (ZimeEngine, self).hide_auxiliary_text ()
            return
        super (ZimeEngine, self).update_auxiliary_text (ibus.Text (s), True)

    def update_lookup_table (self, lookup_table):
        pass

    @classmethod
    def CONFIG_VALUE_CHANGED (cls, bus, section, name, value):
        config = bus.get_config ()
        if section != "engine/Zime":
            return

    @classmethod
    def CONFIG_RELOADED (cls, bus):
        config = bus.get_config ()

