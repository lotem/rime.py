#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ibus import keysyms
from ibus import modifier

from zimecore import *

class RomanParser (Parser):
    def __init__ (self, schema):
        Parser.__init__ (self, schema)
        self.__alphabet = schema.get_config_char_sequence (u'Alphabet') or u'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
    def clear (self):
        pass
    def process_input (self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return None
        if event.keycode == keysyms.space:
            return None
        ch = event.get_char ()
        if ch in self.__alphabet or not ctx.is_empty () and ch in self.__delimiter:
            return [ch]
        return None

class GroupingParser (Parser):
    def __init__ (self, schema):
        Parser.__init__ (self, schema)
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
        self.__key_groups = schema.get_config_value (u'KeyGroups').split ()
        self.__code_groups = schema.get_config_value (u'CodeGroups').split ()
        self.__group_count = len (self.__key_groups)
        self.clear ()
    def clear (self):
        self.__slots = [u''] * self.__group_count
        self.__cursor = 0
    def __is_empty (self):
        return not any (self.__slots)
    def process_input (self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return None
        if ctx.being_converted ():
            return None
        if event.keycode == keysyms.Escape:
            return None
        if event.keycode == keysyms.BackSpace:
            ctx.input.pop ()
            if not self.__is_empty ():
                # delete last one symbol from current keyword
                j = self.__group_count - 1
                while j > 0 and not self.__slots[j]:
                    j -= 1
                self.__slots[j] = u''
                while j > 0 and not self.__slots[j]:
                    j -= 1
                self.__cursor = j
                if not self.__is_empty ():
                    # update keyword
                    result = u''.join (self.__slots)
                    return [result]
            # keyword disposed, go back
            if not ctx.is_empty () and ctx.input[-1] == self.__delimiter[0]:
                ctx.input.pop ()
            return []
        if event.keycode == keysyms.space:
            if self.__is_empty ():
                return None
            self.clear ()
            return []
        # handle input
        ch = event.get_char ()
        k = self.__cursor
        while ch not in self.__key_groups[k]:
            k += 1
            if k >= self.__group_count:
                k = 0
            if k == self.__cursor:
                if self.__is_empty ():
                    return None
                else:
                    return []
        # update input
        if not self.__is_empty ():
            ctx.input.pop ()
        elif not ctx.is_empty ():
            ctx.input.append (self.__delimiter[0])
        # update current keyword
        idx = self.__key_groups[k].index (ch)
        self.__slots[k] = self.__code_groups[k][idx]
        result = u''.join (self.__slots)
        k += 1
        if k >= self.__group_count:
            self.clear ()
        else:
            self.__cursor = k
        return [result]

def register_parsers ():
    Parser.register ('roman', RomanParser)
    #Parser.register ('combo', ComboParser)
    Parser.register ('grouping', GroupingParser)

