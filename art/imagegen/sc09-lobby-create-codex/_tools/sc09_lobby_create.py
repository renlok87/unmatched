#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-09 extends the final immutable SC-08 renderer: board selection and busy."""
import sys
sys.dont_write_bytecode=True
import sc08_lobby_list as base

def create_states(ai=False):
    if ai:return {'create-ai':{'ai':True,'board':1},'busy':{'ai':True,'board':1,'busy':True}}
    return {'create-marmoreal':{'board':0},'create-sarpedon':{'board':1},'busy':{'board':0,'busy':True}}

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    base.build('SC-09',create_states())
