"""Read-only independent deliverable audit. Never rewrites the manifest."""
import sys
sys.dont_write_bytecode=True
import hashlib,json,csv
from pathlib import Path
import numpy as np
from PIL import Image
PKG=Path(__file__).resolve().parents[1];ROOT=PKG.parents[2]
DERIVED=ROOT/'scraped-data/derived/hud-pending-v1-codex'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fix1_checks(f,v):
    """Independent checks over emitted facts, geometry and actual final pixels."""
    errors=[];checked=0;hold_ratios=[]
    with (ROOT/'docs/unreal/contracts/hud/st-hud.csv').open(encoding='utf-8-sig',newline='') as stream:
        strings={row['Key']:row for row in csv.DictReader(stream)}
    texts={o['id']:[t for t in f['rendered_texts'] if t['id']==o['id']] for o in f['outputs']}
    def require(ok,case,check):
        nonlocal checked
        checked+=1
        if not ok:errors.append({'id':case,'fix1_check':check})
    def contains(parent,child):
        return child[0]>=parent[0] and child[1]>=parent[1] and child[0]+child[2]<=parent[0]+parent[2]+1e-6 and child[1]+child[3]<=parent[1]+parent[3]+1e-6
    for o in f['outputs']:
        ident=o['id'];rows=texts[ident];g=o['geometries'];small=ident.endswith('-150')
        status=[r for r in rows if r['block']=='STATUS']
        require(len(status)==1,ident,'one sourced STATUS')
        keys=g['status_keys']['chips']
        for chip in keys:
            field='SourceString' if '-en-' in ident else 'ru'
            require(chip['text']==strings[chip['key']][field],ident,'key label from st-hud.csv')
        if '-toast-' in ident:require([k['key'] for k in keys]==['hud.key.maneuver','hud.key.attack','hud.key.scheme'],ident,'M/A/G chip keys')
        if '-after-combat-' in ident:require([k['key'] for k in keys]==['hud.key.resolve'],ident,'resolve chip key')
        if keys:
            first=keys[0]['rectangle_su'];require(first[3]==20 and g['status_keys']['text_gap_su']==12,ident,'HB-13 chip height/gap')
            s=1.125 if '1280x720-150' in ident else .75 if '1280x720-100' in ident else 1.5 if small else 1
            require(first[0]*s-max(box[2] for box in status[0]['bbox_px'])>=12*s-1,ident,'actual text-to-key ink clearance')
        for r in rows:
            key=r['source'].get('key','') or ''
            if key.startswith('ms.btn.') or key=='hud.number.confirm':
                require(r['text']==r['source']['source_value'].upper() and r['source']['case_transform']=='upper' and r['not_truncated'],ident,'uppercase sourced button without clipping')
        if '-boost-' in ident and '-slot-boost-' not in ident:
            require(status[0]['source']['key']=='ms.ability.boost',ident,'BOOST question in STATUS')
            require(not any(r['block']=='PENDING' for r in rows),ident,'BOOST compact buttons only')
        if 'ribbon_style' in g:
            rs=g['ribbon_style'];require(rs['owner'] in ['Medusa','King Arthur'] and rs['label'].endswith(' · '+rs['owner']),ident,'owner suffix')
            if rs['kind']=='discard':require(rs['shape']=='outline' and rs['body']=='#061623' and rs['foreground']=='#B9B2A6',ident,'outline discard palette')
            if 'boost_chip' in g:require(contains(g['ribbon_plate'],g['boost_chip']) and abs(g['ribbon_plate'][0]+g['ribbon_plate'][2]-g['boost_chip'][0]-g['boost_chip'][2]-4)<1e-6,ident,'BOOST chip inside ribbon with 4 su right gap')
        if 'hold_progress' in g:
            pr=g['hold_progress'];tr=pr['track'];fill=pr['fill']
            require(tr[3]==4 and fill[2]==tr[2]/2 and tr[1]-g['ribbon_plate'][1]-g['ribbon_plate'][3]==2,ident,'4 su half-filled HOLD with 2 su gap')
            s=1.125 if '1280x720-150' in ident else .75 if '1280x720-100' in ident else 1.5 if small else 1
            with Image.open(DERIVED/(ident+'.png')) as im:
                a=np.asarray(im);colors=[a[round((tr[1]+2)*s),round((tr[0]+tr[2]*fraction)*s),:3] for fraction in [.25,.75]]
            lums=[]
            for color in colors:
                rgb=color.astype(float)/255;linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4);lums.append(float(linear@np.array([.2126,.7152,.0722])))
            ratio=(max(lums)+.05)/(min(lums)+.05);hold_ratios.append(ratio)
            require(ratio>=3,ident,'actual PNG hold fill/track contrast')
    for r in v['compact_geometry']:
        if r['id'].endswith('-150'):
            x,y,w,h=r['rectangle_su'];left,right=r['free_band_su']
            require(r['mode'] in ['single-row','buttons-only'] and w<=720 and x>=left and x+w<=right and r['content_fits'],r['id'],'S one row inside free band')
            row=next(o for o in v['overlap'] if o['id']==r['id'])['panels']['PENDING']
            require(row['figure_overlap_px2']==row['space_overlap_px2']==0,r['id'],'S compact zero masks')
    for r in v['modal_fit']:
        pick='-modal-pick-' in r['id'];cards=r['cards']
        require(len(cards)==(4 if pick else 2) and r['counter_present']==pick,r['id'],'PICK/ORDER card and counter count')
        if pick:require([c['raised_su'] for c in cards]==[16,16,0,0],r['id'],'16 su selection raise')
        else:
            require([c['key'] for c in cards]==['king-arthur:aid-the-chosen-one','king-arthur:command-the-storms'] and all(ch[2]>=24 and ch[3]>=24 for ch in r['number_chips']) and r['numeral_type_su']==20,r['id'],'two real ORDER cards and 24/20 su numbers')
        require(r['scrollbar']==(r['scrolled_part_su']>0) and r['rectangle_su'][3]<=r['cap_su'] and r['scan_row_footer_gap_su']==16 and r['counter_buttons_visible'],r['id'],'content-driven capped modal, fixed footer')
    require(sha(PKG/'source-hashes-before.json')==load(PKG/'fix1-before.json')['source_baseline_sha256'],'package','original source baseline preserved')
    return {'checks':checked,'passed':not errors,'failures':errors,'actual_png_minimum_hold_contrast':min(hold_ratios)}
def audit():
    v=load(PKG/'verification.json');f=load(PKG/'facts.json');m=load(PKG/'manifest-sha256.json')
    problems=[]
    actual={p.relative_to(ROOT).as_posix() for r in [PKG,DERIVED] for p in r.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
    if actual!=set(m['files']):problems.append({'manifest_inventory_delta':sorted(actual.symmetric_difference(m['files']))})
    for n,h in m['files'].items():
        if sha(ROOT/n)!=h:problems.append({'manifest_hash_mismatch':n})
    for n,h in load(PKG/'source-hashes-before.json')['files'].items():
        if sha(ROOT/n)!=h:problems.append({'source_changed':n})
    expected=set()
    for board in ['marmoreal','sarpedon']:
        for w,h,ui in [(1920,1080,100),(1920,1080,150),(1280,720,100),(1280,720,150)]:
            for st in f['state_matrix']:
                base=f'HB-34-{board}-{st}-{w}x{h}-{ui}'
                expected.update([base+'.png',base+'-gray.png'])
                with Image.open(DERIVED/(base+'.png')) as im:
                    if im.size!=(w,h):problems.append({'size':base,'actual':im.size})
    expected.update(['HB-34-marmoreal-compact-target-en-1920x1080-100.png','HB-34-marmoreal-compact-target-en-1920x1080-100-gray.png'])
    found={p.name for p in DERIVED.glob('HB-34-*.png')}
    if found!=expected:problems.append({'final_inventory_delta':sorted(found.symmetric_difference(expected))})
    maximum=0
    for p in DERIVED.glob('HB-34-*.png'):
        if p.stem.endswith('-gray'):continue
        with Image.open(p) as color,Image.open(p.with_name(p.stem+'-gray.png')) as gray:
            a=np.asarray(color.convert('RGBA'));b=np.asarray(gray.convert('RGBA'))
            channels=a[:,:,:3].astype(np.uint64)
            y=((channels @ np.array([2126,7152,722],dtype=np.uint64)+5000)//10000).astype('uint8')
            maximum=max(maximum,int(np.abs(b[:,:,:3].astype(int)-y[:,:,None]).max()))
    if maximum:problems.append({'gray_difference':maximum})
    package_bytes=sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())
    if package_bytes>30*1024*1024:problems.append({'package_budget':package_bytes})
    if len(v['overlap'])!=145:problems.append({'measurement_count':len(v['overlap'])})
    correction=fix1_checks(f,v)
    if correction['failures']:problems.extend(correction['failures'])
    summary={'task':'HB-34 fix1','integrity_pass':not problems,'integrity_problems':problems,'fix1':correction,
      'final_png_count':len(found),'source_file_count':len(load(PKG/'source-hashes-before.json')['files']),
      'package_bytes_including_reports':package_bytes,'manifest_files':len(m['files']),
      'grayscale_max_difference':maximum,'acceptance_failures':{k:r['measured'] for k,r in v['acceptance'].items() if not r['passed']}}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 1 if problems else 0
if __name__=='__main__':sys.exit(audit())
