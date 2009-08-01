# vim:set et sts=4 sw=4:

import ibus
import os
import zime

#from gettext import dgettext
#_  = lambda a : dgettext("ibus-zime", a)
_ = lambda a : a
N_ = lambda a : a


class EngineFactory(ibus.EngineFactoryBase):
    FACTORY_PATH = "/cn/ha/zz/sst/Zime/Factory"
    ENGINE_PATH = "/cn/ha/zz/sst/Zime/Engine"
    NAME = _("ZIME")
    LANG = "zh_TW"
    ICON = os.getenv("IBUS_ZIME_LOCATION") + "/icons/zhung.png"
    AUTHORS = "GONG Chen <chen.sst@gmail.com>"
    CREDITS = "GPLv3"

    def __init__(self, bus):
        self.__bus = bus
        zime.ZimeEngine.CONFIG_RELOADED(self.__bus)
        super(EngineFactory, self).__init__(bus)

        self.__id = 0
        self.__config = self.__bus.get_config()

        self.__config.connect("reloaded", self.__config_reloaded_cb)
        self.__config.connect("value-changed", self.__config_value_changed_cb)

    def create_engine(self, engine_name):
        if engine_name == "zime":
            self.__id += 1
            return zime.ZimeEngine(self.__bus, "%s/%d" % (self.ENGINE_PATH, self.__id))

        return super(EngineFactory, self).create_engine(engine_name)

    def __config_reloaded_cb(self, config):
        zime.ZimeEngine.CONFIG_RELOADED(self.__bus)

    def __config_value_changed_cb(self, config, section, name, value):
        zime.ZimeEngine.CONFIG_VALUE_CHANGED(self.__bus, section, name, value)

