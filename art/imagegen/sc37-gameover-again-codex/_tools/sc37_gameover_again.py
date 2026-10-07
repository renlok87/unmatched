#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-37: VS_AI run F, T. Rex portrait proposal, stable normal/busy row."""
import sys
sys.dont_write_bytecode=True
from sc34_gameover_victory import (build, finalize_review, configuration, gameover,
                                    label, measure, button_width, string_source)

def again_configuration(card,state):
    data,params=configuration(card,state)
    assert data['opponent']=='AI Bot' and data['loser']=='T. Rex'
    assert data['turn']==19 and data['duration']==33
    assert params['right']['hp']==[0,27] and params['left']['hp']==[14,16]
    assert len(params['buttons'])==3 and params['buttons'][1]['key']=='screens.result.again'
    return data,params

def again_gameover(c,*,background,grade,veil,outcome,headline,reason,turn,left,right,buttons,board_strip=None):
    """SC-37 extension: ВР-VS5-SC37-06, class S modal width 760 su."""
    c.grade['background']=background;c.grade['veil']=.6 if veil else 0
    W,H=c.viewport.canvas;S=c.viewport.layout_class=='S'
    if board_strip:
        strip=(W/2-260,H-c.viewport.margin-56,520,56)
        c.panel_named('BoardStrip',strip,'persistent');x,y,w,h=strip
        text=board_strip['text'];tw=measure(text);gap=8;chips=True
        widths=[button_width(b) for b in buttons]
        if tw+sum(widths)+16+2*gap>w:
            chips=False;widths=[button_width(b,False) for b in buttons];c.notes.append('BoardStrip: key chips removed before any type reduction')
        c.ui_text('StripText',(x+8,y+8,tw,40),text,'type.button',align='left',source=board_strip['source'])
        bx=x+w-8-sum(widths)-gap
        for b,bw in zip(buttons,widths):c.action(b['name'],(bx,y+8,bw,40),b['key'],b.get('chip') if chips else None,primary=b.get('primary',False));bx+=bw+gap
        return
    if veil:c.veil()
    mw,mh=(760,560) if S else (760,580);rect=((W-mw)/2,(H-mh)/2,mw,mh);x,y,_,_=rect;cx=W/2
    c.panel_named('ResultModal',rect)
    c.centered_text('OutcomeText',cx,y+32,label(outcome['key']),outcome['role'],outcome['color'],string_source(outcome['key']))
    for name,top,value,role,color,source in [
        ('HeadlineText',96,headline,'type.title','card.cream',string_source('screens.result.wins')),
        ('ReasonText',140,reason,'type.body','text.primary',string_source('screens.result.reason.hp')),
        ('TurnText',168,turn,'type.caption','text.secondary',string_source('screens.result.turn.time'))]:
        if value:c.centered_text(name,cx,y+top,value,role,color,source)
    offset=160 if S else 180;py=y+210
    c.centered_text('VersusText',cx,py+48,label('screens.loading.versus'),'type.heading','text.secondary',string_source('screens.loading.versus'))
    for prefix,center,side in [('Left',cx-offset,left),('Right',cx+offset,right)]:
        c.portrait(prefix+'Portrait',(center-60,py,120,120),side['hero'],side['portrait'],side['look'],side['crop_key'],side.get('crop'))
        ny=py+132
        c.centered_text(prefix+'Name',center,ny,side['hero'],'type.heading',source=side['source'])
        capy=ny+24+4
        hp=(' · HP '+str(side['hp'][0])+'/'+str(side['hp'][1])) if side.get('hp') is not None else ''
        status='screens.result.winner' if side['look']=='winner' else 'screens.result.defeated'
        a=side['role']+hp+' · ';b=label(status);aw=measure(a,'type.caption');bw=measure(b,'type.caption')
        fallen=side['look']=='defeated';total=aw+bw+(30 if fallen else 0);sx=center-total/2
        c.record(prefix+'Caption',(sx,capy,total,24),text=a+b,hp=side.get('hp'),role=side['role'],source=side['source'])
        c.ui_text(prefix+'Caption.RoleHP',(sx,capy,aw,24),a,'type.caption','text.secondary',align='left',source=side['source'])
        c.ui_text(prefix+'Caption.Status',(sx+aw,capy,bw,24),b,'type.caption','turn.flash.yellow' if not fallen else 'text.secondary',align='left',source=string_source(status))
        if fallen:c.native_icon('resource-hp-fallen',(sx+aw+bw+6,capy,24,24),prefix+'FallenIcon')
    widths=[button_width(b) for b in buttons];gap=16;chips=True;available=mw-48
    if sum(widths)+gap*(len(buttons)-1)>available:
        gap=8;c.notes.append('ButtonRow: gaps reduced to 8 su')
    if sum(widths)+gap*(len(buttons)-1)>available:
        chips=False;widths=[button_width(b,False) for b in buttons];c.notes.append('ButtonRow: key chips removed; type and minimum widths retained')
    roww=sum(widths)+gap*(len(buttons)-1);bx=cx-roww/2;by=y+(480 if S else 500)
    c.record('ButtonRow',(bx,by,roww,48),budget_su=available,gap_su=gap,chips=chips,fits_budget=roww<=available)
    if roww>available:c.notes.append(f'Unmet fixed row budget: {roww:.3f} su > {available} su; no clipping/wrapping/font reduction')
    for b,bw in zip(buttons,widths):
        c.action(b['name'],(bx,by,bw,48),b['key'],b.get('chip') if chips else None,b.get('state','normal'),b.get('primary',False));bx+=bw+gap

if __name__=='__main__':
    if '--finalize-review' in sys.argv:finalize_review('SC-37')
    else:build('SC-37',again_gameover,again_configuration)
