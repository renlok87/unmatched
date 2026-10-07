#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-15 extends the immutable final SC-14 foundation with two real rooms."""
import sys
sys.dont_write_bytecode=True
import sc14_room_hero as b

def states():
    return {'board-marmoreal':b.frame_options('room-state.json','both_picked'),
            'board-sarpedon':b.frame_options('room-sarpedon.json','both_picked')}

def build():
    copies=[('art/imagegen/sc14-room-hero-codex/_tools/sc14_room_hero.py','sc14_room_hero.py'),
            ('art/imagegen/sc14-room-hero-codex/_tools/finalize_review.py','finalize_review.py')]
    extra=[source for source,name in copies]
    extra+=['art/imagegen/sc14-room-hero-codex/manifest-sha256.json','backend/src/games/dto/create-game.dto.ts']
    return b.build('SC-15',states(),extra=extra,copies=copies)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');build()
