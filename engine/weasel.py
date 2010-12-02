#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import logging
import logging.config
import os

logfile = os.path.join(os.path.dirname(__file__), "logging.conf")

logging.config.fileConfig(logfile)
logger = logging.getLogger("weasel")

import ibus
from ibus import keysyms
from ibus import modifier

import zimeengine
import zimeparser
from zimedb import DB

def _initialize():
    zimeparser.register_parsers()
    # initialize DB 
    home_path = os.path.expanduser('~')
    if home_path:
        db_path = os.path.join(home_path, '.ibus', 'zime')
    else:
        db_path = '.'
    user_db = os.path.join(db_path, 'zime.db')
    if not os.path.exists(user_db):
        if not os.path.isdir(db_path):
            os.makedirs(db_path)
    DB.open(user_db)

_initialize()


class Session:

    def __init__(self, params=''):
        logger.info("init session: %s", params)
        self.__page_size = DB.read_setting(u'Option/PageSize') or 5
        self.__lookup_table = ibus.LookupTable(self.__page_size)
        self.__clear()
        self.__engine = zimeengine.SchemaChooser(self, params)

    def __clear(self):
        self.__commit = None
        self.__preedit = None
        self.__aux = None
        self.__cand = None

    def process_key_event(self, keycode, mask):
        logger.debug("process_key_event: '%s'(%x), %08x" % (keysyms.keycode_to_name(keycode), keycode, mask))
        self.__clear()
        taken = self.__engine.process_key_event(keycode, mask)
        return taken

    def get_response(self):
        action = set()
        r = list()
        if self.__commit:
            action.add(u'commit')
            r.append(u'commit=%s\n' % u''.join(self.__commit)) 
        if self.__preedit:
            action.add(u'ctx')
            (s, attrs, cursor) = self.__preedit
            r.append(u'ctx.preedit=%s\n' % s)
            if attrs:
                r.append(u'ctx.preedit.attr.length=%d\n' % len(attrs))
                for i in range(len(attrs)):
                    (extent, type) = attrs[i]
                    r.append(u'ctx.preedit.attr.%d.range=%d,%d\n' % (i, extent[0], extent[1]))
                    r.append(u'ctx.preedit.attr.%d.type=%s\n' % (i, type))
            if cursor:
                r.append(u'ctx.preedit.cursor=%d,%d\n' % cursor)
        if self.__aux:
            action.add(u'ctx')
            (s, attrs) = self.__aux
            r.append(u'ctx.aux=%s\n' % s)
        if self.__cand:
            action.add(u'ctx')
            (current_page, total_pages, cursor, cands) = self.__cand
            n = len(cands)
            r.append(u'ctx.cand.length=%d\n' % n)
            for i in range(n):
                r.append(u'ctx.cand.%d=%s\n' % (i, cands[i][0]))
            r.append(u'ctx.cand.cursor=%d\n' % cursor)
            r.append(u'ctx.cand.page=%d/%d\n' % (current_page, total_pages))
            #r.append(u'ctx.cand.current_page=%d\n' % current_page)
            #r.append(u'ctx.cand.total_pages=%d\n' % total_pages)
        #self.__clear()
        if not action:
            return u'action=noop\n.\n'
        else:
            r.insert(0, u'action=%s\n' % u','.join(sorted(action)))
            r.append(u'.\n')
            return u''.join(r)
    
    # implement a frontend proxy for zimeengine

    def commit_string(self, s):
        logger.debug(u'commit: [%s]' % s)
        if self.__commit:
            self.__commit.append(s)
        else:
            self.__commit = [s]

    def update_preedit(self, s, start, end):
        logger.debug(u'preedit: [%s[%s]%s]' % (s[:start], s[start:end], s[end:]))
        #attrs = [((start, end), u'HIGHLIGHTED')] if start < end else None
        #self.__preedit = (s, attrs)
        cursor = (start, end) if start < end else None
        self.__preedit = (s, None, cursor)

    def update_aux_string(self, s):
        logger.debug(u'aux: [%s]' % s)
        self.__aux = (s, None)

    def update_candidates(self, candidates):
        self.__lookup_table.clean()
        self.__lookup_table.show_cursor(False)
        if not candidates:
            self.__cand = (0, 0, 0, [])
        else:
            for c in candidates:
                self.__lookup_table.append_candidate(ibus.Text(c[0]))
            self.__update_page()

    def __update_page(self):
        candidates = self.__lookup_table.get_candidates_in_current_page()
        n = self.__lookup_table.get_number_of_candidates()
        c = self.__lookup_table.get_cursor_pos()
        p = self.__lookup_table.get_page_size()
        current_page = c / p
        total_pages = (n + p - 1) / p
        cands = [(x.get_text(), None) for x in candidates]
        self.__cand = (current_page, total_pages, c % p, cands)
            
    def page_up(self):
        if self.__lookup_table.page_up():
            #print u'page_up.'
            self.__update_page()
            return True
        return False

    def page_down(self):
        if self.__lookup_table.page_down():
            #print u'page_down.'
            self.__update_page()
            return True
        return False

    def cursor_up(self):
        if self.__lookup_table.cursor_up():
            #print u'cursor_up.'
            self.__update_page()
            return True
        return False

    def cursor_down(self):
        if self.__lookup_table.cursor_down():
            #print u'cursor_down.'
            self.__update_page()
            return True
        return False

    def get_candidate_index(self, index):
        index += self.__lookup_table.get_current_page_start()
        #print u'index = %d' % index
        return index

    def get_candidate_cursor_pos(self):
        index = self.__lookup_table.get_cursor_pos()
        #print u'candidate_cursor_pos = %d' % index
        return index


class WeaselService:
    
    def __init__(self):
        self.__sessions = dict()

    def cleanup(self):
        self.__sessions.clear()

    def has_session(self, id):
        if id in self.__sessions:
            return True
        else:
            return False

    def get_session(self, id):
        if id in self.__sessions:
            return self.__sessions[id]
        else:
            return None

    def create_session(self):
        try:
            session = Session()
        except Exception, e:
            logger.error("create_session: error creating session: %s" % e)
            return None
        self.__sessions[id(session)] = session
        return id(session)

    def destroy_session(self, id):
        if id not in self.__sessions:
            logger.warning("destroy_session: invalid session id %d." % id)
            return False
        del self.__sessions[id]
        return True

service = WeaselService()

