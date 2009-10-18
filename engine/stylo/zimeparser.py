#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ibus import keysyms
from ibus import modifier

from zimecore import *

class RomanParser (Parser):
    def __init__ (self, schema):
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
        self.__input = []
    def process (self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return True
        if event.keycode == keysyms.BackSpace:
            if self.__is_empty ():
                return False
            # TODO
            return True
        if event.keycode in (keysyms.space, keysyms.Return):
            return False
        # TODO
        return True

class ComboParser (Parser):
    IN_PLACE_PROMPT = 1

class GroupingParser (Parser):
    IN_PLACE_PROMPT = 1
    def __init__ (self, schema):
        self.__key_groups = schema.get_config_value (u'KeyGroups').split ()
        self.__code_groups = schema.get_config_value (u'CodeGroups').split ()
        self.__group_count = len (self.__key_groups)
        self.clear ()
    def clear (self):
        self.__slots = [u''] * self.__group_count
        self.__cursor = 0
    def process (self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return True
        if event.keycode == keysyms.BackSpace:
            if self.__is_empty ():
                return False
            j = self.__group_count - 1
            while j > 0 and not self.__slots[j]:
                j -= 1
            self.__slots[j] = u''
            while j > 0 and not self.__slots[j]:
                j -= 1
            self.__cursor = j
            ctx.keywords[-1] = u''.join (self.__slots)
            ctx.update_keywords ()
            return True
        if ctx.cursor < len (ctx.keywords) - 1:
            return False
        if event.keycode == keysyms.space:
            if self.__is_empty ():
                return False
            self.clear ()
            ctx.keywords.append (u'')
            ctx.update_keywords ()
            return True
        ch = event.get_char ()
        k = self.__cursor
        while ch not in self.__key_groups[k]:
            k += 1
            if k >= self.__group_count:
                k = 0
            if k == self.__cursor:
                return not self.__is_empty ()
        idx = self.__key_groups[k].index (ch)
        self.__slots[k] = self.__code_groups[k][idx]
        ctx.keywords[-1] = u''.join (self.__slots)
        k += 1
        if k >= self.__group_count:
            self.clear ()
            ctx.keywords.append (u'')
        else:
            self.__cursor = k
        ctx.update_keywords ()
        return True
    def __is_empty (self):
        return not any (self.__slots)

def register_parsers ():
    Parser.register ('roman', RomanParser)
    Parser.register ('combo', ComboParser)
    Parser.register ('grouping', GroupingParser)

