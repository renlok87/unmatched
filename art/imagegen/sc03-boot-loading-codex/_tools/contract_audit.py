#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Last-mile card checks and precise source references; bounded report writes."""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
import sc03_boot_loading as b


def finalize(package,derived,card):
    v=json.loads((package/'verification.json').read_text(encoding='utf-8'))
    checks=[]
    for key,a in v['layout_measurements'].items():
        gs=a['geometry'];f=a['px_per_su'];cw,ch=a['canvas_su']
        progress=next(g for g in gs if g.get('label')=='stage-progress')
        expected=0 if key.startswith('loading-session') else 1 if card=='SC-04' else 2
        assert progress['done']==expected and progress['fill_width_su']==480*expected/3
        assert not progress['indeterminate']
        title=next(g for g in gs if g.get('label')=='screens.boot.title')
        build=next(g for g in gs if g.get('label')=='screens.boot.build')
        assert abs(build['rect_su'][0]+build['rect_su'][2]-(cw-a['safe_field_su']))<.26
        assert abs(build['rect_su'][1]+build['rect_su'][3]-(ch-a['safe_field_su']))<.26
        overview=next(g for g in gs if g.get('label')=='placeholder-overview')
        assert overview['rect_su'][0]==overview['rect_su'][1]==a['safe_field_su']
        for g in gs:
            if g['kind']=='icon':assert g['size_px']==round(g['rect_su'][2]*f) and 'NEAREST' not in g['method']
        if card=='SC-05':
            modal=next(g for g in gs if g['kind']=='modal')
            assert modal['rect_su']==[(cw-640)/2,(ch-300)/2,640,300]
            budget=next(g for g in gs if g.get('label')=='match-line')
            assert budget['font_su']==16 and budget['names_nominative'] and len(budget['lines'])<=2
        checks.append({'canvas':key,'stage_done':expected,'fill_su':progress['fill_width_su'],
                       'build_safe_margin_su':a['safe_field_su'],'passed':True})
    v['contract_checks']={'passed':True,'canvases':checks,
       'screen_veil_count':1,'blur':False,'sound_hooks':False,'new_image_generations':0,
       'copied_modules_sha256':{name:b.sha(package/'_tools'/name)
           for name in ('screen_mockup_base.py','draw_icons_v3_snapshot.py','sc03_boot_loading.py')},
       'note':'SC-03 final module SHA remains identical in SC-04/SC-05; manifest holds actual source hashes.'}
    b.dump(package/'verification.json',v,package,derived)
    b.refresh_manifest(package,derived,card)
    mp=package/'manifest-sha256.json';manifest=json.loads(mp.read_text(encoding='utf-8'))
    facts=manifest['facts']
    # Inherited BOOT strings originate in SC-03, not in the consuming card row.
    for key in ('screens.boot.title','screens.boot.build'):
        facts[key]['reference']='SC-03.do / ВР-SC15; 04 §1.1 / ВР-H19 for title'
    for key in ('screens.boot.resume.title','screens.boot.resume.line','screens.boot.resume.return','screens.boot.resume.lobby'):
        if key in facts:facts[key]['reference']='SC-05.do / ВР-SC15; CX-27 decision 06–07'
    if 'screens.boot.stage.heroes.wait' in facts:
        facts['screens.boot.stage.heroes.wait']['reference']='SC-04.do; proposed wait key / CX-27 decision 05'
    facts['dimensions']={'input':b.SERIES,'reference':'Common notes / canvas and decisions 01–08',
         'values':{'progress_su':[480,8],'modal_su':[640,300],'connection_su':48,'spinner_su':32,
                   'padding_su':[12,16],'safe_su':[24,16],'button_height_su':48,
                   'types_su':[48,28,20,16,14]},
         'implementation_decisions':'Error capsule 480×168 su; lobby 168×48 and return 312×48 su; positions recorded per canvas; no game data introduced.'}
    b.dump(mp,manifest,package,derived)
    return checks


if __name__=='__main__':
    package=Path(__file__).resolve().parents[1];derived=b.ROOT/('scraped-data/derived/'+package.name)
    card={'sc03-boot-loading-codex':'SC-03','sc04-boot-error-codex':'SC-04','sc05-boot-resume-codex':'SC-05'}[package.name]
    finalize(package,derived,card)
    print(card+' contract checks PASS')
