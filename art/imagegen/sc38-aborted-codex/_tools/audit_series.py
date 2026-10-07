#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only checks of completed CX-34 packages; report only inside SC-38.

No rendering, engine, git, network, source changes or writes to other packages.
"""
import sys
sys.dont_write_bytecode = True
import re
from pathlib import Path
import numpy as np
from PIL import Image
import sc38_aborted as m

SETS = [('SC-34','sc34-gameover-victory',32),('SC-35','sc35-gameover-defeat',24),
        ('SC-36','sc36-gameover-board',24),('SC-37','sc37-gameover-again',32),('SC-38','sc38-aborted',32)]

def audit(card,name,expected):
    package=m.ROOT/f'art/imagegen/{name}-codex'; derived=m.ROOT/f'scraped-data/derived/{name}-codex'
    manifest=m.load(package/'manifest-sha256.json'); before=m.load(package/'source-hashes-before.json')
    verification=m.load(package/'verification.json'); review=m.load(package/'visual-review.json')
    files={m.rel(p) for root in [package,derived] for p in root.rglob('*')
           if p.is_file() and p!=package/'manifest-sha256.json'}
    assert files==set(manifest['files']), (card,'manifest coverage')
    assert all(m.info(m.ROOT/path)==value for path,value in manifest['files'].items()), (card,'output hash')
    assert before['files']==manifest['inputs'], (card,'input inventory')
    assert all(m.info(m.ROOT/path)==value for path,value in before['files'].items()), (card,'source hash')
    current_tree=m.icon_tree()
    assert all(current_tree[key]==before['hud_icons_v3_tree'][key]==manifest['hud_icons_v3_tree'][key]
               for key in ['sha256','count']), (card,'icon tree')
    copies=m.load(package/'copy-provenance.json')
    assert len(copies)==(3 if card in ['SC-35','SC-36','SC-37'] else 2)
    for item in copies:
        assert (m.ROOT/item['source']).read_bytes()==(m.ROOT/item['copy']).read_bytes()
        assert m.info(m.ROOT/item['source'])['sha256']==item['sha256']
    assert verification['outside_folder']==[] and verification['visual_review']['passed']
    assert review['all_opened'] and {row['path'] for row in review['files']}==set(verification['exports']['files'])
    assert len(review['files'])==expected
    for row in review['files']: assert m.info(m.ROOT/row['path'])['sha256']==row['sha256']
    assert m.load(package/'generation-records.json')==[]
    mock_count=0
    for path in verification['exports']['files']:
        match=re.search(r'-(1080p|720p)-(100|150)(-gray)?\.png$',path); assert match
        res=match.group(1); width,height=(1920,1080) if res=='1080p' else (1280,720)
        image=Image.open(m.ROOT/path); assert image.mode=='RGBA'
        if '-comparison-' in path: assert image.size[0]==width and image.size[1] in [height,height*2]
        else: assert image.size==(width,height)
        if '-overlay-' not in path and '-comparison-' not in path: mock_count+=1
        if match.group(3):
            gray=np.asarray(image.convert('RGB')); assert np.array_equal(gray[:,:,0],gray[:,:,1]) and np.array_equal(gray[:,:,0],gray[:,:,2])
            color=Image.open(m.ROOT/path.replace('-gray.png','.png')).convert('RGB')
            expected_gray=np.rint(np.asarray(color,dtype=float)@np.array([.2126,.7152,.0722])).astype(np.uint8)
            assert np.array_equal(gray[:,:,0],expected_gray), (card,path,'Rec.709')
    assert all(f['drawn_values_equal_inputs'] and f['primary_button_count']==1 and f['text_overlap_px2']==0
               and f['smallest_text_su']>=14 and f['overlap']['persistent_overlap_px2']==0 for f in verification['frames'].values())
    overlays=verification['overlays']
    if isinstance(overlays,dict): overlays=overlays.values()
    assert all(o['label_overlap_px2']==0 and not o['contains_asset_pixels'] for o in overlays)
    if card=='SC-36':
        assert all(not f['grade']['veil'] and f['grade']['kind']=='victory' for f in verification['frames'].values())
        assert all(layer[key]==0 for f in verification['frames'].values() for layer in f['overlap']['layers']
                   for key in ['field_px2','figures_px2','spaces_px2'])
    if card=='SC-37':
        for res,scale in m.PRESETS:
            normal=verification['frames'][f'again-{res}-{scale}']['geometry']
            busy=verification['frames'][f'again-busy-{res}-{scale}']['geometry']
            for name in ['ButtonRow','ViewBoardButton','AgainButton','LobbyButton']:
                assert normal[name]['rect_su']==busy[name]['rect_su'], (card,'busy moves',name)
    accepted=verification['acceptance']
    if isinstance(accepted,list): accepted={entry['criterion']:entry for entry in accepted}
    return {'card':card,'package':m.rel(package),'exports_checked':expected,'mockup_png_count':mock_count,
            'inputs_checked':len(before['files']),'manifest_files_checked':len(files),'copies_byte_identical':True,
            'inputs_unchanged':True,'manifest_complete':True,'visual_review_complete':True,
            'rgba_dimensions_gray_luma_verified':True,'persistent_overlap_px2':0,
            'failed_acceptance':{k:v for k,v in accepted.items() if not v['passed']}}

if __name__=='__main__':
    # Include this audit script in SC-38's manifest before checking its coverage.
    m.manifest()
    reports=[audit(*entry) for entry in SETS]
    total=sum(r['exports_checked'] for r in reports); mockups=sum(r['mockup_png_count'] for r in reports)
    assert total==144 and mockups==64
    m.dump(m.PKG/'series-audit.json',{'schema':'CX-34.series-audit/1','status':'предложено',
           'package_integrity_passed':True,'acceptance_all_passed':False,'all_final_png_count':total,
           'mockup_png_count':mockups,'packages':reports,
           'scope':'Writes only SC-38 report and SC-38 manifest; no Git, engine, network or MCP.'})
    m.manifest()
    audit('SC-38','sc38-aborted',32)
    for report in reports:
        print(report['card'],str(report['exports_checked'])+' PNG',str(report['inputs_checked'])+' input hashes',
              'integrity PASS; documented acceptance failures:',', '.join(report['failed_acceptance']))
    print('TOTAL: 5 packages, 144 inspected PNGs, 64 mockups; inputs and copied libraries unchanged')
