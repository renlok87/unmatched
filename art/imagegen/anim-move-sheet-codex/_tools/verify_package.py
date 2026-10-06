#!/usr/bin/env python
"""Independent on-disk checks. Writes only package-local verification results."""
from pathlib import Path
import hashlib
import json
import math
import sys
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
import build_step_sheet as builder
import fix1_support as fix1

PKG = Path(__file__).resolve().parent.parent
ROOT = PKG.parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    before = json.loads((PKG/'source-hashes-before.json').read_text(encoding='utf8'))
    changed = []
    for name, row in before['files'].items():
        p = Path(name) if Path(name).is_absolute() else ROOT/name
        if not p.is_file() or sha(p) != row['sha256'] or p.stat().st_size != row['bytes']:
            changed.append(name)
    hud_prefix='art/imagegen/hud-icons-v3/'
    original={p for p in before['files'] if p.startswith(hud_prefix)}
    current={p.relative_to(ROOT).as_posix() for p in (ROOT/hud_prefix).rglob('*') if p.is_file()}
    changed += sorted(current ^ original)
    checks = {'external_sources_unchanged':not changed,
              'snapshot_byte_identical':sha(PKG/'_tools/draw_icons_v3_snapshot.py')==sha(ROOT/hud_prefix/'_tools/draw_icons.py')}
    master=Image.open(PKG/'vector/AN-22-step-sheet.png')
    checks['master_RGBA_1920x1080']=master.mode=='RGBA' and master.size==(1920,1080)
    checks['master_matches_comparison']=sha(PKG/'vector/AN-22-step-sheet.png')==sha(PKG/'comparison/AN-22-step-sheet-color.png')
    for size,suffix in [((1920,1080),''),((1280,720),'-1280x720')]:
        color=Image.open(PKG/f'comparison/AN-22-step-sheet-color{suffix}.png')
        gray=Image.open(PKG/f'comparison/AN-22-step-sheet-gray{suffix}.png')
        a=np.array(color); b=np.array(gray)
        checks[f'RGBA_size{suffix}']=color.mode==gray.mode=='RGBA' and color.size==gray.size==size
        y=np.rint(a[:,:,:3].astype(float) @ np.array([.2126,.7152,.0722])).astype(np.uint8)
        checks[f'Rec709{suffix}']=all(np.array_equal(b[:,:,i],y) for i in range(3)) and np.array_equal(a[:,:,3],b[:,:,3])
    rgb=np.array(master)[:,:,:3]
    for role,hexval in json.loads((PKG/'palette.json').read_text()).items():
        value=np.array([int(hexval[i:i+2],16) for i in [1,3,5]])
        checks[f'token_present:{role}']=bool(np.any(np.all(rgb==value,axis=2)))
    records=json.loads((PKG/'generation-records.json').read_text(encoding='utf8'))
    task=ROOT/'docs/game-design/visual/06-tasks/prompts/AN-22.codex.md'
    prompts=fix1.read(PKG/'prompts/AN-22-prompts.json')
    for i,r in enumerate(records['records']):
        checks[f'raw_generation_{i+1}_unchanged']=sha(PKG/r['output'])==r['output_sha256']
        checks[f'exact_prompt_{i+1}']=sha(PKG/r['exact_prompt_file'])==r['prompt_sha256'] and prompts[r['prompt_key']]==(PKG/r['exact_prompt_file']).read_text(encoding='utf8')
    checks['final_matches_last_raw_generation']=sha(PKG/records['records'][-1]['output'])==sha(PKG/'vector/AN-22-step-sheet.png')
    checks['last_generation_current_script']=records['records'][-1]['generator_sha256']==sha(PKG/'_tools/build_step_sheet.py')
    poses=json.loads((PKG/'pose-transforms.json').read_text(encoding='utf8'))
    checks['twelve_pose_glyphs']=len(poses['poses'])==12
    checks['flat_ground_no_hop']=all(p['hop']==0 and p['base_rotation_degrees']==0 and p['base_ground_y']=={'KingArthur':455,'Harpy':620}[p['hero']] for p in poses['poses'])
    checks['10deg_body_rigid_rotation']=all(
      np.allclose(np.array(p['rotation_after_reflection']).T @ np.array(p['rotation_after_reflection']),np.eye(2),atol=1e-12)
      and math.isclose(math.degrees(math.atan2(p['rotation_after_reflection'][1][0],p['rotation_after_reflection'][0][0])),0 if p['time_ms'] in [0,710] else 10,abs_tol=1e-12)
      for p in poses['poses'])
    checks['no_back_facing_diagram']=all(p['facing'][1]>=0 for p in poses['facings'])
    checks['idle_within45_camera']=all(math.degrees(math.atan2(abs(p['facing'][0]),p['facing'][1]))<=45 for p in poses['facings'] if p['idle'])
    verification=json.loads((PKG/'verification.json').read_text(encoding='utf8'))
    baseline=fix1.read(PKG/'fix1-before.json')
    checks['source_baseline_not_recaptured']=sha(PKG/'source-hashes-before.json')==baseline['files']['source-hashes-before.json']['sha256']
    checks['concepts_01_03_immutable']=all(sha(PKG/p)==r['sha256'] and (PKG/p).stat().st_size==r['bytes'] for p,r in baseline['files'].items() if p.startswith('concepts/'))
    checks['exact_base_task_prompt']=prompts['AN-22/task']==fix1.task_text('AN-22.codex.md')
    checks['exact_fix1_task_prompt']=prompts['AN-22/fix1']==fix1.task_text('AN-22.fix1.codex.md')
    checks['pass04_selected_only']=len(records['records'])==4 and [r['prompt_key'] for r in records['records'] if r['selected']]==['AN-22/fix1-pass04']
    checks['support_module_hash']=records['records'][-1]['support_sha256']==sha(PKG/'_tools/fix1_support.py')
    # Fresh native render in memory: never resample the master and never save a new pass.
    native,_=fix1.render_native(builder,fix1.load_heroes())
    checks['working_native_render_reproducible']=np.array_equal(np.array(native),np.array(Image.open(PKG/'comparison/AN-22-step-sheet-color-1280x720.png')))
    checks['native_differs_from_master_resize']=not np.array_equal(np.array(native),np.array(master.resize((1280,720),Image.Resampling.LANCZOS)))
    builder.TEXT_BOXES=[]; builder.POSE_TRANSFORMS=[]; builder.FACINGS=[]
    rebuilt=builder.build(fix1.load_heroes())
    checks['master_render_reproducible']=np.array_equal(np.array(rebuilt),np.array(master))
    checks['overview_960_removed']=not any((PKG/'comparison').glob('*960x540.png'))
    diff=np.any(np.array(master)!=np.array(Image.open(PKG/'concepts/AN-22-step-sheet-pass03.png')),axis=2)
    checks['accepted_drawing_preserved']=diff.any() and not diff[:657].any() and not diff[681:].any()
    measured=fix1.measurements()
    checks['measurement_records_match_saved_pixels']=all(verification[k]==v for k,v in measured.items())
    checks['exports_complete_RGBA_margin']=len(measured['exports'])==5 and all(r['mode']=='RGBA' and r['margin_px']>0 and not r['touches_edge'] for r in measured['exports'])
    checks['palette_dE76_share_zero']=measured['palette']['off_palette_share']==0
    checks['grey_distinctions_measured']=all(r['passed'] for r in measured['gray']['distinguishable_pairs'])
    checks['eight_acceptance_records']=len(measured['acceptance'])==8 and all(r['passed'] for r in measured['acceptance'].values())
    checks['working_not_downscaled']=all(r['downscaled_from_master'] is False for r in measured['sizes']['working'])
    # Keys inventoried when the original report was read, prior to correction.
    historical={'task','status','source_unchanged','changed_sources','source_files_checked',
                'hud_tree_files_checked','outside_folder','outside_folder_scope','checks',
                'all_automated_checks_pass','comparison_files','limitations','unmet_requirements',
                'visual_review','generation','processes_started_in_background','numeric_samples',
                'ground_contract','silhouette_transform','reviewed_final_sha256','failures_resolved',
                'readme','independent_verification','independent_checks_summary','output_manifest'}
    checks['historical_verification_keys_retained']=historical<=set(verification) and {'method','images','checks','working_size_limit','source_proofs'}<=set(verification['visual_review'])
    checks['manifest_name_and_legacy_removed']=verification['output_manifest']=='manifest-sha256.json' and not (PKG/'manifest.json').exists()
    checks['visual_review_matches_final_hash']=verification['reviewed_final_sha256']==sha(PKG/'vector/AN-22-step-sheet.png')
    # Independently evaluate the first-edge closed form, without importing the builder model.
    samples=verification['numeric_samples']
    checks['samples_match_first_edge_formula']=all(math.isclose(samples[str(t)]['s'],
        t*t/(2*80*240) if t<=80 else (t-40)/240,abs_tol=1e-12) for t in [0,40,50,60,80,280])
    checks['samples_match_second_edge_formula']=all(math.isclose(samples[str(t)]['s'],
        1+(t-280)/240 if t<=480 else 2-(560-t)**2/(2*80*240),abs_tol=1e-12) for t in [280,400,480,560])
    checks['vertex_velocity_continuous_positive']=samples['280']['v_edges_per_ms']==1/240
    checks['arrival_and_idle']=samples['560']['s']==2 and samples['560']['v_edges_per_ms']==0 and samples['710']['lean_degrees']==0
    checks['build_checks_pass']=verification['all_automated_checks_pass'] and all(verification['checks'].values())
    checks['visual_review_done']=verification['visual_review']['status']=='passed'
    audit=json.loads((PKG/'write-audit.json').read_text(encoding='utf8'))
    allowed=[d.replace('\\','/') for d in audit['allowed']]
    checks['write_audit_confined']=all(any(p==d or p.startswith(d+'/') for d in allowed) for p in audit['writes'])
    checks['outside_folder_empty']=verification['outside_folder']==[]
    checks['readme_status']= '**предложено**' in (PKG/'README.md').read_text(encoding='utf8')
    if '--check-manifest' in sys.argv:
        manifest=fix1.read(PKG/'manifest-sha256.json')
        files={p.relative_to(ROOT).as_posix():p for base in [PKG,fix1.DERIVED] for p in base.rglob('*') if p.is_file() and p!=PKG/'manifest-sha256.json'}
        checks['manifest_covers_all_files']=set(manifest['files'])==set(files)
        checks['manifest_hashes_and_sizes']=all(name in files and sha(files[name])==r['sha256'] and files[name].stat().st_size==r['bytes'] for name,r in manifest['files'].items())
    result={'checks':checks,'all_pass':all(checks.values()),'changed_sources':changed,'source_files_checked':len(before['files']),
            'scope':'Independent reread of package and named source inputs; no git/MCP/runtime, no background processes.'}
    if '--check-manifest' not in sys.argv:
        (PKG/'independent-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        verification['independent_checks_summary']={'checks':len(checks),'all_pass':result['all_pass']}
        fix1.dump(PKG/'verification.json',verification)
    print(json.dumps({'independent_checks':len(checks),'all_pass':result['all_pass'],'failed':[k for k,v in checks.items() if not v]},ensure_ascii=False))
    if not result['all_pass']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
