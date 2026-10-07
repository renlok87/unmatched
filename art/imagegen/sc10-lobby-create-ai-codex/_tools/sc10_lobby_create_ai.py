#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-10 adds the real AI Bot note to the immutable SC-09 create family."""
import sys
sys.dont_write_bytecode=True
import sc09_lobby_create as create

original_layout=create.base.layout
def ai_layout(vp):
    g=original_layout(vp)
    if vp.layout_class=='S':
        # The note ink starts >8 su below the chips. The board-label ink
        # follows >8 su below the note; tiles retain 96 su illustrations.
        x,y,w,h=g['CreateNote'];g['CreateNote']=(x,y+2,w,h)
        for name in ('BoardLabel','BoardChips[0]','BoardChips[1]'):
            x,y,w,h=g[name];g[name]=(x,y+12,w,h)
        x,y,w,h=g['CreateButton'];g['CreateButton']=(x,y+8,w,h)
    return g

create.base.layout=ai_layout

original_icon=create.base.LobbyCanvas.icon
def ai_icon(self,name,xy,size_su):
    # Moving the button must not move the cursor beyond CreateColumn.
    if name=='cursor-busy' and self.viewport.layout_class=='S':
        xy=(xy[0],xy[1]-8)
    return original_icon(self,name,xy,size_su)
create.base.LobbyCanvas.icon=ai_icon

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    create.base.build('SC-10',create.create_states(ai=True))
