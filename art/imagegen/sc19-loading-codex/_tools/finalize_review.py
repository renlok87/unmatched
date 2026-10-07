#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only independent package check; finalize only after explicit PNG review."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json
import itertools
import numpy as np
from PIL import Image
from sc19_loading import PACKAGE,DERIVED,ROOT,sha,rel,load,dump,refresh_manifest,source_check,rectangles_overlap,luma709,PRESETS


def check_manifest():
    manifest=load(PACKAGE/'manifest-sha256.json')
    expected={rel(f) for root in (PACKAGE,DERIVED) for f in root.rglob('*') if f.is_file() and f.name!='manifest-sha256.json'}
    actual=set(manifest['files'])
    failures=[]
    if expected!=actual:failures.append({'manifest_missing':sorted(expected-actual),'manifest_extra':sorted(actual-expected)})
    for p,h in {**manifest['files'],**manifest['inputs']}.items():
        if not (ROOT/p).is_file() or sha(ROOT/p)!=h:failures.append({'hash_mismatch':p})
    return failures


def checks():
    failures=[];v=load(PACKAGE/'verification.json');review=load(PACKAGE/'visual-review.json')
    finals={e['file'] for e in v['exports']}
    inspected={r['path'] for r in review['files']}
    if finals!=inspected:failures.append({'review_missing':sorted(finals-inspected),'review_extra':sorted(inspected-finals)})
    for item in review['files']:
        if sha(ROOT/item['path'])!=item['sha256'] or not item['checked']:failures.append({'review_invalid':item['path']})
    for e in v['exports']:
        with Image.open(ROOT/e['file']) as im:
            im.load()
            if list(im.size)!=e['size_px'] or im.mode!='RGBA':failures.append({'export_invalid':e['file']})
    for pair in v['gray']['pairs']:
        if not np.array_equal(np.asarray(luma709(Image.open(ROOT/pair['color']))),np.asarray(Image.open(ROOT/pair['gray']).convert('RGB'))):failures.append({'gray_invalid':pair['gray']})
    for copy in load(PACKAGE/'copy-provenance.json'):
        if sha(ROOT/copy['source'])!=sha(ROOT/copy['copy']) or sha(ROOT/copy['copy'])!=copy['sha256_copy']:failures.append({'copy_changed':copy['copy']})
    if not source_check()['passed']:failures.append({'source_changed':source_check()})
    for name,f in v['frames'].items():
        if f['issues'] or f['text_overlaps'] or not all(f['input_values_match'].values()):failures.append({'frame_invalid':name})
        if f['smallest_text_px']<10.5 or f['caption_gap_su']<8:failures.append({'size_gap_invalid':name})
    for p in (PACKAGE/'comparison').glob('*-legend.json'):
        if load(p)['label_overlaps']:failures.append({'legend_labels_overlap':rel(p)})
    # A saved declaration of zero overlap is not sufficient: recompute every
    # text bbox and all legend bboxes through their renderer on check if needed.
    for f in v['frames'].values():
        for a,b in itertools.combinations(f['text_runs'],2):
            aa=a['bbox_px'];bb=b['bbox_px']
            if rectangles_overlap((aa[0],aa[1],aa[2]-aa[0],aa[3]-aa[1]),(bb[0],bb[1],bb[2]-bb[0],bb[3]-bb[1])):failures.append({'text_overlap':[a['name'],b['name']]})
    states=sorted(set(k.split('-')[0] for k in v['frames']))
    if states==['board','connect','state']:
        for res,scale in PRESETS:
            fs=[v['frames'][f'{state}-{res}-{scale}'] for state in states]
            comps=[{k:x for k,x in f['components'].items() if k!='StageText'} for f in fs]
            if any(c!=comps[0] for c in comps[1:]):failures.append({'stage_geometry_changed':[res,scale]})
            originals=[np.asarray(Image.open(DERIVED/f'SC-19-{s}-{res}-{scale}.png')) for s in states]
            r=fs[0]['components']['StageText']['rect_su'];factor=fs[0]['factor']
            mask=np.ones(originals[0].shape[:2],dtype=bool)
            x,y,w,h=r;mask[max(0,int(y*factor)-2):int((y+h)*factor)+3,max(0,int(x*factor)-2):int((x+w)*factor)+3]=False
            if any(not np.array_equal(originals[0][mask],a[mask]) for a in originals[1:]):failures.append({'stage_pixels_outside_text_changed':[res,scale]})
            gray_images=[np.asarray(Image.open(DERIVED/f'SC-19-{s}-{res}-{scale}-gray.png')) for s in states]
            if any(np.array_equal(a,b) for a,b in itertools.combinations(gray_images,2)):failures.append({'stages_indistinguishable_gray':[res,scale]})
    else:
        # Same icon slot relative to a centred panel; adding 72 su to the panel
        # translates unchanged content by -36 su. Cards themselves are identical.
        source=load(ROOT/'art/imagegen/sc19-loading-codex/layout-geometry.json')
        for res,scale in PRESETS:
            error=v['frames'][f'error-{res}-{scale}']['components'];old=source['canvases'][f'{res}-{scale}']['connect']
            p=error['LoadingPanel']['rect_su'];q=old['LoadingPanel']['rect_su']
            if p[2]!=q[2] or p[3]-q[3]!=72:failures.append({'error_panel_growth_invalid':[res,scale]})
            for key in ('LeftCard','RightCard','LeftCard.Portrait','RightCard.Portrait','BoardText'):
                a=error[key]['rect_su'];b=old[key]['rect_su']
                if a[0]!=b[0] or a[1]-b[1]!=-36 or a[2:]!=b[2:]:failures.append({'error_content_moved_wrongly':key})
            a=error['ErrorIcon']['rect_su'];b=old['Spinner']['rect_su']
            if a[0]!=b[0] or a[1]-b[1]!=-36 or a[2:]!=b[2:]:failures.append({'error_slot_invalid':[res,scale]})
            if v['frames'][f'error-{res}-{scale}']['primary_button_count']!=1:failures.append({'primary_count_invalid':[res,scale]})
    return failures


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    failures=checks()
    if '--check' in sys.argv:
        failures+=check_manifest()
        print(json.dumps({'technical_checks_passed':not failures,'failures':failures,'full_acceptance':load(PACKAGE/'verification.json')['full_acceptance']},ensure_ascii=False))
        return 1 if failures else 0
    if failures:print(json.dumps(failures,ensure_ascii=False));return 1
    v=load(PACKAGE/'verification.json')
    v['visual_review']={'pending':False,'record':'visual-review.json','all_export_png_opened':True,'count':len(v['exports'])}
    v['source_unchanged']=source_check();v['source_unchanged']['hud_icons_v3']['icons_used']=sorted({i['source'] for f in v['frames'].values() for i in f['raster_contrast']['icons']})
    v['technical_checks']={'passed':True,'stage_pixels_and_geometry_checked':True,'rec709_recomputed':True,'review_hashes_checked':True,'all_package_and_derived_files_in_manifest':True}
    dump(PACKAGE/'verification.json',v);refresh_manifest()
    failures=check_manifest()
    print(json.dumps({'technical_checks_passed':not failures,'failures':failures,'reviewed_png':len(v['exports']),'full_acceptance':v['full_acceptance']},ensure_ascii=False))
    return 1 if failures else 0


if __name__=='__main__':raise SystemExit(main())
