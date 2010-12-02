#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:set et sts=4 sw=4:

import ibus
from ibus import keysyms
from ibus import modifier

import weasel

def feed(session, input):
    name = ''
    is_name = False
    for c in input:
        if c == '{':
            name = ''
            is_name = True
        elif c == '}':
            is_name = False
            print session.process_key_event(keysyms.name_to_keycode(name), 0)
            print session.get_response()
        elif is_name:
            name += c
        else:
            print session.process_key_event(ord(c), 0)
            print session.get_response()

def test(session):
    # Ctrl+grave
    print session.process_key_event(keysyms.grave, modifier.CONTROL_MASK)
    print session.get_response()
    # noop
    feed(session, '2')
    # choose Pinyin
    feed(session, '1')
    # input
    #feed(session, "pinyin-shuru'fa' ")
    feed(session, 'jiong ')

def main():
    sid = weasel.service.create_session()
    print "session_id:", sid
    assert weasel.service.has_session(sid)
    session = weasel.service.get_session(sid)
    assert bool(session)
    print
    test(session)
    weasel.service.destroy_session(sid)

if __name__ == "__main__":
    main()
