"""Persist the human-readable visual inspection performed in this task.
This is an inspection record, not a substitute for opening changed images.
"""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'art/imagegen/env-u16-marmoreal-codex'
IMG=ROOT/'scraped-data/derived/env-u16-marmoreal-codex'
p=PKG/'verification.json'
v=json.loads(p.read_text(encoding='utf-8'))
reviewed_sha='a127769e876620310f617310c439d4ceb973f0fb05d91a446f2846c27d02ba08'
current_sha=hashlib.sha256((IMG/'marmoreal-clean.png').read_bytes()).hexdigest()
if current_sha!=reviewed_sha or v['selected']!='A':
 raise RuntimeError('Plate changed: direct visual inspection is required; refusing to restore old review.')
v['visual_review']={
 'performed':True,'reviewer':'Codex main agent, direct view_image inspection',
 'inspected':['marmoreal-clean.png','concepts/EN-01-A-raw.png','concepts/EN-01-B-raw.png','concepts/EN-01-A-R1-raw.png','concepts/EN-01-A-R2-raw.png','comparison/05-K2-six-lights-colour.png','comparison/05-K2-six-lights-gray.png','comparison/02-K1-x065-colour.png','comparison/01-full-gray.png','comparison/08-diff-outside-remove-mask.png'],
 'selected':'A','reason':'Conservative restoration; four lamp pedestal bodies and four spherical balustrade finials retained in raw A. B and A-R2 removed unrelated spherical finials; refinements did not meet Lstar gate.',
 'four_lantern_heads_removed':True,'two_sconces_removed':True,'four_pedestal_bodies_intact':True,'plain_stone_caps':True,'no_water':True,'no_figures':True,'no_new_objects_or_baked_text':True,
 'warm_pool_only_inside_door':False,'residual_warmth':'Retained original warm spill on entry steps and adjacent architecture, plus warm highlights on the strictly protected painted frame. This criterion is not passed.',
 'plate_sha256_at_review':reviewed_sha
}
limit='Residual original warm spill remains on entry steps/architecture and warm highlights on the protected wooden frame; only-door warmth criterion is not passed.'
if limit not in v['limits']:v['limits'].append(limit)
v['acceptance_pass']=False
v['process_lifecycle']={'persistent_processes_started':[],'all_python_commands_exited':True,'all_imagegen_calls_finished':True}
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Visual inspection recorded; acceptance remains false.')
