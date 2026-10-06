"""Capture inputs BEFORE the corrective build; never invoke git or Unreal."""
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
if (PACKAGE / 'fix1-provenance.json').exists():
    raise SystemExit('CX-02r baseline already captured; do not overwrite it.')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name, data):
    (PACKAGE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

old = PACKAGE / '_tools/draw_icons_v3_snapshot.py'
current = ROOT / 'art/imagegen/hud-icons-v3/_tools/draw_icons.py'
def nodes(p):
    result = {}
    for node in ast.parse(p.read_text(encoding='utf-8')).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in ('rect_sil', 'Poly', 'poly', 'hx'):
            result[node.name] = ast.dump(node, include_attributes=False)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TOKENS' for t in node.targets):
            result['TOKENS'] = ast.dump(node.value, include_attributes=False)
    return result
a, b = nodes(old), nodes(current)
readme = (PACKAGE / 'README.md').read_bytes()
marker = '## Ревью Claude (2026-10-06, VS-1, единственный проход, по делегированию)'.encode('utf-8')
review = readme[readme.index(marker):]
(PACKAGE / '_tools/claude-review-verbatim.md').write_bytes(review)
records = json.loads((PACKAGE / 'generation-records.json').read_text(encoding='utf-8'))
runs = sorted({r['run'] for r in records['records']})
write('fix1-provenance.json', {
    'started_utc': datetime.now(timezone.utc).isoformat(),
    'old_engine_sha256': sha(old), 'new_engine_sha256': sha(current),
    'geometry_ast_unchanged': {k: a.get(k) == b.get(k) for k in ('rect_sil', 'Poly', 'poly', 'hx', 'TOKENS')},
    'claude_review_sha256': hashlib.sha256(review).hexdigest(),
    'pruned_runs': [{'run': r, 'note': 'moved out of the repo by Claude to C:/tmp/visual/CX-02r/pruned/, not in git'} for r in runs],
    'outside_folder': [],
    'write_scope_method': 'All mutations are explicit package-relative patches or Python guarded writes in the two allowed roots; no git, Unreal, external service or external writes.'
})
files = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / 'art/imagegen/hud-icons-v3').rglob('*')) if p.is_file()}
for name in (
    'docs/game-design/visual/02-visual-design.md', 'docs/game-design/visual/04-hud-spec.md',
    'docs/game-design/visual/07-prompt-templates.md',
    'docs/game-design/visual/06-tasks/prompts/HB-08.codex.md',
    'docs/game-design/visual/06-tasks/prompts/HB-08.fix1.codex.md',
    'docs/game-design/visual/06-tasks/hud.csv',
    'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/p7c/packaged-marmoreal/bench-K1-1920x1080.png',
    'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
):
    files[name] = sha(ROOT / name)
write('source-hashes-before.json', {'run': 'CX-02r', 'algorithm': 'sha256', 'files': files})
old.write_bytes(current.read_bytes())
print(json.dumps({'inputs': len(files), 'geometry': {k: a.get(k) == b.get(k) for k in b}, 'old_runs': runs}))
