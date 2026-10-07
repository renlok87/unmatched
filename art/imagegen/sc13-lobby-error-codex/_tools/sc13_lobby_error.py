#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-13 extends immutable SC-08 with list failure and normal Retry."""
import sys
sys.dont_write_bytecode = True
import sc08_lobby_list as base


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    base.build('SC-13', {'error': {'list': 'error'}})
