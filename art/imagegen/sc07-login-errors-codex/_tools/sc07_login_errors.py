#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-07 extends the immutable, completed SC-06 layout; own-folder writes only."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import json
from pathlib import Path
import numpy as np
from PIL import Image
import sc06_login_form as base

STATES=('busy','error-credentials','error-server')


def draw_errors(c,state):
    if state not in STATES:raise ValueError(state)
    g=base.draw_shell(c)
    base.draw_field(c,'email',base.IDENTITY['email'],locked=state=='busy')
    base.draw_field(c,'password','' if state=='error-credentials' else base.MASK,
                    'focus' if state=='error-credentials' else 'normal',locked=state=='busy')
    x,y,w,h=g['submit'];ex,ey,ew,eh=g['error_zone']
    if state=='busy':
        # Keep the accepted disabled skin. Visible busy label explains the locked action.
        c.button(g['submit'],'','disabled',primary=True,why=('why.syncing',''),source='screens.login.busy')
        label=base.STRINGS['screens.login.busy'].upper()
        width=c.theme.font('type.button',c.factor).getlength(label)/c.factor
        group=32+12+width;left=x+(w-group)/2
        c.icon('loader-spinner',(left,y+8),32)
        c.text((left+44,y+h/2),label,'type.button','text.primary','lm',source='screens.login.busy')
        # Pointer centre is its hotspot, on the bottom edge at 70% of width.
        # Native accepted glyph straddles the button outline and the card below.
        cursor=(x+.7*w-16,y+h-16)
        c.icon('cursor-busy',cursor,32)
        c.geometry.append({'kind':'busy-tooltip','rect_su':list(g['submit']),
            'why':'why.syncing','text':base.REASONS['why.syncing'],'drawn':False,
            'visible_reason_key':'screens.login.busy','cursor_hotspot_su':[cursor[0]+16,cursor[1]+16],
            'keyboard_focus':False})
        lines=0
    elif state=='error-credentials':
        # Library owns disabled button; relocate its reason to the second error-zone row.
        c.button(g['submit'],base.STRINGS['screens.login.submit'],'disabled',primary=True,
                 why=('why.login.fields',''),source='screens.login.submit')
        c.icon('badge-refuse',(ex,ey),24)
        c.text((ex+32,ey+12),base.STRINGS['screens.login.error.credentials'],
               anchor='lm',source='screens.login.error.credentials')
        c.text((ex,ey+28),base.REASONS['why.login.fields'],'type.caption','text.secondary',source='why.login.fields')
        lines=2
    else:
        c.button(g['submit'],base.STRINGS['common.btn.retry'],'focus',primary=True,source='common.btn.retry')
        c.icon('resource-connection-lost',(ex,ey),24)
        c.text((ex+32,ey+12),base.STRINGS['screens.login.error.server'],anchor='lm',source='screens.login.error.server')
        lines=1
    c.geometry.append({'kind':'error-zone','rect_su':list(g['error_zone']),'lines':lines,'max_height_su':44})


def supplement():
    p=base.PACKAGE
    v=json.loads((p/'verification.json').read_text(encoding='utf-8'))
    t=base.theme();checks=[];red=[]
    for key,measurements in v['layout_measurements'].items():
        for state in STATES:
            image=np.asarray(Image.open(base.DERIVED/f'SC-07-{state}-{key}.png'))[:,:,:3]
            m=measurements[state];allowed_red=np.zeros(image.shape[:2],bool);screen=np.zeros_like(allowed_red)
            f=base.Viewport.preset(key.split('-')[0],int(key.split('-')[1])).factor
            underlay=None
            if state=='busy':
                vp=base.Viewport.preset(key.split('-')[0],int(key.split('-')[1]))
                native=base.LoginCanvas(vp,t,Image.open(base.ROOT/base.FRAME))
                draw_errors(native,state)
                underlay=np.asarray(base.Canvas.finish(native).convert('RGBA'))[:,:,:3]
            for item in m['geometry']:
                if item['kind']!='screen':continue
                x,y,w,h=item['rect_su'];pad=max(2,round(8*f))
                screen[round(y*f)+pad:round((y+h)*f)-pad,round(x*f)+pad:round((x+w)*f)-pad]=True
            for icon in m['icons']:
                x,y=icon['position_px'];n=icon['size_px'];crop=image[y:y+n,x:x+n]
                if icon['name'] in ('badge-refuse','resource-connection-lost'):
                    allowed_red[y:y+n,x:x+n]=True
                # Measure actual native-pixel print cores; dark outer keyline excluded.
                reference=t.color('panel.bg') if state!='busy' else next(i for i in m['geometry'] if i['kind']=='button')['fill']
                ratios=[]
                for name in ('card.glyph','card.cream','text.secondary','state.error'):
                    ink=t.color(name)
                    exact=np.all(crop==ink,axis=2)
                    # The 18 px connection X has no fully covered red pixel.
                    # Keep its near-solid raster pixels and report measured ink honestly.
                    near=np.sqrt(((crop.astype(float)-ink)**2).sum(2))<=20
                    selected=exact if exact.any() else near
                    count=int(selected.sum())
                    if count:
                        colors=np.unique(crop[selected],axis=0)
                        measured=min(base.contrast(color,reference) for color in colors)
                        if icon['name']=='cursor-busy':
                            backgrounds=underlay[y:y+n,x:x+n]
                            pairs=np.unique(np.concatenate((crop[selected],backgrounds[selected]),axis=1),axis=0)
                            measured=min(base.contrast(pair[:3],pair[3:]) for pair in pairs)
                        ratios.append({'token':name,'core_pixels':count,'exact_token_pixels':int(exact.sum()),
                            'actual_ink_min_contrast':measured,
                            'ratio':measured,
                            'token_contrast':base.contrast(ink,reference)})
                assert ratios,'No semantic print core at native size'
                check={'canvas':key,'state':state,'name':icon['name'],'size_su':icon['size_su'],
                       'size_px':n,'cores':ratios,'background':reference,'passed':min(r['ratio'] for r in ratios)>=3,
                       'note':'Semantic glyph/edge print against placement surface; source shape unchanged, keyline/AA excluded.'}
                if icon['name']=='cursor-busy':
                    check['background']='actual native raster before icons: button, outline, card'
                    check['note']='Semantic cursor cores measured pixelwise against the real two-surface underlay; no constant-background assumption.'
                checks.append(check)
            rgb=image.astype(int);red_pixels=screen&(rgb[:,:,0]>130)&(rgb[:,:,0]>rgb[:,:,1]*1.4)&(rgb[:,:,0]>rgb[:,:,2]*1.4)
            red.append({'canvas':key,'state':state,'red_pixels':int(red_pixels.sum()),
                        'outside_accepted_X_icons_pixels':int((red_pixels&~allowed_red).sum()),
                        'passed':not bool((red_pixels&~allowed_red).any()),
                        'method':'Red-dominant rendered pixels in opaque screen interiors; accepted badge/refuse and connection-loss icon rectangles only.'})
    v['icon_contrast']={'measurements':checks,'passed':all(c['passed'] for c in checks)}
    v['red_signs_only']={'measurements':red,'passed':all(c['passed'] for c in red)}
    v['acceptance']['red only in X and connection X']={'passed':v['red_signs_only']['passed'],
        'measured':red,'expected':'0 red UI pixels outside accepted X icons','note':'Source accepted glyphs pasted unchanged; no red text or red panel/button fill.'}
    v['acceptance']['edges and icons >=3:1']['measured']['icons']=v['icon_contrast']
    v['acceptance']['edges and icons >=3:1']['passed'] &= v['icon_contrast']['passed']
    v['acceptance_pass']=all(a['passed'] for a in v['acceptance'].values())
    v['sc06_reuse']={'source':'art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py',
                    'sha256':base.sha(p/'_tools/sc06_login_form.py'),'copied_unchanged':True,
                    'extension':'_tools/sc07_login_errors.py'}
    # Per-canvas tooltip and icon rectangles, alongside the immutable base rectangles.
    geo=json.loads((p/'layout-geometry.json').read_text(encoding='utf-8'))
    for key,m in v['layout_measurements'].items():
        geo[key]['state_geometry']={s:{'icons':m[s]['icons'],
            'tooltip':[i for i in m[s]['geometry'] if i['kind']=='busy-tooltip'],
            'focus_components':m[s]['layout']['focused_components']} for s in STATES}
    base.dump(p/'layout-geometry.json',geo)
    base.dump(p/'verification.json',v);base.refresh_manifest()
    print(json.dumps({'icon_contrast_pass':v['icon_contrast']['passed'],
                      'red_signs_only_pass':v['red_signs_only']['passed'],
                      'icons_720p_150':[c['size_px'] for c in checks if c['canvas']=='720p-150'],
                      'sc06_copy_sha256':v['sc06_reuse']['sha256']},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    base.build('SC-07',STATES,draw_errors)
    supplement()
