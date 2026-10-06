#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent read-only verification of published SC-01 files and library states."""
from pathlib import Path
import json
import sys

import numpy as np
from PIL import Image

from source_audit import ROOT, PACKAGE, FONT_ROOT, sha256
from screen_mockup_base import Canvas, Theme, Viewport, draw_base_modal, draw_screen, luma709
from fix1_audit import inventory, compact_sources


def main():
    manifest=json.loads((PACKAGE/'manifest-sha256.json').read_text(encoding='utf-8'))
    verification=json.loads((PACKAGE/'verification.json').read_text(encoding='utf-8'))
    failures=[]
    for name,data in manifest['outputs'].items():
        path=ROOT/name
        if not path.is_file() or sha256(path)!=data['sha256']:
            failures.append('Output hash: '+name)
    actual={p.relative_to(ROOT).as_posix() for d in (PACKAGE,ROOT/'scraped-data/derived/sc01-screen-base-codex')
        for p in d.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
    if actual!=set(manifest['outputs']):failures.append('Output inventory mismatch')
    live_source_drift=[]
    for name,data in manifest['sources'].items():
        original=Path(name) if Path(name).is_absolute() else ROOT/name
        if not original.is_file() or sha256(original)!=data['sha256']:live_source_drift.append(name)
        path=ROOT/data['snapshot'] if 'snapshot' in data else original
        if not path.is_file() or sha256(path)!=data['sha256']:failures.append('Render input hash: '+name)
    icon_now=compact_sources(inventory())['icons']
    if icon_now['tree_digest']!=manifest['icon_tree']['tree_digest'] or icon_now['file_count']!=manifest['icon_tree']['file_count']:
        failures.append('Icon tree digest/count changed')
    for name in manifest['output_images']:
        path=ROOT/name
        im=Image.open(path)
        if '720p' in name and im.width!=1280:failures.append('720p width: '+name)
        if '1080p' in name and im.width!=1920:failures.append('1080p width: '+name)
        if name.endswith('-gray.png'):
            color=Image.open(path.with_stem(path.stem[:-5])).convert('RGB')
            if not np.array_equal(np.asarray(im),np.asarray(luma709(color))):failures.append('Rec.709 mismatch: '+name)
    theme=Theme(ROOT/'docs/unreal/contracts/hud/hud-style-tokens.json',
        FONT_ROOT/'Roboto-BoldCondensed.ttf',FONT_ROOT/'Roboto-Regular.ttf',
        ROOT/'art/imagegen/hud-icons-v3/sizes/loader-spinner-48.png',ROOT/'art/imagegen/hud-skins-v1-codex')
    strings={'title':'Покинуть партию','body':'Партия прервётся для обоих игроков','cancel':'Отмена','confirm':'Да'}
    # Independent non-black fixture verifies visibility semantics, not real gameplay.
    bg=Image.new('RGB',(320,180),theme.color('panel.bg.hover'))
    for res in ('1080p','720p'):
        for scale in (100,150):
            vp=Viewport.preset(res,scale)
            baseline=Canvas(vp,theme,bg).finish()
            hidden=Canvas(vp,theme,bg);draw_screen(hidden,False)
            closed=Canvas(vp,theme,bg);draw_base_modal(closed,strings,False)
            if not np.array_equal(np.asarray(baseline),np.asarray(hidden.finish())):failures.append('Hidden screen changed background')
            if not np.array_equal(np.asarray(baseline),np.asarray(closed.finish())):failures.append('Closed modal changed background')
            shown=Canvas(vp,theme,bg);draw_screen(shown)
            if np.array_equal(np.asarray(baseline),np.asarray(shown.finish())):failures.append('Shown screen has no veil')
    # Disabled states cannot silently lose their explanation; primary selection cannot leak into production.
    c=Canvas(Viewport(400,200,1,1),theme)
    for arguments in ({'state':'disabled'},{'state':'selected','primary':True}):
        try:c.button((8,8,220,48),'Отмена',**arguments)
        except ValueError:pass
        else:failures.append('Missing guard: '+repr(arguments))
    sources=verification['source_integrity']
    assert sources['snapshot_unchanged']
    assert all(f['bounds']['primary_button_count']==1 for f in verification['frames'])
    assert verification['smallest_text_720p_px']>=10.5
    assert verification['source_unchanged'] and sources['original_before_file_preserved']
    assert verification['outside_folder']==[]
    assert not (PACKAGE/'_tools/input-snapshots').exists()
    for data in verification['frames']:
        runs=data['text_runs']
        assert not any('уточнить' in r['text'].lower() for r in runs)
        assert sum(r['source']=='background' for r in runs)==(1 if data['board']=='marmoreal' else 0)
        assert [r['text'] for r in runs[:4]]==['Покинуть партию','Партия прервётся для обоих игроков','ОТМЕНА','ДА']
    for data in verification['comparison_bounds'].values():
        assert not any('уточнить' in r['text'].lower() for r in data['text_runs'])
    for data in verification['button_states_grayscale'].values():
        assert len(data['normal']['states'])==6 and len(data['primary']['states'])==5
        assert all(s['all_distinct'] for s in data.values())
    # Rendering is deterministic and protected corners survive arbitrary target width.
    c1=Canvas(Viewport(400,200,1,1),theme);c2=Canvas(Viewport(400,200,1,1),theme)
    c1.button((16,16,168,48),'Отмена',state='focus')
    c2.button((16,16,168,48),'Отмена',state='focus')
    assert np.array_equal(np.asarray(c1.finish()),np.asarray(c2.finish()))
    a=Canvas(Viewport(400,200,1,1),theme);b=Canvas(Viewport(400,200,1,1),theme)
    a.skin((16,16,120,48),'Btn_Hover');b.skin((16,16,240,48),'Btn_Hover')
    assert np.array_equal(np.asarray(a.image)[60:88,60:88],np.asarray(b.image)[60:88,60:88])
    assert all(f['overlap']['persistent']['overlap_figures_px2']==0 and f['overlap']['persistent']['overlap_spaces_px2']==0 for f in verification['frames'])
    result={'package_consistency':'PASS' if not failures else 'FAIL',
        'checked_outputs':len(manifest['outputs']),'checked_images':len(manifest['output_images']),
        'render_input_version_preserved':not any(x.startswith('Render input') for x in failures),
        'live_source_drift_after_render_start':live_source_drift,
        'original_baseline_unchanged':sources['all_unchanged'],
        'acceptance_all_passed':verification['all_acceptance_passed'],
        'limitations':[x['id'] for x in verification['limitations']], 'failures':failures}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
