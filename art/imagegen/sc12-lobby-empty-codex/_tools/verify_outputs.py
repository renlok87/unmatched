#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only independent package integrity check; -B prevents bytecode writes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image

PACKAGE=Path(__file__).resolve().parents[1]
ROOT=PACKAGE.parents[2]
DERIVED=ROOT/'scraped-data/derived'/PACKAGE.name
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def path(p):return ROOT/p if not Path(p).is_absolute() else Path(p)
def verify():
    errors=[];checks=0
    manifest=load(PACKAGE/'manifest-sha256.json')['files']
    for p,h in manifest.items():
        checks+=1
        if not path(p).is_file() or sha(path(p))!=h:errors.append('hash '+p)
    owned=[p.relative_to(ROOT).as_posix() for root in (PACKAGE,DERIVED) for p in root.rglob('*') if p.is_file() and p!=PACKAGE/'manifest-sha256.json']
    for p in owned:
        checks+=1
        if p not in manifest:errors.append('unlisted '+p)
    before=load(PACKAGE/'source-hashes-before.json')['files']
    for p,h in before.items():
        checks+=1
        if sha(path(p))!=h:errors.append('input changed '+p)
    now={p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    if now!={p for p in before if p.startswith('art/imagegen/hud-icons-v3/')}:errors.append('icon inventory changed')
    for source,copy in [('art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py','screen_mockup_base.py'),('art/imagegen/hud-icons-v3/_tools/draw_icons.py','draw_icons_v3_snapshot.py')]:
        checks+=1
        if sha(ROOT/source)!=sha(PACKAGE/'_tools'/copy):errors.append('copy mismatch '+copy)
    if not PACKAGE.name.startswith('sc08'):
        checks+=1
        if sha(ROOT/'art/imagegen/sc08-lobby-list-codex/_tools/sc08_lobby_list.py')!=sha(PACKAGE/'_tools/sc08_lobby_list.py'):errors.append('SC-08 copy mismatch')
    if PACKAGE.name.startswith('sc10'):
        checks+=1
        if sha(ROOT/'art/imagegen/sc09-lobby-create-codex/_tools/sc09_lobby_create.py')!=sha(PACKAGE/'_tools/sc09_lobby_create.py'):errors.append('SC-09 copy mismatch')
    v=load(PACKAGE/'verification.json')
    for pair in v['gray']:
        checks+=1
        with Image.open(path(pair['color'])) as c,Image.open(path(pair['gray'])) as g:
            rgb=np.asarray(c.convert('RGB'),dtype=float);expected=np.rint(rgb@np.array([.2126,.7152,.0722])).astype(np.uint8)
            actual=np.asarray(g.convert('RGB'))
            if not np.all(actual==expected[:,:,None]):errors.append('gray mismatch '+pair['gray'])
    for exp in v['exports']:
        checks+=1
        with Image.open(path(exp['path'])) as im:
            im.verify()
        with Image.open(path(exp['path'])) as im:
            if list(im.size)!=exp['size'] or im.mode!='RGBA':errors.append('PNG metadata '+exp['path'])
    for key,states in v['layout_measurements'].items():
        for state,m in states.items():
            checks+=1
            if m['primary_button_count']!=1:errors.append('primary '+key+' '+state)
            if m['text_overlap'] or m['clipped_text']:errors.append('layout '+key+' '+state)
    review=PACKAGE/'visual-review.json'
    if review.exists():
        rv=load(review);checks+=1
        if {r['path'] for r in rv['files']}!={r['path'] for r in v['exports']}:errors.append('incomplete visual review')
        for r in rv['files']:
            if sha(path(r['path']))!=r['sha256']:errors.append('stale visual review '+r['path'])
    unmet=[]
    if 'fix1' in v:
        fix=v['fix1']
        def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        for item in fix['changed_files']:
            checks+=1
            p=path(item['path']);scope=item['after_hash_scope']
            if scope=='canonical JSON without fix1':actual=digest({k:value for k,value in v.items() if k!='fix1'})
            elif scope=='canonical JSON without files[verification.json]':
                projected=load(PACKAGE/'manifest-sha256.json');projected['files'].pop((PACKAGE/'verification.json').relative_to(ROOT).as_posix(),None);actual=digest(projected)
            else:actual=sha(p) if p.exists() else None
            if actual!=item['sha256_after']:errors.append('fix1 after hash '+item['path'])
        for key,states in v['layout_measurements'].items():
            for state,m in states.items():
                checks+=1
                if any(q['minimum_su']<8-1e-6 for q in m['row_content_insets']):errors.append('row inset '+key+' '+state)
        for key,item in v['overlay_review'].items():
            checks+=1
            if item['label_overlap_pairs']:errors.append('overlay '+key)
        baseline=load(PACKAGE/'fix1-baseline.json')['files']
        for p,h in baseline.items():
            if p.startswith(DERIVED.relative_to(ROOT).as_posix()+'/inputs/'):
                checks+=1
                if sha(path(p))!=h:errors.append('capture modified '+p)
        geom=load(PACKAGE/'layout-geometry.json')
        for key,item in geom.items():
            g=item['rectangles'];r=g['RecoverButton'];panel=g['CodeColumn'];checks+=1
            if r and not (r[0]>=panel[0] and r[1]>=panel[1] and r[0]+r[2]<=panel[0]+panel[2] and r[1]+r[3]<=panel[1]+panel[3]):errors.append('recover outside column '+key)
    for key,a in v['acceptance'].items():
        checks+=1
        if not a['passed']:unmet.append(key)
    if unmet and not v['limitations']:errors.append('Unreported acceptance limitation')
    print(json.dumps({'package':PACKAGE.name,'checks':checks,'errors':errors,'passed':not errors,'acceptance_pass':not unmet,'unmet_acceptance':unmet},ensure_ascii=False))
    return 1 if errors else 0
if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.exit(verify())
