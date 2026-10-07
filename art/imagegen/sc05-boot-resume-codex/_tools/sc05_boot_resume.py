#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-05 resume modal using the finalized, unchanged SC-03 foundation."""
import csv
import re
import sys
import numpy as np
sys.dont_write_bytecode=True
from sc03_boot_loading import build,loading,icon,data,read,MATRIX,TRACE,text_width,stats,wcag_luminance


def match_line():
    rows={r['contentKey']:r for r in csv.DictReader(read(MATRIX).splitlines())}
    hero=re.search(r'\(([^)]+)\)',rows['medusa']['nazvanie']).group(1)
    opponent=re.search(r'\(([^)]+)\)',rows['king-arthur']['nazvanie']).group(1)
    board=rows['board-marmoreal-original']['nazvanie'].split(' (')[0]
    assert 'RESULT summary outcome=VICTORY winnerHero=Medusa loserHero=King_Arthur' in read(TRACE)
    assert 'boardId=c121b47f8d6eb28daccb76d05' in read(TRACE)
    return data()['screens.boot.resume.line'].format(hero=hero,opponent=opponent,board=board)


def wrap(c,value,max_width):
    lines=['']
    for word in value.split(' '):
        candidate=(lines[-1]+' '+word).strip()
        if text_width(c,candidate)<=max_width:lines[-1]=candidate
        else:lines.append(word)
    assert len(lines)<=2,'Do not shrink the type; modal text budget exceeded'
    return lines


def in_flight(c,rect,label):
    # Reuse accepted button skin; move only the separate runtime label to reserve
    # a 32-su spinner on its left. Canvas.button supplies HB-08 and the why line.
    x,y,w,h=rect;lw=text_width(c,label.upper(),'type.button');group=32+12+lw
    assert group<=w-32
    original=c.text
    def with_spinner_room(xy,value,role='type.body',color='text.primary',anchor='lt',source=None):
        if source=='screens.boot.resume.return' and role=='type.button':
            xy=(x+(w-group)/2+44+lw/2,y+h/2)
        return original(xy,value,role,color,anchor,source)
    c.text=with_spinner_room
    c.button(rect,label,state='disabled',primary=True,why=('why.syncing',data()['why.syncing']),
             source='screens.boot.resume.return')
    c.text=original
    icon(c,'loader-spinner',(x+(w-group)/2,y+8,32,32),opacity=.4)
    # The inactive spinner is over the disabled BUTTON body, not panel.bg.
    im=c.exact_icons[-1][0];a=np.asarray(im)
    solid=a[:,:,3]>=100;alpha=a[solid,3:]/255
    button=next(g for g in reversed(c.geometry) if g['kind']=='button')
    body=np.asarray(button['fill'])
    visible=a[solid,:3]*alpha+body*(1-alpha)
    fg,bg=wcag_luminance(visible),wcag_luminance(body)
    c.metrics['icons'][-1]['glyph_to_panel']=stats((np.maximum(fg,bg)+.05)/(np.minimum(fg,bg)+.05),3)
    c.metrics['icons'][-1]['actual_background']='HB-08 BtnPrimary_Disabled body '+str(button['fill'])


def resume(c,state):
    d=data();loading(c,'loading-boards');cw,ch=c.viewport.canvas
    x,y=(cw-640)/2,(ch-300)/2
    # This is the only modal; screen already supplied the only veil.
    c.panel((x,y,640,300),'modal');c.text_layer='modal'
    for t in c.text_runs:
        a,b,rr,bb=t['bbox_px'];f=c.viewport.factor
        t['occluded_by_modal']=a<(x+640)*f and rr>x*f and b<(y+300)*f and bb>y*f
    c.text((x+16,y+16),d['screens.boot.resume.title'],'type.title',source='screens.boot.resume.title')
    lines=wrap(c,match_line(),608)
    for i,line in enumerate(lines):
        c.text((x+16,y+64+i*22),line,source='screens.boot.resume.line')
    c.geometry.append({'kind':'text-budget','rect_su':[x+16,y+64,608,44],
                       'label':'match-line','lines':lines,'font_su':16,'names_nominative':True})
    lobby=(x+16,y+212,168,48);back=(x+312,y+212,312,48)
    c.button(lobby,d['screens.boot.resume.lobby'],source='screens.boot.resume.lobby')
    if state=='resuming':in_flight(c,back,d['screens.boot.resume.return'])
    else:c.button(back,d['screens.boot.resume.return'],primary=True,source='screens.boot.resume.return')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build('sc05-boot-resume','SC-05',('resume','resuming'),resume,
          ('art/imagegen/sc03-boot-loading-codex/_tools/sc03_boot_loading.py',MATRIX))
