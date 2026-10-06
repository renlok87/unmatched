#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent read-only checks of exported HB-17 artifacts; no renderer imports.

Run python -B -X utf8 .../_tools/verify_package.py. --record saves the report
inside verification.json and then rebuilds manifest as the FINAL write.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
P=ROOT/'art/imagegen/hud-panels-v1-codex'
D=ROOT/'scraped-data/derived/hud-panels-v1-codex'
FONT=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def path(p):return Path(p) if re.match(r'^[A-Z]:/',p) else ROOT/p
def rel(p):return p.relative_to(ROOT).as_posix()
def dump(p,v):
    assert p.resolve().is_relative_to(P.resolve())
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def run():
    v=load(P/'verification.json');f=load(P/'facts.json');before=load(P/'source-hashes-before.json')
    manifest=load(P/'manifest-sha256.json')['files'];fail=[];counts={};provenance=[]
    def check(ok,message):
        if not ok:fail.append(message)
    actual={rel(q) for root in [P,D] for q in root.rglob('*') if q.is_file() and q!=P/'manifest-sha256.json'}
    check(actual==set(manifest),'Manifest file set differs: '+str(actual.symmetric_difference(set(manifest))))
    for p,h in manifest.items():check(path(p).is_file() and sha(path(p))==h,'Manifest hash mismatch: '+p)
    counts['manifest_files']=len(manifest)
    for p,data in before['files'].items():
        actualhash=sha(path(p))
        if p=='docs/game-design/visual/06-tasks/hud.csv':
            if actualhash!=data['sha256']:provenance.append(p)
        else:check(actualhash==data['sha256'],'Immutable input changed: '+p)
    counts['immutable_input_files']=len(before['files'])-1
    for prefix in ['art/imagegen/hud-icons-v3/','art/imagegen/hud-composition-v1-codex/']:
        old={p for p in before['files'] if p.startswith(prefix)}
        now={rel(p) for p in (ROOT/prefix).rglob('*') if p.is_file()}
        check(old==now,'Immutable input directory inventory changed: '+prefix)
    check(sha(P/'_tools/draw_icons_v3_snapshot.py')==sha(ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py'),
          'Generator snapshot differs')
    exports={x['path']:x for x in v['exports']}
    pngs={p for p in actual if p.endswith('.png')}
    check(pngs==set(exports),'PNG inventory differs from exports: '+str(pngs.symmetric_difference(exports)))
    counts['png_files']=len(pngs)
    pairs=0
    for p,entry in exports.items():
        with Image.open(path(p)) as im:
            check(im.mode=='RGBA' and list(im.size)==entry['size'],'PNG mode/size mismatch: '+p)
            check(im.width>0 and im.height>0,'Empty PNG: '+p)
        if p.endswith('-gray.png'):continue
        gp=p[:-4]+'-gray.png';check(gp in exports,'Gray pair missing: '+p)
        if gp not in exports:continue
        with Image.open(path(p)) as im,Image.open(path(gp)) as gim:
            aa=np.asarray(im);bb=np.asarray(gim)
            yy=np.rint(aa[:,:,:3]@np.array([.2126,.7152,.0722])).astype('uint8')
            check(np.array_equal(bb[:,:,:3],np.repeat(yy[:,:,None],3,axis=2)) and np.array_equal(aa[:,:,3],bb[:,:,3]),
                  'Gray not exact Rec.709 or alpha changed: '+p)
        pairs+=1
    counts['rec709_pairs_checked']=pairs
    expected=set()
    loc=['own-start','own','own-055','wait','action-filled-1','action-filled-2','damage','heal','fallen','sidekick-fallen','no-avatar']
    for board in ['marmoreal','sarpedon']:
        for res,ui in [('1920x1080',100),('1280x720',150)]:
            for block,states in [('loc',loc),('opp',['opp','wait','ai','fallen']),('opphand',['3','5','10','stale'])]:
                for state in states:
                    if board=='marmoreal' and block=='loc' and state=='heal':continue
                    expected.add(f'HB-17-{board}-{block}-{state}-{res}-{ui}')
    check(expected=={o['id'] for o in f['outputs']},'Required full-canvas state inventory mismatch')
    counts['full_colour_canvases']=len(expected)
    # Prove no scene pixel was changed outside the three panel rectangles.
    masks=load(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json');basecache={};maskcache={}
    for o in f['outputs']:
        w,h=o['resolution'];s=o['su_to_px'];board=o['board'];key=(board,w,h)
        if key not in basecache:
            with Image.open(ROOT/f['boards'][board]['background']) as im:
                base=im.convert('RGBA')
                if base.size!=(w,h):base=base.resize((w,h),Image.Resampling.LANCZOS)
                basecache[key]=np.asarray(base)
            fm=Image.new('L',(w,h));dr=ImageDraw.Draw(fm)
            for poly in masks['figure_polygons_1080p'][board]:dr.polygon([(x*w/1920,y*w/1920) for x,y in poly],fill=255)
            tr=masks['topology_transforms'][f'{board}-{w}x{h}']
            fm=fm.filter(ImageFilter.MaxFilter(2*tr['figure_conservative_dilation_px']+1))
            sm=Image.new('L',(w,h));dr=ImageDraw.Draw(sm)
            for space in tr['spaces']:dr.polygon([tuple(x) for x in space['polygon_px']],fill=255)
            sm=sm.filter(ImageFilter.MaxFilter(2*tr['cell_conservative_dilation_px']+1))
            maskcache[key]=(np.asarray(fm)>0,np.asarray(sm)>0)
        visible=np.zeros((h,w),bool)
        for block,r in o['panels'].items():
            x,y,ww,hh=r;px,py=round(x*s),round(y*s);pw,ph=round(ww*s),round(hh*s)
            check(px>=0 and py>=0 and px+pw<=w and py+ph<=h,'Panel outside canvas: '+o['id']+'/'+block)
            visible[py:py+ph,px:px+pw]=True
        with Image.open(ROOT/o['path']) as im:aa=np.asarray(im)
        check(aa.shape==basecache[key].shape and np.array_equal(aa[~visible],basecache[key][~visible]),'Scene changed outside HUD: '+o['id'])
        fm,sm=maskcache[key]
        check(not np.any(visible&fm) and not np.any(visible&sm),'Conservative rectangle/mask overlap: '+o['id'])
    counts['untouched_background_canvases']=len(f['outputs'])
    # Every crop in the contact sheet is a full native translation, including both tooltip panels.
    tile_sizes=[]
    for o in f['outputs']:
        scale=o['su_to_px'];rects=list(o['panels'].values())
        tile_sizes.append((sum(round(r[2]*scale) for r in rects)+12*(len(rects)-1),max(round(r[3]*scale) for r in rects)))
    cw=max(w for w,h in tile_sizes);ch=max(h for w,h in tile_sizes)+30;contact_crops=0
    with Image.open(D/'HB-17-contact-all.png') as contact:
        for i,o in enumerate(f['outputs']):
            x=16+(i%3)*(cw+12);y=64+(i//3)*(ch+12)+26;scale=o['su_to_px']
            with Image.open(ROOT/o['path']) as full:
                for block,r in o['panels'].items():
                    xx,yy=round(r[0]*scale),round(r[1]*scale);ww,hh=round(r[2]*scale),round(r[3]*scale)
                    check(np.array_equal(np.asarray(full.crop((xx,yy,xx+ww,yy+hh))),np.asarray(contact.crop((x,y,x+ww,y+hh)))),'Contact crop clipped/scaled/changed: '+o['id']+'/'+block)
                    x+=ww+12;contact_crops+=1
    counts['full_native_contact_crops']=contact_crops
    # Check every recorded label independently with the actual font and native size.
    fcache={};labels=0;text_overlaps=[];back_overlaps=[];protected_checks=0;mirror_checks=0;sidekick_checks=0;dot_checks=0;tooltip_checks=0;fix_failures=[]
    def fixcheck(ok,message):
        if not ok:fix_failures.append(message)
        check(ok,message)
    for panel in f['rendered_panels']:
        texts=panel['texts'];labels+=len(texts)
        for t in texts:
            key=(t['font'],t['font_px'])
            if key not in fcache:fcache[key]=ImageFont.truetype(str(FONT/(t['font']+'.ttf')),t['font_px'])
            check(abs(fcache[key].getlength(t['text'])-t['width_px'])<.001,'Incorrect label measurement: '+t['text'])
            check(t['type_su']>=14 and t['font_px']>=14,'Font below token minimum: '+t['text'])
            if t['available_width_px'] is not None:check(t['width_px']<=t['available_width_px']+.01,'Caption too wide: '+t['text'])
            check(t['contrast_min']>=4.5,'Text contrast below threshold: '+t['text'])
            check('уточнить' not in t['text'].lower() and '…' not in t['text'],'Placeholder/ellipsis: '+t['text'])
        def area(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
        for i,t in enumerate(texts):
            for z in texts[i+1:]:
                if area(t['bbox_local_px'],z['bbox_local_px']):text_overlaps.append([panel['id'],panel['block'],t['text'],z['text']])
            for el in panel['elements']:
                if el['kind']=='card-back' and area(t['bbox_local_px'],el['bbox_local_px']):back_overlaps.append([panel['id'],t['text']])
        els=panel['elements'];scale=panel['scale'];rect=panel['rectangle_su']
        windows=[e for e in els if e['kind']=='ring-window']
        for window in windows:
            wb=window['bbox_local_px']
            for e in els:
                # Avatar and accepted ring layers necessarily inhabit their own reserved window.
                allowed=e['kind'] in ['avatar','monogram','ring-window'] or (e['kind']=='icon' and str(e.get('source','')).startswith('marker-turn-ring'))
                if e['kind']=='text' and e.get('text') in ['M','KA']:
                    allowed=True
                if not allowed:
                    protected_checks+=1
                    fixcheck(area(e['bbox_local_px'],wb)==0,'Element over avatar/ring window: '+panel['id']+'/'+panel['block']+'/'+e['kind'])
        sklabels=[e for e in els if e['kind']=='sidekick-label']
        for el in sklabels:
            sidekick_checks+=1
            sf=el['source'];params=sf['parameters']
            exact=f['strings']['hud.panel.sidekick']['ru'].format(**params)
            fixcheck(sf['key']=='hud.panel.sidekick' and el['label']==exact,'Non-StringTable sidekick label: '+panel['id'])
            if params['name'].startswith('Harpies'):
                fixcheck(params['name']==f"Harpies {el['index']}",'Incorrect Harpy name/order: '+panel['id'])
            if panel['block']=='PANEL-LOC-SIDEKICK-TOOLTIP':
                fixcheck(exact in [t['text'] for t in texts],'Tooltip does not actually render full label: '+panel['id'])
            else:
                # L is the explicitly preserved accepted split presentation, not a new literal caption.
                fixcheck(f"{params['hp']}/{params['max']}" in [t['text'] for t in texts],'L HP fragment missing: '+panel['id'])
                fixcheck((str(el['index']) if params['name'].startswith('Harpies') else params['name']) in [t['text'] for t in texts],'L name/index fragment missing: '+panel['id'])
        if panel['block']=='PANEL-OPP':
            mirror_checks+=1
            right=(148 if rect[2]==240 else 212)
            hp=next(e for e in els if e['kind']=='hp-group')
            col=next(e for e in els if e['kind']=='text-column')
            fixcheck(abs(hp['right_edge_su']-right)<1e-6 and col['right_edge_su']==right,'OPP HP group/column right edges differ: '+panel['id'])
            hptext=next(t for t in texts if t['source'] and t['source'].get('key')=='hud.panel.hp')
            for t in texts:
                if t['source'] and (t['source'].get('key') in ['hud.panel.hp','hud.panel.fallen','hud.opp.thinking','hud.panel.status.wait','Hero.nameRu'] or t['text'] in ['Merlin','7/7']):
                    fixcheck(abs(t['bbox_local_px'][2]-round(right*scale))<=1,'OPP label not right aligned: '+panel['id']+'/'+t['text'])
            slots=[e for e in els if e['kind']=='tracker-slot']
            for slot in slots:
                fixcheck(slot['rectangle_su'][0]==12+(slot['slot']-1)*(slot['rectangle_su'][2]+4),'OPP tracker not mirrored to outer side: '+panel['id'])
                fixcheck((hptext['bbox_local_px'][0]-slot['bbox_local_px'][2])/scale>=8,'OPP HP text/disc gap below 8 su: '+panel['id'])
            hearts=[e for e in els if e['kind']=='icon' and str(e.get('source','')).startswith('resource-hp-')]
            for heart in hearts:
                hb=heart['bbox_local_px'];tb=hptext['bbox_local_px']
                fixcheck((tb[0]-hb[2])/scale>=4-1/scale,'OPP heart/number gap below 4 su after rounding: '+panel['id'])
            if rect[2]==340:
                for slot in slots:
                    for sk in [e for e in els if e['kind']=='avatar' and e['rectangle_su'][2]==32]:
                        sb=slot['rectangle_su'];ab=sk['rectangle_su']
                        dx=max(0,sb[0]-ab[0]-ab[2],ab[0]-sb[0]-sb[2]);dy=max(0,sb[1]-ab[1]-ab[3],ab[1]-sb[1]-sb[3])
                        fixcheck(math.hypot(dx,dy)>=4,'OPP tracker/sidekick separation below 4 su: '+panel['id'])
                for hpfragment in [t for t in texts if t['text']=='1/1']:
                    for badge in [e for e in els if e['kind']=='sidekick-index-disc']:
                        ab=badge['bbox_local_px'];tb=hpfragment['bbox_local_px']
                        dx=max(0,ab[0]-tb[2],tb[0]-ab[2]);dy=max(0,ab[1]-tb[3],tb[1]-ab[3])
                        fixcheck(math.hypot(dx,dy)/scale>=4-1/scale,'OPP badge/HP gap below 4 su after rounding: '+panel['id'])
            if rect[2]==340:
                row=next(e for e in els if e['kind']=='sidekick-row')
                fixcheck(row['right_edge_su']==right and abs(row['rectangle_su'][0]+row['rectangle_su'][2]-right)<1e-6,'OPP sidekick row not right aligned: '+panel['id'])
                if len(sklabels)>1:
                    fixcheck([e['index'] for e in sklabels]==[1,2,3] and all(a['rectangle_su'][0]<b['rectangle_su'][0] for a,b in zip(sklabels,sklabels[1:])),'Harpy order not left-to-right: '+panel['id'])
                    last_hp=[t for t in texts if t['text']=='1/1'][-1]
                    fixcheck(abs(last_hp['bbox_local_px'][2]-round(right*scale))<=1,'OPP Harpy HP right edge differs: '+panel['id'])
        for dot in [e for e in els if e['kind']=='ai-pulse-dot']:
            dot_checks+=1
            t=next(t for t in texts if t['source'] and t['source'].get('key')=='hud.opp.thinking')
            rr=dot['rectangle_su'];box=t['bbox_local_px']
            fixcheck(rr[2:]==[8,8] and dot['gap_su']==5,'AI pulse not 8 su / 5 su gap: '+panel['id'])
            fixcheck(abs((rr[1]+4)*scale-(box[1]+box[3])/2)<1e-6,'AI pulse not vertically centred: '+panel['id'])
            fixcheck(abs(box[0]/scale-(rr[0]+8)-5)<=1/scale,'AI pulse spacing wrong: '+panel['id'])
        if panel['block']=='PANEL-LOC-SIDEKICK-TOOLTIP':
            tooltip_checks+=1
            o=next(o for o in f['outputs'] if o['id']==panel['id']);own=o['panels']['PANEL-LOC']
            fixcheck(rect[0]==own[0] and rect[1]+rect[3]+8==own[1],'Tooltip anchor/gap incorrect: '+panel['id'])
            for name,r in o['panels'].items():
                if name==panel['block']:continue
                a=[rect[0],rect[1],rect[0]+rect[2],rect[1]+rect[3]];b=[r[0],r[1],r[0]+r[2],r[1]+r[3]]
                fixcheck(area(a,b)==0,'Tooltip overlaps block '+name)
            expected_labels=['Harpies 1 0/1','Harpies 2 1/1','Harpies 3 1/1'] if o['board']=='marmoreal' else ['Merlin 0/7']
            fixcheck([t['text'] for t in texts]==expected_labels,'Tooltip sidekick inventory/values wrong: '+panel['id'])
        if panel['block']=='PANEL-LOC' and panel['id'].startswith('HB-17-sarpedon-'):
            output=next(o for o in f['outputs'] if o['id']==panel['id'])
            hp=0 if output['block']=='loc' and output['state']=='fallen' else 17 if output['block']=='loc' and output['state']=='damage' else 18
            fixcheck(any(t['text']==f'{hp}/18' and t['source'] and t['source'].get('key')=='hud.panel.hp' for t in texts),'Sarpedon HP inconsistent: '+panel['id'])
        if panel['caption']:
            cp=panel['caption'];board=next(o['board'] for o in f['outputs'] if o['id']==panel['id'])
            vals=f['boards'][board]['run_values']
            check(cp['deck']==vals['opponent_deck'] and cp['discard']==vals['opponent_discard'],'Deck/discard not from board run: '+panel['id'])
            check(cp['back_size_su']==[48,67] and cp['whole_back_inside_frame'],'Wrong/partial card back: '+panel['id'])
    check(not text_overlaps,'Text/text overlaps: '+str(text_overlaps))
    check(not back_overlaps,'Runtime labels cover card scans: '+str(back_overlaps))
    counts.update({'labels_measured':labels,'protected_window_element_checks':protected_checks,'opponent_mirror_panels':mirror_checks,'canonical_sidekick_labels':sidekick_checks,'ai_pulse_dots':dot_checks,'state_tooltips':tooltip_checks})
    fixcheck(tooltip_checks==2,'Expected exactly two state-only S tooltips')
    fixcheck(f['neutral_hp']['sarpedon']['King Arthur']==18 and f['heal']['from']==17 and f['heal']['to']==18,'HP facts inconsistent')
    fixcheck(sha(P/'source-hashes-before.json')==load(P/'fix1-before.json')['source_baseline_sha256'],'Source baseline recaptured')
    expected_pose={0:(0,.15,0),120:(.042,1,0),300:(.105,1-(180/880)**2,2),600:(.21,1-(480/880)**2,4),1000:(.35,0,6),2000:(.35,0,6)}
    check(len(v['ring_timesheet'])==24,'Ring pose inventory not24')
    for row in v['ring_timesheet']:
        rim,flash,frame=expected_pose[row['t_ms']];po=row['pose']
        check(abs(po['rim']['opacity']-rim)<1e-9 and abs(po['flash']['opacity']-flash)<1e-9 and po['flash']['frame']==frame,
              'Wrong appear pose: '+str(row))
    for b,data in f['boards'].items():
        ls=(ROOT/data['trace']).read_text(encoding='utf8').splitlines()
        for action in data['action_tracker']['actions']:check(ls[action['line']-1]==action['text'],'Action trace citation changed')
    check(v['source_unchanged'] and v['outside_folder']==[],'Source/scope verification claim not valid')
    check(v['palette']['fraction']==0,'Palette exception')
    check(not v['text_fit_failures'],'Reported text fit failures')
    check(all(row['passed'] for row in v['gray']['state_pairs']),'Gray pair failure')
    check(load(P/'generation-records.json')==[],'Unexpected image generation records')
    total=sum(q.stat().st_size for q in P.rglob('*') if q.is_file())
    counts['package_bytes']=total;check(total<30*1024*1024,'Package exceeds30MiB')
    for key,entry in v['acceptance'].items():check(entry['passed'],'Acceptance failed: '+key)
    report={'passed':not fail,'failures':fail,'counts':counts,'provenance_only_current_changes':provenance,
            'checks':['manifest exact file set and hashes','194 PNGs decoded, native dimensions/RGBA',
             '97 exact Rec.709 pairs','74 required canvases, unchanged scene outside blocks + state-only tooltip',
             '74 conservative rectangle intersections with registered masks, including tooltip','font advances/contrast and text overlap',
             'no labels over card backs','Run I trace citations and per-board captions','24 analytic ring poses',
             'immutable inputs + icon generator snapshot','package size and declared acceptance','protected avatar/ring window in every state','OPP right alignment/outer tracker/gaps','StringTable canonical sidekick labels and full S lines','Sarpedon HP states','8 su centred AI dot','state-only tooltip anchors and block separation','224 complete native contact crops including two tooltips'],
            'method':'Independent file reader; no build_panels import or rendering.'}
    if '--record' in sys.argv:
        v['independent_verification']=report
        v['fix1_checks']={'passed':not fix_failures,'failures':fix_failures,'counts':counts}
        v['acceptance']['fix1_corrective_checks']={'passed':not fix_failures,'measured':fix_failures or counts,'expected':'All five corrective requirements','note':'Independent verifier; preserved accepted L sidekick split presentation is reconstructed through StringTable.'}
        v['sizes']['package_bytes_verified']=total
        dump(P/'verification.json',v)
        # Manifest is always the last write; stdout is not a filesystem mutation.
        dump(P/'manifest-sha256.json',{'schema':'HB-17.manifest/1','files':{
            rel(q):sha(q) for root in [P,D] for q in sorted(root.rglob('*'))
            if q.is_file() and q!=P/'manifest-sha256.json'}})
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not fail else 1

if __name__=='__main__':sys.exit(run())
