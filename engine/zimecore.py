#!/usr/bin/env python

from ibus import keysyms
from ibus import modifier

from zimedb import DB
from zimemodel import *

class KeyEvent:
    def __init__(self, keycode, mask, coined=False):
        self.keycode = keycode
        self.mask = mask
        self.coined = coined
    def get_char(self):
        return unichr(self.keycode)
    def __str__(self):
        return "<KeyEvent: '%s'(%x), %08x>" % (keysyms.keycode_to_name(self.keycode), self.keycode, self.mask)

class Prompt:
    def __init__(self, text=None, start=0, end=0, padding=None):
        if text and not end:
            end = len(text)
        if text and padding:
            self.text = padding + text
            self.start = len(padding) + start
            self.end = len(padding) + end
        else:
            self.text = text
            self.start = start
            self.end = end
    def is_empty(self):
        return not self.text

class Commit(unicode):
    pass

class Schema:
    def __init__(self, name):
        self.__name = name
        self.__db = DB(name)
        self.__parser_name = self.__db.read_config_value(u'Parser')
    def get_name(self):
        return self.__name
    def get_db(self):
        return self.__db
    def get_parser_name(self):
        return self.__parser_name
    def get_config_value(self, key):
        return self.__db.read_config_value(key)
    def get_config_char_sequence(self, key):
        r = self.__db.read_config_value(key)
        if r and r.startswith(u'[') and r.endswith(u']'):
            return r[1:-1]
        return r
    def get_config_list(self, key):
        return self.__db.read_config_list(key)

class Parser:
    __parsers = dict()
    @classmethod
    def register(cls, name, parser_class):
        cls.__parsers[name] = parser_class
    @classmethod
    def get_parser_class(cls, parser_name):
        return cls.__parsers[parser_name]
    @classmethod
    def create(cls, schema):
        return cls.get_parser_class(schema.get_parser_name()) (schema)
    def __init__(self, schema):
        self.__schema = schema
        self.auto_prompt = schema.get_config_value(u'AutoPrompt') in (u'yes', u'true')
        self.auto_predict = schema.get_config_value(u'Predict') in (None, u'yes', u'true')
        self.alphabet = schema.get_config_char_sequence(u'Alphabet') or u'abcdefghijklmnopqrstuvwxyz'
        self.initial = self.alphabet.split(None, 1)[0]
        self.delimiter = schema.get_config_char_sequence(u'Delimiter') or u' '
        self.quote = schema.get_config_char_sequence('Quote') or u'`'
        acc = (schema.get_config_char_sequence('Acceptable') or \
               u'''ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
                   0123456789!@#$%^&*()`~-_=+[{]}\\|;:'",<.>/?''').split(None, 1)
        self.acceptable = lambda x: x == u' ' or any([x in s for s in acc])
        self.initial_acceptable = lambda x: x in self.quote or x in acc[0]
        get_rules = lambda f, key: [f(r.split()) for r in schema.get_config_list(key)]
        compile_repl_pattern = lambda x: (re.compile(x[0]), x[1])
        transform = lambda s, r: r[0].sub(r[1], s)
        self.xform_rules = get_rules(compile_repl_pattern, u'TransformRule')
        self.xform = lambda s: reduce(transform, self.xform_rules, s)
        punct_mapping = lambda(x, y): (x, (0, y.split(u' ')) if u' ' in y else \
                                           (2, y.split(u'~', 1)) if u'~' in y else \
                                           (1, y))
        self.__punct = dict([punct_mapping(c.split(None, 1)) for c in schema.get_config_list(u'Punct')])
        key_mapping = lambda(x, y): (keysyms.name_to_keycode(x), keysyms.name_to_keycode(y))
        self.__edit_keys = dict([key_mapping(c.split(None, 1)) for c in schema.get_config_list(u'EditKey')])
        self.prompt = u''
    def get_schema(self):
        return self.__schema
    def start_raw_mode(self, ch):
        self.prompt = ch
        return Prompt(self.prompt)
    def process_raw_mode(self, event):
        p = self.prompt
        ch = event.get_char()
        if event.keycode == keysyms.Return:
            if len(p) > 1 and p[0] in self.quote:
                return Commit(p[1:]) 
            else:
                return Commit(p)
        if event.keycode == keysyms.Escape:
            self.clear()
            return Prompt()
        if event.keycode == keysyms.BackSpace:
            self.prompt = p[:-1]
            return Prompt(self.prompt)
        if ch in self.quote and p[0] in self.quote:
            return Commit(p + ch)
        if self.acceptable(ch):
            self.prompt += ch
            return Prompt(self.prompt)
        return True
    def check_punct(self, event):
        ch = event.get_char()
        if ch in self.__punct:
            if event.mask & modifier.RELEASE_MASK:
                return True, None
            p = self.__punct[ch]
            if p[0] == 1:
                return True, p[1]
            elif p[0] == 2:
                x = p[1][0]
                p[1].reverse()
                return True, x
            else:
                return True, p[1]
        return False, None
    def check_edit_key(self, event):
        if not event.coined and event.keycode in self.__edit_keys:
            return KeyEvent(self.__edit_keys[event.keycode], 0, coined=True)
        return None

class Context:
    def __init__(self, callback, schema):
        self.__cb = callback
        self.__model = Model(schema)
        #self.schema = schema
        self.__delimiter = schema.get_config_char_sequence(u'Delimiter') or u' '
        self.__auto_delimit = schema.get_config_value(u'AutoDelimit') in (u'yes', u'true')
        self.__auto_predict = schema.get_config_value(u'Predict') in (None, u'yes', u'true')
        prompt_char = schema.get_config_char_sequence(u'PromptChar')
        if prompt_char:
            alphabet = schema.get_config_char_sequence(u'Alphabet') or u'abcdefghijklmnopqrstuvwxyz'
            xlit = dict(zip(list(alphabet), list(prompt_char)))
            self.__translit = lambda s: u''.join([xlit[c] if c in xlit else c for c in s])
        else:
            self.__translit = None
        self.__reset()
    def __reset(self, keep_context=False):
        self.input = []
        self.err = None
        self.cur = []
        if not keep_context:
            self.sel = []
            self.confirmed = 0
            self.info = self.__model.create_context_info()
        self.__candidates = []
        self.__display = (u'', [0])
    def clear(self):
        self.__reset()
        self.__cb.update_ui()
    def is_empty(self):
        return not self.input
    def pop_input(self, till=-1):
        if till == -1:
            till = max(0, len(self.input) - 1)
        while len(self.input) > till:
            self.input.pop()
            if self.input and self.input[-1] == self.__delimiter[0]:
                self.input.pop()
    def commit(self):
        if self.is_completed():
            self.__model.train(self, self.sel + self.cur)
            self.edit([])
        else:
            self.clear()
    def edit(self, input, start_conversion=False):
        self.__reset(keep_context=True)
        self.input = input
        if input:
            self.__model.query(self)
            m, n = self.info.m, self.info.n
            self.__calculate_display_string(input, self.info.d, n, m)
            if m != n:
                self.err = Entry(None, m, n)
            elif start_conversion:
                self.__update_candidates(self.__predict(exclude_the_last=True))
                return
            if self.__auto_predict:
                self.__predict()
        self.__cb.update_ui()
    def has_error(self):
        return self.err is not None
    def cancel_conversion(self):
        self.edit(self.input)
    def __predict(self, exclude_the_last=False):
        i = self.sel[-1].j if self.sel else (-1 if self.info.last else 0)
        p = (self.sel[-1].next if self.sel else None) or self.info.pred[i]
        while p:
            s = p.get_all()
            if s[0].i < 0:
                del s[0]
            if s:
                p = s[-1]
                if exclude_the_last and p.j == self.info.m:
                    break
                self.sel.extend(s)
            i = p.j
            p = self.info.pred[i]
        return max(0, i)
    def home(self):
        if not self.being_converted():
            return False
        self.sel = []
        self.confirmed = 0
        self.__update_candidates(0)
        return True
    def end(self, start_conversion=False):
        if not self.being_converted():
            if not start_conversion or self.has_error():
                return False
            # do a fresh new prediction in case of a full prediction is present
            self.sel = []
            self.confirmed = 0
        self.__update_candidates(self.__predict(exclude_the_last=True))
    def left(self):
        if not self.being_converted():
            return
        i = self.cur[0].i
        j = self.cur[-1].j
        for k in range(j - 1, i, -1):
            if self.info.cand[i][k] or self.info.fraz[i][k]:
                self.__update_candidates(i, k)
                return
        self.back()
    def right(self):
        if not self.being_converted():
            return
        i = self.cur[0].i
        j = self.cur[-1].j
        for k in range(j + 1, self.info.m + 1):
            if self.info.cand[i][k] or self.info.fraz[i][k]:
                self.__update_candidates(i, k)
                return
        self.forth()
    def back(self):
        if not self.being_converted():
            return False
        if self.sel:
            e = self.sel.pop()
            self.confirmed = min(self.confirmed, len(self.sel))
            self.__update_candidates(e.i)
            return True
        return False
    def forth(self):
        if not self.being_converted():
            return False
        i = self.cur[0].i
        p = (self.sel[-1].next if self.sel else None) or self.info.pred[i]
        if p and p.j < self.info.m:
            self.sel.append(p)
            i = p.j
            j = 0
            for k in range(i + 1, self.info.m + 1):
                if self.info.cand[i][k] or self.info.fraz[i][k]:
                    j = k
                    break
            self.__update_candidates(i, j)
            return True
        return False
    def forward(self):
        c = self.cur
        if c:
            self.sel.extend(c)
            self.confirmed = len(self.sel)
            self.__update_candidates(c[-1].j)
    def __update_candidates(self, i, j=0):
        #print '__update_candidates:', i, j
        self.__candidates = self.__model.make_candidate_list(self, i, j)
        if self.__candidates:
            self.cur = self.__candidates[0][1].get_all()
        else:
            err_pos = self.cur[-1].i if self.cur else 0
            self.err = Entry(None, err_pos, len(self.input))
            self.cur = []
        self.__cb.update_ui()
    def select(self, e):
        self.cur = e.get_all()
    def being_converted(self):
        return bool(self.cur)
    def is_completed(self):
        return self.cur and self.cur[-1].j == len(self.input)
    def __calculate_display_string(self, s, d, n, m):
        if n == 0:
            return
        t = [0 for i in range(n + 1)]
        p = []
        c = 0
        for i in range(n):
            if self.__auto_delimit and i > 0 and i in d and s[i - 1] not in self.__delimiter:
                p.append(self.__delimiter[0])
                c += 1
            t[i] = c
            w = self.__translit(s[i]) if self.__translit else s[i]
            p.append(w)
            c += len(w)
        t[-1] = c
        self.__display = (u''.join(p), t)
    def get_preedit(self):
        if self.is_empty():
            return u'', 0, 0
        r = []
        rest = 0
        start = 0
        for s in self.sel:
            w = s.get_word()
            r.append(w)
            start += len(w)
            rest = s.j
        end = start
        for s in self.cur:
            w = s.get_word()
            r.append(w)
            end += len(w)
            rest = s.j
        if rest < self.info.n:
            s, t = self.__display
            r.append(s[t[rest]:])
            if self.has_error():
                diff = t[rest] - end
                start, end = t[self.err.i] - diff, t[self.err.j] - diff
        return u''.join(r), start, end
    def get_commit_string(self):
        i = 0
        r = []
        for s in self.sel + self.cur:
            r.append(s.get_word())
            i = s.j
        if i < len(self.input):
            s, t = self.__display
            r.append(s[t[i]:])
        return u''.join(r)
    def get_input_string(self):
        return u''.join(self.input)
    def get_aux_string(self):
        c = self.cur
        if c:
            s, t = self.__display
            # return the corresponding part of display string without trailing space
            return s[t[c[0].i]:t[c[-1].j]].rstrip()
        return u''
    def get_candidates(self):
        return self.__candidates
    def delete_phrase(self, e):
        pass

