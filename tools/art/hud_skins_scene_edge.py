#!/usr/bin/env python
"""VS-6 F4 (по делегированию ВР-VS6-35; VS-5 review, open item 2 / ВР-VS5-48): the scene edge of the HUD skins.

G-READ on the painted Marmoreal (EN-16, docs/game-design/evidence/VISUAL/ENV-U16/README.md) measured the 1 su hairline
of the HUD block panels against the backdrop below 3 : 1 on 9 of 11 panels: card.cream at 0.45 over the 0.92 body does
not separate from the mid tones of the plate (#30486A ... #997584). The fix is a token, not new art: the skins of the
blocks that lie on the scene - Panel, Capsule, Toast - draw their hairline with the new token panel.edge.scene
(card.cream, alpha 0.85); buttons, chips, the modal and the card frame keep panel.edge 0.45 (they sit on a panel).

The three skins are re-rendered by the accepted HB-08 engine itself (art/imagegen/hud-skins-v1-codex/_tools/draw_skins.py,
unchanged: its render() with the style's edge opacity replaced for these names) at x1 / x2 (vector/) and x4 (masters/);
the geometry, the slice margins and every other skin stay byte-identical. The importer tools/art/hud_skins_import.py
then puts them into /Game/S08/UI/Skins (UE commandlet, worktree project).

  python -B tools/art/hud_skins_scene_edge.py            write the 9 PNGs + scene-edge-vs6.json (old / new sha256)
  python -B tools/art/hud_skins_scene_edge.py --check    verify the files match the render (exit 1 otherwise)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'art/imagegen/hud-skins-v1-codex'
TOKENS_JSON = ROOT / 'docs/unreal/contracts/hud/hud-style-tokens.json'
NAMES = ('Panel', 'Capsule', 'Toast')
DIRS = ((1, 'vector/x1'), (2, 'vector/x2'), (4, 'masters'))
RECORD = PACKAGE / 'scene-edge-vs6.json'


def scene_edge_alpha() -> float:
    tokens = json.loads(TOKENS_JSON.read_text(encoding='utf-8'))
    entry = tokens['colors']['panel.edge.scene']
    return float(entry['alpha'])


def load_engine():
    spec = importlib.util.spec_from_file_location('hb08_draw_skins', PACKAGE / '_tools/draw_skins.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render_all(alpha: float):
    eng = load_engine()
    base_style = eng.style

    def style(name):
        st = base_style(name)
        if name in NAMES:
            st['edge_opacity'] = alpha
        return st

    eng.style = style
    out = {}
    for scale, directory in DIRS:
        for name in NAMES:
            im, meta = eng.render(name, scale)
            buf = io.BytesIO()
            im.convert('RGBA').save(buf, format='PNG', optimize=True)
            out[f'{directory}/T_Skin_{name}.png'] = (buf.getvalue(), meta)
    return out


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    alpha = scene_edge_alpha()
    files = render_all(alpha)
    if args.check:
        bad = [k for k, (data, _) in files.items() if (PACKAGE / k).read_bytes() != data]
        print(json.dumps({'check': 'fail' if bad else 'ok', 'alpha': alpha, 'mismatch': bad}))
        return 1 if bad else 0
    record = {'task': 'VS-6 F4 HUD scene edge (ВР-VS6-35, ВР-VS5-48)', 'token': 'panel.edge.scene', 'alpha': alpha,
              'engine': 'art/imagegen/hud-skins-v1-codex/_tools/draw_skins.py render() (unchanged), edge_opacity of '
                        + ', '.join(NAMES), 'files': {}}
    old = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.exists() else {}
    for key, (data, meta) in files.items():
        path = PACKAGE / key
        before = (old.get('files', {}).get(key) or {}).get('before') or sha(path.read_bytes())
        path.write_bytes(data)
        record['files'][key] = {'before': before, 'after': sha(data), 'size_px': meta['size_px'],
                                'slice_px': meta['slice_px'], 'edge_px': meta['edge_px']}
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'written': len(files), 'alpha': alpha, 'record': RECORD.relative_to(ROOT).as_posix()}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
