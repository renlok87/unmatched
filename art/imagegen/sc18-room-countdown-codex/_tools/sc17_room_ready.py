#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-17 extends immutable SC-14; final module is copied unchanged by SC-18."""
import sys
sys.dont_write_bytecode=True
from PIL import Image
import sc14_room_hero as b

def states():
    return {'waiting':b.frame_options('room-state.json','host_ready'),
            'ready':b.frame_options('room-state.json','host_view_all_ready'),
            'guest':b.frame_options('room-state.json','guest_view_both_picked','guest'),
            'ai':b.frame_options('room-vsai.json','ready_before_start'),
            'leave':b.frame_options('room-state.json','host_ready',leave=True)}

def screen_icons_below_veil(c,alpha):
    """Keep native menu pixels under a later veil; never resample the icon."""
    navy=c.theme.color('panel.veil');layers=[]
    for (im,xy),meta in zip(c.icon_layers,c.icons):
        if meta['name'].startswith('cursor-'):continue
        channels=list(im.split())
        for i in range(3):channels[i]=channels[i].point(lambda v,n=navy[i]:round(v*(1-alpha)+n*alpha))
        layers.append((Image.merge('RGBA',channels),xy))
    return layers

def renderer(c,options):
    room=b.draw_room(c,options)
    if options.get('leave'):
        beneath=screen_icons_below_veil(c,.6)
        draw_leave(c)
        c.icon_layers=beneath+c.icon_layers
    return room

def draw_leave(c):
    """SC-01 skins and base width, with content-sized geometry local to SC-17."""
    c.active_layer='modal';c.icon_layers=[];c.veil()
    W,H=c.viewport.canvas;w=b.modal_rect(c.viewport)[2]
    title_h=c.theme.size('type.title');h=24+title_h+24+48+24
    r=((W-w)/2,(H-h)/2,w,h);c.panel(r,kind='modal')
    c.record('UUmConfirmDialog',r,padding_su=24,title_gap_su=24)
    x,y,w,h=r
    title=b.STRINGS['screens.room.leave.confirm']
    c.text((x+24,y+24),title,'type.title',source=b.string_source('screens.room.leave.confirm'))
    c.record('UUmConfirmDialog.TitleText',(x+24,y+24,w-48,title_h),value=title)
    cancel=(x+w-376,y+h-72,168,48);yes=(x+w-192,y+h-72,168,48)
    c.button(cancel,b.STRINGS['common.confirm.cancel'],source=b.string_source('common.confirm.cancel'))
    c.button(yes,b.STRINGS['common.confirm.yes'],primary=True,source=b.string_source('common.confirm.yes'))
    c.record('UUmConfirmDialog.CancelButton',cancel,primary=False)
    c.record('UUmConfirmDialog.ConfirmButton',yes,primary=True)
    c.icon('cursor-default',(x+w-40,y+h-40),32)

def ready_frame(c,viewer='host'):
    step='host_view_all_ready' if viewer=='host' else 'all_ready'
    return renderer(c,b.frame_options('room-state.json',step,viewer))

def build():
    copies=[('art/imagegen/sc14-room-hero-codex/_tools/sc14_room_hero.py','sc14_room_hero.py'),
            ('art/imagegen/sc14-room-hero-codex/_tools/finalize_review.py','finalize_review.py')]
    extra=[source for source,name in copies]+['art/imagegen/sc14-room-hero-codex/manifest-sha256.json',
        'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/README.md']
    v=b.build('SC-17',states(),renderer,extra,copies)
    v['readiness_proof']={'waiting_refusal':{'file':b.rel(b.DERIVED/'inputs/room-state.json'),'step':'start_refused_guest_not_ready',
        'server_message':'Не все игроки готовы','client_why':'why.room.not.ready'},
        'AI_slot':{'captured_seats_before_start':1,'synthetic_future_seat':True,'name_source':'backend/prisma/seed-ai.ts:24',
                   'heroId':None,'portrait':'empty','isReady':True,'decision':'series ВР-VS4-SC17-01; server seats bot at startGame'},
        'primary_counts':{key:frame['primary_buttons'] for key,frame in v['frames'].items()},
        'five_required_states':list(states()),'no_team_colour':True}
    assert all(f['primary_buttons']==1 for f in v['frames'].values())
    b.dump(b.PACKAGE/'verification.json',v)
    p=b.PACKAGE/'README.md'
    b.text_file(p,p.read_text(encoding='utf-8')+'\n## SC-17: готовность и выход\n\nwaiting/leave: host_ready; отказ Start подтверждён start_refused_guest_not_ready. ready: host_view_all_ready. guest: guest_view_both_picked, без Start, Ready — главная. ai: ready_before_start, PKKN2P, режим «Против ИИ», один захваченный игрок и оговорённый пустой будущий слот AI Bot. Его имя — seed-ai.ts:24, готовность — правило посадки сервера и решение серии; до старта у ответа нет heroId бота. Leave: неизменённый шаблон SC-01, заголовок «Выйти из комнаты?», обычная «ОТМЕНА», главная «ДА». У каждого из двадцати кадров одна главная в текущем окне; disabled Start под модалью не считается вторым окном подтверждения. Принятая navy-кромка normal primary не проходит буквальный контраст 3:1 к navy-панели (1:1), хотя жёлтое тело и его текст различимы. Полная буквальная приёмка поэтому false, цвета не подменены.\n')
    b.refresh_manifest()
    return v

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');build()
