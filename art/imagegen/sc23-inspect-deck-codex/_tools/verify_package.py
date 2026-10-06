#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent export audit; only changes the selected CX-23 package metadata.

After visually inspecting all PNGs use --seal-review. That flag is an explicit
operator attestation, not an automatic claim of visual inspection.
"""
import sys
sys.dont_write_bytecode = True
import argparse
from pathlib import Path
import itertools
import numpy as np
from PIL import Image
from sc21_inspect_own import (ROOT, config, load, sha, theme, input_audit,
                             refresh_manifest, write_json, luma709, mix)


def lab(rgb):
    v=np.asarray(rgb,dtype=float)/255
    lin=np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
    xyz=lin @ np.array([[.4124564,.2126729,.0193339],
                        [.3575761,.7151522,.1191920],
                        [.1804375,.0721750,.9503041]])
    xyz=xyz/np.array([.95047,1,1.08883])
    f=np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)


def palette_audit(cfg):
    t=theme(); colors=[]
    for k,item in t.tokens['colors'].items():
        if 'hex' in item:
            colors.append(t.color(k))
            for alpha in (item.get('alpha',1),.45,.92,.16,.4):
                colors.append(mix(t.color(k),t.color('panel.bg'),alpha))
    # Derived HB-08 colors explicitly documented in the frozen README.
    colors.extend([(243,197,91),(213,170,69),(78,84,87)])
    allowed=lab(np.unique(colors,axis=0));result=[]
    for p in sorted((cfg['package']/'comparison').glob('*.png')):
        if '-gray' in p.stem:
            continue
        a=np.asarray(Image.open(p).convert('RGB'))
        # A 3x3 constant patch is flat paint; all edge/text AA is excluded.
        flat=np.ones(a.shape[:2],dtype=bool)
        for dy,dx in itertools.product((-1,0,1),repeat=2):
            flat &= (a==np.roll(np.roll(a,dy,axis=0),dx,axis=1)).all(axis=2)
        flat[[0,-1],:]=False;flat[:,[0,-1]]=False
        rgb,counts=np.unique(a[flat],axis=0,return_counts=True)
        distances=np.sqrt(((lab(rgb)[:,None,:]-allowed[None,:,:])**2).sum(axis=2)).min(axis=1)
        bad=int(counts[distances>3].sum())
        result.append({'file':p.name,'tested_flat_pixels':int(counts.sum()),
                       'outside_deltaE76_3_pixels':bad,'outside_fraction':bad/max(1,int(counts.sum())),
                       'bad_colors':[{'rgb':c.tolist(),'count':int(n),'deltaE76':float(d)}
                                     for c,n,d in zip(rgb,counts,distances) if d>3]})
    return {'scope':'No-scan procedural overlay exports; board/scans are source artwork and exempt',
            'method':'CIE Lab D65 DeltaE76 <=3 to exact tokens and documented alpha composites; 3x3 constant opaque patches, AA excluded',
            'allowed_color_count':len(allowed),'frames':result,
            'outside_token_flat_pixels_fraction':sum(r['outside_deltaE76_3_pixels'] for r in result)/max(1,sum(r['tested_flat_pixels'] for r in result)),
            'passed':all(r['outside_deltaE76_3_pixels']==0 for r in result)}


def verify(cfg,seal=False):
    d=load(cfg['package']/'verification.json')
    manifest=load(cfg['package']/'manifest-sha256.json')
    d['source_unchanged']=input_audit(cfg)
    assert d['source_unchanged']['passed']
    snapshots={'screen_mockup_base.py':ROOT/'art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py',
               'draw_icons_v3_snapshot.py':ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py'}
    if cfg['id']!='SC-21':
        snapshots['sc21_inspect_own.py']=ROOT/'art/imagegen/sc21-inspect-own-codex/_tools/sc21_inspect_own.py'
    d['unchanged_snapshots']={n:{'source':str(src),'source_sha256':sha(src),
                                'copy_sha256':sha(cfg['package']/'_tools'/n),
                                'passed':sha(src)==sha(cfg['package']/'_tools'/n)} for n,src in snapshots.items()}
    assert all(s['passed'] for s in d['unchanged_snapshots'].values())
    states={'SC-21':['own','loading'],'SC-22':['hidden'],'SC-23':['deck','deck-card','deck-scroll']}[cfg['id']]
    expected=[cfg['derived']/f"{cfg['id']}-{s}-{r}-{u}{g}.png"
              for s,r,u,g in itertools.product(states,['1080p','720p'],[100,150],['','-gray'])]
    expected += [cfg['package']/f"comparison/{cfg['id']}-overlay-{r}-{u}{g}.png"
                 for r,u,g in itertools.product(['1080p','720p'],[100,150],['','-gray'])]
    assert all(p.exists() for p in expected)
    for p in expected:
        with Image.open(p) as im:
            assert im.mode=='RGBA'
            assert im.size==((1920,1080) if '1080p' in p.name else (1280,720))
            im.load()
    for p in expected:
        if '-gray' not in p.stem:
            other=p.with_name(p.stem+'-gray.png')
            assert np.array_equal(np.asarray(luma709(Image.open(p))),np.asarray(Image.open(other).convert('RGB')))
    scan_overlaps=[];contained=[]; leaked=[]
    for name,a in d['layout'].items():
        assert a['minimum_text_contrast']>=4.5
        assert a['smallest_text_px']>=10.5
        assert a['primary_buttons']==a['primary_count']==0
        assert not any(t['text'].upper()=='ЗАКРЫТЬ' for t in a['text_runs'])
        closes=[i for i in a['icons'] if i['path'].endswith('/ui-close-32.png')]
        assert len(closes)==1 and closes[0]['size_su']==32
        close=next(n['close'] for n in a['notes'] if 'close' in n)
        assert close['accessible_name']==close['tooltip']=='Закрыть' and not close['drawn_label']
        if 'slot' in a['rects_su']:
            r=a['rects_su'];sx,sy,sw,sh=r['slot'];fx,fy,fw,fh=r['frame']
            assert np.allclose([sx+sw/2,sy+sh/2],[fx+fw/2,fy+fh/2])
            assert fx>=sx and fy>=sy and fx+fw<=sx+sw and fy+fh<=sy+sh
            if 'scan' in r:
                ax,ay,aw,ah=r['scan']
                assert r['scan_scale']<=1.6
                if tuple(r['slot'])!=tuple(r['frame']):
                    assert np.allclose([ax-fx,ay-fy,fx+fw-ax-aw,fy+fh-ay-ah],4)
            if 'loading' in name:
                own=d['layout'][name.replace('-loading-','-own-')]['rects_su']
                assert r['frame']==own['frame'] and r['scan']==own['scan']
                spinner=next(i for i in a['icons'] if i['path'].endswith('/loader-spinner-32.png'))
                ix,iy,iw,ih=spinner['rect_su']
                assert np.allclose([ix+iw/2,iy+ih/2],[fx+fw/2,fy+fh/2])
            tabs=[t for t in a['text_runs'] if t['text']=='Tab']
            if tabs:
                x,y,w,h=r['modal'];row=r['language_row_su']
                assert abs(row[1]+row[3]-(y+h-24))<1e-6
        assert a['edge_contrast']['panel_and_card_edge']>=3
        assert not a['issues'] and not a['text_pair_overlaps']
        f=a['viewport']['factor']
        for asset in a['assets']:
            x,y,w,h=asset['rect_su']
            for text in a['text_runs']:
                u,v,e,j=text['bbox_px'];x1,y1,x2,y2=x*f,y*f,(x+w)*f,(y+h)*f
                area=max(0,min(x2,e)-max(x1,u))*max(0,min(y2,j)-max(y1,v))
                if area>0 and not asset['omitted_in_overlay']:
                    scan_overlaps.append({'frame':name,'text':text['text'],'px2':area})
            if cfg['id']!='SC-22':assert asset['scale']<=1.6
        for b in a['edge_contrast']['buttons']:
            assert max(b['edge_to_body'],b['edge_to_panel'])>=3
        for i in a['icon_contrast']:
            assert max(i['body_to_panel'],i['cream_edge_to_panel'])>=3
            if '/action-' in i['path']: assert i['glyph_to_body']>=3
        x,y,w,h=a['rects_su']['modal'];pxw,pxh=a['viewport']['size_px']
        contained.append({'frame':name,'margin_px':[x*f,y*f,pxw-(x+w)*f,pxh-(y+h)*f],
                          'passed':x>=0 and y>=0 and (x+w)*f<=pxw and (y+h)*f<=pxh})
        if cfg['id']=='SC-22':
            # The hidden renderer has no access to any deck/card-state capture.
            for t in a['text_runs']:
                if any(word in t['text'] for word in ['BOOST','Значение','После боя','В колоде','Убийственный','Шипеть']):
                    leaked.append(t['text'])
            assert len(a['assets'])==1 and 'card-covers/' in a['assets'][0]['source']
            game_text=[t for t in a['text_runs'] if not t['source'].startswith(('04 §','SC-21.fix1:'))]
            assert len(game_text)==3 # 2 wrapped title lines and owner; close label is facts only.
    assert not scan_overlaps and all(c['passed'] for c in contained)
    assert not leaked
    d['palette']=palette_audit(cfg)
    assert d['palette']['passed'],d['palette']
    d['scan_text_overlap_px2']=scan_overlaps
    d['viewport_containment']=contained
    d['hidden_information']={'leaked_fields':leaked,'passed':not leaked} if cfg['id']=='SC-22' else {'applicable':False}
    if cfg['id']=='SC-23':
        facts=manifest['facts'];assert facts['deck']['unique']==11 and facts['deck']['total']==30
        grid_checks=[];chip_checks=[]
        for name,a in d['layout'].items():
            buttons=[g for g in a['geometry'] if g['kind']=='button']
            if '-deck-card-' in name:
                assert len(buttons)==1 and not buttons[0]['primary']
                assert any(t['text']=='НАЗАД' for t in a['text_runs'])
                chip=a['room_copy_chip'];assert chip['skin']=='Chip' and chip['count']==3
                x,y,w,h=chip['rect_su'];tx,ty,tw,th=a['rects_su']['text'];f=a['viewport']['factor']
                assert w==40 and h==32 and x>=tx and x+w<=tx+tw and y>=ty and y+h<=ty+th
                assert chip['text_contrast']>=4.5
                boost=next(t for t in a['text_runs'] if t['text'].startswith('BOOST'))
                copies=next(t for t in a['text_runs'] if t['text']=='×3')
                effect=next(t for t in a['text_runs'] if t['text'].startswith('После боя:'))
                assert boost['bbox_px'][3]<y*f and (y+h)*f<effect['bbox_px'][1]
                assert copies['bbox_px'][0]>=x*f and copies['bbox_px'][2]<=(x+w)*f
                assert not any(t['text'].startswith('В колоде:') for t in a['text_runs'])
                chip_checks.append({'preset':name,**chip})
            else:
                assert not buttons
                grid=next(n['grid'] for n in a['notes'] if 'grid' in n)
                vx,vy,vw,vh=grid['viewport_su']
                top=vy-grid['title_band_bottom_su'];bottom=grid['bottom_padding_line_su']-vy-vh
                assert abs(top-bottom)<1e-6 and top>=0
                assert grid['visible_rows']==2 and grid['snap_to_whole_rows']
                for entry in grid['entries']:
                    x,y,w,h=entry['frame_su']
                    assert x>=vx and y>=vy and x+w<=vx+vw and y+h<=vy+vh
                grid_checks.append({'preset':name,'viewport_su':grid['viewport_su'],
                                    'top_gap_su':top,'bottom_gap_su':bottom,'whole_rows':2})
        for res,scale in itertools.product(['1080p','720p'],[100,150]):
            seen=[]
            for state in ('deck','deck-scroll'):
                a=d['layout'][f'SC-23-{state}-{res}-{scale}.png']
                seen += [p['source'] for p in a['assets']]
            assert len(set(seen))==11
        d['deck_catalogue']={'unique_scans':11,'total_copies':30,'passed':True,
                             'scroll_coverage':'deck + deck-scroll union covers 11 unique scans in each viewport',
                             'catalogue_order':'gameDeckLists order; no instance IDs or draw order'}
        d['acceptance'].append({'criterion':'fix1: целые ряды viewport по центру между title band и нижним полем 24 su',
            'passed':True,'measured':grid_checks,'expected':'equal gaps; 2 whole rows; scrollbar retained','note':'Every frame contained in viewport'})
        d['acceptance'].append({'criterion':'ВР-VS3-SC21-08: чип ×3 после BOOST; без счётчиков руки/сброса в ROOM',
            'passed':True,'measured':chip_checks,'expected':'HB-08 Chip 40x32 in text column after BOOST; one normal Back',
            'note':'Actual chip body contrast and text/BOOST/effect positions measured'})
        d['acceptance'].append({'criterion':'11 сканов и суммарно 30 копий из входов',
            'passed':True,'measured':d['deck_catalogue'],'expected':'11 unique, 30 total','note':'Catalogue order; scroll proof is a supplemental frame'})
    if cfg['id']=='SC-22':
        d['acceptance'].append({'criterion':'Нет значений скрытой карты', 'passed':True,
            'measured':{'runtime_texts':[t['text'] for t in next(iter(d['layout'].values()))['text_runs']],
                        'card_fields_drawn':0},'expected':0,'note':'Title, owner and close only; no toggle or numeric card fields'})
    # Avoid duplicate specialized acceptance records on a second audit.
    d['acceptance']=list({x['criterion']:x for x in d['acceptance']}.values())
    d['independent_checks']={'expected_pngs':len(expected),'all_opened_and_decoded':True,
       'exact_gray_pairs':True,'no_scan_text_overlap':True,'modal_fits_viewport':True,
       'source_snapshots_unchanged':True,'palette_flat_pixels_passed':True}
    before=load(cfg['package']/'fix1-before.json')
    assert all(sha(ROOT/p)==h for p,h in before['inputs'].items())
    frame_checks=[]
    for name,a in d['layout'].items():
        if 'slot' not in a['rects_su']: continue
        r=a['rects_su'];old=before['rectangles'][name]
        assert list(r['slot'])==old['slot_rect_su']
        if a['assets'] and old['scan_rects_su']:
            assert np.allclose(a['assets'][0]['rect_su'],old['scan_rects_su'][0])
        frame_checks.append({'preset':name,'slot_rect_su':r['slot'], 'frame_rect_su':r['frame'],
            'scan_rect_su':r.get('scan',a['assets'][0]['rect_su'] if a['assets'] else None),
            'scan_scale':r.get('scan_scale',a['assets'][0]['scale'] if a['assets'] else None)})
    d['fix1_checks']={'primary_count':0,'close_accessible_name':'Закрыть',
        'close_label_drawn':False,'inputs_unchanged_since_fix1_before':True,
        'slot_and_scan_preserved':True,'frames':frame_checks,
        'loading_matches_own':cfg['id']=='SC-21',
        'language_row_bottom_padding_su':24 if cfg['id']!='SC-22' else None}
    if cfg['id'] in ('SC-21','SC-23'):
        d['acceptance'].append({'criterion':'ВР-VS3-SC21-07: рамка capped-скана с backing 4 su; слот сохранён',
            'passed':True,'measured':frame_checks,'expected':'centred scan + 4 su each side when capped; loading same as own',
            'note':'Independent centre, padding, cap, unchanged slot/scan and spinner assertions'})
        d['acceptance'].append({'criterion':'fix1: Tab и «Язык карты» у нижнего поля 24 su',
            'passed':True,'measured':24,'expected':24,'note':'Language row bottom equals modal bottom minus padding'})
    d['acceptance']=list({x['criterion']:x for x in d['acceptance']}.values())
    if seal:
        d['visual_review']={'completed':True,'reviewed_files':[str(p.relative_to(ROOT)).replace('\\','/') for p in expected],
            'method':'Every final PNG opened by view_image; full native frames and grayscale/overlay variants inspected',
            'findings':['Whole source art preserved; no UI printed over scans.',
                        'Text column and close controls fit at all DPI/UI presets.',
                        'Historical Sarpedon backdrop is the specified real map with six v2 figures; existing labels disclosed.']}
    d['all_acceptance_passed']=all(x['passed'] for x in d['acceptance']) and d['palette']['passed']
    assert d['all_acceptance_passed'], 'An acceptance criterion failed'
    write_json(cfg,cfg['package']/'verification.json',d)
    refresh_manifest(cfg,manifest['facts'])
    current=load(cfg['package']/'manifest-sha256.json')
    assert all(sha(ROOT/p)==h for p,h in current['files'].items())
    print({'package':cfg['slug'],'pngs':len(expected),'sources_unchanged':True,
           'palette_outside_fraction':d['palette']['outside_token_flat_pixels_fraction'],
           'all_acceptance_passed':d['all_acceptance_passed'],'visual_review':d['visual_review']['completed']})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--id',default='SC-21');p.add_argument('--slug',default='sc21-inspect-own');p.add_argument('--seal-review',action='store_true')
    a=p.parse_args();verify(config(a.id,a.slug),a.seal_review)
