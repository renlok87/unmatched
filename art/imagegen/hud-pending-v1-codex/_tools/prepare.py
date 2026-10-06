"""Record immutable sources before building. No git, UE, network or external writes."""
import sys
sys.dont_write_bytecode = True
import hashlib, json, re, shutil
from pathlib import Path
PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[2]
PROMPT = ROOT/'docs/game-design/visual/06-tasks/prompts/HB-34.codex.md'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):
    try: return p.relative_to(ROOT).as_posix()
    except ValueError: return p.as_posix()
paths = set()
expected = {}
for line in PROMPT.read_text(encoding='utf-8').splitlines():
    if line.startswith('| `'):
        parts = line.split('|'); name = parts[1].strip().strip('`')
        if name in ('art/imagegen/',) or name.startswith('unreal/'): continue
        p = ROOT/name
        if p.is_file(): paths.add(p)
        elif p.is_dir(): paths.update(q for q in p.rglob('*') if q.is_file() and '__pycache__' not in q.parts)
        if len(parts)>4 and re.fullmatch('[0-9a-f]{64}',parts[4].strip()): expected[name] = parts[4].strip()
paths.add(PROMPT)
paths.add(ROOT/'docs/game-design/visual/07-prompt-templates.md')
paths.update(q for q in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if q.is_file())
fontdir=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
paths.update(fontdir/n for n in ['Roboto-BoldCondensed.ttf','Roboto-Regular.ttf'])
cards=json.loads((ROOT/'art/imagegen/mvp-v1/reused-cardart.json').read_text(encoding='utf-8'))['cards']
paths.update(ROOT/r[lang]['path'] for r in cards for lang in ['ru','en'])
baseline={'task':'HB-34','files':{rel(p):sha(p) for p in sorted(paths)},'expected':expected,
          'missing':[rel(p) for p in paths if not p.exists()],
          'scope':'All explicitly named input files and recursive input packages, all hud-icons-v3 files, fonts; broad art/imagegen ancestor excluded.'}
dest=PKG/'source-hashes-before.json'
if dest.exists(): raise SystemExit('Existing baseline: do not overwrite')
dest.write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
copies={
 'art/imagegen/hud-icons-v3/_tools/draw_icons.py':'draw_icons_v3_snapshot.py',
 'art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py':'composition_build_snapshot.py',
 'art/imagegen/hud-composition-v1-codex/_tools/layout_reference.py':'layout_reference_snapshot.py',
 'art/imagegen/hud-hand-v1-codex/_tools/build_mockups.py':'hand_build_snapshot.py',
 'art/imagegen/hud-hand-v1-codex/_tools/frame_native.py':'frame_native.py',
 'art/imagegen/hud-skins-v1-codex/_tools/draw_skins.py':'skins_snapshot.py'}
for src,name in copies.items(): shutil.copyfile(ROOT/src,PKG/'_tools'/name)
print(json.dumps({'hashed':len(paths),'copies':len(copies),'mismatches':[{ 'path':p,'expected':v,'actual':baseline['files'].get(p)} for p,v in expected.items() if p in baseline['files'] and v!=baseline['files'][p]]},ensure_ascii=False))
