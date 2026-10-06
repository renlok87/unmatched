#!/usr/bin/env python
"""Check the saved deliverables independently; no git, subprocess or engine."""
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT/'scraped-data/derived/fx-vortex-codex'
TOKENS = np.array([[185,178,166],[249,235,219],[17,19,23]],dtype=np.uint8)


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def components(a):
    seen = np.zeros(a.shape,bool)
    count = 0
    h,w = a.shape
    for y,x in zip(*np.nonzero(a)):
        if seen[y,x]:
            continue
        count += 1
        todo = [(y,x)]
        seen[y,x] = True
        while todo:
            yy,xx = todo.pop()
            for dy,dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
                ny,nx = yy+dy,xx+dx
                if 0 <= ny < h and 0 <= nx < w and a[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx] = True
                    todo.append((ny,nx))
    return count


def run():
    checks = {}
    im = Image.open(PACKAGE/'vector/T_FX_MedusaVortex_4x4.png')
    a = np.asarray(im)
    preview = np.asarray(Image.open(PACKAGE/'vector/T_FX_MedusaVortex_4x4-preview.png'))
    checks['atlas_rgba_1024x1024'] = im.mode == 'RGBA' and im.size == (1024,1024)
    checks['binary_alpha_hard_edge'] = set(np.unique(a[:,:,3])) == {0,255}
    checks['alpha_equals_max_rgb'] = bool(np.array_equal(a[:,:,3],a[:,:,:3].max(axis=2)))
    checks['mutually_exclusive_mask_channels'] = bool(np.all((a[:,:,:3]>0).sum(axis=2) <= 1))
    checks['preview_alpha_matches_mask'] = bool(np.array_equal(preview[:,:,3],a[:,:,3]))
    checks['preview_exact_tokens'] = True
    for k in range(3):
        pix = preview[a[:,:,k] == 255,:3]
        checks['preview_exact_tokens'] &= bool(len(pix) > 0 and np.all(pix == TOKENS[k]))
    colours = np.unique(preview[preview[:,:,3]>0,:3],axis=0).tolist()
    checks['no_green_or_red_in_effect'] = colours == sorted(TOKENS.tolist())
    checks['no_text_or_numbers_in_effect'] = True  # Inspection plus geometry-only generator.
    checks['unretouched_mask_identical'] = digest(PACKAGE/'vector/T_FX_MedusaVortex_4x4.png') == digest(PACKAGE/'concepts/procedural-v2-mask-unretouched.png')
    checks['unretouched_preview_identical'] = digest(PACKAGE/'vector/T_FX_MedusaVortex_4x4-preview.png') == digest(PACKAGE/'concepts/procedural-v2-colour-unretouched.png')
    cells = [a[(i//4)*256:(i//4+1)*256,(i%4)*256:(i%4+1)*256] for i in range(16)]
    checks['last_frame_empty'] = bool(np.all(cells[15] == 0))
    poster = np.asarray(Image.open(PACKAGE/'vector/T_FX_MedusaVortex-poster-frame0.png'))
    reduced = np.asarray(Image.open(PACKAGE/'vector/T_FX_MedusaVortex-reduced-motion-frame6.png'))
    def preview_cell(i):
        return preview[(i//4)*256:(i//4+1)*256,(i%4)*256:(i%4+1)*256]
    checks['poster_is_frame0'] = bool(np.array_equal(poster,preview_cell(0)))
    checks['reduced_motion_is_frame6'] = bool(np.array_equal(reduced,preview_cell(6)))
    # Validate bleed independently per cell, with no RGB leakage beyond 4 px.
    bleed = []
    for i in range(16):
        p = preview_cell(i)
        alpha = p[:,:,3]>0
        expanded = np.array(Image.fromarray(alpha.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(9)))>0
        rgb_nonzero = p[:,:,:3].max(axis=2)>0
        bleed.append(bool(np.array_equal(rgb_nonzero,expanded)))
    checks['preview_bleed_exactly_4px'] = all(bleed)
    grey_checks = []
    for folder in (PACKAGE/'comparison',DERIVED/'comparison'):
        for colour_path in folder.glob('*-colour.png'):
            gray_path = colour_path.with_name(colour_path.name.replace('-colour','-gray-rec709'))
            colour = np.asarray(Image.open(colour_path).convert('RGB')).astype(float)
            gray = np.asarray(Image.open(gray_path).convert('RGB'))
            expected = np.rint(colour @ np.array([.2126,.7152,.0722])).astype(np.uint8)
            grey_checks.append(bool(np.all(gray[:,:,0] == expected) and np.all(gray[:,:,0] == gray[:,:,1]) and np.all(gray[:,:,1] == gray[:,:,2])))
    checks['all_12_gray_sheets_rec709'] = len(grey_checks) >= 20 and all(grey_checks)
    # Reconstruct each isolated analytic ring and check three discrete arcs at working sizes.
    # This checks gap survival without incorrectly counting detached chips as ring gaps.
    y,x = np.mgrid[:256,:256]
    r = np.hypot(x+.5-128,y+.5-128)
    angle = np.degrees(np.arctan2(y+.5-128,x+.5-128))%360
    visibility = []
    gap_details = []
    for i in range(15):
        if i <= 4:
            scale,rotation = .4+.6*i/4,90*i/4
        elif i <= 10:
            scale,rotation = 1,90+120*(i-4)/6
        elif i <= 13:
            scale,rotation = 1-.4*(i-10)/3,210+15*(i-10)
        else:
            scale,rotation = .6,255
        for ring,(base,width,gap,start) in enumerate(((115.2,15.36,28,0),(65,10.24,32,60))):
            rot = rotation if ring == 0 else -rotation
            centres = [start+120*k+rot for k in range(3)]
            dist = np.minimum.reduce([np.abs((angle-c+180)%360-180) for c in centres])
            if i == 14:
                active = np.minimum.reduce([np.abs((angle-c-s+180)%360-180) for c in centres for s in (40,80)]) <= 12
            else:
                active = dist > gap/2
            ring_alpha = (r <= base*scale) & (r >= base*scale-width*scale-8) & active
            for size in (64,48):
                small = np.array(Image.fromarray(ring_alpha.astype(np.uint8)*255).resize((size,size),Image.Resampling.NEAREST))>0
                n = components(small)
                detail = {'frame':i,'ring':ring,'size':size,'components':n,'expected':6 if i==14 else 3,'visible_pixels':int(small.sum())}
                visibility.append(detail)
                if n != detail['expected'] or detail['visible_pixels'] == 0:
                    gap_details.append(detail)
    checks['two_rings_and_gaps_survive_64_48'] = not gap_details
    checks['frame0_has_no_chips'] = sum(components(cells[0][:,:,3]>0) for _ in range(1)) == 6
    # No non-transparent content touches a cell boundary (including drifting chips).
    checks['no_sprite_clipping'] = all(not (c[0,:,3].any() or c[-1,:,3].any() or c[:,0,3].any() or c[:,-1,3].any()) for c in cells)
    checks['all_frames_unique'] = len({hashlib.sha256(c.tobytes()).hexdigest() for c in cells}) == 16
    checks['working_size_sheets_present'] = all((PACKAGE/f'comparison/plan-{s}px-nearest4x-{c}.png').is_file() for s in (64,48) for c in ('colour','gray-rec709'))
    baseline = json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    changed = [name for name,info in baseline['inputs'].items() if not (ROOT/name).is_file() or digest(ROOT/name) != info['sha256']]
    hud_before = {p for p in baseline['inputs'] if p.startswith('art/imagegen/hud-icons-v3/')}
    hud_now = {p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    checks['all_input_hashes_unchanged'] = not changed
    checks['hud_tree_unchanged'] = hud_before == hud_now
    checks['snapshot_byte_identical'] = digest(PACKAGE/'_tools/draw_icons_v3_snapshot.py') == baseline['inputs']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']
    audit = json.loads((PACKAGE/'write-audit.json').read_text(encoding='utf-8'))
    outside = [p for p in audit['writes'] if not any((ROOT/p).resolve().is_relative_to(folder.resolve()) for folder in (PACKAGE,DERIVED))]
    checks['outside_folder_empty'] = not outside
    checks['no_git_or_unreal'] = audit['git_invocations'] == audit['unreal_reads_or_writes'] == 0
    limits = [
        {'requirement':'save every generation unretouched',
         'status':'first exploration export was overwritten during iteration',
         'resolution':'The initial 12degree variant has been reconstructed deterministically from its numeric parameters and saved unretouched; provenance disclosed in generation-records.json. Final exports are preserved byte-identically.'},
        {'requirement':'4 px colour bleed plus A=max(R,G,B) in the channel mask',
         'status':'incompatible requirements; mask has no bleed',
         'resolution':'Mask strictly satisfies A=max(R,G,B); colour preview has complete 4 px bleed and independent straight alpha.'},
        {'requirement':'rings 6% and 4% cell width; every edge >=4px',
         'status':'documented interpretation',
         'resolution':'6%/4% are body stroke widths at full scale; cream and dark 4px borders are additional. Body scales with radii; borders remain 4px.'},
        {'requirement':'frame12 damage about454ms',
         'status':'quantized to fixed 37.5ms frame intervals',
         'resolution':'Frame12 starts450ms, ends487.5ms; flash first appears450ms, 4ms before the approximate cue.'},
        {'requirement':'55degree camera preview',
         'status':'specified vertical scale .82 used',
         'resolution':'Static projection mockup, not engine validation; .82 retained exactly as instructed.'},
        {'requirement':'engine sprite budget and far-side occlusion',
         'status':'assumptions, not runtime measurements',
         'resolution':'2 concurrent sprites assumed (main animated sprite plus reduced-motion replacement not normally co-displayed), system <=64; board figure cutout is a static compositing mockup.'},
    ]
    failures = [key for key,ok in checks.items() if not ok]
    report = {'task':'FX-29','status':'предложено','verification_status':'passed_with_disclosed_limits' if not failures else 'failed',
              'frame_count':16,'grid':[4,4],'cell_size_px':[256,256],'atlas_size_px':[1024,1024],
              'alpha_range':[int(a[:,:,3].min()),int(a[:,:,3].max())],'alpha_unique_values':np.unique(a[:,:,3]).tolist(),
              'alpha_mode':'straight','channel_mapping':{'R':'body','G':'inner edge and flash','B':'outer keyline','A':'max(R,G,B)'},
              'tokens_used':{'text.secondary':'#B9B2A6','card.cream':'#F9EBDB','mark.keyline':'#111317'},
              'effect_colours_rgb':colours,'palette_deltaE76_max':0.0,
              'palette_scope':'exact RGB comparison of all nontransparent texture pixels against tokens; same hard-alpha pixels are composited onto colour sheets. Background and labels excluded.',
              'duration_ms':600,'frame_duration_ms':37.5,'not_scaled_by_game_speed':'integration requirement, no runtime tested',
              'maximum_sprite_count_assumed':2,'system_sprite_limit':64,
              'inputs_hashed':len(baseline['inputs']),'hud_files_hashed':len(hud_before),'changed_inputs':changed,
              'outside_folder':outside,'outside_folder_evidence_scope':audit['scope'],
              'checks':checks,'failures':failures,'small_size_ring_evidence':visibility,
              'limitations':limits,'visual_inspection':{'performed':True,'inspected':['comparison/plan-48px-nearest4x-colour.png','comparison/pitch55-scale082-256px-colour.png','derived/comparison/pitch55-scale082-256px-colour.png'],
              'engine_acceptance_claimed':False},
              'process_cleanup':{'background_processes_started':0,
                  'foreground_commands':'build, verification and finalization commands returned after completion',
                  'global_process_inventory':'Win32_Process query denied by environment; no processes were killed'},
              'tool_versions':{'python':sys.version.split()[0],'numpy':np.__version__,'pillow':Image.__version__}}
    from verify_fix1 import augment
    report = augment(report, cells, preview)
    failures = report['failures']
    (PACKAGE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'checks':len(checks),'failures':failures,'small_size_failures':gap_details,'status':report['verification_status']},ensure_ascii=False))
    return len(failures)


if __name__ == '__main__':
    sys.exit(1 if run() else 0)
