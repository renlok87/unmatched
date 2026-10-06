#!/usr/bin/env python
"""Read-only saved-file audit; never imports or runs the generator.

The builder calls correction_reports after exporting PNGs, then writes the report.
This CLI independently recomputes measurements and validates all manifest entries.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT/'scraped-data/derived/fx-hitstar-codex'


def polar_report(cell, size, rays=10, visible_only=False):
    coverage = np.any(cell[:, :, :2], axis=2) if visible_only else cell[:, :, 3] > 0
    visible = np.array(Image.fromarray(coverage.astype(np.uint8)*255).resize((size,size),Image.Resampling.NEAREST))>0
    yy,xx = np.mgrid[:size,:size]
    radius = np.hypot(xx+.5-129*size/256, yy+.5-129*size/256)
    angle = np.mod(np.arctan2(yy+.5-129*size/256,xx+.5-129*size/256)+np.pi/2,2*np.pi)
    step = 2*np.pi/rays
    def reach(theta,width):
        pixels = visible & (np.abs(np.angle(np.exp(1j*(angle-theta))))<=width)
        return float(radius[pixels].max()) if np.any(pixels) else 0.
    values=[]
    for j in range(rays):
        valley_angle = np.radians(24 if j%2==0 else 12) if rays==10 else step/2
        tip=reach(j*step,step*.22)
        valley=max(reach(j*step-valley_angle,step*.09),reach(j*step+valley_angle,step*.09))
        prominence=tip-valley
        values.append({'ray':j,'tip_radius_px':round(tip,4),'adjacent_valley_radius_px':round(valley,4),'prominence_px':round(prominence,4),'distinct':prominence>=.5})
    return {'size':size,'method':'nearest master sample; polar tip wedges 0.22 step, valley wedges 0.09 step at actual valleys; prominence >=0.5 px','expected_rays':rays,'distinct_rays':sum(v['distinct'] for v in values),'passed':all(v['distinct'] for v in values),'rays':values}


def correction_reports(cells):
    """Measurements from delivered pixels, independent of construction code."""
    long_radius=94.4
    axis_reaches=[]
    sample=np.arange(0,long_radius+.01,.025)
    for j in range(5):
        theta=-np.pi/2+j*2*np.pi/5
        x=np.floor(129+sample*np.cos(theta)).astype(int)
        y=np.floor(129+sample*np.sin(theta)).astype(int)
        body=cells[2][y,x,0]>0
        reach=float(sample[body].max()) if np.any(body) else 0.
        axis_reaches.append({'ray':2*j,'radius_px':round(reach,4),'fraction_of_R_L':round(reach/long_radius,6)})
    growth=[]
    yy,xx=np.mgrid[:256,:256]
    radius=np.hypot(xx+.5-129,yy+.5-129)
    for i in (0,1,2):
        shape=np.any(cells[i][:,:,:2],axis=2)
        growth.append({'frame':i,'circumscribed_radius_px':round(float(radius[shape].max()),6),'pixel_area':int(shape.sum())})
    visible={str(s):polar_report(cells[2],s,visible_only=True) for s in (36,27)}
    long_pass_27=all(visible['27']['rays'][j]['distinct'] for j in (0,2,4,6,8))
    # Measure exact angular samples of the saved R/G silhouette at short axes
    # and adjacent valleys (raster uncertainty is stated separately).
    samples=np.arange(0,long_radius+.01,.025)
    def radial_extent(theta):
        x=np.floor(129+samples*np.cos(theta)).astype(int)
        y=np.floor(129+samples*np.sin(theta)).astype(int)
        covered=np.any(cells[2][y,x,:2],axis=1)
        return float(samples[covered].max()) if np.any(covered) else 0.
    shorts=[]
    for j in (1,3,5,7,9):
        theta=-np.pi/2+j*2*np.pi/10
        tip=radial_extent(theta)
        valleys=[radial_extent(theta+sign*np.radians(12)) for sign in (-1,1)]
        shorts.append({'ray':j,'tip_radius_px':round(tip,4),'adjacent_valley_radii_px':[round(v,4) for v in valleys],'prominence_fraction':round((tip-max(valleys))/long_radius,6)})
    return {
        'body_reach_long_rays':{'passed':all(v['fraction_of_R_L']>=.55 for v in axis_reaches),'measured':axis_reaches,'expected':'>=0.55 R_L for each of five long rays','note':'Saved R channel sampled along each axis in 0.025 master-pixel steps.'},
        'visible_rays_on_navy':{'passed':visible['36']['distinct_rays']==10 and long_pass_27,'measured':visible,'expected':{'36px':10,'27px':'all five long rays distinct; report total honestly'},'note':'R or G only; navy #061623 excludes the near-navy keyline. Same polar wedge test as alpha.'},
        'visible_growth_on_navy':{'passed':all(growth[i][k]<growth[i+1][k] for i in (0,1) for k in ('circumscribed_radius_px','pixel_area')),'measured':growth,'expected':'frame 0 < frame 1 < frame 2 in radius and area','note':'Saved R/G union at master size, B excluded.'},
        'short_ray_prominence':{'passed':all(v['prominence_fraction']>=.15 for v in shorts),'measured':shorts,'expected':'>=0.15 R_L for each short tip minus both adjacent valleys','note':'Saved silhouette angular samples; continuous design prominence is 0.55-0.37=0.18; pixel quantization is included.'}
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(visual_reviewed=False):
    checks = {}
    baseline = json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    changed = [name for name, info in baseline['inputs'].items() if not (ROOT/name).is_file() or digest(ROOT/name) != info['sha256']]
    old_hud = {n for n in baseline['inputs'] if n.startswith('art/imagegen/hud-icons-v3/')}
    now_hud = {p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    checks['all_sources_unchanged'] = not changed and old_hud == now_hud
    hud_digest_after = hashlib.sha256(''.join(n+'\t'+digest(ROOT/n)+'\n' for n in sorted(now_hud)).encode()).hexdigest()
    checks['hud_tree_digest_matches_before'] = hud_digest_after == baseline['hud_tree_digest']
    checks['snapshot_byte_identical'] = digest(PACKAGE/'_tools/draw_icons_v3_snapshot.py') == baseline['inputs']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']
    with Image.open(PACKAGE/'vector/T_FX_HitStar_4x2.png') as mask_image:
        checks['atlas_dimensions_and_mode'] = mask_image.size == (1024,512) and mask_image.mode == 'RGBA'
        mask = np.array(mask_image)
    preview = np.array(Image.open(PACKAGE/'vector/T_FX_HitStar_4x2-preview.png'))
    checks['mask_a_max_rgb'] = np.array_equal(mask[:,:,3],np.max(mask[:,:,:3],axis=2))
    checks['mask_binary_disjoint'] = set(np.unique(mask).tolist()) == {0,255} and bool(np.all(np.count_nonzero(mask[:,:,:3],axis=2) <= 1))
    checks['same_alpha_mask_preview'] = np.array_equal(mask[:,:,3],preview[:,:,3])
    palette = np.array([[255,180,92],[249,235,219],[17,19,23]],dtype=np.uint8)
    expected_colours = {tuple(c) for c in palette}
    actual_colours = {tuple(c) for c in np.unique(preview[:,:,:3][preview[:,:,3]>0],axis=0)}
    checks['opaque_colour_exact_tokens'] = actual_colours == expected_colours
    master = np.array(Image.open(PACKAGE/'comparison/master-colour.png'))
    cells, preview_cells = [], []
    bleed_results = []
    for i in range(8):
        x,y = (i%4)*256,(i//4)*256
        m = mask[y:y+256,x:x+256]
        p = preview[y:y+256,x:x+256]
        cells.append(m)
        preview_cells.append(p)
        distance, indices = distance_transform_edt(m[:,:,3] == 0,return_indices=True)
        halo = (m[:,:,3]==0) & (distance<=4)
        far = (m[:,:,3]==0) & (distance>4)
        bleed_results.append(bool(np.all(p[:,:,:3][far]==0) and np.array_equal(p[:,:,:3][halo],p[:,:,:3][indices[0][halo],indices[1][halo]])))
        sx, sy = 24+(i%4)*276, 88+(i//4)*316
        sheet_cell = master[sy:sy+256,sx:sx+256]
        checks[f'frame_{i}_sheet_colour_is_delivered_preview'] = np.array_equal(sheet_cell[m[:,:,3]>0],p[:,:,:3][m[:,:,3]>0])
    checks['all_cells_exact_4px_preview_bleed'] = all(bleed_results)
    # Retain legacy check key; fix1 changes frame1 to body + outer keyline.
    checks['frame0_and_frame1_body_only'] = bool(np.all(cells[0][:,:,1:3]==0) and np.all(cells[1][:,:,1]==0) and np.any(cells[1][:,:,2]))
    checks['frame7_body_only'] = bool(np.all(cells[7][:,:,1:3]==0))
    for i in range(1,7):
        silhouette=np.any(cells[i][:,:,:2],axis=2)
        inside=distance_transform_edt(silhouette)
        outside=distance_transform_edt(~silhouette)
        checks[f'frame{i}_keyline_outside_8px'] = bool(np.array_equal(cells[i][:,:,2]>0,(~silhouette)&(outside<=8)))
        if i>=2:
            checks[f'frame{i}_cream_inside_8px'] = bool(np.array_equal(cells[i][:,:,1]>0,silhouette&(inside<=8)))
    checks['hold_frames_identical'] = all(np.array_equal(cells[2],cells[i]) for i in (3,4,5))
    checks['centre_opens'] = bool(cells[6][129,129,3]==0 and cells[7][129,129,3]==0)
    checks['five_broken_ring_components'] = int(label(cells[7][:,:,3]>0,np.ones((3,3),dtype=int))[1]) == 5
    for size in (36,27):
        for i in (0,1,2):
            count=8 if i<2 else 10
            checks[f'saved_alpha_frame{i}_{size}px_{count}_distinct_rays'] = polar_report(cells[i],size,count)['passed']
    checks['poster0_is_frame0'] = np.array_equal(np.array(Image.open(PACKAGE/'vector/poster-frame0-mask.png')),cells[0])
    checks['reduced_motion_is_frame2'] = np.array_equal(np.array(Image.open(PACKAGE/'vector/reduced-motion-frame2-mask.png')),cells[2])
    records = json.loads((PACKAGE/'generation-records.json').read_text(encoding='utf-8'))
    b=next(g for g in records['generations'] if g['prompt_key'].endswith('procedural-B'))
    for kind in ('mask','preview'):
        name=f'concepts/variant-B-{kind}.png'
        checks[f'raw_variantB_unchanged_{kind}'] = digest(PACKAGE/name)==b['output_sha256'][name]
        checks[f'raw_variantC_matches_final_{kind}'] = digest(PACKAGE/f'concepts/variant-C-{kind}.png')==digest(PACKAGE/f'vector/T_FX_HitStar_4x2{"-preview" if kind=="preview" else ""}.png')
    # Every colour/gray pair, including boards and labels, must be exactly Y'.
    pairs = [(PACKAGE/f'comparison/{stem}-colour.png',PACKAGE/f'comparison/{stem}-gray.png') for stem in ('master','working','working-bilinear','timing','variants','reduced-motion')]
    pairs += [(DERIVED/f'{stem}-colour.png',DERIVED/f'{stem}-gray.png') for stem in ('master-board','working-board','working-board-bilinear')]
    for cpath,gpath in pairs:
        c = np.array(Image.open(cpath).convert('RGB'),dtype=np.float64)
        g = np.array(Image.open(gpath).convert('RGB'))
        y = np.rint(c @ np.array([.2126,.7152,.0722])).astype(np.uint8)
        checks[f'gray_pair_{cpath.stem}'] = bool(np.array_equal(g,np.repeat(y[:,:,None],3,axis=2)))
    playback = json.loads((PACKAGE/'playback.json').read_text(encoding='utf-8'))
    intervals = playback['frame_intervals_ms']
    checks['timing_270ms_and_30fps'] = len(intervals)==8 and playback['delay_from_contact_ms']==70 and playback['lifetime_ms']==270 and all(abs(f['start']-i*1000/30)<1e-9 for i,f in enumerate(intervals)) and intervals[-1]['end']==270
    checks['generation_scripts_match_records'] = all((g.get('historical_script_revision') or digest(PACKAGE/g['script'])==g['script_sha256']) and all(digest(PACKAGE/n)==h for n,h in g['output_sha256'].items()) for g in records['generations'])
    # Manifest is checked without repairing stale entries or writing any files.
    old_manifest = json.loads((PACKAGE/'manifest-sha256.json').read_text(encoding='utf-8'))
    stale = [entry['path'] for entry in old_manifest['entries'] if not (ROOT/entry['path']).is_file() or digest(ROOT/entry['path']) != entry['sha256']]
    checks['previous_manifest_entries_valid'] = not stale
    actual_paths={p.relative_to(ROOT).as_posix() for base in (PACKAGE,DERIVED) for p in base.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
    checks['manifest_covers_every_file'] = actual_paths=={e['path'] for e in old_manifest['entries']} and len(actual_paths)==len(old_manifest['entries'])
    vpath = PACKAGE/'verification.json'
    verification = json.loads(vpath.read_text(encoding='utf-8'))
    checks['ray_tests_all_frames0_to5_at36_and27'] = all(polar_report(cells[i],s,8 if i<2 else 10)['passed'] for i in range(6) for s in (36,27))
    reports=correction_reports(cells)
    for name,report in reports.items():
        checks[name]=report['passed']
        checks[f'{name}_report_matches_saved_files']=verification.get(name)==report
    checks['acceptance_objects_complete'] = isinstance(verification['acceptance'],dict) and len(verification['acceptance'])==6 and all(set(v)=={'passed','measured','expected','note'} for v in verification['acceptance'].values())
    checks['acceptance_clauses_passed'] = all(v['passed'] for v in verification['acceptance'].values())
    checks['sampler_mipmaps_on'] = 'mipmaps ON' in playback['sampler']
    png_paths={p.relative_to(ROOT).as_posix() for base in (PACKAGE,DERIVED) for p in base.rglob('*.png')}
    checks['exports_cover_every_png']=png_paths==set(verification['exports'])
    export_matches=[]
    for name in sorted(png_paths):
        with Image.open(ROOT/name) as im:
            bbox=im.getchannel('A').getbbox() if im.mode=='RGBA' else (0,0,*im.size)
            margins=[bbox[0],bbox[1],im.width-bbox[2],im.height-bbox[3]] if bbox else [im.width,im.height,im.width,im.height]
            e=verification['exports'][name]
            export_matches.append(e['size_px']==list(im.size) and e['mode']==im.mode and e['rgba']==(im.mode=='RGBA') and e['margins_ltrb_px']==margins and e['margin_px']==min(margins) and e['touches_edge']==(min(margins)==0))
    checks['export_dimensions_modes_margins_match_saved_pngs']=all(export_matches)
    checks['palette_report_matches_tokens']=verification['palette']['dE76_max']==0 and verification['palette']['outside_tolerance_fraction']==0 and checks['opaque_colour_exact_tokens']
    checks['sizes_report_matches_master']=verification['sizes']['atlas_px']==[1024,512] and verification['sizes']['frames']==8 and verification['sizes']['grid']==[4,2] and verification['sizes']['master_cell_px']==[256,256] and verification['sizes']['working_px']==[36,27] and verification['sizes']['master_downscaled'] is False
    checks['gray_report_pairs_present_and_correct']=len(verification['gray']['pairs'])==9 and all(checks[f'gray_pair_{(PACKAGE/p["colour"]).stem}'] for p in verification['gray']['pairs'])
    checks['outside_folder_empty']=verification['outside_folder']==[]
    if visual_reviewed:
        checks['visual_review_recorded']=isinstance(verification['visual_review'],dict) and verification['visual_review'].get('completed') is True
    failed=[k for k,v in checks.items() if not v]
    return {'passed':not failed,'read_only':True,'checks':checks,'check_count':len(checks),'failed':failed,'sources_checked':len(baseline['inputs']),'manifest_entries':len(old_manifest['entries']),'correction_reports':reports,'source_mismatches':changed,'manifest_mismatches':stale,'hud_tree_digest_before':baseline['hud_tree_digest'],'hud_tree_digest_after':hud_digest_after,'method':'Loads delivered PNGs and input files independently; does not import procedural builder. Alpha and visible-ray tests both gate completion.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--visual-reviewed',action='store_true',help='Require prior explicit visual review record; never writes it.')
    args=parser.parse_args()
    result=audit(args.visual_reviewed)
    print(json.dumps(result))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
