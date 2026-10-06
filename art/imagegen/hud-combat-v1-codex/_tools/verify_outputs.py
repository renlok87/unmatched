#!/usr/bin/env python
"""Read-only independent check of HB-29 outputs and their stored measurements."""
import hashlib
import json
from pathlib import Path
import sys
import math
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'art/imagegen/hud-combat-v1-codex'
OUT=ROOT/'scraped-data/derived/hud-combat-v1-codex'
FONT=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify_fix1_frame(a,pixels,baseline,fix,fitdata,problems):
    ident=a['id'];old=baseline['per_mockup'][ident];s=a['su_to_px'];w,h=a['size']
    def issue(text):problems.append(ident+': '+text)
    def pxbox(r):
        x,y,rw,rh=r;return [round(x*s),round(y*s),round((x+rw)*s),round((y+rh)*s)]
    keep=np.ones((h,w),bool)
    for x0,y0,x1,y1 in old['allowed_change_boxes_px']:keep[y0:y1,x0:x1]=False
    if hashlib.sha256(pixels[keep].tobytes()).hexdigest()!=old['outside_allowed_sha256']:issue('pixels changed outside fix1 regions')
    if {k:p['rectangle_su'] for k,p in a['panels'].items() if k not in ['CENTER','STATUS']}!=old['unchanged_rectangles_su']:issue('unrelated panel rectangles changed')
    if not all(t['passed'] for t in a['texts']):issue('text does not fit')
    if not a['persistent_pass']:issue('persistent overlap')
    for p in a['panels'].values():
        if not p['transient'] and (p['figure_overlap_px2'] or p['space_overlap_px2'] or p['reserved_overlaps']):issue('persistent masks/blocks overlap')
    if 'STATUS' in a['panels'] and 'CENTER' in a['panels']:
        sr=a['panels']['STATUS']['rectangle_su'];cr=a['panels']['CENTER']['rectangle_su']
        if cr[1]<sr[1]+sr[3]+8:issue('CENTER <8su after STATUS')
    if a['state'] in ['slam','hit','holds']:
        r=next(r for r in fix['centers'] if r['id']==ident);cr=a['panels']['CENTER']['rectangle_su']
        keys={t['key'] for t in a['texts'] if t['parent']=='CENTER'}
        if cr[3]>160 or r['padding_top_su']!=12 or r['padding_bottom_su']!=12:issue('CENTER height/padding')
        if r['variant']=='resolved-lines':
            if not {'effect.feint','effect.swift'}<=keys or 'effects.more' in keys:issue('missing resolved lines')
            if any(p['key']=='EFFECT-CURRENT' for p in a['parts']):issue('current bar in resolved state')
            if not any(p['key']=='marker-x-stamp' and p['parent']=='CENTER' for p in a['parts']):issue('missing cancelled X')
        if a['state']=='holds':
            if 'effect.dash' not in keys or any(t['ellipsis'] for t in a['texts'] if t['key']=='effect.dash'):issue('Dash not whole')
        content=[p for p in a['parts'] if p['parent']=='CENTER']
        top=min(pxbox(p['rectangle_su'])[1] for p in content);bottom=max(pxbox(p['rectangle_su'])[3] for p in content)
        box=pxbox(cr)
        if abs((top-box[1])/s-12)>1/s+1e-6 or abs((box[3]-bottom)/s-12)>1/s+1e-6:issue('empty band / measured content padding')
    for chip in [p for p in a['parts'] if p['key']=='MORE-CHIP']:
        text=next(t for t in a['texts'] if t['key']=='effects.more');r=chip['rectangle_su'];cr=a['panels']['CENTER']['rectangle_su'];box=pxbox(r)
        if r[0]!=cr[0]+44 or r[3]!=24 or text['type_su']!=14 or text['alignment']!='left' or text['contrast_min']<4.5:issue('chip geometry/type/contrast')
        if abs(text['rectangle_su'][0]-r[0]-8)>.01:issue('chip horizontal padding')
        expected=Image.new('RGBA',(w,h));mask=Image.new('L',(w,h));d=ImageDraw.Draw(expected);md=ImageDraw.Draw(mask)
        rect=[box[0],box[1],box[2]-1,box[3]-1]
        d.rounded_rectangle(rect,radius=round(4*s),fill=(21,35,46,255));md.rounded_rectangle(rect,radius=round(4*s),fill=255)
        f=ImageFont.truetype(str(FONT/'Roboto-BoldCondensed.ttf'),math.ceil(14*s));tr=text['rectangle_su'];by=f.getbbox(text['text'])[1]
        d.text((round(tr[0]*s),round(tr[1]*s-by)),text['text'],font=f,fill=(242,237,228,255))
        select=np.asarray(mask)>0
        if not np.array_equal(pixels[select],np.asarray(expected)[select]):issue('chip pixels mismatch inset capsule and tag')
    if a['board']=='marmoreal' and 'STATUS' in a['panels']:
        fit=fitdata[f'HB-13-marmoreal-defend-{w}x{h}-{a["ui_scale"]}'];record=next(r for r in fix['status'] if r['id']==ident)
        text=next(t for t in a['texts'] if t['key']=='status');r=a['panels']['STATUS']['rectangle_su']
        if text['rows']!=fit['lines'] or text['type_su']!=fit['type_su'] or record['alignment']!='left' or r[2]!=fit['block_width_su'] or r[3]!=(78 if fit['line_count']==2 else 48):issue('HB13 STATUS layout mismatch')
        union=[min(b[0] for b in fit['ink_line_bboxes_px']),min(b[1] for b in fit['ink_line_bboxes_px']),max(b[2] for b in fit['ink_line_bboxes_px']),max(b[3] for b in fit['ink_line_bboxes_px'])]
        if list(text['ink_bbox_px'])!=union:issue('HB13 STATUS ink bbox mismatch')
        with Image.open(ROOT/'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png') as im:expected=im.convert('RGBA')
        if expected.size!=(w,h):expected=expected.resize((w,h),Image.Resampling.LANCZOS)
        layer=Image.new('RGBA',(w,h));box=pxbox(r);ImageDraw.Draw(layer).rectangle([box[0],box[1],box[2]-1,box[3]-1],fill=(6,22,35,235));expected=Image.alpha_composite(expected,layer)
        ft=ImageFont.truetype(str(FONT/'Roboto-BoldCondensed.ttf'),fit['font_px']);draw=ImageDraw.Draw(expected)
        sy=r[1]+12
        if fit['line_count']==2:
            inkheight=max(round(i*fit['line_pitch_su']*s)+ft.getbbox(line,anchor='lt')[3] for i,line in enumerate(fit['lines']))
            sy=(box[1]+(box[3]-box[1]-inkheight)//2)/s
        for i,line in enumerate(fit['lines']):draw.text((round((r[0]+16)*s),round((sy+i*fit['line_pitch_su'])*s)),line,font=ft,fill=(242,237,228,255),anchor='lt')
        pad=math.ceil(6*s);x0,y0,x1,y1=box
        if not np.array_equal(pixels[y0+pad:y1-pad,x0+pad:x1-pad],np.asarray(expected)[y0+pad:y1-pad,x0+pad:x1-pad]):issue('HB13 STATUS actual text pixels mismatch')

def main():
    manifest=load(PKG/'manifest-sha256.json')['files'];v=load(PKG/'verification.json')
    problems=[]
    for path,expected in manifest.items():
        p=Path(path) if Path(path).is_absolute() else ROOT/path
        if not p.exists() or digest(p)!=expected:problems.append('manifest: '+path)
    actual={p.relative_to(ROOT).as_posix() for root in [PKG,OUT] for p in root.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
    if actual!=set(manifest):problems.append('manifest does not enumerate exactly all files')
    baseline=load(PKG/'fix1-before.json');fix=v['fix1'];fits=load(ROOT/'art/imagegen/hud-topstrip-v1-codex/verification.json')['status_text_fit']
    before={**load(PKG/'source-hashes-before.json')['files'],**load(PKG/'fix1-inputs.json')['files']}
    if digest(PKG/'source-hashes-before.json')!=baseline['source_baseline_sha256']:problems.append('original source baseline was recaptured')
    audits={a['id']:a for a in v['overlap']['per_mockup']}
    for path,data in before.items():
        p=Path(path) if Path(path).is_absolute() else ROOT/path
        if not p.exists() or digest(p)!=data['sha256']:problems.append('source changed: '+path)
    colors=[]
    for board in ['marmoreal','sarpedon']:
        states=['declare','defense-window','timer-warning','defense-chosen','reveal','effects','slam','hit','effects-long','holds','nodefense']
        if board=='sarpedon':states.remove('timer-warning')
        for w,h,ui in [(1920,1080,100),(1920,1080,150),(1280,720,100),(1280,720,150)]:
            previous=None
            for state in states:
                p=OUT/f'HB-29-{board}-{state}-{w}x{h}-{ui}.png'
                gp=p.with_name(p.stem+'-gray.png')
                if not p.exists() or not gp.exists():problems.append('missing: '+str(p));continue
                with Image.open(p) as im:
                    if im.size!=(w,h) or im.mode!='RGBA':problems.append('size/mode: '+str(p))
                    a=np.asarray(im)
                    y=np.rint(a[:,:,:3].astype(float)@np.array([.2126,.7152,.0722])).astype(np.uint8)
                verify_fix1_frame(audits[p.stem],a,baseline,fix,fits,problems)
                with Image.open(gp) as im:
                    ga=np.asarray(im)
                    if not np.array_equal(ga[:,:,:3],np.repeat(y[:,:,None],3,axis=2)) or not np.array_equal(ga[:,:,3],a[:,:,3]):problems.append('Rec709: '+str(gp))
                if previous is not None and np.array_equal(previous,y):problems.append('identical consecutive gray: '+str(p))
                previous=y;colors.append(p)
    if len(colors)!=84:problems.append('expected 84 color finals')
    for item in v['exports']:
        p=ROOT/item['path']
        with Image.open(p) as im:
            if list(im.size)!=item['size'] or im.mode!=item['mode']:problems.append('export metadata: '+item['path'])
    size=sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())
    if size>30_000_000:problems.append('package exceeds 30MB: '+str(size))
    if not v['source_unchanged'] or v['outside_folder']!=[]:problems.append('source/scope check')
    failed=[k for k,a in v['acceptance'].items() if not a['passed']]
    expected_failures={'C2':'ВР-VS2-HB29-11','C3':'ВР-VS2-HB29-12','C7':'ВР-VS2-HB29-11','edge_icon_contrast':'ВР-VS2-HB29-13'}
    if set(failed)!=set(expected_failures):problems.append('unexpected acceptance failure')
    for key,decision in expected_failures.items():
        if v['acceptance'][key].get('accepted_by_review')!=decision or v['acceptance'][key]['passed']!=baseline['acceptance'][key]['passed']:problems.append('literal acceptance / review decision changed: '+key)
        if key!='C2' and v['acceptance'][key]['measured']!=baseline['acceptance'][key]['measured']:problems.append('accepted exception measurement changed: '+key)
    if {r['decision_id'] for r in v['accepted_exceptions']}!=set(expected_failures.values()):problems.append('accepted_exceptions decisions')
    if len(fix['centers'])!=24 or len(fix['status'])!=16 or len(fix['more_chips'])!=8:problems.append('incomplete fix1 render measurements')
    print(json.dumps({'integrity_passed':not problems,'fix1_passed':not problems,'problems':problems,'manifest_files':len(manifest),'source_files':len(before),'mockups_color':len(colors),'package_bytes':size,'acceptance_failed_literal':failed,'accepted_exceptions':[r['decision_id'] for r in v['accepted_exceptions']],'limitations':v['limits']},ensure_ascii=False,indent=2))
    return 1 if problems else 0

if __name__=='__main__':raise SystemExit(main())
