# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

__all__ = (
    "ZimeEngine",
)

import ibus
import gobject
import os
import os.path as path
from ibus import keysyms
from ibus import modifier
from ibus import ascii

#from gettext import dgettext
#_  = lambda a : dgettext("ibus-zime", a)
_ = lambda a : a
N_ = lambda a : a

IBUS_ZIME_LOCATION = os.getenv("IBUS_ZIME_LOCATION")


class ZimeEngine(ibus.EngineBase):

    def __init__(self, conn, object_path):
        super(ZimeEngine, self).__init__(conn, object_path)

    def process_key_event(self, keyval, state):
        return False

    @classmethod
    def CONFIG_VALUE_CHANGED(cls, bus, section, name, value):
        config = bus.get_config()
        if section != "engine/Zime":
            return

    @classmethod
    def CONFIG_RELOADED(cls, bus):
        config = bus.get_config()

