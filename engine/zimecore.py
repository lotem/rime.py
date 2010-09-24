# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

from ibus import keysyms
from ibus import modifier

from zimedb import DB
from zimemodel import *

class KeyEvent:
    '''
    鍵盤事件
    按ibus／GNOME對鍵值的定義，keycode與字符對應而非與按鍵對應，即區分A與a
    mask含各種功能鍵狀態及按鍵的RELEASE狀態
    coined，是否偽造的按鍵，有時會在程序裡產生不同於實際輸入的鍵盤事件以模擬某個功能
    '''
    def __init__(self, keycode, mask, coined=False):
        self.keycode = keycode
        self.mask = mask
        self.coined = coined

    def get_char(self):
        return unichr(self.keycode)

    def __str__(self):
        return "<KeyEvent: '%s'(%x), %08x>" % (keysyms.keycode_to_name(self.keycode), self.keycode, self.mask)

class Prompt:
    '''
    編碼提示，在寫作串preedit內高亮顯示正在編輯的編碼／標點符號
    其文字內容不記入已輸入編碼中因此也不做轉換，例如未完成的注音音節
    '''
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
    '''由Engine發出的一個上屏動作'''
    pass

class Schema:
    '''輸入方案對象'''
    def __init__(self, name):
        self.__name = name
        self.__db = DB(name)
        self.__parser_name = self.__db.read_config_value(u'Parser')

    def get_name(self):
        '''取得輸入方案的內部名稱'''
        return self.__name

    def get_db(self):
        return self.__db

    def get_parser_name(self):
        return self.__parser_name

    def get_config_value(self, key):
        '''取單一設定值'''
        return self.__db.read_config_value(key)

    def get_config_char_sequence(self, key):
        '''
        讀字符序列設定
        可將字符序列寫在[]內以包含空白字符
        '''
        r = self.__db.read_config_value(key)
        if r and r.startswith(u'[') and r.endswith(u']'):
            return r[1:-1]
        return r

    def get_config_list(self, key):
        '''取多個設定值'''
        return self.__db.read_config_list(key)

class Parser:
    '''Parser基類'''

    '''註冊工廠方法用'''
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
        # 從Schema中讀取Parser會用到的一些設定值
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
        # 初始化一個Prompt對象
        self.prompt = u''

    def get_schema(self):
        return self.__schema

    def start_raw_mode(self, ch):
        '''
        進入西文模式
        ch為進入西文模式的前導編碼
        用Prompt來表現西文模式下的輸入串（反白顯示且不作為編碼輸入）
        '''
        self.prompt = ch
        return Prompt(self.prompt)

    def process_raw_mode(self, event):
        '''處理西文模式下的輸入'''
        p = self.prompt
        ch = event.get_char()
        if event.keycode == keysyms.Return:
            if len(p) > 1 and p[0] in self.quote:
                # 以quote做前導的西文，上屏時不包含quote
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
            # 成對的quote與引文一同上屏
            return Commit(p + ch)
        if self.acceptable(ch):
            self.prompt += ch
            return Prompt(self.prompt)
        return True

    def check_punct(self, event):
        '''
        判斷給定的鍵盤事件是否標點輸入
        結果中包含查表所得的標點符號
        '''
        ch = event.get_char()
        if ch in self.__punct:
            if event.mask & modifier.RELEASE_MASK:
                return True, None
            p = self.__punct[ch]
            if p[0] == 1:
                # 唯一的標點，直接上屏
                return True, p[1]
            elif p[0] == 2:
                # 成對使用的標號，如以"輸入“”，前後引交替著出
                x = p[1][0]
                p[1].reverse()
                return True, x
            else:
                # 一鍵表示多種標點，反覆按鍵輪循
                return True, p[1]
        return False, None

    def check_edit_key(self, event):
        '''
        檢查給定的鍵盤事件是否自定義編輯功能鍵
        若擊自定義編輯鍵，會返回一個偽造的等效預設編輯鍵
        '''
        if not event.coined and event.keycode in self.__edit_keys:
            return KeyEvent(self.__edit_keys[event.keycode], 0, coined=event)
        return None

class Context:
    '''
    輸入上下文
    '''
    # TODO: 下次重構，細分為保存寫作狀態的Context對象，和實現各種編輯操作的Editor

    def __init__(self, callback, schema):
        # 上下文更新後通過callback反饋給前端
        self.__cb = callback
        # Context調用Model完成輸入串到預測結果的轉換，並取得所有相關候選詞
        self.__model = Model(schema)
        #self.schema = schema
        # 以下讀取Context關心的設定值
        self.__delimiter = schema.get_config_char_sequence(u'Delimiter') or u' '
        self.__auto_delimit = schema.get_config_value(u'AutoDelimit') in (u'yes', u'true')
        self.__auto_prompt = schema.get_config_value(u'AutoPrompt') in (u'yes', u'true')
        self.__aux_length = int(schema.get_config_value(u'AuxLength') or 20)
        self.__auto_predict = schema.get_config_value(u'Predict') in (None, u'yes', u'true')
        prompt_char = schema.get_config_char_sequence(u'PromptChar')
        if prompt_char:
            alphabet = schema.get_config_char_sequence(u'Alphabet') or u'abcdefghijklmnopqrstuvwxyz'
            xlit = dict(zip(list(alphabet), list(prompt_char)))
            self.__translit = lambda s: u''.join([xlit[c] if c in xlit else c for c in s])
        else:
            self.__translit = None
        # 置為初始狀態
        self.__reset()

    def __reset(self, keep_context=False):
        # 輸入串，可以是字符序列（如在羅馬字解析方式下）或音節編碼的序列
        self.input = []
        # 錯誤狀態，非空時為一個Entry對象標記輸入串中輸入出錯的位置
        self.err = None
        # 當前候選詞，可能是多個單詞組成的詞組
        self.cur = []
        if not keep_context:
            # 清除手工編輯狀態
            self.sel = []
            self.confirmed = 0
            # 這個結構中保存的信息是詞庫查詢結果和由語言模型生成的轉換狀態，可用於增量計算
            self.info = self.__model.create_context_info()
        # 候選列表
        self.__candidates = []
        # 輸入串的介面展現形式，譬如字母變鍵名、音節自動添加隔音符之後的結果，及如何對應到原始輸入串
        self.__display = (u'', [0])
    
    def clear(self):
        self.__reset()
        self.__cb.update_ui()
    
    def is_empty(self):
        return not self.input
    
    def pop_input(self, till=-1):
        '''
        刪除輸入串末尾的編碼
        可選的參數，指定從某位置之後全刪掉；缺席時刪除最末一個編碼
        '''
        if till == -1:
            till = max(0, len(self.input) - 1)
        while len(self.input) > till:
            self.input.pop()
            # 刪除編碼後也清除末尾處自動添加上的隔音符
            if self.input and self.input[-1] == self.__delimiter[0]:
                self.input.pop()

    def commit(self):
        '''
        處理結果上屏事件
        當前算法，上屏動作由Engine發出，這是上屏後由Context響應的事件處理函數，並無上屏的具體操作
        '''
        if self.is_completed():
            # 學一遍
            self.__model.train(self, self.sel + self.cur)
            # 這樣清除Context可保留「上文信息」
            self.edit([])
        else:
            # 未完成轉換；捨棄結果
            self.clear()

    def edit(self, input, start_conversion=False):
        '''
        編輯輸入串
        替換輸入串內容並重新執行候選信息的計算
        '''
        self.__reset(keep_context=True)
        self.input = input
        if input:
            self.__model.query(self)
            m, n = self.info.m, self.info.n
            self.__calculate_display_string(input, self.info.d, n, m)
            if m != n:
                # 未完成整個輸入串的轉換
                self.err = Entry(None, m, n)
            elif start_conversion:
                # 轉換模式下需要顯示候選詞列表
                self.__update_candidates(self.__predict(exclude_the_last=True))
                return
            if self.__auto_predict:
                # 使用設定值Predict = yes，寫作串顯示為預測的轉換結果，而不是輸入串本身，否則需要按空格手動轉換
                self.__predict()
        # 更新到前端
        self.__cb.update_ui()

    def has_error(self):
        '''錯誤的輸入串'''
        return self.err is not None

    def cancel_conversion(self):
        '''取消轉換，回到輸入串編輯狀態'''
        self.edit(self.input)

    def __predict(self, exclude_the_last=False):
        '''
        預測轉換結果
        依據未確認部份由Model算出的最優整句變換結果自動選詞
        '''
        # 處理的起始位置為句首或已確認部份之後
        # 如果Context中記錄了上文信息，則以位置-1（前一回上屏的末一個單詞）代替句首
        i = self.sel[-1].j if self.sel else (-1 if self.info.last else 0)
        # 取得詞組的後續部份或從後續位置起的最佳預測結果
        p = (self.sel[-1].next if self.sel else None) or self.info.pred[i]
        while p:
            # 組成當前詞組的單詞序列，如［中國｜功夫］
            s = p.get_all()
            # 詞組應排除上文的尾詞，方得到屬於當前Context的有效部份
            # 如上一次輸入了［我｜喜歡｜中國］，上文信息為［中國］
            # 又輸入［gungfu］，則組成詞組［（中國）｜功夫］，預測結果為［功夫］
            if s[0].i < 0:
                del s[0]
            if s:
                p = s[-1]
                if exclude_the_last and p.j == self.info.m:
                    # 如果要顯示候選詞列表，最後一個詞組就不必執行自動選詞
                    break
                # 自動選用當前詞組
                self.sel.extend(s)
            # 預測後續詞句
            i = p.j
            p = self.info.pred[i]
        # 返回自動選詞的結束位置
        return max(0, i)

    def home(self):
        '''選詞光標回退至句首'''
        if not self.being_converted():
            return False
        # 清除手工選詞的記錄
        self.sel = []
        self.confirmed = 0
        # 顯示句首的候選詞
        self.__update_candidates(0)
        return True

    def end(self, start_conversion=False):
        '''選詞光標前進至句尾'''
        if not self.being_converted():
            if not start_conversion or self.has_error():
                return False
            # do a fresh new prediction in case of a full prediction is present
            self.sel = []
            self.confirmed = 0
        if self.cur and self.cur[-1].j == self.info.m:
            # 已在句尾則調轉到未確認部份的起始處
            del self.sel[self.confirmed:]
            self.__update_candidates(self.sel[-1].j if self.sel else 0)
            return True
        # 預測轉換結果，並顯示句尾的候選詞
        self.__update_candidates(self.__predict(exclude_the_last=True))
        return True

    def left(self):
        '''
        選詞光標左移
        首先向左縮小選區範圍，已縮小到最短編碼時選詞光標位置回退到上一個詞
        '''
        if not self.being_converted():
            return
        i = self.cur[0].i
        j = self.cur[-1].j
        # 由大到小枚舉各種長度的子編碼串
        for k in range(j - 1, i, -1):
            # 遇到最長的、有候選詞的子編碼串，就以這個範圍生成候選詞列表
            if self.info.cand[i][k] or self.info.fraz[i][k]:
                self.__update_candidates(i, k)
                return
        self.back()

    def right(self):
        '''
        選詞光標右移
        首先向右擴大選區範圍，已擴大到最長編碼串時選詞光標位置前進到下一個詞
        '''
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
        '''向後移動選詞光標'''
        if not self.being_converted():
            return False
        if self.sel:
            e = self.sel.pop()
            self.confirmed = min(self.confirmed, len(self.sel))
            self.__update_candidates(e.i)
            return True
        return False

    def forth(self):
        '''向前移動選詞光標'''
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
        '''確認當前候選詞，並將選詞光標移動到後續的詞'''
        c = self.cur
        if c:
            self.sel.extend(c)
            self.confirmed = len(self.sel)
            self.__update_candidates(c[-1].j)

    def __update_candidates(self, i, j=0):
        '''更新候選詞列表'''
        #print '__update_candidates:', i, j
        self.__candidates = self.__model.make_candidate_list(self, i, j)
        if self.__candidates:
            # 高亮顯示第一個候選詞
            self.cur = self.__candidates[0][1].get_all()
        else:
            # 無候選詞，將對應的編碼範圍標記為錯誤編碼
            err_pos = self.cur[-1].i if self.cur else 0
            self.err = Entry(None, err_pos, len(self.input))
            self.cur = []
        # 更新到前端
        self.__cb.update_ui()

    def select(self, e):
        '''從候選詞列表中手工選定一條候選詞'''
        self.cur = e.get_all()

    def being_converted(self):
        '''轉換模式'''
        return bool(self.cur)

    def is_completed(self):
        '''轉換完畢'''
        return self.cur and self.cur[-1].j == len(self.input)

    def __calculate_display_string(self, s, d, n, m):
        '''計算編碼展現串'''
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
        '''取得寫作串'''
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
        '''取得上屏文字'''
        i = 0
        r = []
        for s in self.sel + self.cur:
            r.append(s.get_word())
            i = s.j
        if i < len(self.input):
            s, t = self.__display
            r.append(s[t[i]:])
        return u''.join(r)

    def get_display_string(self):
        '''取得編碼串'''
        return self.__display[0]

    def get_input_string(self):
        '''取得輸入串'''
        return u''.join(self.input)
        
    def get_aux_string(self):
        '''取得提示文字'''
        if self.info.m == 0:
            return u''
        s, t = self.__display
        c = self.cur
        if self.__auto_prompt:
            if not c or c[-1].j == self.info.n:
                # 編碼提示限長
                return s if len(s) <= self.__aux_length else u'...' + s[-self.__aux_length:]
        elif not c:
            return u''
        # return the corresponding part of display string without trailing space
        return s[t[c[0].i]:t[c[-1].j]].rstrip()

    def get_candidates(self):
        '''取得當前候選詞'''
        return self.__candidates

    def delete_phrase(self, e):
        '''手工刪詞（未實作）'''
        pass

