"""DE-028 (W-28): the A/B sheet for the user from packaged -Bench frames and the packaged icon gallery.

Input - the frames of tools/art/render/live_tune.py bench --packaged runs, one folder per variant:
  <frames>/<map>/<variant>/bench-<View>-1920x1080.png + bench.trace.log + cmdline.txt + exit.txt
and the packaged gallery shots <gallery>/icon-gallery-normal-<t>.png (-S08IconGallery -S08IconGalleryShots).

Output (<out>): the overview 00-ab-sheet.jpg, the detail sheets 01..04, a JPG of every source frame, the trace lines
that prove each frame (RENDER / ARTLOOK / concept paste / bench pose / dissolve / turn hud), the command lines and
summary.json (pixel differences against the default of each question). The README is written by hand.

  python tools/s08/de028_ab_sheet.py --frames C:/tmp/de028/frames --gallery C:/tmp/de028/gallery \
      --out docs/game-design/evidence/DE-FOOTAGE/2026-10-04/AB-SHEET
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

MAPS = {"marmoreal": "Marmoreal original", "sarpedon": "Sarpedon original"}
MOVE = [("move-default", "по умолчанию: подскок 0, наклон 10°, без ease"),
        ("move-hop008", "подскок 0,08 (-S08MoveHop=0.08)"),
        ("move-lean0", "без наклона (-S08MoveLean=0)"),
        ("move-ease", "ease концов пути (-S08MoveEase)")]
DISSOLVE = [("dissolve-fade35", "fade 35 % (по умолчанию)"), ("dissolve-fade70", "fade 70 % (по умолчанию)"),
            ("dissolve-ash35", "«пепел» 35 % (-S08DissolveAsh)"), ("dissolve-ash70", "«пепел» 70 % (-S08DissolveAsh)")]
HUD = [("hud-none-t400", "по умолчанию: кольца нет, 400 мс"),
       ("hud-warm-t400", "кольцо тёплое, вспышка, 400 мс"),
       ("hud-team-t400", "кольцо цвета команды, вспышка, 400 мс"),
       ("hud-warm-glow-t400", "тёплое + ореол сердца (-S08HeartGlow), 400 мс"),
       ("hud-warm-t1500", "кольцо тёплое, тлеющий обод, 1500 мс"),
       ("hud-team-t1500", "кольцо цвета команды, тлеющий обод, 1500 мс")]
# short captions of the overview cells (the detail sheets carry the full ones)
SHORT = {"move-default": "умолч.: 0 / 10°", "move-hop008": "подскок 0,08", "move-lean0": "наклон 0°",
         "move-ease": "ease вкл", "dissolve-fade35": "fade 35 %", "dissolve-fade70": "fade 70 %",
         "dissolve-ash35": "пепел 35 %", "dissolve-ash70": "пепел 70 %", "hud-none-t400": "умолч.: нет",
         "hud-warm-glow-t400": "тёплое+ореол 400", "hud-warm-t1500": "тёплое 1500", "hud-team-t1500": "команда 1500"}
PROOF = re.compile(r"(RENDER|ARTLOOK|concept-paste status|concept-scene|bench-pose|dissolve bench|BENCH turn-hud|"
                   r"HUD-TURN config|BENCH scene|heroesV2 summary|MS-ANIM settings)")
# packaged icon gallery (-S08IconGallerySize=64, 1920x1080): 6 columns from x 426 (pitch 180, cell 168 x 130),
# rows from y 191 (pitch 142); the order is the contract's `order` (DE-012 evidence frame icon-gallery-normal-00600)
GALLERY_CELLS = {"resource-action-full": (3, 2), "resource-hp-full": (3, 3), "marker-turn-ring": (5, 3),
                 "marker-turn-ring-team": (0, 4), "resource-hp-fallen": (1, 4), "marker-x-stamp": (2, 4),
                 "marker-action-slot-de": (3, 4), "action-attack": (2, 1)}

BG = (22, 24, 32)
FG = (235, 235, 240)
ACCENT = (242, 193, 78)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def frame(frames: Path, map_key: str, variant: str, view: str) -> Path:
    return frames / map_key / variant / f"bench-{view}-1920x1080.png"


def trace(frames: Path, map_key: str, variant: str) -> list[str]:
    p = frames / map_key / variant / "bench.trace.log"
    return p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []


def head_of(lines: list[str], fighter: str, nth: int) -> tuple[float, float] | None:
    """Screen position of the fighter's Head socket in the nth SHOT (0 = the first view of the run)."""
    hits = [ln for ln in lines if f"SHOT head fighter={fighter} " in ln]
    if len(hits) <= nth:
        return None
    m = re.search(r"screen=\((-?[\d.]+),(-?[\d.]+)\)", hits[nth])
    return (float(m.group(1)), float(m.group(2))) if m else None


def bench_hero(lines: list[str]) -> str:
    for ln in lines:
        m = re.search(r"bench-pose hero=(\S+)", ln)
        if m:
            return m.group(1)
    for ln in lines:
        m = re.search(r"BENCH scene .* hero=(\S+)", ln)
        if m:
            return m.group(1)
    return ""


def hero_name(lines: list[str], fighter: str) -> str:
    """'King Arthur' from the SHOT head mesh of the fighter (SK_KingArthur_H2LD), else the fighter id."""
    for ln in lines:
        m = re.search(rf"SHOT head fighter={re.escape(fighter)} .*mesh=SK_([A-Za-z]+)_", ln)
        if m:
            return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", m.group(1))
    return fighter


def crop_around(img: Image.Image, cx: float, cy: float, w: int, h: int) -> Image.Image:
    x0 = int(round(min(max(cx - w / 2, 0), img.width - w)))
    y0 = int(round(min(max(cy - h / 2, 0), img.height - h)))
    return img.crop((x0, y0, x0 + w, y0 + h))


def diff(a: Path, b: Path) -> dict:
    x = np.asarray(Image.open(a).convert("RGB")).astype(np.int16)
    y = np.asarray(Image.open(b).convert("RGB")).astype(np.int16)
    d = np.abs(x - y).max(axis=2)
    px = d > 24
    out = {"pxOver24": int(px.sum()), "meanAbs": round(float(np.abs(x - y).mean()), 3)}
    if px.any():
        ys, xs = np.nonzero(px)
        out["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return out


def grid(cells: list[tuple[Image.Image, str]], cols: int, title: str, note: str = "") -> Image.Image:
    cw = max(c[0].width for c in cells)
    ch = max(c[0].height for c in cells)
    lab = 34
    head = 64 if not note else 92
    rows = (len(cells) + cols - 1) // cols
    pad = 8
    sheet = Image.new("RGB", (cols * (cw + pad) + pad, head + rows * (ch + lab + pad) + pad), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad + 4, 12), title, font=font(30, True), fill=FG)
    if note:
        d.text((pad + 4, 54), note, font=font(20), fill=(170, 175, 190))
    for i, (img, label) in enumerate(cells):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = head + r * (ch + lab + pad)
        d.text((x + 4, y + 4), label, font=font(22, True), fill=ACCENT)
        sheet.paste(img, (x, y + lab))
    return sheet


def save_jpg(img: Image.Image, path: Path, quality: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=quality, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--gallery", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    frames, gallery, out = Path(a.frames), Path(a.gallery), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"maps": {}, "gallery": {}}
    overview_rows: list[tuple[str, list[tuple[Image.Image, str]]]] = []
    ov_move: list[tuple[Image.Image, str]] = []
    ov_dis: list[tuple[Image.Image, str]] = []
    ov_hud: list[tuple[Image.Image, str]] = []

    for map_key, map_name in MAPS.items():
        ms: dict = {"variants": {}}
        summary["maps"][map_key] = ms
        # every source frame as JPG + its proof lines + command line
        for variant_dir in sorted((frames / map_key).iterdir()) if (frames / map_key).exists() else []:
            v = variant_dir.name
            lines = trace(frames, map_key, v)
            info = {"exit": (variant_dir / "exit.txt").read_text().strip() if (variant_dir / "exit.txt").exists() else "?",
                    "frames": []}
            for png in sorted(variant_dir.glob("bench-*-1920x1080.png")):
                view = png.name.split("-")[1]
                if v.startswith("move-") and view != "K2x2p5":
                    continue  # the move sheet crops K2x2.5; K2x1.6 stays with the source PNGs
                name = f"{map_key}-{v}-{view}.jpg"
                # the repo copy is 1280x720 (the sheets crop the 1920x1080 source PNGs, kept outside git)
                save_jpg(Image.open(png).convert("RGB").resize((1280, 720), Image.LANCZOS), out / "frames" / name, 84)
                info["frames"].append(name)
            proof = [ln for ln in lines if PROOF.search(ln)]
            (out / "frames" / f"{map_key}-{v}.trace.txt").write_text("\n".join(proof) + "\n", encoding="utf-8")
            if (variant_dir / "cmdline.txt").exists():
                (out / "frames" / f"{map_key}-{v}.cmdline.txt").write_text(
                    (variant_dir / "cmdline.txt").read_text(encoding="utf-8"), encoding="utf-8")
            info["renderReference"] = sorted({m.group(1) for ln in lines for m in [re.search(r"reference=(\d)", ln)]
                                              if m and "RENDER" in ln})
            info["artlook"] = next((ln.split(" ", 2)[2] for ln in lines if " ARTLOOK " in ln), "")
            ms["variants"][v] = info

        # 01 move: K2x2.5 crop around the posed hero, x2
        cells = []
        base_lines = trace(frames, map_key, "move-default")
        hero = bench_hero(base_lines)
        h = head_of(base_lines, hero, 1) if hero else None
        for v, label in MOVE:
            p = frame(frames, map_key, v, "K2x2p5")
            if not p.exists() or not h:
                continue
            c = crop_around(Image.open(p).convert("RGB"), h[0], h[1] + 70, 460, 345).resize((920, 690), Image.LANCZOS)
            if v != "move-default":
                ms.setdefault("diff", {})[v] = diff(frame(frames, map_key, "move-default", "K2x2p5"), p)
            cells.append((c, label))
            ov_move.append((c.resize((480, 360), Image.LANCZOS), f"{map_key[:4]} · {SHORT[v]}"))
        if cells:
            save_jpg(grid(cells, 2, f"Ход: подскок, наклон, ease — {map_name}",
                          f"packaged -Bench, K2x2.5, вырез вокруг {hero_name(base_lines, hero)} ×2, -BenchMovePose=420 (середина 2-го ребра)"),
                     out / f"01-move-{map_key}.jpg")

        # 02 dissolve: K2x1.6 around the viewer's hero
        cells = []
        dl = trace(frames, map_key, "dissolve-fade35")
        hero = bench_hero(dl)
        h = head_of(dl, hero, 1) if hero else None
        for v, label in DISSOLVE:
            p = frame(frames, map_key, v, "K2x1p6")
            if not p.exists() or not h:
                continue
            c = crop_around(Image.open(p).convert("RGB"), h[0], h[1] + 40, 880, 495).resize((960, 540), Image.LANCZOS)
            cells.append((c, label))
            ov_dis.append((c.resize((480, 270), Image.LANCZOS), f"{map_key[:4]} · {SHORT[v]}"))
        if cells:
            save_jpg(grid(cells, 2, f"Растворение при смерти — {map_name}",
                          f"packaged -Bench -BenchDissolve=<p>, K2x1.6 вокруг {hero_name(dl, hero)}; все 6 фигур заморожены на прогрессе p"),
                     out / f"02-dissolve-{map_key}.jpg")

        # 03 turn HUD: the bottom-left corner of K1, x2
        cells = []
        for v, label in HUD:
            p = frame(frames, map_key, v, "K1")
            if not p.exists():
                continue
            c = Image.open(p).convert("RGB").crop((0, 840, 320, 1080)).resize((640, 480), Image.LANCZOS)
            if v != "hud-none-t400":
                ms.setdefault("diff", {})[v] = diff(frame(frames, map_key, "hud-none-t400", "K1"), p)
            cells.append((c, label))
            if v in ("hud-none-t400", "hud-warm-t1500", "hud-team-t1500", "hud-warm-glow-t400"):
                ov_hud.append((c.resize((480, 360), Image.LANCZOS), f"{map_key[:4]} · {SHORT[v]}"))
        if cells:
            save_jpg(grid(cells, 3, f"Кольцо хода, трекер v3, сердце — {map_name}",
                          "packaged -Bench -BenchTurnHud=<мс>, K1, левый нижний угол ×2; часы портретов от начала моего хода"),
                     out / f"03-turnhud-{map_key}.jpg")

    # 04 icons: packaged gallery cells over time
    shots = sorted(gallery.glob("icon-gallery-normal-*.png"))
    if shots:
        rows = [("resource-action-full", "трекер v3 (по умолчанию): слот гаснет"),
                ("marker-action-slot-de", "трекер DE (кандидат): призрак → тип"),
                ("marker-turn-ring", "кольцо тёплое (кандидат)"),
                ("marker-turn-ring-team", "кольцо цвета команды (кандидат)"),
                ("resource-hp-full", "сердце damage (ореол виден с -S08HeartGlow)"),
                ("resource-hp-fallen", "сердце павшего (кандидат)"),
                ("marker-x-stamp", "крест-штамп (кандидат)")]
        times = [int(s.stem.rsplit("-", 1)[1]) for s in shots]
        imgs = [Image.open(s).convert("RGB") for s in shots]
        cw, ch, lw = 168 * 2, 130 * 2, 600
        sheet = Image.new("RGB", (lw + len(imgs) * (cw + 6) + 8, 96 + len(rows) * (ch + 6)), BG)
        d = ImageDraw.Draw(sheet)
        d.text((12, 12), "Значки: трекер v3 / DE, кольцо, сердце, штампы — упакованная галерея 64 px, ×2",
               font=font(30, True), fill=FG)
        for j, t in enumerate(times):
            d.text((lw + j * (cw + 6) + 8, 60), f"t = {t} мс", font=font(22, True), fill=ACCENT)
        for i, (icon, label) in enumerate(rows):
            col, row = GALLERY_CELLS[icon]
            y = 96 + i * (ch + 6)
            d.text((12, y + ch // 2 - 30), label, font=font(22, True), fill=FG)
            d.text((12, y + ch // 2 + 2), icon, font=font(18), fill=(170, 175, 190))
            for j, im in enumerate(imgs):
                x0, y0 = 426 + 180 * col, 191 + 142 * row
                cell = im.crop((x0, y0, x0 + 168, y0 + 130)).resize((cw, ch), Image.NEAREST)
                sheet.paste(cell, (lw + j * (cw + 6) + 8, y))
        save_jpg(sheet, out / "04-icons-gallery.jpg")
        for s, im in zip(shots, imgs):
            save_jpg(im, out / "frames" / f"gallery-{s.stem}.jpg", 92)
        summary["gallery"] = {"times": times, "cells": GALLERY_CELLS}
        by_t = dict(zip(times, imgs))

        def cell(icon: str, t: int) -> Image.Image:
            col, row = GALLERY_CELLS[icon]
            x0, y0 = 426 + 180 * col, 191 + 142 * row
            im = by_t.get(t, imgs[-1])
            return im.crop((x0, y0, x0 + 168, y0 + 130)).resize((336, 260), Image.NEAREST)

        overview_rows.append(("Трекер v3 / DE (галерея, 64 px ×2)", [
            (cell("resource-action-full", 600), "v3: слот есть"), (cell("resource-action-full", 1000), "v3: потрачен"),
            (cell("marker-action-slot-de", 600), "DE: призрак"), (cell("marker-action-slot-de", 2000), "DE: заполнен типом")]))

    # 00 overview: one page, both maps
    parts = []
    if ov_move:
        parts.append(grid(ov_move, 4, "1. Ход: подскок / наклон / ease", "слева направо: по умолчанию, подскок 0,08, наклон 0°, ease; ряды — Marmoreal, Sarpedon"))
    if ov_dis:
        parts.append(grid(ov_dis, 4, "2. Растворение: fade (по умолчанию) / «пепел»", "35 % и 70 %; ряды — Marmoreal, Sarpedon"))
    if ov_hud:
        parts.append(grid(ov_hud, 4, "3. Кольцо хода и ореол сердца", "нет (по умолчанию) / тёплое + ореол 400 мс / тёплое 1500 мс / цвет команды 1500 мс"))
    for title, cells in overview_rows:
        parts.append(grid(cells, len(cells), f"4. {title}", "t = 600 / 1000 / 600 / 2000 мс; полная раскадровка — 04-icons-gallery.jpg"))
    if parts:
        w = max(p.width for p in parts)
        ov = Image.new("RGB", (w, sum(p.height for p in parts) + 70), BG)
        ImageDraw.Draw(ov).text((12, 14), "DE-028 · лист A/B · packaged, Marmoreal original + Sarpedon original · выбор — в README",
                                font=font(32, True), fill=ACCENT)
        y = 70
        for p in parts:
            ov.paste(p, (0, y))
            y += p.height
        save_jpg(ov, out / "00-ab-sheet.jpg", 88)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "maps": {k: sorted(v["variants"]) for k, v in summary["maps"].items()},
                      "gallery": len(shots)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
