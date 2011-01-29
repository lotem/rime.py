# vim:set et sts=4 sw=4:

import ibus
import os
from rhyme import RhymeSession

#from gettext import dgettext
#_  = lambda a : dgettext("ibus-rhyme", a)
_ = lambda a : a
N_ = lambda a : a

class EngineFactory(ibus.EngineFactoryBase):
    FACTORY_PATH = "/cn/zzsst/zime/Rhyme/Factory"
    ENGINE_PATH = "/cn/zzsst/zime/Rhyme/Engine"
    NAME = _("Rhyme")
    LANG = "zh_CN"
    ICON = os.getenv("IBUS_RHYME_LOCATION") + "/icons/zhung.png"
    AUTHORS = "GONG Chen <chen.sst@gmail.com>"
    CREDITS = "GPLv3"

    def __init__(self, bus):
        self.__bus = bus
        super(EngineFactory, self).__init__(bus)

        self.__id = 0
        self.__config = self.__bus.get_config()

        self.__config.connect("reloaded", self.__config_reloaded_cb)
        self.__config.connect("value-changed", self.__config_value_changed_cb)

    def create_engine(self, engine_name):
        if engine_name == "rhyme":
            self.__id += 1
            return RhymeSession(self.__bus, "%s/%d" % (self.ENGINE_PATH, self.__id))
        return super(EngineFactory, self).create_engine(engine_name)

    def __config_reloaded_cb(self, config):
        pass

    def __config_value_changed_cb(self, config, section, name, value):
        pass

