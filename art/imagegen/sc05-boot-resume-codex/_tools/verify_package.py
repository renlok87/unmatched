#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent integrity, sources, grayscale, bounded UI palette and layout checks.

Numeric acceptance may fail while the package integrity succeeds. No engine/git.
"""
import importlib
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.dont_write_bytecode=True
import sc03_boot_loading as b


def lab(rgb):
    v=np.asarray(rgb,float)/255
    v=np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
    xyz=v@np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])
    xyz/=np.array([.95047,1,1.08883]);f=np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)


def palette_audit(package,derived,v):
    t=b.theme();navy=np.array(t.color('panel.bg'))
    colors=list(t.color(k) for k in t.tokens['colors'])
    # Opaque flats and alpha OVER colors of the unchanged, accepted source art.
    for p in sorted((b.ROOT/(b.SKINS+'vector')).rglob('*.png')):
        a=np.array(Image.open(p).convert('RGBA'));flat=np.unique(a.reshape(-1,4),axis=0)
        flat=flat[flat[:,3]>0]
        colors.extend(np.rint(flat[:,:3]*flat[:,3:]/255+navy*(1-flat[:,3:]/255)).astype('uint8'))
        colors.extend(flat[flat[:,3]>=230,:3])
    for g in v['hud_icons_v3']['icons_used']:
        name=g['name'];px=g['size_px'];path=b.ROOT/(b.ICONS+f'sizes/{name}-{px}.png')
        if path.exists(): im=Image.open(path)
        else:
            from draw_icons_v3_snapshot import render
            im=render(name,px)
        colors.extend(np.array(im.convert('RGBA')).reshape(-1,4)[:,:3])
    allowed=np.unique(np.asarray(colors,dtype='uint8'),axis=0);allowed_lab=lab(allowed)
    count=bad=0;bad_colors={}
    for key,audit in v['layout_measurements'].items():
        p=derived/(v['card']+'-'+key+'.png');rgb=np.array(Image.open(p).convert('RGB'))
        mask=b.mask_rects([g['rect_su'] for g in audit['geometry'] if g['kind'] in ('screen','modal','button')],
                           b.Viewport.preset('1080p' if '1080p' in key else '720p',150 if key.endswith('-150') else 100))
        flat=np.ones(mask.shape,bool)
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                flat &= np.all(rgb==np.roll(rgb,(dy,dx),(0,1)),axis=2)
        flat[[0,-1],:]=False;flat[:,[0,-1]]=False
        samples=rgb[mask&flat];unique,counts=np.unique(samples,axis=0,return_counts=True)
        dist=np.sqrt(((lab(unique)[:,None,:]-allowed_lab[None,:,:])**2).sum(axis=2)).min(axis=1)
        count+=len(samples);bad+=int(counts[dist>3].sum())
        for color,n in zip(unique[dist>3],counts[dist>3]):bad_colors[str(color.tolist())]=bad_colors.get(str(color.tolist()),0)+int(n)
    return {'ui_opaque_outside_palette_fraction':bad/count if count else 0,'sample_count':count,
            'outside_pixels':bad,'outside_colors':bad_colors,'deltaE76_threshold':3,
            'method':'Uniform 3×3 flat RGB neighborhoods within UI geometry; accepted skin flats and alpha OVER + exact token colors + native v3 flats; excludes scene and AA'}


def main():
    package=Path(__file__).resolve().parents[1];set_name=package.name.removesuffix('-codex')
    derived=b.ROOT/('scraped-data/derived/'+package.name)
    card={'sc03-boot-loading':'SC-03','sc04-boot-error':'SC-04','sc05-boot-resume':'SC-05'}[set_name]
    extras=[] if card=='SC-03' else ['art/imagegen/sc03-boot-loading-codex/_tools/sc03_boot_loading.py']
    if card=='SC-05':extras.append(b.MATRIX)
    before=json.loads((package/'source-hashes-before.json').read_text(encoding='utf-8'))
    assert before==b.source_inputs(card,extras),'Sources changed'
    manifest=json.loads((package/'manifest-sha256.json').read_text(encoding='utf-8'))
    actual={b.rel(p):b.sha(p) for folder in (package,derived) for p in folder.rglob('*')
            if p.is_file() and p!=package/'manifest-sha256.json'}
    assert actual==manifest['files'],'Manifest incomplete or stale'
    assert b.sha(package/'_tools/screen_mockup_base.py')==b.sha(b.ROOT/(b.SC01+'_tools/screen_mockup_base.py'))
    assert b.sha(package/'_tools/draw_icons_v3_snapshot.py')==b.sha(b.ROOT/(b.ICONS+'_tools/draw_icons.py'))
    if card!='SC-03':assert b.sha(package/'_tools/sc03_boot_loading.py')==b.sha(b.ROOT/extras[0])
    v=json.loads((package/'verification.json').read_text(encoding='utf-8'));v['card']=card
    if (package/'fix1-before.json').exists():
        def area(a,r):
            return max(0,min(a[0]+a[2],r[0]+r[2])-max(a[0],r[0]))*max(0,min(a[1]+a[3],r[1]+r[3])-max(a[1],r[1]))
        for path,o in v['overlay_measurements'].items():
            pairs=0
            for i,label in enumerate(o['annotations']):
                pairs+=sum(area(label['rect_su'],other['rect_su'])>0 for other in o['annotations'][i+1:])
                pairs+=sum(area(label['rect_su'],obstacle['rect_su'])>0 for obstacle in o['obstacles'])
                element=next((e for e in o['labelled_elements'] if e['name']==label['element']),None)
                if element:assert area(label['rect_su'],element['rect_su'])==0
            assert pairs==o['overlay_annotation_overlaps']==v['overlay_annotation_overlaps'][path]==0
            assert o['labels_within_safe_field']
            names={e['name'] for e in o['labelled_elements']}
            required=({'ResumeModal','ResumeTitle','ResumeLine','LobbyButton','ResumeButton','ResumeSpinner · resuming','WhyText · resuming'} if card=='SC-05' else
                      {'Wordmark','Progress'} | ({'ErrorBanner','ErrorIcon','ErrorText','RetryButton','WhyText · retrying'} if card=='SC-04' else {'StageText · session','StageText · heroes','StageText · boards'}))
            assert required<=names,(path,names)
            if card=='SC-05':assert not {'Wordmark','Progress','StageText'}&names
        b.fix1_audit(package,derived,card,v,v['overlay_measurements'])
        if card=='SC-04':
            for a in v['layout_measurements'].values():
                gs=a['geometry'];f=a['px_per_su']
                banner=next(g['rect_su'] for g in gs if g.get('label')=='error-capsule')
                caption=next(g['rect_su'] for g in gs if g.get('label')=='stage-caption')
                icon=next(g['rect_su'] for g in gs if g['kind']=='icon')
                button=next(g['rect_su'] for g in gs if g['kind']=='button')
                assert banner[2:]==[480,104] and abs(banner[1]-caption[1]-caption[3]-16)<1e-6
                assert icon==[banner[0]+16,banner[1]+16,48,48]
                assert button==[banner[0]+296,banner[1]+16,168,48]
                text=next(g['rect_su'] for g in gs if g.get('label')=='screens.boot.error.server')
                assert abs(text[0]-icon[0]-60)<=.3/f and abs(text[1]+text[3]/2-icon[1]-24)<=.3/f
                why=next((g['rect_su'] for g in gs if g.get('label')=='why.syncing'),None)
                if why:assert abs(why[0]+why[2]-button[0]-button[2])<=.3/f and abs(why[1]-button[1]-54)<=.3/f
            assert v['acceptance']['the 48 su icon reads in grayscale']['passed']
    originals=[p for folder in (package,derived) for p in sorted(folder.rglob('*.png')) if not p.stem.endswith('-gray')]
    for p in originals:
        gray=p.with_stem(p.stem+'-gray');assert gray.exists()
        with Image.open(p) as a,Image.open(gray) as g:
            assert np.array_equal(np.array(b.luma709(a)),np.array(g.convert('RGB'))),str(gray)
    assert json.loads((package/'generation-records.json').read_text())==[]
    for a in v['layout_measurements'].values():
        assert a['text_within_frame'] and a['buttons_margin_32'] and a['minimum_text_px']>=10.5
        assert a['primary_buttons']==(0 if card=='SC-03' else 1)
        assert a['overlap']['persistent']['figures_px2']==a['overlap']['persistent']['spaces_px2']==0
        assert all(g['why'] for g in a['geometry'] if g['kind']=='button' and g['state']=='disabled')
    review=package/'visual-review.json'
    if review.exists():
        rv=json.loads(review.read_text(encoding='utf-8'))
        assert {x['path']:x['sha256'] for x in rv['files']}=={b.rel(p):b.sha(p) for folder in (package,derived) for p in folder.rglob('*.png')},'Visual review incomplete'
    v['palette']=palette_audit(package,derived,v)
    assert v['palette']['outside_pixels']==0, v['palette']
    v['integrity_verification']={'passed':True,'input_files':len(before['inputs']),
        'v3_files':before['hud_icons_v3']['count'],'manifest_files':len(actual),
        'gray_pairs_exact':len(originals),'snapshots_byte_identical':True,'visual_review_complete':review.exists(),
        'palette_passed':True,'text_bounds_and_sizes_passed':True,
        'fix1_overlay_overlap_recomputed':True,'fix1_final_hashes_recomputed':True,
        'note':'Integrity pass is separate from numerical visual acceptance; boundary failures remain recorded.'}
    b.dump(package/'verification.json',v,package,derived);b.refresh_manifest(package,derived,card)
    from contract_audit import finalize
    finalize(package,derived,card)
    # Re-read all final hashes after report mutation.
    final=json.loads((package/'manifest-sha256.json').read_text(encoding='utf-8'))
    assert all(b.sha(b.ROOT/p)==h for p,h in final['files'].items())
    print(json.dumps({'card':card,'integrity_pass':True,'palette_outside':v['palette']['outside_pixels'],
                      'gray_pairs':len(originals),'visual_review_complete':review.exists(),'acceptance_pass':v['acceptance_pass']},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
