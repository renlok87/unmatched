#!/usr/bin/env python
"""Independent HB-07 audit. Read-only by default; --record-reviewed only AFTER PNG review.

python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/verify_package.py
python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/verify_package.py --record-reviewed
"""
import argparse
import itertools
import math
import json
from pathlib import Path
import numpy as np
from PIL import Image
import build_mockups as b


def run(record=False):
    v=b.ref.load_json(b.PACKAGE/'verification.json')
    before=b.ref.load_json(b.PACKAGE/'source-hashes-before.json')
    assert not b.ref.hash_mismatches(before),'Source bytes changed'
    expected={k for k in before['files'] if k.startswith('art/imagegen/hud-icons-v3/')}
    actual={b.ref.relative(p) for p in b.ref.ICONS.rglob('*') if p.is_file()}
    assert actual==expected,'v3 source file set changed'
    assert (b.PACKAGE/'_tools/draw_icons_v3_snapshot.py').read_bytes()==(b.ref.ICONS/'_tools/draw_icons.py').read_bytes()
    facts=b.ref.load_json(b.PACKAGE/'facts.json')
    previous=b.ref.load_json(b.PACKAGE/'fix1-before.json')
    assert b.ref.sha(b.PACKAGE/'source-hashes-before.json')==previous['source_baseline_sha256']
    preserved={p:d for p,d in previous['previous_manifest_files'].items() if
        p.endswith('/masks.json') or '/mask-' in p or '/mask-registration-' in p or
        '-04-literal-overlay' in p or '/contact-04-literal' in p or
        p.endswith(('/draw_icons_v3_snapshot.py','/layout_reference.py'))}
    assert all(b.ref.sha(b.ROOT/p)==d for p,d in preserved.items()),'Accepted masks, literal geometry or source snapshots changed'
    assert len(facts['outputs'])==24
    checked=[]; backgrounds=[]; overlaps=[]; gap_checks=[]; width_checks=[]
    for o in facts['outputs']:
        audit=next(a for a in v['overlap']['per_mockup'] if a['id']==o['id'])
        w,h=audit['resolution']; scale=audit['su_to_px']; board=audit['board']
        im=Image.open(b.ROOT/o['color']); grey=Image.open(b.ROOT/o['gray'])
        assert im.size==grey.size==(w,h) and im.mode==grey.mode=='RGBA'
        assert np.array_equal(np.asarray(b.ref.gray(im).convert('RGB')),np.asarray(grey.convert('RGB'))),'Rec.709 mismatch'
        sm=np.asarray(Image.open(b.PACKAGE/'comparison'/f'mask-{board}-{w}x{h}-spaces.png').convert('L'))>0
        fm=np.asarray(Image.open(b.PACKAGE/'comparison'/f'mask-{board}-{w}x{h}-figures.png').convert('L'))>0
        scene=b.ref.original(str(b.ROOT/b.BOARD[board]['background']))
        if scene.size!=(w,h):scene=scene.resize((w,h),Image.Resampling.LANCZOS)
        union=np.zeros((h,w),dtype=bool); blocks={}
        # Full rectangular envelopes are stronger than rounded panel silhouettes.
        for name,p in audit['panels'].items():
            x,y,rw,rh=p['rectangle_su']; x0,y0=max(0,round(x*scale)),max(0,round(y*scale))
            x1,y1=min(w,round((x+rw)*scale)),min(h,round((y+rh)*scale))
            mask=np.zeros((h,w),dtype=bool);mask[y0:y1,x0:x1]=True
            union|=mask;blocks[name]=mask
            if p['persistent']:
                assert not np.any(mask&(sm|fm)),(o['id'],name,'mask overlap')
        for ka,kb in itertools.combinations(blocks,2):
            if ka not in ('CENTER','BANNER') and kb not in ('CENTER','BANNER'):
                assert not np.any(blocks[ka]&blocks[kb]),(o['id'],ka,kb)
        outside=np.any(np.asarray(im)[:,:,:3]!=np.asarray(scene)[:,:,:3],axis=2)&~union
        assert not np.any(outside),(o['id'],'source background edited outside HUD',int(np.count_nonzero(outside)))
        assert audit['hand_gap_su']>=8 and not audit['text_fit_failures']
        assert all(row['passed'] for row in audit['button_text_fit'])
        # Recompute every text/visual pair from independent facts, rather than
        # trusting the renderer's pass flag or aggregate minimum.
        texts=[t for t in facts['rendered_texts'] if t['mockup']==o['id']]
        visuals=[i for i in facts['rendered_visual_boxes'] if i['mockup']==o['id']]
        for panel in audit['panels']:
            gaps=[]; hp_gaps=[]; pairs=0
            for t in (t for t in texts if t['block']==panel):
                for tb in t['bbox_px']:
                    for icon in (i for i in visuals if i['block']==panel):
                        ib=icon['bbox_px']
                        overlap=max(0,min(tb[2],ib[2])-max(tb[0],ib[0]))*max(0,min(tb[3],ib[3])-max(tb[1],ib[1]))
                        gap=math.sqrt(max(0,tb[0]-ib[2],ib[0]-tb[2])**2+max(0,tb[1]-ib[3],ib[1]-tb[3])**2)/scale
                        required=8 if t['source']['key']=='hud.panel.hp' and icon.get('name')=='marker-action-slot-de' else 4
                        assert overlap==0 and gap+1e-8>=required,(o['id'],panel,t['displayed'],icon,gap)
                        gaps.append(gap); pairs+=1
                        if required==8:hp_gaps.append(gap)
            recorded=next(r for r in v['panel_inner_gaps'] if r['mockup']==o['id'] and r['block']==panel)
            assert len(recorded['pairs'])==pairs
            assert recorded['smallest_gap_su']==min(gaps,default=None)
            assert recorded['hp_tracker_gap_min_su']==min(hp_gaps,default=None)
            gap_checks.append({'mockup':o['id'],'panel':panel,'pairs_recomputed':pairs,'passed':True})
        sr=next(t for t in texts if t['block']=='STATUS')
        measure=b.font(sr['font_px'],True).getlength(sr['text'])/scale
        cap=600 if audit['class']=='S' else (880 if w==1920 else 720)
        expected_width=cap if len(sr['lines'])>1 else min(cap,measure+32)
        sx,sy,sw,sh=audit['panels']['STATUS']['rectangle_su']
        assert abs(sw-expected_width)<1e-8 and abs(sx+sw/2-w/scale/2)<1e-8
        assert sy==(16 if audit['class']=='S' else 24)
        wr=next(r for r in v['status_width'] if r['mockup']==o['id'])
        assert wr['measured_text_width_su']==measure and wr['capsule_width_su']==sw
        width_checks.append({'mockup':o['id'],'measured_width_su':measure,'capsule_width_su':sw,'passed':True})
        if board=='sarpedon' and audit['state']=='combat-defense':
            assert sr['text']=='Ждём защитника' and sr['source']['key']=='why.wait.defender' and sr['token']=='text.secondary'
            center=next(t for t in texts if t['block']=='CENTER')
            assert center['text']=='Ждём защиту…' and center['source']['key']=='hud.combat.wait.defense'
            assert [r['line'] for r in sr['source']['trace_lines']]==[380,913]
            for row in sr['source']['trace_lines']:
                assert (b.ROOT/row['path']).read_text(encoding='utf-8').splitlines()[row['line']-1]==row['text']
        for suffix in ('overlay','04-literal-overlay'):
            op=b.PACKAGE/'comparison'/(o['id']+'-'+suffix+'.png')
            gp=op.with_name(op.stem+'-gray.png')
            oi=Image.open(op);og=Image.open(gp)
            assert oi.size==og.size==(w,h) and oi.mode==og.mode=='RGBA'
            assert np.array_equal(np.asarray(b.ref.gray(oi).convert('RGB')),np.asarray(og.convert('RGB')))
        checked.append(o['id']);backgrounds.append({'id':o['id'],'changed_pixels_outside_HUD':0})
        overlaps.append({'id':o['id'],'full_rectangular_envelopes_overlap_px2':0})
    assert all(t['source'].get('source') and t['source'].get('key') for t in facts['rendered_texts'])
    assert not any('уточнить' in t['displayed'].lower() for t in facts['rendered_texts'])
    assert v['min_text_px_720p']>=10.5
    assert v['palette']['fraction_off_tokens']==0
    failures=[k for k,r in v['acceptance'].items() if not r['passed']]
    assert not failures,failures
    assert v['contrast']['edge_vs_body_min']>=3 and v['contrast']['functional_icon_min']>=3
    assert v['contrast']['informational']['note']=='вне пары 02 §3.5'
    png_paths={b.ref.relative(p) for folder in (b.PACKAGE,b.DERIVED) for p in folder.rglob('*.png')}
    assert png_paths=={row['path'] for row in v['exports']},'PNG exports missing or stale'
    if record:
        # R3 asks for every button on every canvas, including the §04 discs whose
        # compact labels exist only in tooltips. Defense rows remain measured by
        # the actual renderer; the additional rows use stored rendered text facts.
        button_rows=[r for r in v['button_text_fit'] if r['key'] in ('hud.combat.defend','hud.combat.no.defense')]
        for row in button_rows:row['kind']='defense'
        for o in facts['outputs']:
            audit=next(a for a in v['overlap']['per_mockup'] if a['id']==o['id'])
            scale=audit['su_to_px'];small=audit['class']=='S'
            textrows=[t for t in facts['rendered_texts'] if t['mockup']==o['id']]
            for key,kind,width,available in [('hud.top.menu','TOP menu',42,42),
                ('hud.top.log','TOP journal',60,60),
                ('hud.decks.deck','deck chip',64 if small else 144,22 if small else 90),
                ('hud.decks.discard','discard chip',64 if small else 144,30 if small else 88)]:
                matches=[t for t in textrows if t['source'].get('key')==key]
                if not matches:continue
                t=matches[0];tw=max(t['line_width_su'])
                button_rows.append({'mockup':o['id'],'kind':kind,'key':key,'label':t['displayed'],
                    'label_rendered':True,'type_su':t['type_su'],'font_px':t['font_px'],
                    'text_width_su_at_canvas':tw,'text_width_px':tw*scale,
                    'button_width_su':width,'available_text_width_su':available,
                    'button_width_px':round(width*scale),'passed':tw<=available,
                    'note':'TOP widths are renderer text corridors; DECKS widths are §1.6/§2.9 chip cells.'})
            for tail in ('maneuver','attack','scheme','end_turn'):
                key='hud.action.'+tail;val,_=b.st(key)
                f=b.font(int(np.ceil(14*scale)),True);tw=f.getlength(val)/scale
                button_rows.append({'mockup':o['id'],'kind':'action disc','key':key,'label':val,
                    'label_rendered':not small,'type_su':14,'font_px':int(np.ceil(14*scale)),
                    'text_width_su_at_canvas':tw,'text_width_su_at_14px':b.font(14,True).getlength(val),
                    'text_width_px':tw*scale,'button_width_su':40 if small else 80,
                    'button_width_px':round((40 if small else 80)*scale),
                    'available_text_width_su':None if small else 80,
                    'passed':small or tw<=80,'note':'Class S labels in tooltip per §1.6; no label is drawn or clipped in the disc.'})
        assert all(r['passed'] for r in button_rows),'Additional button label overflow'
        v['button_text_fit']=button_rows
        v['acceptance']['all_visible_button_labels_fit']={'passed':True,'measured':len(button_rows),
            'expected':'Every visible button label fits at actual raster size; S disc captions only in tooltip',
            'note':'Defense labels retain 20su caps and measured padding; action captions are prescribed 14su tags, TOP 14su, DECKS 16/20su.'}
        v['independent_verification']={'native_RGBA_and_Rec709_pairs':checked,
            'backgrounds':backgrounds,'stronger_rectangle_overlap_check':overlaps,
            'panel_inner_gaps_recomputed':gap_checks,'status_width_recomputed':width_checks,
            'fix1_preserved_v2_artifacts':sorted(preserved),
            'all_source_bytes_and_v3_file_set_unchanged':True,'snapshot_byte_identical':True}
        v['visual_review']={'reviewer':'Codex','reviewed_final_ids':checked,
            'reviewed_sources':['painted Marmoreal K1','lit3d Sarpedon K1'],
            'run_I_data':'Accepted v2 inputs unchanged; fix1 re-read MS-STATUS seq=6/10 at lines 380/913.',
            'reviewed_mask_registration':['marmoreal-1920x1080','sarpedon-1920x1080'],
            'method':'Direct view_image inspection of all 24 final PNGs, all-24 grayscale contact, recommended and 04-literal overlay contacts and both mask-registration PNGs.',
            'checks':['real boards','correct per-board backdrop','six v2 figures','owner-specific combat sides',
                'no persistent block covers figures/cells','full defense labels','background labels retained and documented'],
            'result':'предложено; fix1 verified; manual projection documented; decorative/exterior contrast informational per 02 §3.5'}
        v['gray']['all_pairs_present']=True
        v['acceptance']['manifest']['measured']='Every non-manifest file covered, SHA256 independently checked after last write'
        v['source_unchanged']=not b.ref.hash_mismatches(before)
        b.save_json(b.PACKAGE/'verification.json',v)
        files={b.ref.relative(p):b.ref.sha(p) for folder in (b.PACKAGE,b.DERIVED) for p in sorted(folder.rglob('*')) if p.is_file() and p!=b.PACKAGE/'manifest-sha256.json'}
        b.save_json(b.PACKAGE/'manifest-sha256.json',{'algorithm':'sha256','files':files,
            'self_excluded':'manifest-sha256.json: recursive self-hash undefined; every other file in both output folders is included.'})
    manifest=b.ref.load_json(b.PACKAGE/'manifest-sha256.json')['files']
    all_files={b.ref.relative(p) for folder in (b.PACKAGE,b.DERIVED) for p in folder.rglob('*') if p.is_file() and p!=b.PACKAGE/'manifest-sha256.json'}
    assert set(manifest)==all_files,'Manifest file set differs'
    assert all(b.ref.sha(b.ROOT/path)==digest for path,digest in manifest.items()),'Manifest digest mismatch'
    print(json.dumps({'result':'PASS','mockups':len(checked),'RGBA_and_Rec709_pairs':len(checked)+48,
        'persistent_full_rectangle_overlap_px2':0,'background_changes_outside_HUD':0,
        'inputs_unchanged':len(before['files']),'v3_files_unchanged':len(expected),'manifest_files':len(manifest),
        'visual_review_recorded':record,'failed_acceptance':failures},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--record-reviewed',action='store_true')
    run(parser.parse_args().record_reviewed)
