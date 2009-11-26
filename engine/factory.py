# vim:set et sts=4 sw=4:

import ibus
import os
import zime

#from gettext import dgettext
#_  = lambda a : dgettext ("ibus-zime", a)
_ = lambda a : a
N_ = lambda a : a

def get_zime_engine_module (engine_name):
    if engine_name == "stylo":
        from stylo import zimeengine
        return zimeengine
    if engine_name == "plume":
        from plume import zimeengine
        return zimeengine
    return None

class EngineFactory (ibus.EngineFactoryBase):
    FACTORY_PATH = "/cn/ha/zz/sst/Zime/Factory"
    ENGINE_PATH = "/cn/ha/zz/sst/Zime/Engine"
    NAME = _ ("ZIME")
    LANG = "zh_TW"
    ICON = os.getenv ("IBUS_ZIME_LOCATION") + "/icons/zhung.png"
    AUTHORS = "GONG Chen <chen.sst@gmail.com>"
    CREDITS = "GPLv3"

    def __init__ (self, bus):
        self.__bus = bus
        zime.ZimeEngine.CONFIG_RELOADED (self.__bus)
        super (EngineFactory, self).__init__ (bus)

        self.__id = 0
        self.__config = self.__bus.get_config ()

        self.__config.connect ("reloaded", self.__config_reloaded_cb)
        self.__config.connect ("value-changed", self.__config_value_changed_cb)

    def create_engine (self, engine_name):
        module = get_zime_engine_module (engine_name)
        if module:
            self.__id += 1
            return zime.ZimeEngine (self.__bus, "%s/%d" % (self.ENGINE_PATH, self.__id), module)
        return super (EngineFactory, self).create_engine (engine_name)

    def __config_reloaded_cb (self, config):
        zime.ZimeEngine.CONFIG_RELOADED (self.__bus)

    def __config_value_changed_cb (self, config, section, name, value):
        zime.ZimeEngine.self.CONFIG_VALUE_CHANGED (__bus, section, name, value)

