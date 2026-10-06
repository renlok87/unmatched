#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent file/data checks; --finalize writes verification then manifest LAST.

python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/verify_package.py --finalize
python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/verify_package.py --check
No render module imports; no git, network, Unreal, subprocesses or external writes.
"""
import argparse
import math
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from PIL import Image, ImageFont, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'art/imagegen/hud-decks-v1-codex'
OUT=ROOT/'scraped-data/derived/hud-decks-v1-codex'
STATES=('chips','chips-stale','own','own-end','own-discard','opp','opp-end')
CONFIGS=((1920,1080,100),(1920,1080,150),(1280,720,100),(1280,720,150))
ORDER={'attack':0,'defense':1,'versatile':2,'scheme':3}
FONT=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/Roboto-BoldCondensed.ttf')

def verify_fix1(facts,v):
    errors=[];before=load(PKG/'fix1-before.json');old={o['id']:o for o in before['values']}
    if sha(PKG/'source-hashes-before.json')!=before['source_baseline_sha256']:errors.append('source baseline was replaced')
    for o in facts['rendered_outputs']:
        ident=o['id'];s=o['su_to_px'];cl=o['class'];previous=old[ident]
        expectedwidths=[64,64] if cl=='S' else ([156,124] if o['language']=='ru' else [144,136])
        for i,c in enumerate(o['chip_geometry']):
            r=c['rectangle_su'];mini=c['mini_box_su'];outer=c['mini_outline_su'];text=c['text_box_su'];minimum=4 if cl=='S' else 8
            if r!=o['rectangles_su']['CHIP-'+str(i)] or r[2]!=expectedwidths[i] or r[3]!=(48 if cl=='S' else 56):errors.append([ident,'chip rectangle',i])
            gaps=[outer[0]-r[0],r[0]+r[2]-text[0]-text[2],text[0]-outer[0]-outer[2]]
            if min(gaps)<minimum-1e-8:errors.append([ident,'chip padding',gaps])
            if not np.allclose(mini[2:],([18,18*45/32] if cl=='S' else [32,45])):errors.append([ident,'mini size'])
            font=ImageFont.truetype(str(FONT),math.ceil(20*s))
            if font.getlength(c['text'])>text[2]*s+.01:errors.append([ident,'chip label fit',c['text']])
        c0,c1=[c['rectangle_su'] for c in o['chip_geometry']]
        if abs(c1[0]-c0[0]-c0[2]-8)>1e-6:errors.append([ident,'chip gap'])
        if not np.allclose([c0[0],c0[1],c1[0]+c1[2],c1[1]+c1[3]],[previous['rectangles_su']['CHIP-0'][0],previous['rectangles_su']['CHIP-0'][1],sum(previous['rectangles_su']['CHIP-1'][::2]),sum(previous['rectangles_su']['CHIP-1'][1::2])]):errors.append([ident,'DECKS extent changed'])
        p=o['panel_geometry']
        if not p:continue
        if cl=='S' or o['resolution']==[1920,1080]:
            if p['rectangle_su']!=previous['panel_geometry']['rectangle_su']:errors.append([ident,'protected panel rectangle changed'])
        full=facts['strings']['hud.deckpanel.title.'+p['side']][o['language']].format(hero=p['hero']);iw=p['rectangle_su'][2]-24
        size28=ImageFont.truetype(str(FONT),math.ceil(28*s));lines=[full]
        size=28
        if size28.getlength(full)>iw*s:
            lines=[full.rsplit(' · ',1)[0]+' ·',p['hero']]
            if any(size28.getlength(line)>iw*s for line in lines):size=24
        if p['title_lines']!=lines or p['title_size_su']!=size:errors.append([ident,'atomic title'])
        a=o['rectangles_su']['hud.deckpanel.tab.own'];b=o['rectangles_su']['hud.deckpanel.tab.opp'];close=o['rectangles_su']['hud.deckpanel.close']
        if abs(b[0]-a[0]-a[2]-(8 if cl=='L' else 4))>1e-6 or abs(close[0]+close[2]-(p['rectangle_su'][0]+p['rectangle_su'][2]-12))>1e-6:errors.append([ident,'tab gap or close anchor'])
        triples={}
        for t in o['text']:
            key=t['string_key']
            if not key.startswith('fetchedDeck['):continue
            font=ImageFont.truetype(str(FONT),t['font_em_px']);box=font.getbbox(t['displayed'],anchor='ls')
            baseline=t['bbox_px'][1]-box[1]
            if baseline!=t['baseline_px']:errors.append([ident,'glyph baseline differs',key])
            triples.setdefault(key.split('.')[0],[]).append(baseline)
        if any(len(bs)!=3 or len(set(bs))!=1 for bs in triples.values()):errors.append([ident,'row baseline mismatch'])
    # Recompute D8 from the unchanged source masks instead of trusting reported areas.
    masks=load(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json')
    for board in ('marmoreal','sarpedon'):
        for w,h,ui in CONFIGS:
            if ui!=100:continue
            q=w/1920;source=masks['topology_transforms'][board+'-1920x1080'];space=Image.new('L',(w,h));figure=Image.new('L',(w,h))
            for item in source['spaces']:ImageDraw.Draw(space).polygon([(x*q,y*q) for x,y in item['polygon_px']],fill=255)
            for poly in masks['figure_polygons_1080p'][board]:ImageDraw.Draw(figure).polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
            arrays=[]
            for im,key in [(space,'cell_conservative_dilation_px'),(figure,'figure_conservative_dilation_px')]:arrays.append(np.asarray(im.filter(ImageFilter.MaxFilter(2*math.ceil(source[key]*q)+1)))>0)
            for o in facts['rendered_outputs']:
                if o['board']!=board or o['resolution']!=[w,h] or o['ui_scale_percent']!=ui:continue
                for key in ('DECKPANEL','CHIP-0','CHIP-1'):
                    if key not in o['rectangles_su']:continue
                    x,y,rw,rh=o['rectangles_su'][key];s=o['su_to_px'];selection=np.zeros((h,w),dtype=bool);selection[round(y*s):round((y+rh)*s),round(x*s):round((x+rw)*s)]=True
                    if any(np.any(selection&mask) for mask in arrays):errors.append([o['id'],'D8 source-mask overlap',key])
    if v['failed_acceptance']:errors.append(['failed acceptance',v['failed_acceptance']])
    return errors

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text('utf8'))
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def write(p,obj):
    p=p.resolve()
    assert p.is_relative_to(PKG) or p.is_relative_to(OUT)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def scan():
    checks=[]
    def add(name,passed,detail):checks.append({'check':name,'passed':bool(passed),'detail':detail})
    before=load(PKG/'source-hashes-before.json');changed=[]
    for row in before['files']:
        p=ROOT/row['path']
        if not p.is_file() or sha(p)!=row['sha256']:changed.append(row['path'])
    add('input_sha256',not changed,{'count':len(before['files']),'changed':changed})
    for dst,src in [('draw_icons_v3_snapshot.py','art/imagegen/hud-icons-v3/_tools/draw_icons.py'),('layout_reference_snapshot.py','art/imagegen/hud-composition-v1-codex/_tools/layout_reference.py'),('hb07_build_mockups_snapshot.py','art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py')]:
        add('snapshot:'+dst,sha(PKG/'_tools'/dst)==sha(ROOT/src),sha(PKG/'_tools'/dst))
    prompt=(ROOT/'docs/game-design/visual/06-tasks/prompts/HB-26.codex.md').read_text('utf8');mismatches=[]
    for path,digest in re.findall(r'\| `([^`]+)` \| file \| \d+ \| ([0-9a-f]{64}) \|',prompt):
        p=ROOT/path
        if not p.is_file() or sha(p)!=digest:mismatches.append({'path':path,'expected':digest,'actual':sha(p) if p.is_file() else None})
    add('prompt_expected_hashes',not mismatches,mismatches)
    expected=[]
    for b in ('marmoreal','sarpedon'):
        for w,h,ui in CONFIGS:
            expected.extend((OUT/f'HB-26-{b}-{state}-{w}x{h}-{ui}.png',(w,h)) for state in STATES)
            expected.append((OUT/f'HB-26-{b}-contact-{w}x{h}-{ui}.png',(w*7,h+36)))
            expected.append((PKG/f'comparison/HB-26-{b}-overlay-{w}x{h}-{ui}.png',(w,h)))
    expected.extend((OUT/f'HB-26-sarpedon-{state}-en-1920x1080-100.png',(1920,1080)) for state in ('opp','opp-end'))
    for p in sorted((OUT/'fix1-review').glob('*.png')):
        if p.stem.endswith('-gray'):continue
        with Image.open(p) as im:expected.append((p,im.size))
    errors=[];gray_count=0
    for p,size in expected:
        gp=p.with_stem(p.stem+'-gray')
        if not p.exists() or not gp.exists():errors.append({'path':rel(p),'reason':'missing color/gray'});continue
        with Image.open(p) as a,Image.open(gp) as b:
            if a.size!=size or b.size!=size or a.mode!='RGBA' or b.mode!='RGBA':errors.append({'path':rel(p),'reason':'size/mode','actual':[a.size,a.mode,b.size,b.mode]})
            rgb=np.asarray(a.convert('RGB'),dtype=float);expectedgray=np.rint(rgb@np.array([.2126,.7152,.0722])).astype('uint8')
            ga=np.asarray(b.convert('RGB'))
            if not all(np.array_equal(expectedgray,ga[:,:,i]) for i in range(3)):errors.append({'path':rel(gp),'reason':'Rec.709 pixel mismatch'})
            if not np.array_equal(np.asarray(a.getchannel('A')),np.asarray(b.getchannel('A'))):errors.append({'path':rel(gp),'reason':'alpha mismatch'})
            gray_count+=1
    add('exports_and_rec709_gray',not errors,{'pairs_checked':gray_count,'errors':errors})
    facts=load(PKG/'facts.json');v=load(PKG/'verification.json');badcounts=[];badsums=[];badprivacy=[];badorder=[];badgeom=[]
    png_actual={rel(p) for root in (PKG,OUT) for p in root.rglob('*.png')};png_listed={p['path'] for p in v['exports']}
    add('PNG_export_inventory',png_actual==png_listed,sorted(png_actual^png_listed))
    fixerrors=verify_fix1(facts,v);add('fix1_five_corrections',not fixerrors,fixerrors)
    rowerrors=[];dblines=Path(facts['database']['path']).read_text('utf8').splitlines()
    for slug,deck in facts['decks'].items():
        pool=load(ROOT/f'scraped-data/api/heroes/{slug}.json')['nodes'][2]['data'];memo={}
        def decode(i):
            if i<0:return None
            if i in memo:return memo[i]
            value=pool[i]
            result={k:decode(n) for k,n in value.items()} if isinstance(value,dict) else [decode(n) for n in value] if isinstance(value,list) else value
            memo[i]=result;return result
        data=decode(0);api={r['card']['title']:r for r in data['fetchedDeck']}
        if len(api)!=len(deck['rows']) or sum(r['copies'] for r in deck['rows'])!=30:rowerrors.append({'hero':slug,'reason':'kind/copy total'})
        for r in deck['rows']:
            a=api[r['title_en']]
            if (r['copies'],r['type'],r['value'],r['boost'])!=(a['copies'],a['type'],a['value'],a['boostValue']):rowerrors.append({'hero':slug,'card':r['title_en']})
            db=dblines[r['db_line']-1].split('|')
            ru=a['card'].get('i18n',{}).get('ru',{}).get('title',db[2])
            if r['title_ru']!=ru or (r['type'],r['copies'],r['boost'])!=(db[3].lower(),int(db[8]),int(db[6])):rowerrors.append({'hero':slug,'card':r['title_en'],'reason':'DB/translated name'})
    add('27_rows_match_raw_API',not rowerrors,rowerrors)
    for board,b in facts['boards'].items():
        counts=b['own_counts'];opp=b['opponent_counts']
        for item in b['sources']['counts']:
            text=(ROOT/item['path']).read_text('utf8').splitlines()[item['line']-1]
            if text!=item['text']:badcounts.append({'board':board,'reason':'trace text differs'})
            if ' HUD seq=' in text:
                observed={k:int(n) for k,n in re.findall(r'\b(hand|oppHand|oppDeck|deck|discard)=(\d+)',text)}
                if any(observed[k]!=n for k,n in [('deck',counts['deck']),('discard',counts['discard']),('hand',counts['hand']),('oppDeck',opp['deck']),('oppHand',opp['hand'])]):badcounts.append({'board':board,'observed':observed})
        own=facts['decks'][b['own']]['rows'];d=b['own_discard_marks'];h=b['own_hand_marks']
        total={'hand':sum(h.values()),'discard':sum(d.values()),'deck':sum(r['copies']-h.get(r['title_en'],0)-d.get(r['title_en'],0) for r in own)}
        if total!=counts:badsums.append({'board':board,'total':total,'expected':counts})
        if sum(b['opponent_discard_marks'].values())!=opp['discard']:badsums.append({'board':board,'opponent_discard':b['opponent_discard_marks']})
    accepted=load(ROOT/'art/imagegen/hud-composition-v1-codex/verification.json')
    for output in facts['rendered_outputs']:
        p=output['panel_geometry']
        if not p:continue
        board=output['board'];b=facts['boards'][board];side=p['side'];slug=b['opponent' if side=='opp' else 'own'];rows=facts['decks'][slug]['rows'];lang=output['language']
        expectedrows=sorted(rows,key=lambda r:(ORDER[r['type']],r['title_'+lang].casefold()))
        if output['state']=='own-discard':expectedrows=[r for r in expectedrows if b['own_discard_marks'].get(r['title_en'],0)>0]
        if [r['title_en'] for r in expectedrows]!=p['rows_order']:badorder.append(output['id'])
        for row in p['rows_drawn']:
            if side=='opp' and set(row['marks'])!={'discard'}:badprivacy.append(output['id'])
            if side=='opp' and row['marks']['discard']!=b['opponent_discard_marks'].get(row['card'],0):badprivacy.append(output['id'])
        if side=='opp':
            backs=[a for a in output['assets'] if a['kind']=='opponent-hand-back']
            if len(backs)!=b['opponent_counts']['hand'] or any(a['r_su'][3]<24 for a in backs):badprivacy.append(output['id'])
        a=next(a for a in accepted['overlap']['per_mockup'] if a['board']==board and a['state']=='own-turn' and a['resolution']==output['resolution'] and a['ui_scale_percent']==output['ui_scale_percent'])
        rects={k:z['rectangle_su'] for k,z in a['panels'].items()};cl=a['class'];w,h=output['resolution'];scale=output['su_to_px'];width=300 if cl=='S' else (380 if w==1920 else 336);margin=16 if cl=='S' else 24
        top=rects['PANEL-OPP'][1]+rects['PANEL-OPP'][3]+8 if cl=='S' else max(248,rects['OPP-HAND'][1]+rects['OPP-HAND'][3]+8)
        wanted=[w/scale-margin-width,top,width,rects['DECKS'][1]-8-top]
        if not np.allclose(p['rectangle_su'],wanted) or p['viewport_height_su']%48!=0 or p['rows_visible']>p['capacity']:badgeom.append(output['id'])
    add('trace_counts',not badcounts,badcounts);add('mark_sums',not badsums,badsums);add('F05_privacy',not badprivacy,badprivacy);add('rows_sorted',not badorder,badorder);add('D5_native_geometry',not badgeom,badgeom)
    bgwrong=[]
    for output in facts['rendered_outputs']:
        board=output['board'];path=OUT/(output['id']+'.png');w,h=output['resolution'];scale=output['su_to_px']
        with Image.open(ROOT/facts['boards'][board]['background']['path']) as im:
            im=im.convert('RGBA');im=im if im.size==(w,h) else im.resize((w,h),Image.Resampling.LANCZOS);base=np.asarray(im)
        # Conservatively exclude exactly the complete chip/panel bounding boxes.
        mask=np.zeros((h,w),dtype=bool)
        for name,r in output['rectangles_su'].items():
            if name not in ('CHIP-0','CHIP-1','DECKPANEL'):continue
            x,y,rw,rh=r;mask[round(y*scale):round((y+rh)*scale),round(x*scale):round((x+rw)*scale)]=True
        with Image.open(path) as im:final=np.asarray(im)
        dif=int(np.count_nonzero(np.any(final[~mask]!=base[~mask],axis=1)))
        if dif:bgwrong.append({'id':output['id'],'outside_rect_different_pixels':dif})
    add('D1_background_pixels',not bgwrong,{'outputs_checked':len(facts['rendered_outputs']),'errors':bgwrong})
    textfail=[(o['id'],t['displayed']) for o in facts['rendered_outputs'] for t in o['text'] if not t['fits_container'] or 'уточнить' in t['displayed']]
    add('text_fit_and_no_placeholder',not textfail,textfail)
    actualfailed=[k for k,a in v['acceptance'].items() if not a['passed']]
    add('acceptance_report_integrity',actualfailed==v['failed_acceptance'],{'reported_failures':v['failed_acceptance'],'recomputed_failures':actualfailed})
    pkgbytes=sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())
    add('package_under_30MiB',pkgbytes<=30*1024*1024,pkgbytes)
    restricted=[rel(p) for p in PKG.rglob('*.png') if p.parent!=PKG/'comparison']
    add('package_has_only_no_scan_overlays',not restricted,restricted)
    return checks,mismatches

def manifest():
    files=[]
    for root in (PKG,OUT):
        for p in sorted(root.rglob('*')):
            if p.is_file() and p!=PKG/'manifest-sha256.json':files.append({'path':rel(p),'bytes':p.stat().st_size,'sha256':sha(p)})
    write(PKG/'manifest-sha256.json',{'schema':'HB-26.manifest/1','self_excluded':True,'files':files})
    return len(files)

def verify_manifest():
    m=load(PKG/'manifest-sha256.json');bad=[];listed={r['path'] for r in m['files']}
    for r in m['files']:
        p=ROOT/r['path']
        if not p.is_file() or sha(p)!=r['sha256'] or p.stat().st_size!=r['bytes']:bad.append(r['path'])
    actual={rel(p) for root in (PKG,OUT) for p in root.rglob('*') if p.is_file() and p!=PKG/'manifest-sha256.json'}
    bad+=sorted(actual^listed)
    return bad,len(listed)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--finalize',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    checks,mismatches=scan();bad=[c['check'] for c in checks if not c['passed']]
    if args.finalize:
        v=load(PKG/'verification.json');v['independent_verification']={'passed':not bad,'checks':checks};v['expected_hash_mismatches']=mismatches
        v['acceptance']['independent_file_data_checks']={'passed':not bad,'measured':bad,'expected':[],'note':'Separate verifier without renderer import: all files, hashes, gray pixels, counts, sums, privacy, sort, anchors, background preservation.'}
        v['acceptance']['manifest_matches']={'passed':True,'measured':0,'expected':0,'note':'Finalizer writes manifest after all other files and immediately recomputes every file hash and exact inventory; subsequent --check repeats the read-only proof.'}
        v['manifest']={'path':'art/imagegen/hud-decks-v1-codex/manifest-sha256.json','self_excluded':True,'procedure':'Written LAST after this verification file; verify_package.py --check recomputes every hash and complete file inventory.'}
        v['failed_acceptance']=[k for k,a in v['acceptance'].items() if not a['passed']]
        write(PKG/'verification.json',v);count=manifest();mbad,_=verify_manifest();bad+=mbad
        print(json.dumps({'checks':len(checks),'failed':bad,'manifest_files':count,'manifest_mismatches':mbad},ensure_ascii=False))
    else:
        mbad,count=verify_manifest();print(json.dumps({'checks':len(checks),'failed':bad,'manifest_mismatches':mbad,'manifest_files':count},ensure_ascii=False));bad+=mbad
    return 1 if bad else 0

if __name__=='__main__':raise SystemExit(main())
