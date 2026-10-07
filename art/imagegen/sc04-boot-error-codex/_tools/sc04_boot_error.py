#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-04 extension of the finalized, byte-identical SC-03 module."""
import sys
sys.dont_write_bytecode=True
from sc03_boot_loading import build,loading,capsule,icon,data
from PIL import ImageDraw


def error(c,state):
    d=data();layout=loading(c,'heroes-wait');w,h=c.viewport.canvas
    # Caption capsule starts at caption_y-4 and is 28 su tall.
    x,y=w/2-240,layout['caption_y']-4+28+16
    capsule(c,(x,y,480,104),'error-capsule')
    icon(c,'resource-connection-lost',(x+16,y+16,48,48))
    font=c.theme.font('type.body',c.factor)
    bounds=ImageDraw.Draw(c.image).textbbox((0,0),d['screens.boot.error.server'],font=font,anchor='lt')
    text_h=(bounds[3]-bounds[1])/c.factor
    c.text((x+76,y+16+(48-text_h)/2),d['screens.boot.error.server'],source='screens.boot.error.server')
    retrying=state=='retrying'
    # Extend Canvas.button without changing the accepted SC-01 library.
    # The reason strip shares the action button's RIGHT edge in both states.
    original=c.text
    def right_aligned_reason(xy,value,role='type.body',color='text.primary',anchor='lt',source=None):
        if source=='why.syncing':xy=(x+464,y+70);anchor='rt'
        return original(xy,value,role,color,anchor,source)
    c.text=right_aligned_reason
    c.button((x+296,y+16,168,48),d['common.btn.retry'],
        state='disabled' if retrying else 'normal',primary=True,
        why=('why.syncing',d['why.syncing']) if retrying else None,source='common.btn.retry')
    c.text=original


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build('sc04-boot-error','SC-04',('error','retrying'),error,
          ('art/imagegen/sc03-boot-loading-codex/_tools/sc03_boot_loading.py',))
