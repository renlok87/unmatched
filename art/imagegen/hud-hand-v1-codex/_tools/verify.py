"""Read-only independent HB-22 audit. Does not regenerate or edit evidence."""
import hashlib
import itertools
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PKG=Path(__file__).resolve().parents[1]
ROOT=PKG.parents[2]
DERIVED=ROOT/'scraped-data/derived/hud-hand-v1-codex'


def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):
    try:return p.relative_to(ROOT).as_posix()
    except ValueError:return p.as_posix()


def maskrect(r,s,w,h):
    x,y,rw,rh=r
    x0,y0,x1,y1=round(x*s),round(y*s),round((x+rw)*s),round((y+rh)*s)
    x1=max(x1,x0+round(rw*s));y1=max(y1,y0+round(rh*s))
    m=np.zeros((h,w),bool);m[max(0,y0):min(h,y1),max(0,x0):min(w,x1)]=True
    return m


def run():
    errors=[];v=load(PKG/'verification.json');facts=load(PKG/'facts.json')
    readme=(PKG/'README.md').read_text(encoding='utf8')
    lan='Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-hand-v1-codex/.'
    if lan not in readme:errors.append('Missing verbatim H12 LAN sentence')
    if not any(t['text']=='Hand 5/7' and '-en-' in t['mockup'] for t in facts['rendered_texts']):errors.append('Missing traced EN caption')
    manifest=load(PKG/'manifest-sha256.json')['files']
    paths={rel(p) for r in [PKG,DERIVED] for p in r.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
    if paths!=set(manifest):errors.append('Manifest file set mismatch')
    for p,digest in manifest.items():
        if sha(ROOT/p)!=digest:errors.append('Manifest bytes differ: '+p)
    sources=load(PKG/'source-hashes-before.json')['files']
    for p,row in sources.items():
        if not (ROOT/p).is_file() or sha(ROOT/p)!=row['sha256']:errors.append('Source changed: '+p)
    for original,snapshot in [('art/imagegen/hud-icons-v3/_tools/draw_icons.py','draw_icons_v3_snapshot.py'),
                              ('art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py','hb07_build_snapshot.py'),
                              ('art/imagegen/hud-composition-v1-codex/_tools/layout_reference.py','hb07_layout_snapshot.py')]:
        if sha(ROOT/original)!=sha(PKG/'_tools'/snapshot):errors.append('Snapshot mismatch '+snapshot)
    initial={p for p in sources if p.startswith('art/imagegen/hud-icons-v3/')}
    current={rel(p) for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    if initial!=current:errors.append('v3 file set changed')
    outputs=facts['outputs'];assert len(outputs)==97
    for o in outputs:
        p=ROOT/o['path'];gp=p.with_stem(p.stem+'-gray')
        with Image.open(p) as im,Image.open(gp) as gi:
            a=np.asarray(im.convert('RGBA'));g=np.asarray(gi.convert('RGBA'))
            expected=np.floor(np.einsum('ijk,k->ij',a[:,:,:3].astype(float),np.array([.2126,.7152,.0722]))+.5).astype('uint8')
            if not np.all(g[:,:,:3]==expected[:,:,None]) or not np.array_equal(g[:,:,3],a[:,:,3]):errors.append('Rec709 mismatch '+p.name)
            parts=o['id'].rsplit('-',2);res=parts[-2];w,h=map(int,res.split('x'))
            if im.size!=(w,h) or im.mode!='RGBA':errors.append('Wrong native size/mode '+p.name)
    for row in v['exports']:
        with Image.open(ROOT/row['path']) as im:
            if list(im.size)!=row['size'] or im.mode!=row['mode']:errors.append('Export metadata mismatch '+row['path'])
    if len(v['exports'])!=226:errors.append('PNG count differs')
    # Rebuild immutable registered masks and independently recompute all audit intersections.
    masks=load(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json')
    old=load(ROOT/'art/imagegen/hud-composition-v1-codex/verification.json')
    cached={}
    for o in v['overlap']['per_mockup']:
        w,h,ui=o['canvas'];s=(1 if w==1920 else .75)*ui/100;board=o['board']
        key=(board,w,h)
        if key not in cached:
            m=masks['topology_transforms'][f'{board}-{w}x{h}'];sm=Image.new('L',(w,h));d=ImageDraw.Draw(sm)
            for r in m['spaces']:d.polygon([tuple(p) for p in r['polygon_px']],fill=255)
            sm=sm.filter(ImageFilter.MaxFilter(2*m['cell_conservative_dilation_px']+1))
            fm=Image.new('L',(w,h));d=ImageDraw.Draw(fm)
            for r in masks['figure_polygons_1080p'][board]:d.polygon([(round(x*w/1920),round(y*w/1920)) for x,y in r],fill=255)
            fm=fm.filter(ImageFilter.MaxFilter(2*m['figure_conservative_dilation_px']+1));cached[key]=(np.asarray(sm)>0,np.asarray(fm)>0)
        sm,fm=cached[key]
        ref=next(r for r in old['overlap']['per_mockup'] if r['board']==board and r['state']=='own-turn' and r['resolution']==[w,h] and r['ui_scale_percent']==ui)
        blockmasks={}
        for name,row in o['panels'].items():
            m=np.zeros((h,w),bool)
            for r in row['rectangles_su']:m|=maskrect(r,s,w,h)
            blockmasks[name]=m
            if int(np.count_nonzero(m&sm))!=row['space_overlap_px2'] or int(np.count_nonzero(m&fm))!=row['figure_overlap_px2']:
                errors.append('Incorrect mask measurement '+o['id']+'/'+name)
            for reserved,measured in row['reserved_overlap_px2'].items():
                actual=int(np.count_nonzero(m&maskrect(ref['panels'][reserved]['rectangle_su'],s,w,h)))
                if actual!=measured:errors.append('Incorrect reserved intersection '+o['id']+'/'+name)
            if name=='HAND-CAPTION':
                reserve=row['reserved_row'];rm=maskrect(reserve['rectangle_su'],s,w,h)
                if int(np.count_nonzero(rm&sm))!=reserve['space_overlap_px2'] or int(np.count_nonzero(rm&fm))!=reserve['figure_overlap_px2']:
                    errors.append('Incorrect full caption reservation '+o['id'])
                for reserved,measured in reserve['reserved_overlap_px2'].items():
                    if int(np.count_nonzero(rm&maskrect(ref['panels'][reserved]['rectangle_su'],s,w,h)))!=measured:
                        errors.append('Incorrect caption reserved intersection '+o['id'])
        for a,b in itertools.combinations(blockmasks,2):
            if int(np.count_nonzero(blockmasks[a]&blockmasks[b]))!=o['block_pairs_px2'][a+' / '+b]:errors.append('Incorrect block pair '+o['id'])
        allowed=o['intentional_occlusion_px2']
        if any(set(k.split(' / '))!={'ATTACK-BOOST','COMBAT-L'} or o['state']!='boost-attack' or o['block_pairs_px2'][k]!=value for k,value in allowed.items()):
            errors.append('Invalid intentional occlusion '+o['id'])
        zero=all(r['figure_overlap_px2']==r['space_overlap_px2']==0 and not any(r['reserved_overlap_px2'].values()) for r in o['panels'].values()) and not any(value for k,value in o['block_pairs_px2'].items() if k not in allowed)
        if zero!=o['persistent_zero']:errors.append('Incorrect persistent_zero '+o['id'])
        transient=next(t['elements'] for t in v['transient_overlap'] if t['id']==o['id'])
        for name,row in transient.items():
            tm=maskrect(row['rectangle_su'],s,w,h)
            if int(np.count_nonzero(tm&sm))!=row['space_overlap_px2'] or int(np.count_nonzero(tm&fm))!=row['figure_overlap_px2']:
                errors.append('Incorrect transient mask measurement '+o['id']+'/'+name)
            for block,value in row['persistent_blocks_overlap_px2'].items():
                if int(np.count_nonzero(tm&blockmasks[block]))!=value:errors.append('Incorrect transient block measurement '+o['id']+'/'+name)
            for reserved,value in row['reserved_overlap_px2'].items():
                if int(np.count_nonzero(tm&maskrect(ref['panels'][reserved]['rectangle_su'],s,w,h)))!=value:errors.append('Incorrect transient reserve measurement '+o['id']+'/'+name)
    import fix1_audit
    correction=fix1_audit.check(facts,v,load(PKG/'fix1-before.json'))
    if correction!=v['fix1'] or correction!=facts['fix1']:errors.append('Stale fix1 measurements')
    for name,row in correction['checks'].items():
        if not row['passed']:errors.append('Corrective check failed '+name)
        if v['acceptance'][name]['passed']!=row['passed'] or v['acceptance'][name]['measured']!=row['measured']:
            errors.append('Incorrect corrective acceptance '+name)
    before=load(PKG/'fix1-before.json')
    for p,digest in before['package_files_before'].items():
        # The correction may regenerate all outputs, but these bytes must stay fixed.
        immutable=p.endswith(('/source-hashes-before.json','/generation-records.json','/frame_native.py','/draw_icons_v3_snapshot.py','/hb07_build_snapshot.py','/hb07_layout_snapshot.py')) or ('/HB-22-' in p and '-lowered-' in p)
        if immutable and sha(ROOT/p)!=digest:errors.append('Unrequested content changed '+p)
    for t in facts['rendered_texts']:
        if 'уточнить' in t['text'].lower():errors.append('Placeholder on final')
        if not t['source'].get('key'):errors.append('Untraced text')
    package_bytes=sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())
    if package_bytes>30_000_000:errors.append('Package exceeds 30 MB')
    failures=[k for k,r in v['acceptance'].items() if not r['passed']]
    result={'manifest_files':len(manifest),'sources':len(sources),'native_finals_checked':len(outputs),
                      'exports':len(v['exports']),'package_bytes':package_bytes,'audit_errors':errors,
                      'declared_acceptance_failures':failures,'corrective_checks':{k:r['passed'] for k,r in correction['checks'].items()}}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)
    return result


if __name__=='__main__':run()
