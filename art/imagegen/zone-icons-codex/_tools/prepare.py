"""Capture IC-37 inputs before creating assets; never writes outside the package."""
import csv
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
INPUTS = [
    'art/imagegen/hud-icons-v3/STYLE-v3.md',
    'art/imagegen/hud-icons-v3/_tools/draw_icons.py',
    'docs/game-design/visual/02-visual-design.md',
    'backend/prisma/fixtures/boards/marmoreal.topology.json',
    'backend/prisma/fixtures/boards/sarpedon.topology.json',
    'docs/unreal/contracts/hud/HUD-AND-ICONS.md',
    'docs/game-design/visual/07-prompt-templates.md',
    'docs/game-design/visual/06-tasks/icons.csv',
    'docs/game-design/visual/06-tasks/prompts/IC-37.codex.md',
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    out = PACKAGE / 'source-hashes-before.json'
    if out.exists():
        raise SystemExit('Baseline already exists; do not replace it.')
    paths = set(INPUTS)
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'art/imagegen/hud-icons-v3').rglob('*') if p.is_file())
    hashes = {p: {'sha256': sha(ROOT / p), 'bytes': (ROOT / p).stat().st_size} for p in sorted(paths)}
    out.write_text(json.dumps({'task': 'IC-37', 'inputs': INPUTS, 'files': hashes}, indent=2), encoding='utf-8')
    shutil.copyfile(ROOT / INPUTS[1], PACKAGE / '_tools/draw_icons_v3_snapshot.py')
    for name in ['concepts', 'comparison', 'vector', 'prompts']:
        (PACKAGE / name).mkdir(exist_ok=True)
    for filename, sections in [(INPUTS[0], ['1', '2', '3', '4', '8', '11']), (INPUTS[2], ['5', '7.4', '11.4']), (INPUTS[6], ['1.1'])]:
        content = (ROOT / filename).read_text(encoding='utf-8-sig')
        headings = list(re.finditer(r'^#{1,6}\s+([^\n]+)', content, re.M))
        print('\nFILE', filename)
        for i, h in enumerate(headings):
            if any(re.match(re.escape(s) + r'[.\s—·)]', h.group(1)) for s in sections):
                level = len(h.group(0)) - len(h.group(0).lstrip('#'))
                end = len(content)
                for following in headings[i+1:]:
                    next_level = len(following.group(0)) - len(following.group(0).lstrip('#'))
                    if next_level <= level:
                        end = following.start()
                        break
                print(content[h.start():end])
    with (ROOT / INPUTS[7]).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if any(v in {'IC-37', *('IC-' + str(i) for i in range(62,70))} for v in row.values()):
            print(json.dumps(row, ensure_ascii=False))
    for board in ['marmoreal','sarpedon']:
        data = json.loads((ROOT / f'backend/prisma/fixtures/boards/{board}.topology.json').read_text(encoding='utf-8-sig'))
        print(board, 'zones', json.dumps(data.get('zones'), ensure_ascii=False))
    print('baseline_files', len(hashes))

if __name__ == '__main__':
    main()
