#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read sources, verify outputs, write reports ONLY inside this package."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import sys
import numpy as np
from PIL import Image

sys.dont_write_bytecode = True
P = Path(__file__).resolve().parents[1]
ROOT = P.parents[2]
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):return json.loads((P/name).read_text(encoding='utf-8'))
def write(name,obj):
    path=(P/name).resolve()
    assert path.is_relative_to(P)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

baseline=read('source-hashes-before.json')
after={}
changes=[]
for path,expected in baseline['files'].items():
    f=Path(path) if Path(path).is_absolute() else ROOT/path
    actual={'sha256':digest(f),'bytes':f.stat().st_size} if f.is_file() else None
    after[path]=actual
    if actual!=expected:changes.append(path)
hud_before={p for p in baseline['files'] if p.startswith('art/imagegen/hud-icons-v3/')}
hud_after={p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
membership=sorted(hud_before.symmetric_difference(hud_after))
changes.extend(membership)
checks={}
checks['hud_snapshot_byte_identical']=digest(P/'_tools/draw_icons_v3_snapshot.py')==digest(ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py')
checks['no_layout_outside_canvas']=read('layout-audit.json')['outside_canvas']==[]
checks['concept_unretouched']=digest(P/'concepts/AN-26-concept-B-fix1-unretouched.png')==digest(P/'vector/AN-26-facing-sheet.png')
checks['no_character_image_generation']=read('generation-records.json')['image_generation_calls']==0
checks['all_masks_have_render_provenance']=all(r['source'] and r['bones'] and not r['back_view'] for r in read('silhouettes/tracing-records.json'))
tokens=read('palette.json')
checks['exact_tokens']=tokens=={'card.navy':'#061623','card.cream':'#F9EBDB','mark.keyline':'#111317','text.secondary':'#B9B2A6','turn.flash.yellow':'#F2C14E','state.error':'#D9483F','text.primary':'#F2EDE4'}
images=[]
for size in [(1920,1080),(1280,720),(960,540)]:
    suffix='' if size[0]==1920 else f'-{size[0]}x{size[1]}'
    color=P/f'vector/AN-26-facing-sheet{suffix}.png'
    compare=P/f'comparison/AN-26-facing-sheet-color{suffix}.png'
    gray=P/f'comparison/AN-26-facing-sheet-gray{suffix}.png'
    im=Image.open(color);gm=Image.open(gray)
    a=np.array(im);g=np.array(gm)
    luma=np.rint(a[:,:,:3].astype(float) @ np.array([.2126,.7152,.0722])).astype(np.uint8)
    checks[f'{size[0]}_rgba_png']=im.mode==gm.mode=='RGBA' and im.format==gm.format=='PNG' and im.size==gm.size==size
    checks[f'{size[0]}_opaque']=bool(np.all(a[:,:,3]==255) and np.all(g[:,:,3]==255))
    checks[f'{size[0]}_color_comparison_identical']=digest(color)==digest(compare)
    checks[f'{size[0]}_rec709_exact']=bool(np.all(g[:,:,:3]==luma[:,:,None]) and np.array_equal(a[:,:,3],g[:,:,3]))
    # Include antialiased reds: red must exceed green/blue substantially, not just exact #D9483F.
    rgb=a[:,:,:3].astype(int)
    red=(rgb[:,:,0]>rgb[:,:,1]+70)&(rgb[:,:,0]>rgb[:,:,2]+70)&(rgb[:,:,0]>90)
    ys,xs=np.where(red);scale=size[0]/1920
    checks[f'{size[0]}_red_only_forbidden_X']=bool(len(xs) and xs.min()>=1495*scale and xs.max()<=1605*scale and ys.min()>=665*scale and ys.max()<=798*scale)
    images.append({'color':color.relative_to(P).as_posix(),'gray':gray.relative_to(P).as_posix(),'size':size,'color_sha256':digest(color),'gray_sha256':digest(gray)})

model=read('timing-model.json')
checks['base_timing']=model['base']=={'pause':[-300,0],'turn':[-120,0],'clip':[0,583],'return':[583,733],'contact_arthur_harpy':292,'contact_merlin_medusa':333}
checks['shared_axis']=model['axis_master_px']==[250,1405] and model['axis_ms']==[-300,1025]
checks['speed_unscaled_turn_return']=all(r['turn']==[-120,0] and abs(r['return'][1]-r['return'][0]-150)<1e-9 for r in model['speed_lanes'])
checks['speed_scaled_clip_contacts']=all(r['clip'][1]==583*r['factor'] and r['contacts']==[292*r['factor'],333*r['factor']] for r in model['speed_lanes'])
checks['speed_rate_rounding']=all(round(r['exact_play_rate'],2)==r['display_play_rate'] for r in model['speed_lanes'])
checks['reduced_and_none_instant']=all(model[lane]['turn_ms']==model[lane]['return_ms']==0 for lane in ['reduced_motion','none'])
checks['cue_timing']=model['cue_offsets']=={'notify':0,'flash_duration':70,'damage':60,'hp':80}
checks['plan_angles']=model['angles']=={'idle_limit':45,'dead_band':10,'attack_limit':90,'step_tilt':10}
# Validate actual rendered marker centres, not only duplicated JSON declarations.
master=np.array(Image.open(P/'vector/AN-26-facing-sheet.png'))
def xx(t):return round(250+(t+300)/1325*1155)
yellow=np.array([242,193,78])
cream=np.array([249,235,219])
pixel_checks=[]
for y,factor in [(883,.5),(924,1),(965,1.5)]:
    for t,col in [(292*factor,yellow),(333*factor,cream)]:
        pixel_checks.append(bool(np.all(np.abs(master[y,xx(t),:3].astype(int)-col)<5)))
checks['speed_contacts_rendered_on_axis']=all(pixel_checks)
for y,t in [(718,292),(782,352),(814,372)]:
    checks[f'cue_circle_{y}_position']=bool(np.all(np.abs(master[y,xx(t),:3].astype(int)-yellow)<5))
prompt=(P/'prompt.txt').read_text(encoding='utf-8')
checks['exact_prompt_key']=read('generation-records.json')['records'][0]['prompt_key']=='AN-26/task/sha256:'+hashlib.sha256(prompt.encode('utf-8')).hexdigest()
card=(ROOT/'docs/game-design/visual/06-tasks/prompts/AN-26.codex.md').read_text(encoding='utf-8')
card_matches=[]
for path,h in re.findall(r'(art/pipeline-candidates/[^\s`]+)\s+sha256 ([a-f0-9]{64})',card):
    if (ROOT/path).is_file():card_matches.append({'path':path,'expected':h,'actual':digest(ROOT/path),'matches':digest(ROOT/path)==h})
checks['named_render_hashes_match_card']=len(card_matches)==6 and all(x['matches'] for x in card_matches)
checks['no_bytecode_in_package']=not list(P.rglob('*.pyc'))
write('source-hashes-after.json',{'algorithm':'sha256','files':after,'changed':changes,'hud_tree_membership_diff':membership})
limitations=[{'id':'back-render-unavailable','severity':'partial_requirement','requirement':'Forbidden back-view example',
    'actual':'Clearly labelled schematic using a traced idle contour and cape line; not a real rear render.',
    'reason':'No rear tile in the authorized inputs; no AI character generation and no Unreal access allowed.'},
    {'id':'harpy-contact-source-conflict','severity':'source_conflict','actual':'Task AN-26 frame 7 / 292 ms followed; visual design section 8.4 says frames 7-9.'},
    {'id':'540p-secondary-text','severity':'readability','actual':'Overview size; secondary text is small. Recommend master or 720p.'},
    {'id':'scope-of-outside-folder-audit','severity':'audit_scope','actual':'Task writes constrained to package and reviewed command history. No global scan of Unreal, Git or independently edited files.'}]
result={'task':'AN-26','status':'предложено','verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'source_unchanged':not changes,'outside_folder':[],'changed_inputs':changes,
    'source_files_checked':len(after),'hud_files_checked':len(hud_before),
    'source_hashes_after':'source-hashes-after.json','checks':checks,'automated_checks_pass':all(checks.values()) and not changes,
    'images':images,'limitations':limitations,'unmet_requirements':['Real traced back-view unavailable; schematic substituted and explicitly labelled'],
    'visual_review':{'reviewer':'Codex','method':'Locally opened PNGs with view_image; no MCP',
      'reviewed':['master color','master grayscale','720p color','720p grayscale','540p color','540p grayscale','tracing proof'],
      'findings':'Five render-derived poses, shared metric axis, correct bounds, readable main information, gray shape coding; secondary 540p text small.'},
    'execution':{'git_commands':0,'mcp_calls':0,'unreal_project_reads_writes_or_launches':0,
                 'background_processes_started':0,'scraped_data_writes':0}}
from verify_fix1 import measurements, write_manifest
# Keep existing keys, including visual-review evidence recorded after opening the PNGs.
previous=read('verification.json')
visual_review=previous.get('visual_review',result['visual_review'])
previous.update(result)
previous['visual_review']=visual_review
result=measurements(previous)
checks=result['checks']
write('verification.json',result)
legacy=P/('package'+'-manifest.json')
if legacy.exists():legacy.unlink()
write_manifest()  # Last file written, after README and verification.
failed=[k for k,v in checks.items() if not v]
print(json.dumps({'checks':len(checks),'failed':failed,'source_unchanged':not changes,'sources':len(after),'hud_files':len(hud_before),'outside_folder':[],'known_unmet':result['unmet_requirements']},ensure_ascii=False))
sys.exit(0 if not failed and not changes else 1)
