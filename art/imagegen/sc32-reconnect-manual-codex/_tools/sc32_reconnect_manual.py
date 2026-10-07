#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-32 extension of the byte-identical final SC-31 snapshot.

Manual has equal-width Leave/Retry buttons; expired routes only to LOGIN.
This module owns SC-32 output. Its shared renderer never writes to SC-31.
"""
import sys
sys.dont_write_bytecode = True
from sc31_reconnect_auto import reconnect, main


def draw_manual(viewport, expired=False):
    return reconnect(viewport, board='sarpedon', desaturation_weight=1,
                     veil_opacity=.8, card_state='expired' if expired else 'manual')


if __name__ == '__main__':
    main('SC-32')
