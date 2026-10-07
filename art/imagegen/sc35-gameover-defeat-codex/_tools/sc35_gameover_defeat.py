#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-35: extend the byte-identical final SC-34 renderer in this package only."""
import sys
sys.dont_write_bytecode=True
from sc34_gameover_victory import build, finalize_review, configuration, gameover

def defeat_configuration(card,state):
    data,params=configuration(card,state)
    assert params['background']=='sarpedon' and params['grade']=='defeat'
    assert data['turn']==5 and data['duration']==13
    return data,params

if __name__=='__main__':
    if '--finalize-review' in sys.argv:finalize_review('SC-35')
    else:build('SC-35',gameover,defeat_configuration)
