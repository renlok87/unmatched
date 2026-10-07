#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Finalize an already visually inspected package; never generates images."""
import sys
sys.dont_write_bytecode=True
import json
from pathlib import Path
import numpy as np
from PIL import Image
import sc08_lobby_list as b

def main():
    v=b.load(b.PACKAGE/'verification.json')
    review={'status':'предложено','reviewer':'Codex','method':'Every final PNG opened using view_image: all four canvases, all states, colour and Rec.709 gray. Geometry and real data checked alongside native renders.',
            'checks':['real Marmoreal placeholder K1 with explicit caption','only two adminBoard maps','full map aspect, names underneath','CP-07 B portrait discs without team rings','no permanent host names','why text and missing Join buttons','code kept after failure','one primary','no avatar or map pixels in package overlays'],
            'limitations':['Conditional RecoverButton is hidden for the captured empty myGames. Its reserved slot needs panel expansion when active; on smallest S overlay it is described in the ledger rather than drawn outside safe bounds.'],
            'files':[{'path':e['path'],'sha256':b.sha(b.ROOT/e['path'])} for e in v['exports']]}
    b.dump(b.PACKAGE/'visual-review.json',review)
    reused=[]
    for local,source in [('screen_mockup_base.py','art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py'),
                         ('draw_icons_v3_snapshot.py','art/imagegen/hud-icons-v3/_tools/draw_icons.py'),
                         ('sc08_lobby_list.py','art/imagegen/sc08-lobby-list-codex/_tools/sc08_lobby_list.py'),
                         ('sc09_lobby_create.py','art/imagegen/sc09-lobby-create-codex/_tools/sc09_lobby_create.py')]:
        destination=b.PACKAGE/'_tools'/local
        if destination.exists():reused.append({'source':source,'destination':b.label_path(destination),'sha256':b.sha(destination),'copied_unchanged':b.sha(destination)==b.sha(b.ROOT/source)})
    v['reuse']=reused
    panel_checks=[]
    for canvas,states in v['layout_measurements'].items():
        for state,m in states.items():
            f=m['factor']
            im=np.asarray(Image.open(b.DERIVED/f"{v['task']}-{state}-{canvas}.png").convert('RGB'))
            for item in m['geometry']:
                if item.get('kind')!='screen':continue
                x,y,w,h=item['rect_su'];values=[]
                # straight-edge normal samples at both side midpoints; corners excluded
                for xx,yy,dx,dy in ((x,y+h/2,1,0),(x+w,y+h/2,-1,0),(x+w/2,y,0,1),(x+w/2,y+h,0,-1)):
                    pts=[]
                    for depth in (-2,.5,8):
                        px=round((xx+dx*depth)*f);py=round((yy+dy*depth)*f)
                        if 0<=py<im.shape[0] and 0<=px<im.shape[1]:pts.append(im[py,px].tolist())
                    if len(pts)==3:
                        outside,edge,body=pts
                        # Fractional one-su skin edges can lie between native pixels.
                        # Search their protected 2-su band, not a guessed centre pixel.
                        candidates=[]
                        for depth in np.arange(-.5,2.01,.25):
                            px=round((xx+dx*depth)*f);py=round((yy+dy*depth)*f)
                            if 0<=py<im.shape[0] and 0<=px<im.shape[1]:candidates.append(im[py,px].tolist())
                        edge=max(candidates,key=lambda color:max(b.contrast(color,outside),b.contrast(color,body)))
                        values.append({'outer_edge':b.contrast(edge,outside),'body_boundary':b.contrast(body,outside),'inner_edge':b.contrast(edge,body),
                                       'boundary':max(b.contrast(edge,outside),b.contrast(body,outside),b.contrast(edge,body))})
                panel_checks.append({'canvas':canvas,'state':state,'component':item.get('component'),'samples':values,
                                     'method':'native raster at four straight-edge midpoints, strongest sample in protected 2-su edge band; max inner/outer edge or body contrast'})
    v['panel_edge_contrast']=panel_checks
    panel_min=min(q['boundary'] for item in panel_checks for q in item['samples'])
    edge_acceptance=v['acceptance']['edges and icons >=3:1']
    edge_acceptance['measured']['native_panel_boundary_min']=panel_min
    edge_acceptance['passed']=edge_acceptance['measured']['active_button_boundary_min']>=3 and edge_acceptance['measured']['icons_passed'] and panel_min>=3
    if panel_min<3:
        v['limitations'].append('Accepted immutable HB-08 screen-panel edge/body boundary is below 3:1 at some native raster samples over the prescribed K1 veil; no skin/token override. Minimum '+str(round(panel_min,4))+':1. Full edge acceptance is not passed.')
    v['acceptance_pass']=all(a['passed'] for a in v['acceptance'].values())
    v['gray_state_differences']=[]
    for canvas,states in v['layout_measurements'].items():
        names=list(states)
        for left,right in zip(names,names[1:]):
            a=np.asarray(Image.open(b.DERIVED/f"{v['task']}-{left}-{canvas}-gray.png"))[:,:,:3]
            c=np.asarray(Image.open(b.DERIVED/f"{v['task']}-{right}-{canvas}-gray.png"))[:,:,:3]
            delta=np.abs(a.astype(int)-c.astype(int))[:,:,0]
            v['gray_state_differences'].append({'canvas':canvas,'a':left,'b':right,'changed_pixels':int((delta>0).sum()),'pixels_delta_ge20':int((delta>=20).sum()),'max_luma_delta':int(delta.max())})
    v['visual_review']=b.label_path(b.PACKAGE/'visual-review.json')
    v['limitations']=list(dict.fromkeys(v['limitations']+review['limitations']))
    # The full palette task is about procedural ink, not the real source photos.
    v['palette']['token_values']={k:d['hex'] for k,d in b.theme().tokens['colors'].items()}
    v['palette']['accepted_skins_sha256']=b.sha(b.SKINS/'slice-margins.json')
    v['palette']['numeric_full_canvas_deltaE']='not applicable to source-art composites; no claim that illustrations fit HUD tokens'
    b.dump(b.PACKAGE/'verification.json',v)
    readme=b.PACKAGE/'README.md'
    text=readme.read_text(encoding='utf-8')
    if 'Осмотр завершён:' not in text:
        text+='\nОсмотр завершён: все финальные PNG открыты в цвете и сером на четырёх холстах; пути и SHA-256 в visual-review.json. Независимая проверка: `python -B '+b.label_path(b.PACKAGE/'_tools/verify_outputs.py')+'`.\n'
        text+='\nУсловный RecoverButton: реальный myGames пуст, поэтому кнопки нет. При активной партии потребуется расширение Join-панели; на самом тесном S-холсте схема содержит пояснение слота в ledger, без рисования за безопасным полем. Это ограничение статической схемы сохранено явно.\n'
    if 'Растровые кромки панелей:' not in text:
        text+='\nРастровые кромки панелей: минимум границы '+f'{panel_min:.4f}:1'+', ниже 3:1 на части отсчётов поверх заданного K1 под вуалью. Это ограничение неизменяемых HB-08 и SC-01; цвета, скины и альфа сохранены. Критерий кромок и общая приёмка отмечены false; остальные результаты приведены отдельно.\n'
    b.guard(readme).write_text(text,encoding='utf-8');b.refresh_manifest()
if __name__=='__main__':main()
