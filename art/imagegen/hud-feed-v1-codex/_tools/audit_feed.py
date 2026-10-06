"""Independent read-only HB-38 audit; no output files or bytecode writes.

Exit 0: outputs, provenance and reports are internally consistent. It does not
turn an explicitly documented acceptance failure into a passing acceptance.
"""
import sys
sys.dont_write_bytecode=True
import json, hashlib, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
PKG=Path(__file__).resolve().parents[1]
ROOT=PKG.parents[2]
DERIVED=ROOT/'scraped-data/derived/hud-feed-v1-codex'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()
def rect(r,s,w,h):
    x,y,rw,rh=r;x0,y0=round(x*s),round(y*s)
    x1=max(round((x+rw)*s),x0+round(rw*s));y1=max(round((y+rh)*s),y0+round(rh*s))
    out=np.zeros((h,w),bool);out[max(y0,0):min(y1,h),max(x0,0):min(x1,w)]=True
    return out
def main():
    errors=[];v=load(PKG/'verification.json');f=load(PKG/'facts.json');manifest=load(PKG/'manifest-sha256.json')['files']
    actual={rel(p) for root in [PKG,DERIVED] for p in root.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
    if actual!=set(manifest):errors.append({'manifest_coverage':sorted(actual^set(manifest))})
    for p,digest in manifest.items():
        if sha(ROOT/p)!=digest:errors.append({'manifest_hash':p})
    baseline=load(PKG/'source-hashes-before.json')['files'];changed=[]
    for p,row in baseline.items():
        path=Path(p) if Path(p).is_absolute() else ROOT/p
        if not path.is_file() or sha(path)!=row['sha256']:changed.append(p)
    if bool(not changed)!=v['source_unchanged']:errors.append({'source_unchanged_report':changed})
    if set(changed)!=set(v['source_changed_paths']):errors.append({'source_changes_report':changed})
    originals=[p for p in DERIVED.glob('HB-38-*.png') if not p.stem.endswith('-gray') and '-contact-' not in p.stem]
    if len(originals)!=65:errors.append({'final_count':len(originals)})
    gray_count=0
    for root in [PKG,DERIVED]:
        for p in root.rglob('*.png'):
            if p.stem.endswith('-gray'):continue
            gp=p.with_stem(p.stem+'-gray')
            if not gp.is_file():errors.append({'missing_gray':rel(p)});continue
            with Image.open(p) as im,Image.open(gp) as gi:
                if im.mode!='RGBA' or gi.mode!='RGBA':errors.append({'mode':rel(p)})
                a=np.asarray(im);g=np.asarray(gi);z=a[:,:,:3].astype(np.uint32)
                y=((2126*z[:,:,0]+7152*z[:,:,1]+722*z[:,:,2]+5000)//10000).astype('uint8')
                if a.shape!=g.shape or not np.all(g[:,:,:3]==y[:,:,None]) or not np.array_equal(a[:,:,3],g[:,:,3]):errors.append({'rec709':rel(p)})
                gray_count+=1
    maskdata=load(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json');masks={}
    for row in v['overlap']:
        board=row['board'];w,h=row['size'];ui=row['ui_scale'];s=(1 if w==1920 else .75)*ui/100
        mk=(board,w,h)
        if mk not in masks:
            entry=maskdata['topology_transforms'][f'{board}-{w}x{h}'];sm=Image.new('L',(w,h));d=ImageDraw.Draw(sm)
            for z in entry['spaces']:d.polygon([tuple(x) for x in z['polygon_px']],fill=255)
            sm=sm.filter(ImageFilter.MaxFilter(2*entry['cell_conservative_dilation_px']+1));fm=Image.new('L',(w,h));d=ImageDraw.Draw(fm)
            for poly in maskdata['figure_polygons_1080p'][board]:d.polygon([(round(x*w/1920),round(y*w/1920)) for x,y in poly],fill=255)
            fm=fm.filter(ImageFilter.MaxFilter(2*entry['figure_conservative_dilation_px']+1));masks[mk]=(np.asarray(sm)>0,np.asarray(fm)>0)
        sm,fm=masks[mk]
        output=next(x for x in f['outputs'] if x['id']==row['id']);blocks=output['blocks']
        for key,reported in row['panels'].items():
            m=rect(reported['rectangle_su'],s,w,h)
            fo=int(np.count_nonzero(m&fm));sp=int(np.count_nonzero(m&sm));ob=np.zeros_like(m)
            for name,r in blocks.items():
                if name!=key:ob|=rect(r,s,w,h)
            hu=int(np.count_nonzero(m&ob))
            if [fo,sp,hu]!=[reported['figures_px2'],reported['spaces_px2'],reported['hud_px2']]:errors.append({'overlap_report':row['id']+'/'+key,'recomputed':[fo,sp,hu]})
    # All accepted inputs are reused as byte-identical local code snapshots.
    copies={'composition_build_snapshot.py':'hud-composition-v1-codex/_tools/build_mockups.py','layout_reference.py':'hud-composition-v1-codex/_tools/layout_reference.py','hand_build_snapshot.py':'hud-hand-v1-codex/_tools/build_mockups.py','frame_native.py':'hud-hand-v1-codex/_tools/frame_native.py','pending_build_snapshot.py':'hud-pending-v1-codex/_tools/build_mockups.py','skins_snapshot.py':'hud-pending-v1-codex/_tools/skins_snapshot.py','topstrip_build_snapshot.py':'hud-topstrip-v1-codex/_tools/build_mockups.py','draw_icons_v3_snapshot.py':'hud-icons-v3/_tools/draw_icons.py','fix1_layout.py':'hud-pending-v1-codex/_tools/fix1_layout.py'}
    for dst,src in copies.items():
        if sha(PKG/'_tools'/dst)!=sha(ROOT/'art/imagegen'/src):errors.append({'snapshot':dst})
    for board,logs in f['logs'].items():
        for row in logs['rows']:
            t=row['trace'];line=(ROOT/t['path']).read_text(encoding='utf8').splitlines()[t['line']-1]
            if line!=t['text'] or 'text="'+row['en']+'"' not in line:errors.append({'log_trace':board+'/'+str(row['seq'])})
    for b,x in f['board_figures'].items():
        spaces={r['id']:r for r in load(ROOT/x['topology'])['spaces']}
        shared=set(spaces[x['attacker_space']]['zones'])&set(spaces[x['refused_space']]['zones'])
        if shared:errors.append({'target_is_in_range':b})
    for row in f['rendered_texts']:
        if 'уточнить' in row.get('text','').lower():errors.append({'placeholder':row['id']})
    en='HB-38-marmoreal-toast-stack-en-1920x1080-100'
    en_feed=[r for r in f['rendered_texts'] if r['id']==en and str(r.get('block','')).startswith(('LOG','TOAST'))]
    if any(re.search('[А-Яа-яЁё]',r['text']) for r in en_feed):errors.append({'EN_feed_cyrillic':True})
    before=load(PKG/'fix1-before.json')
    if sha(PKG/'source-hashes-before.json')!=before['source_baseline_sha256']:errors.append({'baseline_rewritten':True})
    for key in ('toast_placement','sub_placement','persistent_blocks','hand_geometry'):
        def game_only(rows):
            unique={}
            for r in rows:
                if '-en-' not in r['id'] and '-combat-overlay-' not in r['id']:unique.setdefault(r['id'],r)
            return [unique[k] for k in sorted(unique)]
        old=game_only(before['game_placements'][key]);new=game_only(v[key])
        if old!=new:errors.append({'GAME_placement_changed':key})
    logs={(r['id'],r['seq']):r for r in before['log_rows']}
    for row in v['log_ellipsis']:
        if logs[(row['id'],row['seq'])]['full_text']!=row['full_text']:errors.append({'full_LOG_changed':row['id']})
    # Independent combat count: accepted dilations, every stored HUD obstacle,
    # no spaces in the predicate; all attempts, including rejected ones.
    accepted=load(ROOT/'art/imagegen/hud-combat-v1-codex/verification.json')['overlap']['per_mockup']
    for row in v['toast_placement_combat']:
        m=re.fullmatch(r'HB-38-(marmoreal|sarpedon)-combat-overlay-(\d+)x(\d+)-(\d+)',row['id'])
        board=m[1];w,h,ui=map(int,m.groups()[1:]);s=(1 if w==1920 else .75)*ui/100
        sm,fm=masks[(board,w,h)];blocks=row['obstacle_blocks']
        reference=next(r for r in accepted if r['board']==board and r['state']=='defense-window' and r['size']==[w,h] and r['ui_scale']==ui)
        for name,r in reference['panels'].items():
            if blocks.get(name)!=r['rectangle_su']:errors.append({'combat_missing_HUD':row['id']+'/'+name})
        if 'LOG' in blocks:errors.append({'combat_LOG_not_hidden':row['id']})
        if 'HAND-CAPTION' in blocks:
            x,y,rw,rh=blocks['HAND-CAPTION']
            if blocks.get('HAND-CAPTION-gap')!=[x-8,y-8,rw+16,rh+16]:errors.append({'combat_caption_gap':row['id']})
        hud=np.zeros_like(sm)
        for r in blocks.values():hud|=rect(r,s,w,h)
        for attempt in row['attempts']:
            zero=True
            for r,reported in zip(attempt['toast_rectangles_su']+[attempt['subtitle_rectangle_su']],attempt['overlap']):
                rm=rect(r,s,w,h)
                actual=[int(np.count_nonzero(rm&a)) for a in (fm,hud,sm)]
                if actual!=[reported[k] for k in ('figures_px2','hud_px2','spaces_px2')]:errors.append({'combat_overlap':row['id'],'phase':attempt['phase']})
                ok=actual[0]==0 and actual[1]==0 and not reported['outside_canvas']
                if reported['zero']!=ok:errors.append({'combat_predicate':row['id']})
                zero&=ok
            if attempt['zero']!=zero:errors.append({'combat_group_predicate':row['id']})
        chosen=next((a for a in row['attempts'] if a['zero']),None)
        if row['passed']!=bool(chosen):errors.append({'combat_failure_honesty':row['id']})
        if chosen and (row['chosen_rectangles_su']!=chosen['toast_rectangles_su'] or row['chosen_subtitle_rectangle_su']!=chosen['subtitle_rectangle_su']):errors.append({'combat_chosen_mismatch':row['id']})
    from fontTools.ttLib import TTFont
    fontdir=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
    cmaps={}
    for face in ('Roboto-Regular.ttf','Roboto-BoldCondensed.ttf','DroidSansFallback.ttf'):
        with TTFont(fontdir/face) as font:cmaps[face]=set(font.getBestCmap())
    glyph=v['glyph_coverage'];missing=0
    if len(glyph['rendered_texts'])!=len(f['rendered_texts']):errors.append({'glyph_text_count':True})
    for r in glyph['rendered_texts']+glyph['draw_calls']:
        expected=[(i,ch) for i,ch in enumerate(r['text']) if ord(ch) not in cmaps[r['primary_face']]]
        recorded=[(z['index'],z['character']) for z in r['fallback_characters']]
        n=sum(ord(ch) not in cmaps['DroidSansFallback.ttf'] for i,ch in expected);missing+=n
        if expected!=recorded or n!=r['missing_glyphs']:errors.append({'glyph_coverage_record':r['id']})
    if missing!=glyph['missing_glyphs'] or missing:errors.append({'missing_glyphs':missing})
    for name,row in v['fix1_inputs'].items():
        if sha(Path(name))!=row['sha256']:errors.append({'fix1_input_hash':name})
    # Only native LOG text may alter a Russian game final.
    expected_changed=set()
    for row in v['log_ellipsis']:
        old=logs[(row['id'],row['seq'])]
        if chr(0x2192) in row['displayed'] or old['displayed']!=row['displayed']:expected_changed.add(row['id'])
    for name,digest in before['game_png_sha256'].items():
        if '-en-' in name:continue
        cid=Path(name).stem.removesuffix('-gray')
        if cid not in expected_changed and sha(ROOT/name)!=digest:errors.append({'unrequested_final_change':name})
    outputs={r['id']:r for r in f['outputs']};ru=en.replace('-en-','-')
    for name,r in outputs[ru]['blocks'].items():
        if not name.startswith(('LOG','TOAST','SUB','REFUSE')) and outputs[en]['blocks'].get(name)!=r:errors.append({'EN_rectangle_changed':name})
    en_base=[r for r in f['rendered_texts'] if r.get('id')==en and not str(r.get('block','')).startswith(('LOG','TOAST'))]
    if any(re.search('[А-Яа-яЁё]',r['text']) for r in en_base):errors.append({'EN_base_cyrillic':True})
    # Sampling policy itself is audited against the full placement record.
    placements={}
    for key in ('toast_placement','sub_placement','toast_placement_combat','sub_placement_combat'):
        for r in v[key]:placements.setdefault(r['id'],[]).append(r)
    for record in v['overlay_rejections']:
        rec=placements[record['id']][record['record_index']]
        selected=[];seen=set();upward={}
        for i,a in enumerate(rec['attempts']):
            if a['zero']:continue
            if 'upward' in a['phase']:upward[a['phase']]=i
            elif a['phase'] not in seen:selected.append(i);seen.add(a['phase'])
        selected.extend(upward.values())
        if sorted(selected)!=record['shown_attempt_indices']:errors.append({'overlay_rejection_sampling':record['id']})
    recorded_fail=[k for k,r in v['acceptance'].items() if not r['passed']]
    if set(recorded_fail)!=set(v['failures']):errors.append({'failure_list_inconsistent':True})
    report={'audit':'HB-38 independent read-only / fix1','errors':errors,'files_in_manifest':len(manifest),'immutable_inputs':len(baseline),'native_finals':len(originals),'gray_pairs_recomputed':gray_count,'combat_canvases_recomputed':len(v['toast_placement_combat']),'glyph_missing_recomputed':missing,'honest_acceptance_failures':recorded_fail}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(1 if errors else 0)
if __name__=='__main__':main()
