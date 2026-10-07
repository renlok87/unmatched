#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only validation of CX-30; report writes only into SC-18's package."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json
import hashlib
import numpy as np
from PIL import Image
import sc14_room_hero as b

PACKAGES=[('SC-14','sc14-room-hero',3),('SC-15','sc15-room-board',2),
          ('SC-16','sc16-room-deck',2),('SC-17','sc17-room-ready',5),('SC-18','sc18-room-countdown',2)]

def run():
    # This validator and the summary report are SC-18-owned output files.
    b.refresh_manifest()
    icon_tree=b.tree_inventory(b.ICONS);icon_digest=b.digest(icon_tree)
    result={'series':'CX-30','status':'предложено','packages':{},'outside_folder':[],
            'icons':{'count':len(icon_tree),'tree_digest':icon_digest},'commands':'offline Python/Pillow only; no Git, MCP, network or Unreal'}
    total_png=0
    for identifier,slug,state_count in PACKAGES:
        package=b.ROOT/f'art/imagegen/{slug}-codex';derived=b.ROOT/f'scraped-data/derived/{slug}-codex'
        manifest=b.load(package/'manifest-sha256.json');before=b.load(package/'source-hashes-before.json');v=b.load(package/'verification.json')
        assert len(v['frames'])==state_count*4
        changed=[p for p,h in before['inputs'].items() if b.sha(b.ROOT/p)!=h]
        assert not changed,(identifier,changed)
        assert before['hud_icons_v3']['tree_digest']==icon_digest
        expected={b.rel(p) for folder in (package,derived) for p in folder.rglob('*') if p.is_file() and p!=package/'manifest-sha256.json'}
        assert expected==set(manifest['files']),(identifier,'manifest coverage')
        assert all(b.sha(b.ROOT/p)==h for p,h in manifest['files'].items()),identifier
        assert all(b.sha(b.ROOT/p)==h for p,h in manifest['inputs'].items()),(identifier,'manifest inputs')
        assert manifest['inputs']==before['inputs']
        audit_inputs=before.get('audit_inputs',{})
        assert all(b.sha(b.ROOT/p)==h for p,h in audit_inputs.items())
        assert manifest['facts'].get('post_render_audit_inputs',{})==audit_inputs
        fix=v['fix1'];baseline=b.load(package/'fix1-baseline.json')
        assert fix['technical_checks_passed'] and fix['protected_inputs_unchanged']
        assert all(b.sha(b.ROOT/p)==h for p,h in baseline['files'].items() if '/inputs/' in p)
        for entry in fix['changed_files']:
            assert entry['sha256_before']==baseline['files'].get(entry['file'])
            if 'sha256_after' in entry:assert b.sha(b.ROOT/entry['file'])==entry['sha256_after'],entry['file']
        for copy in b.load(package/'copy-provenance.json'):
            assert b.sha(b.ROOT/copy['source'])==copy['sha256']==b.sha(b.ROOT/copy['copy'])
        assert not v['layout_problems']
        assert v['visual_review']['all_final_png_reviewed']
        review=b.load(package/'visual-review.json')
        assert review['status']=='просмотрено'
        assert review['fix1']['personally_viewed_final_pngs']
        reviewed={e['file']:e['sha256'] for e in review['reviewed_files']}
        pngs={b.rel(p):b.sha(p) for folder in (package,derived) for p in folder.rglob('*.png') if not p.is_relative_to(derived/'inputs')}
        assert reviewed==pngs
        for p in pngs:
            with Image.open(b.ROOT/p) as image:assert image.mode=='RGBA'
        for gray in v['gray']['pairs']:
            with Image.open(b.ROOT/gray['color']) as color,Image.open(b.ROOT/gray['gray']) as mono:
                assert np.array_equal(np.asarray(b.luma709(color)),np.asarray(mono.convert('RGB')))
        for frame in v['frames'].values():
            assert frame['capture_values_match'] and not frame['issues'] and not frame['text_pair_overlaps']
            assert frame['min_text_contrast']>=4.5
            assert all(t['source'] for t in frame['text_runs'])
            if frame['viewport']['size_px'][1]==720:assert frame['smallest_text_px']>=10.5
            assert frame['overlap']['persistent']['figures_px2']==frame['overlap']['persistent']['spaces_px2']==0
        readme=(package/'README.md').read_text(encoding='utf-8')
        assert 'предложено' in readme and '???' not in readme
        assert b.load(package/'generation-records.json')==[]
        total_png+=len(pngs)
        result['packages'][identifier]={'package':b.rel(package),'frames':len(v['frames']),'pngs':len(pngs),
            'inputs':len(before['inputs']),'inputs_unchanged':True,'immutable_copies':True,'manifest_complete':True,
            'all_png_reviewed':True,'text_contrast_minimum':v['contrast']['text_minimum'],
            'smallest_720p_text_px':min(f['smallest_text_px'] for key,f in v['frames'].items() if '720p' in key),
            'text_collisions':0,'capture_values_match':True,'persistent_overlap_px2':0,
            'full_card_acceptance':v['full_acceptance'],
            'limitations':{'literal_edge_requirement':not v['contrast']['literal_edge_pass'],
                'pixel_deltaE_fraction_not_measured':v['palette']['outside_token_fraction'] is None},
            'documented_upstream_metadata_revisions':before.get('dependency_metadata_revisions',[])}
        result['packages'][identifier]['fix1']={'technical_checks_passed':True,'checks':fix['checks'],
            'run1_hashes_preserved':True,'changed_file_hashes_verified':True,'all_final_png_personally_reviewed':True}
    result['total_png']=total_png;result['required_state_frames']=sum(n*4 for _,_,n in PACKAGES)
    result['protected_capture_inputs_unchanged']=True;result['renderer_chain_unchanged']=True
    result['technical_checks_passed']=True
    result['full_art_acceptance']=False
    result['full_art_acceptance_note']='SC-17/18 preserve HB-08 primary navy edge (1:1 to navy panel). The measured opaque flat UI palette passes with explicit artwork/AA/transparency exclusions; this is not a claim about every scene pixel. Full artistic acceptance is not asserted.'
    b.dump(b.PACKAGE/'series-verification.json',result)
    b.refresh_manifest()
    print(json.dumps({'technical_checks_passed':True,'total_png':total_png,'required_state_frames':result['required_state_frames'],
                      'full_art_acceptance':False,'icons_unchanged':len(icon_tree)},ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');run()
