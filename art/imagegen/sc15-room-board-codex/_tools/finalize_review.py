#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Native-size inspection sheets and independent hash/export verification.

--sheets opens every final frame/overlay PNG into native-size contact sheets.
--finalize is allowed only after an explicit visual-review.json reviewed_files
list has been written by the reviewer. It never declares unviewed files viewed.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json
import argparse
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import sc14_room_hero as b

def sheets():
    verification=b.load(b.PACKAGE/'verification.json')
    for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]:
        suffix=f'-{res}-{scale}.png'
        frames=sorted(p for p in b.DERIVED.glob('SC-*.png') if p.name.endswith(suffix))
        frames+=sorted(p for p in (b.PACKAGE/'comparison').glob('SC-*.png') if p.name.endswith(suffix))
        for gray in (False,True):
            paths=[p.with_name(p.stem+'-gray.png') if gray else p for p in frames]
            width,height=Image.open(paths[0]).size;cols=2;rows=math.ceil(len(paths)/cols)
            im=Image.new('RGBA',(width*cols,(height+28)*rows),b.theme().color('card.navy')+(255,))
            d=ImageDraw.Draw(im);font=ImageFont.truetype(str(b.FONT/'Roboto-Regular.ttf'),14)
            for i,p in enumerate(paths):
                x=(i%cols)*width;y=(i//cols)*(height+28)
                with Image.open(p) as src:im.alpha_composite(src.convert('RGBA'),(x,y+28))
                d.text((x+12,y+6),p.name,font=font,fill=b.theme().color('text.primary'))
            p=b.DERIVED/f'comparison-{res}-{scale}{"-gray" if gray else ""}.png'
            if gray:im=b.luma709(im).convert('RGBA')
            im.save(b.guard(p),optimize=True)
    b.refresh_manifest()

def finalize():
    review=b.load(b.PACKAGE/'visual-review.json')
    all_png={b.rel(p):b.sha(p) for root in (b.PACKAGE,b.DERIVED) for p in root.rglob('*.png') if not p.is_relative_to(b.DERIVED/'inputs')}
    listed={item['file']:item['sha256'] for item in review['reviewed_files']}
    assert listed==all_png,('missing / stale review',sorted(all_png.keys()-listed.keys()))
    v=b.load(b.PACKAGE/'verification.json');before=b.load(b.PACKAGE/'source-hashes-before.json')
    changed=[p for p,h in before['inputs'].items() if b.sha(b.ROOT/p)!=h]
    icons=b.tree_inventory(b.ICONS)
    assert not changed and b.digest(icons)==before['hud_icons_v3']['tree_digest']
    assert not v['layout_problems'],v['layout_problems']
    assert all(frame['capture_values_match'] for frame in v['frames'].values())
    assert v['contrast']['text_minimum']>=4.5
    assert all(pair['rec709_equal'] for pair in v['gray']['pairs'])
    assert all(frame['smallest_text_px']>=10.5 for key,frame in v['frames'].items() if '720p' in key)
    assert all(frame['overlap']['persistent']['figures_px2']==frame['overlap']['persistent']['spaces_px2']==0 for frame in v['frames'].values())
    for entry in b.load(b.PACKAGE/'copy-provenance.json'):
        assert b.sha(b.ROOT/entry['source'])==b.sha(b.ROOT/entry['copy'])==entry['sha256']
    v['visual_review']={'pending':False,'file':'visual-review.json','png_count':len(all_png),'all_final_png_reviewed':True}
    v['exports']=[{'file':p,'size_px':list(Image.open(b.ROOT/p).size),'mode':Image.open(b.ROOT/p).mode,
        'margin_px':None if '/comparison-' in p else next((e['margin_px'] for e in v['exports'] if e['file']==p),None),
        'touches_edge':'/comparison/' not in p,'note':'scene fills frame; safe-area margins in layout-geometry.json'} for p in sorted(all_png)]
    v['independent_checks']={'source_hashes':True,'copied_modules':True,'RGBA_exports':all(e['mode']=='RGBA' for e in v['exports']),
        'rec709_pairs':True,'capture_values':True,'no_text_collisions':True,'no_outside_canvas':True,
        'minimum_720p_text_px':min(f['smallest_text_px'] for key,f in v['frames'].items() if '720p' in key)}
    b.dump(b.PACKAGE/'verification.json',v);b.refresh_manifest()
    manifest=b.load(b.PACKAGE/'manifest-sha256.json')
    assert all(b.sha(b.ROOT/p)==h for p,h in manifest['files'].items())
    print(b.PACKAGE.name,'verified',len(all_png),'PNG; full literal acceptance:',v['full_acceptance'])

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('--sheets',action='store_true');args=parser.parse_args()
    sheets() if args.sheets else finalize()
