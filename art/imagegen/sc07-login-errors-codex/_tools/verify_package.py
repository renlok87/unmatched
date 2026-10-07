#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent read-only completeness/integrity checks; no Git or engine access."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image

PACKAGE=Path(__file__).resolve().parents[1]
ROOT=PACKAGE.parents[2]
DERIVED=ROOT/'scraped-data/derived'/PACKAGE.name


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def info(p):return {'sha256':sha(p),'bytes':p.stat().st_size}


def verify():
    m=load(PACKAGE/'manifest-sha256.json');v=load(PACKAGE/'verification.json')
    required={'source_unchanged','exports','palette','gray','sizes','outside_folder','acceptance'}
    assert required<=v.keys()
    assert v['source_unchanged'] and v['outside_folder']==[]
    assert load(PACKAGE/'generation-records.json')==[]
    expected={p.relative_to(ROOT).as_posix() for d in (PACKAGE,DERIVED) for p in d.rglob('*') if p.is_file() and p!=PACKAGE/'manifest-sha256.json'}
    assert set(m['outputs'])==expected, 'Manifest file coverage'
    for name,value in m['outputs'].items():assert info(ROOT/name)==value,name
    for name,value in m['sources'].items():
        p=Path(name) if Path(name).is_absolute() else ROOT/name
        assert info(p)==value,name
    tree={p.relative_to(ROOT).as_posix():info(p) for p in sorted((ROOT/'art/imagegen/hud-icons-v3').rglob('*')) if p.is_file()}
    digest=hashlib.sha256(json.dumps(tree,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert digest==m['icon_tree']['tree_digest'] and len(tree)==m['icon_tree']['file_count']
    for name,value in m['icon_tree']['used_files'].items():assert info(ROOT/name)==value,name
    copies=[('screen_mockup_base.py',ROOT/'art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py'),
            ('draw_icons_v3_snapshot.py',ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py')]
    if v['task']=='SC-07':copies.append(('sc06_login_form.py',ROOT/'art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py'))
    for name,source in copies:assert sha(PACKAGE/'_tools'/name)==sha(source),name
    pngs={p.relative_to(ROOT).as_posix() for d in (PACKAGE,DERIVED) for p in d.rglob('*.png')}
    assert pngs=={e['path'] for e in v['exports']},'PNG export coverage'
    for e in v['exports']:
        p=ROOT/e['path']
        with Image.open(p) as im:
            assert list(im.size)==e['size_px'] and im.mode=='RGBA',str(p)
            if not p.stem.endswith('-gray'):
                gray=p.with_stem(p.stem+'-gray')
                a=np.asarray(im)[:,:,:3].astype(float)
                expected_luma=np.rint(a @ np.array([.2126,.7152,.0722])).astype(np.uint8)
                with Image.open(gray) as gm:
                    b=np.asarray(gm)
                    assert np.array_equal(expected_luma,b[:,:,0]) and np.array_equal(b[:,:,0],b[:,:,1]) and np.array_equal(b[:,:,0],b[:,:,2]),str(gray)
    assert v['palette']['passes'], 'Flat UI palette'
    import sc06_login_form as layout_base
    from fix1_audit import preserved_digest
    before=load(PACKAGE/'fix1-before.json')
    assert all(preserved_digest(ROOT/n,before)==h for n,h in before['unchanged_region_sha256'].items())
    assert v['fix1']['scope_pass']
    assert len(v['overlay_measurements'])==8
    for key in ('1080p-100','1080p-150','720p-100','720p-150'):
        vp=layout_base.Viewport.preset(key.split('-')[0],int(key.split('-')[1]))
        ov=layout_base.overlay(vp,layout_base.theme(),v['task'])
        assert np.array_equal(np.asarray(ov.finish()),np.asarray(Image.open(PACKAGE/'comparison'/f"{v['task']}-overlay-{key}.png")))
        for suffix in ('','-gray'):
            measured=v['overlay_measurements'][f"{v['task']}-overlay-{key}{suffix}.png"]
            assert measured==ov.overlay_audit and measured['overlay_annotation_overlaps']==0 and not measured['clipped_labels']
    geo=load(PACKAGE/'layout-geometry.json')
    states=['empty','input'] if v['task']=='SC-06' else ['busy','error-credentials','error-server']
    for key,items in v['layout_measurements'].items():
        for state in states:
            p=DERIVED/f"{v['task']}-{state}-{key}.png";assert p.is_file()
            a=items[state]['layout'];assert a['card_su'][2:]==[480,420] and a['field_step_su']==88
            assert a['primary_count']==1 and a['all_text_within_canvas'] and a['card_content_fits'] and a['error_text_within_zone']
            assert a['minimum_text_su']>=14 and a['minimum_text_px']>=10.5
            assert a['caption_card_overlap_su2']==0 and a['caption_chip_overlap_su2']==0 and a['password_value_before_reveal']
            assert all(r['ratio']>=4.5 for r in items[state]['text_contrast'])
            assert items[state]['overlap']['persistent_panels']==[]
            assert all(s['kind']=='screen' and s['exempt'] for s in items[state]['overlap']['screen_layers'])
            fields={i['component']:i for i in items[state]['geometry'] if i['kind']=='field'}
            assert fields['password']['value'] in ('','••••••••')
            if state=='error-credentials':assert fields['password']['value']=='' and fields['password']['state']=='focus'
            if state in ('busy','error-server','input'):assert fields['password']['value']=='••••••••'
            if state=='busy':assert all(i['locked'] for i in fields.values()) and a['focused_components']==[]
            if state=='busy':
                cursor=next(i for i in items[state]['icons'] if i['name']=='cursor-busy')
                sx,sy,sw,sh=geo[key]['rectangles_su']['submit']
                cx,cy,cw,ch=cursor['rect_su']
                assert abs(cx+cw/2-(sx+.7*sw))<1e-9 and cy+ch/2==sy+sh
                assert cursor['size_px'] in (24,32,36,48) and cy<sy+sh<cy+ch
            if v['task']=='SC-07':
                import sc06_login_form as layout_base
                from sc07_login_errors import draw_errors
                vp=layout_base.Viewport.preset(key.split('-')[0],int(key.split('-')[1]))
                canvas=layout_base.LoginCanvas(vp,layout_base.theme(),Image.open(ROOT/layout_base.FRAME))
                draw_errors(canvas,state)
                # Native backdrop includes the genuine focus-skin antialias fringe.
                without_icons=layout_base.Canvas.finish(canvas).convert('RGBA')
            for icon in items[state]['icons']:
                assert icon['size_px']==icon['size_su']*geo[key]['px_per_su']
                assert 'NEAREST' not in icon['method']
                if v['task']=='SC-07':
                    n=icon['size_px']
                    if 'render(name, px)' in icon['method']:
                        from draw_icons_v3_snapshot import render
                        glyph=render(icon['name'],n).convert('RGBA')
                    else:
                        glyph=Image.open(ROOT/icon['source']).convert('RGBA')
                        if glyph.size!=(n,n):glyph=glyph.resize((n,n),Image.Resampling.LANCZOS)
                    x,y=icon['position_px']
                    patch=without_icons.crop((x,y,x+n,y+n));patch.alpha_composite(glyph)
                    with Image.open(p) as actual:
                        assert np.array_equal(np.asarray(actual.crop((x,y,x+n,y+n))),np.asarray(patch)), 'Native icon paste: '+icon['name']
    if v['task']=='SC-07':
        assert v['icon_contrast']['passed'] and v['red_signs_only']['passed']
        assert all(r['ratio']>=3 for c in v['icon_contrast']['measurements'] for r in c['cores'])
        assert all(c['outside_accepted_X_icons_pixels']==0 for c in v['red_signs_only']['measurements'])
    review=load(PACKAGE/'visual-review.json')
    assert review['completed'] and set(review['files'])==pngs, 'Actual visual inspection coverage'
    assert all(sha(ROOT/n)==h for n,h in review['files'].items()), 'Reviewed image hashes'
    assert v['visual_review']['completed']
    failing=[k for k,a in v['acceptance'].items() if not a['passed']]
    assert failing==['edges and icons >=3:1'], failing
    print(json.dumps({'integrity':'PASS','files':len(expected),'pngs':len(pngs),'source_unchanged':True,
        'acceptance_pass':v['acceptance_pass'],'remaining':failing},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');verify()
