#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ibus import keysyms
from ibus import modifier

from zimecore import *

class RomanParser (Parser):
    def __init__ (self, schema):
        Parser.__init__ (self, schema)
        self.__alphabet = schema.get_config_char_sequence (u'Alphabet') or \
            u'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
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
        self.__prompt_pattern = schema.get_config_char_sequence (u'PromptPattern') or u'%s\u203a'
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
            self.clear ()
            return None
        if event.keycode == keysyms.BackSpace:
            if ctx.is_empty ():
                return None
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
                    result = self.__prompt_pattern % u''.join (self.__slots)
                    return [result]
            # keyword disposed, go back
            if not ctx.is_empty () and ctx.input[-1] == self.__delimiter[0]:
                ctx.input.pop ()
            return []
        if event.keycode == keysyms.space:
            if self.__is_empty ():
                return None
            ctx.input.pop ()
            result = u''.join (self.__slots)
            self.clear ()
            return [result]
        # handle grouping input
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
        elif not ctx.is_empty () and ctx.input[-1] not in self.__delimiter:
            ctx.input.append (self.__delimiter[0]) 
        # update current keyword
        idx = self.__key_groups[k].index (ch)
        self.__slots[k] = self.__code_groups[k][idx]
        result = u''.join (self.__slots)
        k += 1
        if k >= self.__group_count:
            self.clear ()
            return [result]
        else:
            self.__cursor = k
            return [self.__prompt_pattern % result]

class ComboParser (Parser):
    def __init__ (self, schema):
        Parser.__init__ (self, schema)
        self.__delimiter = schema.get_config_char_sequence (u'Delimiter') or u' '
        self.__combo_keys = schema.get_config_char_sequence (u'ComboKeys') or u''
        self.__combo_codes = schema.get_config_char_sequence (u'ComboCodes') or u''
        self.__combo_max_length = min (len (self.__combo_keys), len (self.__combo_codes))
        self.__combo_space = schema.get_config_value (u'ComboSpace') or u'_'
        get_rules = lambda f, key: [f (r.split ()) for r in schema.get_config_list (key)]
        compile_repl_pattern = lambda x: (re.compile (x[0]), x[1])
        self.__xform_rules = get_rules (compile_repl_pattern, u'TransformRule')
        self.__combo = set ()
        self.__held = set ()
    def clear (self):
        self.__combo.clear ()
        self.__held.clear ()
    def __is_empty (self):
        return not bool (self.__held)
    def __commit_combo (self, ctx):
        k = self.__get_combo_string ()
        #print '__commit_combo', k
        self.clear ()
        ctx.input.pop ()
        if not ctx.is_empty () and ctx.input[-1] == self.__delimiter[0]:
            ctx.input.pop ()
        if k == self.__combo_space:
            ctx.edit (ctx.input)
            return KeyEvent (keysyms.space, 0, coined=True)
        else:
            if not k:
                return []
            if not ctx.is_empty ():
                ctx.input.append (self.__delimiter[0])
            return [k]
    def __get_combo_string (self):
        s = u''.join ([self.__combo_codes[i] for i in range (self.__combo_max_length) \
                                                 if self.__combo_keys[i] in self.__combo])
        xform = lambda s, r: r[0].sub (r[1], s, 1)
        return reduce (xform, self.__xform_rules, s)
    def process_input (self, event, ctx):
        if ctx.being_converted ():
            return None
        # handle combo input
        ch = event.get_char ()
        if event.mask & modifier.RELEASE_MASK:
            if ch in self.__held:
                #print 'released:', ch
                self.__held.remove (ch)
                if self.__is_empty ():
                    return self.__commit_combo (ctx)
            return None
        if ch in self.__combo_keys:
            #print 'pressed:', ch
            if not self.__is_empty ():
                ctx.input.pop ()
            elif not ctx.is_empty () and ctx.input[-1] != self.__delimiter[0]:
                ctx.input.append (self.__delimiter[0])
            self.__combo.add (ch)
            self.__held.add (ch)
            return [self.__get_combo_string ()]
        # edit keys
        if event.keycode == keysyms.Escape:
            self.clear ()
            return None
        if event.keycode == keysyms.BackSpace:
            if ctx.is_empty ():
                return None
            ctx.input.pop ()
            if not ctx.is_empty () and ctx.input[-1] == self.__delimiter[0]:
                ctx.input.pop ()
            return []
        return None

def register_parsers ():
    Parser.register ('roman', RomanParser)
    Parser.register ('grouping', GroupingParser)
    Parser.register ('combo', ComboParser)

