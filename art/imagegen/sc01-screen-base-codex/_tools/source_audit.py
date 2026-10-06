"""Read-only source inventory; writes only to the SC-01 package."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = ROOT / 'art/imagegen/sc01-screen-base-codex'
FONT_ROOT = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
INPUTS = [
    'docs/game-design/visual/06-tasks/prompts/SC-01.codex.md',
    'docs/game-design/visual/06-tasks/screens.csv',
    'docs/game-design/visual/06-tasks/hud.csv',
    'docs/game-design/visual/07-prompt-templates.md',
    'docs/game-design/visual/04-hud-spec.md',
    'docs/game-design/visual/02-visual-design.md',
    'docs/unreal/contracts/hud/HUD-RULES.md',
    'docs/unreal/contracts/hud/hud-style-tokens.json',
    'art/imagegen/move-selection-v2/README.md',
    'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
    'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
    'docs/game-design/de-footage/task/runs/I-2026-10-05.md',
]

def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def current_inventory():
    paths = [ROOT / name for name in INPUTS]
    paths += [FONT_ROOT / 'Roboto-BoldCondensed.ttf', FONT_ROOT / 'Roboto-Regular.ttf']
    paths += sorted((ROOT / 'art/imagegen/hud-icons-v3').rglob('*'))
    for directory in [
        ROOT / 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag',
        ROOT / 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged',
    ]:
        paths += list(directory.glob('bench.trace.*')) + [directory / 'cmdline.txt']
    result = {}
    for path in paths:
        if path.is_file():
            key = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
            result[key] = {'sha256': sha256(path), 'bytes': path.stat().st_size}
        elif not path.exists():
            raise FileNotFoundError(path)
    return dict(sorted(result.items()))

def initialize():
    target = PACKAGE / 'source-hashes-before.json'
    if target.exists():
        raise RuntimeError('Refusing to replace the original before snapshot')
    data = current_inventory()
    icon_data = {k: v for k, v in data.items() if k.startswith('art/imagegen/hud-icons-v3/')}
    digest = hashlib.sha256(json.dumps(icon_data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    target.write_text(json.dumps({'schema': 'SC-01.sources/1', 'files': data,
        'icons_file_count': len(icon_data), 'icons_digest': digest,
        'digest_method': 'sha256(canonical sorted JSON mapping path to sha256 and bytes)'}, indent=2), encoding='utf-8')
    shutil.copyfile(ROOT / 'art/imagegen/hud-icons-v3/_tools/draw_icons.py',
                    PACKAGE / '_tools/draw_icons_v3_snapshot.py')
    print(json.dumps({'sources': len(data), 'icons': len(icon_data), 'snapshot': str(target)}))

if __name__ == '__main__':
    initialize()
