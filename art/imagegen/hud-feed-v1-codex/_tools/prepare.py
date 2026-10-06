"""Capture immutable inputs before rendering; no git/UE/network/subprocess."""
import sys
sys.dont_write_bytecode = True
import hashlib, json, re, shutil, os
from pathlib import Path
PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[2]
DERIVED = ROOT/'scraped-data/derived/hud-feed-v1-codex'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def rel(p):
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    if (PKG/'source-hashes-before.json').exists():raise RuntimeError('Do not replace baseline')
    prompt=ROOT/'docs/game-design/visual/06-tasks/prompts/HB-38.codex.md'
    files={prompt}
    for raw in re.findall(r'`([^`]+)`',prompt.read_text(encoding='utf8')):
        p=Path(raw) if raw.startswith('C:/') else ROOT/raw
        if p.is_file():files.add(p)
        elif p.is_dir() and raw.startswith(('art/imagegen/hud-','art/imagegen/card-frame-v1-codex')):
            files.update(q for q in p.rglob('*') if q.is_file() and '__pycache__' not in q.parts)
    for name in ['hud-composition-v1-codex','hud-topstrip-v1-codex','hud-hand-v1-codex','hud-combat-v1-codex','hud-pending-v1-codex','card-frame-v1-codex','hud-skins-v1-codex','hud-icons-v3','hud-icons-vr44-codex']:
        files.update(p for p in (ROOT/'art/imagegen'/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for p in list(files):
        if p.name=='combat-client-host.trace.txt' and '/I/' in p.as_posix():files.add(p.with_name('combat-client-joiner.trace.txt'))
    files.update(p for p in (ROOT/'scraped-data/images').rglob('*') if p.is_file())
    for name in ['Roboto-Regular.ttf','Roboto-BoldCondensed.ttf']:
        files.add(Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')/name)
    files.add(ROOT/'.agents/skills/canvas-design/SKILL.md')
    files.add(ROOT/'docs/game-design/visual/07-prompt-templates.md')
    missing=[str(p) for p in files if not p.is_file()]
    if missing:raise RuntimeError(missing)
    dump(PKG/'source-hashes-before.json',{'task':'HB-38','files':{rel(p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(files)},'method':'All named files, accepted package trees, entire v3 tree, scan tree, fonts. Captured before snapshots/rendering.'})
    copies={'hud-composition-v1-codex/_tools/build_mockups.py':'composition_build_snapshot.py','hud-composition-v1-codex/_tools/layout_reference.py':'layout_reference.py','hud-hand-v1-codex/_tools/build_mockups.py':'hand_build_snapshot.py','hud-hand-v1-codex/_tools/frame_native.py':'frame_native.py','hud-pending-v1-codex/_tools/build_mockups.py':'pending_build_snapshot.py','hud-pending-v1-codex/_tools/skins_snapshot.py':'skins_snapshot.py','hud-topstrip-v1-codex/_tools/build_mockups.py':'topstrip_build_snapshot.py','hud-icons-v3/_tools/draw_icons.py':'draw_icons_v3_snapshot.py'}
    for src,dst in copies.items():shutil.copyfile(ROOT/'art/imagegen'/src,PKG/'_tools'/dst)
    (PKG/'concepts').mkdir(exist_ok=True)
    DERIVED.mkdir(parents=True,exist_ok=True)
    dump(PKG/'generation-records.json',{'task':'HB-38','image_generation':False,'records':[],'exact_prompt_key':'HB-38-procedural-v1','note':'Задание запрещает ImageGen; concepts/ пуст.'})
    print('Inputs hashed:',len(files),'unchanged snapshots:',len(copies),flush=True)
if __name__=='__main__':main()
