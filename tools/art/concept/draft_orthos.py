#!/usr/bin/env python3
"""Черновые ортопроекции модели для этапа 1b скилла 3d-model-pipeline (Blender headless).

    python tools/art/concept/draft_orthos.py --glb <draft.glb> --out <dir> [--views front,left,back,right] \
        [--aspect 3:4] [--long-side 1536] [--bg 0.18] [--blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"]

Выход: <out>/ortho_<view>.png (RGB, ровный нейтральный фон) + <out>/ortho-framing.json (масштаб, положение камер,
места подставки и верха фигуры в % кадра — числа для промптов этапа 1c). Один и тот же кадр для всех видов: общий
ortho_scale, центр подставки по x = 50 %, низ подставки на одной высоте. Код 0 = все виды записаны, 1 = ошибка.

--bg — уровень серого фона в sRGB 0..1 (0.18 → 46/255, тёмно-серый как в hero-quality-v1). Оси — HANDBOOK §2.1
(лицо −Y); left = левый бок фигуры (камера в +X). Blender-часть — _blender_orthos.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
KNOWN_VIEWS = ("front", "left", "back", "right")
TIMEOUT_S = 1800


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolution(aspect: str, long_side: int):
    try:
        aw, ah = (float(x) for x in aspect.split(":"))
    except ValueError as exc:
        raise ValueError(f"--aspect должен быть W:H, получено {aspect!r}") from exc
    if aw <= 0 or ah <= 0 or long_side < 64:
        raise ValueError("--aspect и --long-side должны быть положительными, --long-side ≥ 64")
    if ah >= aw:
        return int(round(long_side * aw / ah)), long_side
    return long_side, int(round(long_side * ah / aw))


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glb", required=True, help="черновая модель Tripo (.glb)")
    ap.add_argument("--out", required=True, help="каталог вывода")
    ap.add_argument("--views", default="front,left,back,right", help="подмножество front,left,back,right")
    ap.add_argument("--aspect", default="3:4", help="аспект кадра W:H (по умолчанию 3:4)")
    ap.add_argument("--long-side", type=int, default=1536, help="длинная сторона кадра, px")
    ap.add_argument("--bg", type=float, default=0.18, help="серый фона, sRGB 0..1")
    ap.add_argument("--blender", default=DEFAULT_BLENDER, help="путь к blender.exe (5.2)")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # пайп cp1251 (Codex/PowerShell, Git Bash) не должен ронять печать «→»
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return 0 if not exc.code else 1
    try:
        return _run(args)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _run(args) -> int:
    glb = Path(args.glb)
    if not glb.is_file():
        raise ValueError(f"нет файла {glb}")
    blender = Path(args.blender)
    if not blender.is_file():
        raise ValueError(f"нет Blender: {blender}")
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    bad = [v for v in views if v not in KNOWN_VIEWS]
    if not views or bad or len(set(views)) != len(views):
        raise ValueError(f"--views: допустимы {', '.join(KNOWN_VIEWS)} без повторов, получено {args.views!r}")
    if not 0.0 <= args.bg <= 1.0:
        raise ValueError("--bg должен быть в 0..1")
    rx, ry = resolution(args.aspect, args.long_side)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    grey = int(round(args.bg * 255))

    with tempfile.TemporaryDirectory(prefix="draft-orthos-", dir=str(out)) as tmp:
        rdir = Path(tmp)
        cmd = [str(blender), "-b", "--factory-startup", "--python-exit-code", "1",
               "--python", str(HERE / "_blender_orthos.py"), "--",
               "--glb", str(glb.resolve()), "--render-dir", str(rdir), "--views", ",".join(views),
               "--res", f"{rx}x{ry}"]
        print("blender:", " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Blender не уложился в {TIMEOUT_S} с") from exc
        log = (proc.stdout or "") + (proc.stderr or "")
        (out / "draft-orthos-blender.log").write_text(log, encoding="utf-8")
        if proc.returncode != 0 or not (rdir / "framing.json").is_file():
            tail = "\n".join(log.strip().splitlines()[-15:])
            raise RuntimeError(f"Blender завершился с кодом {proc.returncode}:\n{tail}")
        framing = json.loads((rdir / "framing.json").read_text(encoding="utf-8"))
        outputs = {}
        for v in views:
            src = rdir / f"{v}.png"
            if not src.is_file():
                raise RuntimeError(f"Blender не записал вид {v}")
            rgba = Image.open(src).convert("RGBA")
            flat = Image.new("RGBA", rgba.size, (grey, grey, grey, 255))
            flat.alpha_composite(rgba)
            dst = out / f"ortho_{v}.png"
            flat.convert("RGB").save(dst, format="PNG", optimize=True)
            outputs[v] = {"path": dst.as_posix(), "sha256": sha256(dst), "size": list(rgba.size)}
        shutil.rmtree(rdir, ignore_errors=True)

    framing.update({
        "schema": "unmatched.draft-orthos/1",
        "tool": "tools/art/concept/draft_orthos.py",
        "glb": {"path": glb.as_posix(), "sha256": sha256(glb), "bytes": glb.stat().st_size},
        "background_srgb": [grey, grey, grey],
        "aspect": args.aspect,
        "outputs": outputs,
        "blender": str(blender),
        "prompt_hint": "в промптах этапа 1c: base centered x{0:.0f}%, base top y{1:.1f}%, bottom y{2:.1f}%, figure top "
                       "y{3:.1f}% (места подставки в % кадра)".format(
                           framing["placement_pct"]["base_center_x"], framing["placement_pct"]["base_top_y_est"],
                           framing["placement_pct"]["base_bottom_y"], framing["placement_pct"]["figure_top_y"]),
    })
    (out / "ortho-framing.json").write_text(json.dumps(framing, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    print(f"OK: {len(outputs)} видов → {out.as_posix()} (ortho-framing.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
