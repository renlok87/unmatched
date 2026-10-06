"""Acceptance sheet of one visual unit (02-visual-design.md 13.2; step 6 of the cycle, 05-production-plan.md 1.7).

  python tools/art/visual/sheet.py HB-02 --inputs a.png b.png [--sizes 24,32,48] [--zoom 4] [--max-tile 960]
      [--backgrounds panel,cream,board] [--out docs/game-design/evidence/VISUAL/HB-02/]

For every input (master, working-size export or UE frame) it writes sheet-NN-<name>.png: the image in colour, in
gray (Rec.709 luma) and with a deuteranopia simulation, side by side. Images with transparency are shown on each
context background (02 13.2 item 4): panel.bg #061623, card.cream #F9EBDB and a neutral board grey #808080.
Small images (longest side <= 128 px) are zoomed x<zoom> nearest. With --sizes it also writes sheet-sizes.png: every
input at each size (native when the file already has that size, otherwise resampled and labelled so - a resampled
master is a preview, not a working-size export, И-9). sheet-manifest.json records inputs and outputs with sha256.
README.md is written from a template with the fields of 02 13.2 when the folder has none (never overwritten).

Gray: Y' = 0.2126 R' + 0.7152 G' + 0.0722 B' on the sRGB-encoded values (Rec.709 luma, as the icon sheets of the
project). Deuteranopia: Machado, Oliveira, Fernandes 2009, severity 1.0, applied in linear RGB.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from visual_common import EVIDENCE_REL, VisualError, rel_or_abs, repo_root, sha256_file, utf8_console  # noqa: E402

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError as _e:  # pragma: no cover - reported loudly at run time
    np = Image = ImageDraw = ImageFont = None
    _IMPORT_ERROR = _e
else:
    _IMPORT_ERROR = None

BACKGROUNDS = {
    "panel": ("panel.bg #061623", (0x06, 0x16, 0x23)),
    "cream": ("card.cream #F9EBDB", (0xF9, 0xEB, 0xDB)),
    "board": ("board grey #808080", (0x80, 0x80, 0x80)),
}
MODES = ("colour", "gray Rec.709", "deuteranopia")
LUMA_709 = (0.2126, 0.7152, 0.0722)
DEUTERANOPIA = (  # Machado et al. 2009, severity 1.0, linear RGB
    (0.367322, 0.860646, -0.227968),
    (0.280085, 0.672501, 0.047413),
    (-0.011820, 0.042940, 0.968881),
)
SHEET_BG = (32, 32, 32)
LABEL_FG = (224, 224, 224)
SMALL = 128
PAD = 12
FONT_CANDIDATES = (
    "C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/Roboto-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _require_libs():
    if _IMPORT_ERROR is not None:
        raise VisualError(f"sheet.py needs Pillow and numpy: {_IMPORT_ERROR}")


# ---------------------------------------------------------------- colour transforms

def gray709(rgb: "np.ndarray") -> "np.ndarray":
    """uint8 HxWx3 -> uint8 HxWx3 with equal channels: Rec.709 luma of the sRGB-encoded values."""
    y = rgb[..., :3].astype(np.float64) @ np.array(LUMA_709)
    y = np.clip(np.rint(y), 0, 255).astype(np.uint8)
    return np.repeat(y[..., None], 3, axis=2)


def _to_linear(c: "np.ndarray") -> "np.ndarray":
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _to_srgb(c: "np.ndarray") -> "np.ndarray":
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def deuteranopia(rgb: "np.ndarray") -> "np.ndarray":
    """uint8 HxWx3 -> uint8 HxWx3: deuteranopia simulation (Machado 2009, severity 1.0) in linear RGB."""
    lin = _to_linear(rgb[..., :3].astype(np.float64) / 255.0)
    sim = lin @ np.array(DEUTERANOPIA).T
    return np.clip(np.rint(_to_srgb(sim) * 255.0), 0, 255).astype(np.uint8)


def apply_mode(img: "Image.Image", mode: str) -> "Image.Image":
    rgb = np.asarray(img.convert("RGB"))
    if mode == MODES[0]:
        return Image.fromarray(rgb, "RGB")
    if mode == MODES[1]:
        return Image.fromarray(gray709(rgb), "RGB")
    return Image.fromarray(deuteranopia(rgb), "RGB")


def has_alpha(img: "Image.Image") -> bool:
    if img.mode not in ("RGBA", "LA", "PA") and "transparency" not in img.info:
        return False
    return img.convert("RGBA").getchannel("A").getextrema()[0] < 255


def flatten(img: "Image.Image", bg: tuple[int, int, int]) -> "Image.Image":
    base = Image.new("RGBA", img.size, bg + (255,))
    base.alpha_composite(img.convert("RGBA"))
    return base.convert("RGB")


# ---------------------------------------------------------------- layout

def _font(size: int = 14):
    for f in FONT_CANDIDATES:
        if Path(f).is_file():
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def display(img: "Image.Image", max_tile: int, zoom: int) -> tuple["Image.Image", str]:
    w, h = img.size
    if max(w, h) <= SMALL and zoom > 1:
        return img.resize((w * zoom, h * zoom), Image.NEAREST), f"{w}x{h} x{zoom} nearest"
    if max(w, h) > max_tile:
        s = max_tile / max(w, h)
        nw, nh = max(1, round(w * s)), max(1, round(h * s))
        return img.resize((nw, nh), Image.LANCZOS), f"{w}x{h} shown {nw}x{nh}"
    return img, f"{w}x{h} 1:1"


def _wrap(label: str, width: int, font) -> list[str]:
    """Pack the ' | '-separated parts of a label into lines no wider than width (a part is never split)."""
    lines: list[str] = []
    for part in label.split(" | "):
        if lines and font.getlength(lines[-1] + " | " + part) <= width:
            lines[-1] += " | " + part
        else:
            lines.append(part)
    return lines


def compose_grid(title: str, rows: list[tuple[str | None, list[tuple["Image.Image", str]]]], font) -> "Image.Image":
    """rows of (row header or None, [(tile, label)]) -> one sheet; labels wrap to the column width."""
    line_h = font.getbbox("Ag")[3] + 6
    ncol = max(len(cells) for _, cells in rows)
    col_w = []
    for c in range(ncol):
        cells = [cells[c] for _, cells in rows if c < len(cells)]
        tile_w = max(t.width for t, _ in cells)
        part_w = max(int(font.getlength(p)) for _, lab in cells for p in lab.split(" | "))
        col_w.append(max(tile_w, part_w, 96))
    layout = []
    for header, cells in rows:
        wrapped = [_wrap(lab, col_w[c], font) for c, (_, lab) in enumerate(cells)]
        label_h = max(len(w) for w in wrapped) * line_h
        head_h = line_h if header else 0
        layout.append((header, cells, wrapped, head_h, label_h, max(t.height for t, _ in cells)))
    width = PAD + sum(w + PAD for w in col_w)
    height = PAD + line_h + PAD + sum(hh + lh + th + PAD for _, _, _, hh, lh, th in layout)
    longest_text = max([font.getlength(title)] + [font.getlength(h) for h, *_ in layout if h])
    sheet = Image.new("RGB", (max(width, int(longest_text) + 2 * PAD), height), SHEET_BG)
    draw = ImageDraw.Draw(sheet)
    draw.text((PAD, PAD), title, fill=LABEL_FG, font=font)
    y = PAD + line_h + PAD
    for header, cells, wrapped, head_h, label_h, tile_h in layout:
        if header:
            draw.text((PAD, y), header, fill=LABEL_FG, font=font)
        x = PAD
        for c, (tile, _) in enumerate(cells):
            for k, line in enumerate(wrapped[c]):
                draw.text((x, y + head_h + k * line_h), line, fill=LABEL_FG, font=font)
            sheet.paste(tile, (x, y + head_h + label_h))
            x += col_w[c] + PAD
        y += head_h + label_h + tile_h + PAD
    return sheet


def _contexts(img: "Image.Image", names: list[str]) -> list[tuple[str, "Image.Image"]]:
    if not has_alpha(img):
        return [("opaque", img.convert("RGB"))]
    return [(BACKGROUNDS[n][0], flatten(img, BACKGROUNDS[n][1])) for n in names]


def input_sheet(cid: str, label: str, img: "Image.Image", bgs: list[str], max_tile: int, zoom: int, font,
                digest: str) -> "Image.Image":
    rows = []
    for ctx, flat in _contexts(img, bgs):
        row = []
        for mode in MODES:
            tile, size_note = display(apply_mode(flat, mode), max_tile, zoom)
            row.append((tile, f"{mode} | {ctx} | {size_note}"))
        rows.append((None, row))
    return compose_grid(f"{cid} | {label} | sha256 {digest[:16]} | colour / gray Rec.709 / deuteranopia", rows, font)


def resize_to(img: "Image.Image", size: int) -> tuple["Image.Image", str]:
    w, h = img.size
    if max(w, h) == size:
        return img, "native"
    s = size / max(w, h)
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS), f"resampled from {w}x{h}"


def sizes_sheet(cid: str, items: list[tuple[str, "Image.Image"]], sizes: list[int], bgs: list[str], zoom: int,
                font) -> "Image.Image":
    rows = []
    for label, img in items:
        contexts = [(BACKGROUNDS[n][0], BACKGROUNDS[n][1]) for n in bgs] if has_alpha(img) else [("opaque", None)]
        for ctx, colour in contexts:
            row = []
            for size in sizes:
                small, how = resize_to(img.convert("RGBA"), size)
                flat = small.convert("RGB") if colour is None else flatten(small, colour)
                for mode in MODES:
                    tile = apply_mode(flat, mode)
                    z = zoom if max(tile.size) <= SMALL else 1
                    if z > 1:
                        tile = tile.resize((tile.width * z, tile.height * z), Image.NEAREST)
                    row.append((tile, f"{size} px | {how} | {mode}" + (f" | x{z}" if z > 1 else "")))
            rows.append((f"{label} | {ctx}", row))
    return compose_grid(f"{cid} | working sizes {', '.join(map(str, sizes))} px | x{zoom} nearest for <= {SMALL} px",
                        rows, font)


# ---------------------------------------------------------------- readme

README_TEMPLATE = """# {cid} — лист приёмки

Лист собран `tools/art/visual/sheet.py` {date} по 02-visual-design.md §13.2. Поля ниже заполняет Claude после
ревью (один проход, 07 §5).

**Решение:** —  <!-- «художественно принято, по делегированию» или «не принято»; слово «лично» — только с цитатой пользователя и датой -->
**Дата решения:** —
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3)
**Флаг отката:** —  <!-- -S08…Legacy / -S08SlateHud, вписан в S08ArtLook.h и трассу ARTLOOK -->

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры (значки 1024 и 24/32/48 ×4 nearest; скины ×1, ×2; карты — показы §6.2) | {sizes_file} | {sizes_have} |
| 2 | Цвет, серый Rec.709, дейтеранопия — для каждого размера | {sheet_files} | да |
| 3 | Кадр на обеих настоящих досках: Marmoreal original и Sarpedon original, K1 и K2, packaged `-Bench` с отпечатком `RENDER`; для HUD ещё 1280×720 и 150 % | — | — |
| 4 | Контекст: на `panel.bg`, на `card.cream`, на поле | {ctx_files} | {ctx_have} |
| 5 | Движение: лист кадров по времени, обычный / reduced | — | — |
| 6 | Трассы: `ARTLOOK`, `SHOT widget` (HUD), `CUE fx` (VFX), `concept-paste` (окружение) | — | — |
| 7 | README: что проверено, замеры, что не прошло, флаг отката | этот файл | — |

## Входы

| файл | размер | sha256 |
|---|---|---|
{inputs_table}

## Замеры

- Контраст (текст ≥ 4,5 : 1, значки и кромки ≥ 3 : 1): —
- ΔE76 к токенам 02 §2: —
- ΔGPU (02 §9.4, `render_bench.py`): —

## Проверка глазами (G-LOOK, AGENTS.md «Look before you report»)

- Каждый PNG листа и кадра открыт (Read): —
- Доска — Marmoreal original или Sarpedon original: —
- Задник верный для карты (Marmoreal — нарисованный, Sarpedon — lit3d): —
- Все шесть фигур — v2: —
- Различимо в сером и при дейтеранопии (G-GRAY): —

## Что не прошло

—
"""


def write_readme(out: Path, cid: str, date: str, inputs: list[dict], sheet_files: list[str], sizes_file: str | None,
                 ctx_files: list[str]) -> bool:
    path = out / "README.md"
    if path.exists():
        return False
    table = "\n".join(f"| `{i['path']}` | {i['size'][0]}×{i['size'][1]} | {i['sha256']} |" for i in inputs)
    path.write_text(README_TEMPLATE.format(
        cid=cid, date=date, sizes_file=f"`{sizes_file}`" if sizes_file else "—",
        sizes_have="да" if sizes_file else "—", sheet_files=", ".join(f"`{f}`" for f in sheet_files),
        ctx_files=", ".join(f"`{f}`" for f in ctx_files) or "—",
        ctx_have="да" if ctx_files else "— (входы непрозрачные)", inputs_table=table), encoding="utf-8", newline="\n")
    return True


# ---------------------------------------------------------------- main

def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "input"


def build(root: Path, cid: str, inputs: list[Path], out: Path | None = None, sizes: list[int] | None = None,
          zoom: int = 4, max_tile: int = 960, backgrounds: list[str] | None = None,
          date: str | None = None) -> dict:
    _require_libs()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", cid):
        raise VisualError(f"bad unit id {cid!r}")
    if not inputs:
        raise VisualError("no --inputs given")
    bgs = backgrounds or list(BACKGROUNDS)
    unknown = [b for b in bgs if b not in BACKGROUNDS]
    if unknown:
        raise VisualError(f"unknown background(s) {', '.join(unknown)}; known: {', '.join(BACKGROUNDS)}")
    if zoom < 1 or max_tile < 16:
        raise VisualError("--zoom must be >= 1 and --max-tile >= 16")
    out = Path(out) if out else root / EVIDENCE_REL / cid
    date = date or dt.date.today().isoformat()
    font = _font(14)
    loaded = []
    for p in inputs:
        p = Path(p)
        if not p.is_file():
            raise VisualError(f"input not found: {p.as_posix()}")
        try:
            img = Image.open(p)
            img.load()
        except OSError as e:
            raise VisualError(f"cannot read image {p.as_posix()}: {e}") from e
        loaded.append((p, img.convert("RGBA") if has_alpha(img) else img.convert("RGB")))
    out.mkdir(parents=True, exist_ok=True)
    manifest_inputs, outputs, sheet_files = [], [], []
    for n, (p, img) in enumerate(loaded, 1):
        digest = sha256_file(p)
        rel = rel_or_abs(root, p)
        manifest_inputs.append({"path": rel, "sha256": digest, "size": list(img.size), "alpha": img.mode == "RGBA"})
        name = f"sheet-{n:02d}-{_safe(p.stem)}.png"
        input_sheet(cid, rel, img, bgs, max_tile, zoom, font, digest).save(out / name, optimize=True)
        sheet_files.append(name)
    sizes_file = None
    if sizes:
        sizes_file = "sheet-sizes.png"
        sizes_sheet(cid, [(Path(p).stem, img) for p, img in loaded], sizes, bgs, zoom, font).save(
            out / sizes_file, optimize=True)
    for name in sheet_files + ([sizes_file] if sizes_file else []):
        with Image.open(out / name) as im:
            outputs.append({"file": name, "sha256": sha256_file(out / name), "size": list(im.size)})
    manifest = {
        "schema": "unmatched.visual-sheet/1",
        "id": cid,
        "date": date,
        "generator": "tools/art/visual/sheet.py",
        "spec": "docs/game-design/visual/02-visual-design.md 13.2",
        "settings": {
            "sizes": sizes or [], "zoom": zoom, "max_tile": max_tile, "small_px": SMALL,
            "backgrounds": {b: BACKGROUNDS[b][0] for b in bgs},
            "gray": "Rec.709 luma Y' = 0.2126 R' + 0.7152 G' + 0.0722 B' on sRGB-encoded values",
            "deuteranopia": "Machado, Oliveira, Fernandes 2009, severity 1.0, linear RGB",
        },
        "inputs": manifest_inputs,
        "outputs": outputs,
    }
    (out / "sheet-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")
    ctx_files = [f for f, i in zip(sheet_files, manifest_inputs) if i["alpha"]]
    readme = write_readme(out, cid, date, manifest_inputs, sheet_files, sizes_file, ctx_files)
    manifest["readme_written"] = readme
    manifest["out"] = rel_or_abs(root, out)
    return manifest


def _sizes(s: str | None) -> list[int]:
    if not s:
        return []
    try:
        vals = [int(x) for x in re.split(r"[,\s]+", s.strip()) if x]
    except ValueError as e:
        raise VisualError(f"--sizes must be integers, got {s!r}") from e
    if any(v < 4 or v > 4096 for v in vals):
        raise VisualError("--sizes values must be within 4..4096 px")
    return vals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("unit_id", help="card or registry id, e.g. HB-02")
    ap.add_argument("--inputs", nargs="+", type=Path, required=True, help="masters, working-size exports, UE frames")
    ap.add_argument("--out", type=Path, help=f"output folder (default {EVIDENCE_REL}/<id>/)")
    ap.add_argument("--sizes", help="display sizes in px (longest side), e.g. 24,32,48")
    ap.add_argument("--zoom", type=int, default=4, help=f"nearest zoom for images <= {SMALL} px (default 4)")
    ap.add_argument("--max-tile", type=int, default=960, help="longest side of a tile on the sheet (default 960)")
    ap.add_argument("--backgrounds", default=",".join(BACKGROUNDS),
                    help="context backgrounds for transparent inputs: " + ", ".join(BACKGROUNDS))
    ap.add_argument("--date", help="ISO date (default today)")
    ap.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    utf8_console()
    root = (a.root or repo_root()).resolve()
    try:
        m = build(root, a.unit_id, a.inputs, a.out, _sizes(a.sizes), a.zoom, a.max_tile,
                  [b.strip() for b in a.backgrounds.split(",") if b.strip()], a.date)
    except VisualError as e:
        print(f"sheet: ERROR: {e}", file=sys.stderr)
        return 2
    for o in m["outputs"]:
        print(f"{m['out']}/{o['file']}  {o['size'][0]}x{o['size'][1]}")
    print(f"{m['out']}/sheet-manifest.json")
    print(f"{m['out']}/README.md" + ("  (template written)" if m["readme_written"] else "  (kept, not overwritten)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
