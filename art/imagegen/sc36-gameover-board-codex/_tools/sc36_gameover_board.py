#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-36: final SC-34 renderer, persistent board strip only, retained victory grade."""
import sys
sys.dont_write_bytecode=True
from sc34_gameover_victory import build, finalize_review, configuration, gameover

def board_configuration(card,state):
    data,params=configuration(card,state)
    assert params['background']=='marmoreal' and params['grade']=='victory'
    assert not params['veil'] and params['board_strip']
    return data,params

if __name__=='__main__':
    if '--finalize-review' in sys.argv:finalize_review('SC-36')
    else:build('SC-36',gameover,board_configuration)
