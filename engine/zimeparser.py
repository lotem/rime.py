#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ibus import keysyms
from ibus import modifier

from zimecore import *

class RomanParser(Parser):
    def __init__(self, schema):
        Parser.__init__(self, schema)
        self.clear()
    def clear(self):
        self.__input = []
        self.prompt = u''
    def is_empty(self):
        return not bool(self.__input)
    def __get_input(self):
        if self.xform_rules:
            # apply transform rules
            s = self.xform(u''.join(self.__input))
            return list(s)
        else:
            return self.__input[:]
    def process_input(self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return False
        if self.prompt:
            return self.process_raw_mode(event)
        # disable input in conversion mode
        if not self.auto_prompt and ctx.being_converted():
            return False
        # normal mode
        if event.keycode == keysyms.Escape:
            self.clear()
            if ctx.has_error():
                ctx.edit([])
                return True
            return False
        if event.keycode == keysyms.BackSpace:
            if self.is_empty():
                return False
            self.__input.pop()
            ctx.input = self.__get_input()
            return []
        if event.keycode == keysyms.space:
            return False
        ch = event.get_char()
        if self.is_empty() and ch in self.initial or \
           not self.is_empty() and (ch in self.alphabet or ch in self.delimiter):
            self.__input.append(ch)
            ctx.input = self.__get_input()
            return []
        if self.is_empty() and self.initial_acceptable(ch):
            return self.start_raw_mode(ch)
        # unused
        return False

class TableParser(Parser):
    def __init__(self, schema):
        Parser.__init__(self, schema)
        self.__max_keyword_length = int(schema.get_config_value(u'MaxKeywordLength') or u'7')
        self.clear()
    def clear(self):
        self.__input = []
        self.prompt = u''
    def is_empty(self):
        return len(self.__input) == 0
    def __auto_commit(self):
        complete = len(self.__input) == self.__max_keyword_length
        if complete:
            self.clear()
        return complete
    def __get_keyword(self):
        if self.xform_rules:
            # apply transform rules
            return self.xform(u''.join(self.__input))
        else:
            return u''.join(self.__input)
    def process_input(self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return False
        if self.prompt:
            return self.process_raw_mode(event)
        # disable input in conversion mode
        if not self.auto_prompt and ctx.being_converted():
            return False
        # normal mode
        if event.keycode == keysyms.Escape:
            self.clear()
            return False
        if event.keycode == keysyms.Return:
            self.clear()
            return False
        if event.keycode == keysyms.space:
            self.clear()
            return False
        if event.keycode == keysyms.BackSpace:
            if self.is_empty():
                return False
            self.__input.pop()
            if not self.is_empty():
                ctx.input[-1] = self.__get_keyword()
            else:
                ctx.pop_input()
            return []
        ch = event.get_char()
        # finish current keyword
        if not ctx.is_empty() and ch in self.delimiter:
            self.clear()
            return [self.delimiter[0]]
        if ch in self.initial:
            # auto-commit keywords with max keyword length
            self.__auto_commit()
            # start a new keyword
            if self.is_empty():
                self.__input.append(ch)
                result = []
                if not ctx.is_empty() and ctx.input[-1] != self.delimiter[0]:
                    result.append(self.delimiter[0])
                result.append(self.__get_keyword())
                return result
        if not self.is_empty():
            # continue current keyword
            if ch in self.alphabet:
                self.__input.append(ch)
                ctx.input[-1] = self.__get_keyword()
                return []
        # start raw mode
        if self.is_empty() and self.initial_acceptable(ch):
            return self.start_raw_mode(ch)
        # unused
        return False

class GroupingParser(Parser):
    def __init__(self, schema):
        Parser.__init__(self, schema)
        self.__prompt_pattern = schema.get_config_char_sequence(u'PromptPattern') or u'%s\u203a'
        self.__key_groups = schema.get_config_value(u'KeyGroups').split()
        self.__code_groups = schema.get_config_value(u'CodeGroups').split()
        self.__group_count = len(self.__key_groups)
        self.clear()
    def clear(self):
        self.__slots = [u''] * self.__group_count
        self.__cursor = 0
    def is_empty(self):
        return not any(self.__slots)
    def __get_prompt(self, first):
        text = self.__prompt_pattern % u''.join(self.__slots)
        padding = None if first or self.auto_predict else self.delimiter[0]
        return Prompt(text, padding=padding)
    def process_input(self, event, ctx):
        if event.mask & modifier.RELEASE_MASK:
            return False
        if not self.auto_prompt and ctx.being_converted():
            return False
        if event.keycode == keysyms.Escape:
            self.clear()
            return False
        if event.keycode == keysyms.BackSpace:
            if self.is_empty():
                return False
            # delete last one symbol from current keyword
            j = self.__group_count - 1
            while j > 0 and not self.__slots[j]:
                j -= 1
            self.__slots[j] = u''
            while j > 0 and not self.__slots[j]:
                j -= 1
            self.__cursor = j
            if not self.is_empty():
                # update prompt
                return self.__get_prompt(ctx.is_empty())
            else:
                # keyword disposed
                self.clear()
                return Prompt()
        if event.keycode == keysyms.space:
            if self.is_empty():
                return False
            result = u''.join(self.__slots)
            self.clear()
            return [result] if ctx.is_empty() else [self.delimiter[0], result]
        # handle grouping input
        ch = event.get_char()
        k = self.__cursor
        while ch not in self.__key_groups[k]:
            k += 1
            if k >= self.__group_count:
                k = 0
            if k == self.__cursor:
                if self.is_empty():
                    return False
                else:
                    return True
        # update current keyword
        idx = self.__key_groups[k].index(ch)
        self.__slots[k] = self.__code_groups[k][idx]
        k += 1
        if k >= self.__group_count:
            keyword = u''.join(self.__slots)
            self.clear()
            return [keyword] if ctx.is_empty() else [self.delimiter[0], keyword]
        else:
            self.__cursor = k
            return self.__get_prompt(ctx.is_empty())

class ComboParser(Parser):
    def __init__(self, schema):
        Parser.__init__(self, schema)
        self.__prompt_pattern = schema.get_config_char_sequence(u'PromptPattern') or u'%s\u203a'
        self.__combo_keys = schema.get_config_char_sequence(u'ComboKeys') or u''
        self.__combo_codes = schema.get_config_char_sequence(u'ComboCodes') or u''
        self.__combo_max_length = min(len(self.__combo_keys), len(self.__combo_codes))
        self.__combo_space = schema.get_config_value(u'ComboSpace') or u'_'
        self.__combo = set()
        self.__held = set()
    def clear(self):
        self.__combo.clear()
        self.__held.clear()
    def is_empty(self):
        return not bool(self.__held)
    def __get_prompt(self, first):
        text = self.__prompt_pattern % self.__get_combo_string()
        padding = None if first or self.auto_predict else self.delimiter[0]
        return Prompt(text, padding=padding)
    def __commit_combo(self, first):
        k = self.__get_combo_string()
        self.clear()
        #print '__commit_combo', k
        if k == self.__combo_space:
            return KeyEvent(keysyms.space, 0, coined=True)
        elif not k:
            return Prompt()
        else:
            return [k] if first else [self.delimiter[0], k]
    def __get_combo_string(self):
        s = u''.join([self.__combo_codes[i] for i in range(self.__combo_max_length) \
                                                 if self.__combo_keys[i] in self.__combo])
        return self.xform(s)
    def process_input(self, event, ctx):
        # handle combo input
        ch = event.get_char()
        if event.mask & modifier.RELEASE_MASK:
            if ch in self.__held:
                #print 'released:', ch
                self.__held.remove(ch)
                if self.is_empty():
                    return self.__commit_combo(ctx.is_empty())
                return True
            return False
        if ch in self.__combo_keys:
            #print 'pressed:', ch
            self.__combo.add(ch)
            self.__held.add(ch)
            return self.__get_prompt(ctx.is_empty())
        # non-combo keys
        if not self.is_empty():
            self.clear()
            return Prompt()
        return False

def register_parsers():
    Parser.register('roman', RomanParser)
    Parser.register('table', TableParser)
    Parser.register('grouping', GroupingParser)
    Parser.register('combo', ComboParser)

