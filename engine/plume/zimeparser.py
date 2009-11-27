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

def register_parsers ():
    Parser.register ('roman', RomanParser)
    #Parser.register ('combo', ComboParser)
    #Parser.register ('grouping', GroupingParser)

