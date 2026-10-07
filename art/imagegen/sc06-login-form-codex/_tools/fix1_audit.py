#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Recheck fix1 scope and the implementation overlays; own-package writes only."""
import sys
sys.dont_write_bytecode=True
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
import sc06_login_form as b


def preserved_digest(path,before):
    key=path.stem.replace('-gray','').rsplit('-',2)
    vp=b.Viewport.preset(key[-2],int(key[-1]));canvas_key='-'.join(key[-2:])
    a=np.array(Image.open(path).convert('RGBA'));mask=np.ones(a.shape[:2],bool)
    rect=before['rectangles_before'][canvas_key]['rectangles_su']['caption']
    for offset in range(0,a.shape[0],vp.height):
        x,y,w,h=rect
        mask[max(0,round(y*vp.factor)-8)+offset:min(vp.height,round((y+h)*vp.factor)+8)+offset,
             max(0,round(x*vp.factor)-8):round((x+w)*vp.factor)+8]=False
    # The SC-07 correction moves just the busy cursor, in addition to the caption.
    if before.get('task')=='SC-07' and ('-busy-' in path.name or '-comparison-' in path.name):
        sx,sy,sw,sh=before['rectangles_before'][canvas_key]['rectangles_su']['submit']
        for x,y in ((sx+sw-56,sy+8),(sx+.7*sw-16,sy+sh-16)):
            mask[round(y*vp.factor):round((y+32)*vp.factor),
                 round(x*vp.factor):round((x+32)*vp.factor)]=False
    return hashlib.sha256(a[mask].tobytes()).hexdigest()


def audit():
    p=b.PACKAGE;v=json.loads((p/'verification.json').read_text(encoding='utf-8'))
    before=json.loads((p/'fix1-before.json').read_text(encoding='utf-8'))
    preserved={n:preserved_digest(b.ROOT/n,before)==digest
               for n,digest in before['unchanged_region_sha256'].items()}
    assert all(preserved.values()),[n for n,ok in preserved.items() if not ok]
    geometries=json.loads((p/'layout-geometry.json').read_text(encoding='utf-8'))
    unchanged_rects={key:all(rect==geometries[key]['rectangles_su'][name]
                       for name,rect in old['rectangles_su'].items() if name!='caption')
                     for key,old in before['rectangles_before'].items()}
    assert all(unchanged_rects.values())
    overlays={}
    for key,geo in geometries.items():
        vp=b.Viewport.preset(*[key.split('-')[0],int(key.split('-')[1])])
        c=b.overlay(vp,b.theme(),v['task']);im=c.finish()
        path=p/'comparison'/f'{v["task"]}-overlay-{key}.png'
        assert np.array_equal(np.asarray(im),np.asarray(Image.open(path))),str(path)
        required={'Title','EmailLabel','EmailBox','PasswordLabel','PasswordBox',
                  'RevealButton','SubmitButton','ErrorText','LangRu','LangEn','OverviewCaption'}
        names={e['bind_widget'] for e in c.overlay_audit['labelled_elements']}
        assert required<=names
        if v['task']=='SC-07':assert {'Spinner','SubmitLabel','CursorBusy','ErrorIcon','WhyText','RetryButton'}<=names
        for suffix in ('','-gray'):
            name=f'{v["task"]}-overlay-{key}{suffix}.png'
            assert c.overlay_audit==v['overlay_measurements'][name]
            overlays[name]=c.overlay_audit['overlay_annotation_overlaps']
        expected=b.theme().font('type.caption',vp.factor*4).getlength(b.CAPTION)/(vp.factor*4)+24
        assert abs(geo['rectangles_su']['caption'][2]-expected)<1e-9
    v['fix1']={'before':'fix1-before.json','unchanged_final_regions':preserved,
               'unchanged_form_rectangles':unchanged_rects,'overlay_annotation_overlaps':overlays,
               'caption_width_rule':'text width + 2 * 12 su',
               'scope_pass':True,'note':'All final pixels outside old caption bounds (+8px AA guard) and, in SC-07 busy only, old/new cursor rectangles, are byte-identical.'}
    v['acceptance']['fix1 preserves accepted form']={'passed':True,'measured':v['fix1'],
          'expected':'unchanged form geometry and final pixels outside explicitly corrected regions'}
    v['acceptance_pass']=all(a['passed'] for a in v['acceptance'].values())
    b.dump(p/'verification.json',v);b.refresh_manifest()
    print(json.dumps({'fix1_scope':'PASS','preserved_pngs':len(preserved),'overlays':overlays},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');audit()
