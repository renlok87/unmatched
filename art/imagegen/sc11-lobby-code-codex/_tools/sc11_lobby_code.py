#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-11 extends immutable SC-08: captured codes, focus, refusal and why."""
import sys
sys.dont_write_bytecode=True
import sc08_lobby_list as base

def code_states():
    room=base.ROWS[0]['code'];errors=base.capture('join-errors.json')
    assert errors['viewer_myGames']['end']['answer']['data']['myGames']==[]
    return {'code-partial':{'code':room[:4],'keyboard':True},
            'code-full':{'code':room,'keyboard':True},
            'code-error-notfound':{'code':errors['notfound']['input_code'],'error':'notfound'},
            'code-error-full':{'code':errors['full']['input_code'],'error':'full'}}

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    base.build('SC-11',code_states())
