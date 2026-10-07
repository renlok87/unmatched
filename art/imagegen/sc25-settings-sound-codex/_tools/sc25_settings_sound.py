#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-25: exact audio defaults, six buses, eight rows, four native canvases."""
from sc24_pause import Viewport, sound_rows
from package_support import run_package

def specifications():
 return [('sound',res,scale,Viewport.preset(res,scale),
  {'background':'marmoreal','open_tab':'sound','rows':sound_rows()})
  for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]]

if __name__=='__main__':run_package(25,specifications())
