#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-18: static countdown frames over the immutable final SC-17 ready screen."""
import sys
sys.dont_write_bytecode=True
import sc14_room_hero as b
import sc17_room_ready as ready

def states():
    return {'countdown-3':b.frame_options('room-state.json','host_view_all_ready'),
            'starting':b.frame_options('room-state.json','all_ready','guest',starting=True)}

def renderer(c,options):
    # Use SC-17's unchanged final renderer and the actual ready capture.
    room=ready.renderer(c,options)
    underneath=ready.screen_icons_below_veil(c,.8)
    draw_countdown(c,starting=options.get('starting',False))
    c.icon_layers=underneath+c.icon_layers
    trigger='guest_view_started' if options.get('starting') else 'started'
    started=b.room_answer('room-state.json',trigger)
    assert started['status']=='IN_PROGRESS'
    c.notes.append({'countdown':{'trigger_source':b.rel(b.DERIVED/'inputs/room-state.json')+':steps.'+trigger,
        'trigger_status':started['status'],'base_source':options['step'],'viewer':options['viewer'],
        'second_veil_alpha':.8,'hover':False,'focus':False,'cursor':'cursor-default',
        'timing':'static frames only; server start not delayed; 2/1 are motion and not exported'}})
    return room

def draw_countdown(c,starting=False):
    """Opaque modal plate above the second veil, with measured text padding."""
    from PIL import Image
    c.active_layer='modal';c.icon_layers=[]
    c.image=Image.alpha_composite(c.image,Image.new('RGBA',c.image.size,c.theme.color('panel.veil')+(204,)))
    W,H=c.viewport.canvas
    value=b.STRINGS['screens.room.countdown'] if starting else '3'
    role='type.title' if starting else 'type.display'
    from PIL import ImageDraw
    bbox=ImageDraw.Draw(c.image).textbbox((0,0),value,font=c.theme.font(role,c.factor),anchor='mm')
    tw=(bbox[2]-bbox[0])/c.factor;th=(bbox[3]-bbox[1])/c.factor
    pw=max(160,tw+64);ph=th+48
    plate=((W-pw)/2,(H-ph)/2,pw,ph)
    c.panel(plate,kind='modal');c.geometry[-1].update(component='CountPlate',radius_su=8,edge_su=1)
    c.record('CountPlate',plate,kind='modal',alpha=1.0,radius_su=8,edge_su=1,padding_su=[32,24],minimum_width_su=160)
    xy=(W/2-(bbox[0]+bbox[2])/(2*c.factor),H/2-(bbox[1]+bbox[3])/(2*c.factor))
    c.text(xy,value,role,'text.primary','mm',source=b.string_source('screens.room.countdown') if starting else 'SC-14-series.codex.md:ВР-VS4-SC18-01 digit 3')
    c.record('CountText',((W-tw)/2,(H-th)/2,tw,th),value=value,veil_alpha=.8,centre=True,plate='CountPlate')
    c.geometry.append({'kind':'modal','rect_su':[0,0,W,H],'alpha':.8,'component':'CountdownVeil'})
    c.icon('cursor-default',(W-48,H-48),32)

def build():
    copies=[('art/imagegen/sc14-room-hero-codex/_tools/sc14_room_hero.py','sc14_room_hero.py'),
            ('art/imagegen/sc14-room-hero-codex/_tools/finalize_review.py','finalize_review.py'),
            ('art/imagegen/sc17-room-ready-codex/_tools/sc17_room_ready.py','sc17_room_ready.py')]
    extra=[source for source,name in copies]+['art/imagegen/sc14-room-hero-codex/manifest-sha256.json',
        'art/imagegen/sc17-room-ready-codex/manifest-sha256.json','art/imagegen/sc17-room-ready-codex/README.md']
    manifest=b.load(b.ROOT/'art/imagegen/sc17-room-ready-codex/manifest-sha256.json')
    script='art/imagegen/sc17-room-ready-codex/_tools/sc17_room_ready.py'
    assert manifest['files'][script]==b.sha(b.ROOT/script)
    v=b.build('SC-18',states(),renderer,extra,copies)
    digit_font=b.theme().font('type.display',4)
    advances={str(n):digit_font.getlength(str(n))/4 for n in range(10)}
    assert max(advances.values())-min(advances.values())<.001
    centred=[]
    for key,frame in v['frames'].items():
        item=frame['components']['CountText'];x,y,w,h=item['rect_su'];W,H=frame['viewport']['canvas_su']
        centred.append({'frame':key,'centre_error_su':[abs(x+w/2-W/2),abs(y+h/2-H/2)],
                        'value':item['value'],'text_contrast':next(t['ratio'] for t in frame['text_contrast'] if t['layer']=='modal')})
        assert abs(x+w/2-W/2)<1e-6 and abs(y+h/2-H/2)<1e-6
        assert frame['primary_buttons']==(0 if key.startswith('starting') else 1)
    v['countdown_proof']={'frames':centred,'display_digit_advances_su':advances,'tabular_digits':True,
        'second_veil_rgba_alpha':204,'second_veil_opacity':.8,'no_hover_or_focus':True,
        'server_delay_added':False,'reduced_motion':'no animation generated',
        'underlying_primary_policy':'host ready = 1; ready guest selected = 0; underlying controls are veiled'}
    b.dump(b.PACKAGE/'verification.json',v)
    manifest=b.load(b.PACKAGE/'manifest-sha256.json');facts=manifest['facts']
    facts['countdown']={'digit':{'value':3,'source':'SC-14-series.codex.md:ВР-VS4-SC18-01'},
        'starting':{'value':b.STRINGS['screens.room.countdown'],'source':'docs/unreal/contracts/hud/st-screens.csv:screens.room.countdown:ru'},
        'triggers':{step:{'value':b.room_answer('room-state.json',step)['status'],'source':b.rel(b.DERIVED/'inputs/room-state.json')+':steps.'+step} for step in ('started','guest_view_started')}}
    p=b.PACKAGE/'README.md'
    b.text_file(p,p.read_text(encoding='utf-8')+'\n## SC-18: отсчёт\n\ncountdown-3 использует host_view_all_ready через неизменённый рендерер SC-17; starting — all_ready в виде гостя. Поверх экрана отдельная вуаль panel.veil 0,8, затем центрированный type.display «3» / type.title «Партия начинается…». Геометрический центр проверен во всех восьми кадрах; цифры 0–9 имеют одинаковый advance. Обе строки читаемы в сером. Триггеры started / guest_view_started имеют IN_PROGRESS, ожидание сервера не добавлено. 2 и 1 не экспортируются; нет hover, focus или анимации. У готового гостя включённый Ready — selected, главных кнопок ноль; это решение серии. Подложка хоста сохраняет одну Start, с известным ограничением исходной navy-кромки, поэтому полный буквальный гейт кромок false. Новый предложенный ключ числа — screens.room.countdown.number «{n}»; сама цифра — числовое значение, строку «Партия начинается…» определяет ST_Screens.\n')
    b.refresh_manifest(facts)
    return v

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');build()
