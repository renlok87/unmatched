"""Capture inputs before production; write only the HB-42 package."""
from pathlib import Path
import hashlib, json, re, shutil

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'art/imagegen/hud-actions-v1-codex'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):
    try: return p.relative_to(ROOT).as_posix()
    except ValueError: return p.as_posix()
prompt = ROOT / 'docs/game-design/visual/06-tasks/prompts/HB-42.codex.md'
paths = set(re.findall(r'`([^`]+)`', prompt.read_text('utf-8').split('## Warnings')[0]))
inputs = {prompt}
missing = []
for name in paths:
    p = ROOT / name
    if p.is_file(): inputs.add(p)
    elif p.is_dir(): inputs.update(x for x in p.rglob('*') if x.is_file())
    elif '/' in name: missing.append(name)
for name in ['hud-icons-v3','hud-icons-vr44-codex','hud-composition-v1-codex','hud-skins-v1-codex','hud-hand-v1-codex','hud-decks-v1-codex']:
    inputs.update(x for x in (ROOT/'art/imagegen'/name).rglob('*') if x.is_file())
for p in (ROOT/'scraped-data/derived/hud-decks-v1-codex').glob('HB-26-*-chips-*.png'): inputs.add(p)
reuse = json.loads((ROOT/'art/imagegen/mvp-v1/reused-cardart.json').read_text('utf-8'))
def visit(obj):
    if isinstance(obj,dict):
        for v in obj.values(): visit(v)
    elif isinstance(obj,list):
        for v in obj: visit(v)
    elif isinstance(obj,str) and obj.startswith('scraped-data/') and (ROOT/obj).is_file(): inputs.add(ROOT/obj)
visit(reuse)
for name in ['Roboto-BoldCondensed.ttf','Roboto-Regular.ttf']:
    inputs.add(Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')/name)
target = PKG/'source-hashes-before.json'
if target.exists(): raise RuntimeError('The before snapshot must never be overwritten')
target.write_text(json.dumps({'schema':'HB-42.inputs/1','files':{rel(p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(inputs)},'missing_paths':missing,'scope':'All named inputs; complete accepted packages and hud-icons-v3 tree; accepted HB-26 chips; card scans and fonts.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
snapshots = {
 'art/imagegen/hud-icons-v3/_tools/draw_icons.py':'draw_icons_v3_snapshot.py',
 'art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py':'hb07_build_mockups_snapshot.py',
 'art/imagegen/hud-composition-v1-codex/_tools/layout_reference.py':'layout_reference_snapshot.py',
 'art/imagegen/hud-decks-v1-codex/_tools/build_mockups.py':'hb26_build_mockups_snapshot.py',
 'art/imagegen/hud-hand-v1-codex/_tools/build_mockups.py':'hb22_build_mockups_snapshot.py',
}
for source,name in snapshots.items():
    shutil.copyfile(ROOT/source,PKG/'_tools'/name)
(PKG/'concepts').mkdir(exist_ok=True)
(PKG/'generation-records.json').write_text(json.dumps({'task':'HB-42','image_generation':False,'records':[],'note':'ImageGen prohibited by the task. Procedural rendering is reproduced by _tools/build_mockups.py; no generated concepts.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Captured {len(inputs)} source files; {len(snapshots)} unchanged script snapshots. Missing: {missing}')
