"""Preview sheets (plain Python + Pillow): side-by-side frames for the report, JPEG q92 (PIPELINE.md frame format).

  compare-{front,side,back}.jpg   concept H2 | Tripo high-poly | H2 game model | previous candidate (ortho, blender)
  closeups-hp-vs-h2.jpg           close-ups, high-poly (left) vs game model (right) per pair
  compare-k2-5x.jpg, compare-k2-1p6.jpg   game camera K2: previous candidate | H2 (crop around the figure, 1:1 px;
                                  the 1.6x crop is also shown x3 nearest-neighbour)
  deform-*-sheet.jpg              rig_deform_probe sheets (copied from the probe output)
  probe-culled-closeups.jpg       seams stage: rest | probe pose close-ups of every contact, FBX read-back, runtime 2K BC,
                                  Workbench with BACKFACE CULLING over magenta (magenta inside the figure = see-through)
  probe-culled-k2.jpg             the same at the game camera K2 5x (1:1 crop), rest and the probe poses
H2.1 (profile preview.baseline: the preview stage rendered the H2 textures before the material pass as set BASE):
  compare-h21-{front,side,back}.jpg   concept | H2 (before) | H2.1 (ortho, the same light and camera)
  compare-h21-k2-5x.jpg, compare-h21-k2-1p6.jpg   concept (front, for colour) | H2 | H2.1 at the game camera K2
  closeups-h2-vs-h21.jpg          close-ups H2 | H2.1 per pair
  pose-h2-vs-h21.jpg              probe-pose close-ups (preview.pose_closeups): H2 | H2.1 (Cycles) | AO H2 | AO H2.1
  channels-h2-vs-h21.jpg          ORM channel views (preview.channel_views, e.g. metallic): H2 | H2.1
Every tile carries its label; all Blender frames say "blender (Cycles), студийный свет — не игровой"."""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (40, 42, 46)


def font(size):
    for f in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def flat(path):
    im = Image.open(path)
    if im.mode == "RGBA":
        bg = Image.new("RGBA", im.size, BG + (255,))
        bg.alpha_composite(im)
        im = bg
    return im.convert("RGB")


def flat_on(path, colour):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, colour + (255,))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def label(im, text, size=26):
    d = ImageDraw.Draw(im)
    f = font(size)
    d.rectangle([0, 0, im.width, size + 16], fill=(0, 0, 0))
    d.text((10, 6), text, fill=(255, 255, 255), font=f)
    return im


def row(tiles, height):
    scaled = [t.resize((max(1, round(t.width * height / t.height)), height), Image.LANCZOS) for t in tiles]
    out = Image.new("RGB", (sum(t.width for t in scaled), height), BG)
    x = 0
    for t in scaled:
        out.paste(t, (x, 0))
        x += t.width
    return out


def save_jpeg(im, path, max_w=2400):
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(path, format="JPEG", quality=92, optimize=False, progressive=False, subsampling=0)
    d = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return {"sha256": d, "bytes": Path(path).stat().st_size, "px": [im.width, im.height]}


def h21_sheets(raw, out, repo, profile, tag):
    """concept | H2 (baseline textures) | H2.1 (current textures): the same game model, light and cameras."""
    written = {}
    concepts = profile["preview"]["concepts"]
    base_label = "H2: PBR Tripo (metallic золота ≈ 0,09)"
    new_label = "H2.1: маска металла, AO без кулака"
    for view in ("front", "side", "back"):
        tiles = [label(Image.open(repo / concepts[view]).convert("RGB"), "концепт H2 (imagegen): %s" % view),
                 label(flat(raw / ("ortho-%s-base.png" % view)), "%s — %s" % (base_label, tag), 18),
                 label(flat(raw / ("ortho-%s-h2.png" % view)), "%s — %s" % (new_label, tag), 18)]
        name = "compare-h21-%s.jpg" % view
        written[name] = save_jpeg(row(tiles, 1100), out / name, max_w=3000)
    for key, crop_px, zoom in (("k2-5x", 640, 1), ("k2-1p6", 220, 3)):
        tiles = []
        for t, name in (("base", "H2"), ("h2", "H2.1")):
            im = flat(raw / ("%s-%s.png" % (key, t)))
            cx, cy = im.width // 2, im.height // 2
            c = im.crop((cx - crop_px // 2, cy - crop_px // 2, cx + crop_px // 2, cy + crop_px // 2))
            if zoom > 1:
                c = c.resize((c.width * zoom, c.height * zoom), Image.NEAREST)
            tiles.append(label(c, "%s: %s 1920x1080, FOV 35, −55°, 1:1 px%s" % (name, key.upper(), "" if zoom == 1 else ", ×%d" % zoom), 18))
        concept = Image.open(repo / concepts["front"]).convert("RGB")
        concept = concept.resize((round(concept.width * tiles[0].height / concept.height), tiles[0].height), Image.LANCZOS)
        tiles.insert(0, label(concept, "концепт (front, для цвета; не ракурс K2)", 18))
        sheet = row(tiles, tiles[1].height)
        label(sheet, "игровая камера K2 (%s): концепт | H2 | H2.1 — %s" % (key, tag), 22)
        written["compare-h21-%s.jpg" % key] = save_jpeg(sheet, out / ("compare-h21-%s.jpg" % key), max_w=2400)
    pairs = []
    for c in profile["preview"]["closeups"]:
        a = label(flat(raw / ("closeup-%s-base.png" % c["name"])), "H2: %s" % c["name"], 22)
        b = label(flat(raw / ("closeup-%s-h2.png" % c["name"])), "H2.1: %s" % c["name"], 22)
        pairs.append(row([a, b], 600))
    grid = Image.new("RGB", (pairs[0].width * 2, 600 * ((len(pairs) + 1) // 2) + 50), BG)
    for i, pr in enumerate(pairs):
        grid.paste(pr, ((i % 2) * pairs[0].width, 50 + (i // 2) * 600))
    label(grid, "крупные планы H2 | H2.1, ортокамера — %s" % tag, 30)
    written["closeups-h2-vs-h21.jpg"] = save_jpeg(grid, out / "closeups-h2-vs-h21.jpg", max_w=2400)
    rows_ = []
    for c in profile["preview"].get("pose_closeups", []):
        stem = "pose-%s-%s" % (c["name"], c["pose"])
        tiles = [label(flat(raw / ("%s-base.png" % stem)), "H2: %s, %s" % (c["name"], c["pose"]), 20),
                 label(flat(raw / ("%s-h2.png" % stem)), "H2.1: %s, %s" % (c["name"], c["pose"]), 20),
                 label(flat(raw / ("%s-ao-base.png" % stem)), "AO (ORM.R) H2", 20),
                 label(flat(raw / ("%s-ao-h2.png" % stem)), "AO (ORM.R) H2.1", 20)]
        rows_.append(row(tiles, 600))
    if rows_:
        sheet = Image.new("RGB", (max(r.width for r in rows_), 600 * len(rows_) + 50), BG)
        for i, r in enumerate(rows_):
            sheet.paste(r, (0, 50 + 600 * i))
        label(sheet, "поза пробы (кулак поднят): Cycles H2 | H2.1 и AO-канал ORM (эмиссия, Standard) — %s" % tag, 26)
        written["pose-h2-vs-h21.jpg"] = save_jpeg(sheet, out / "pose-h2-vs-h21.jpg", max_w=2400)
    tiles = []
    for cv in profile["preview"].get("channel_views", []):
        for t, name in (("base", "H2"), ("h2", "H2.1")):
            tiles.append(label(flat(raw / ("channel-%s-%s-%s.png" % (cv["name"], cv["view"], t))),
                               "%s: ORM.%s (%s), %s" % (name, cv["channel"][0], cv["name"], cv["view"]), 20))
    if tiles:
        sheet = row(tiles, 1100)
        label(sheet, "каналы ORM (эмиссия, Standard; белое = 1): H2 | H2.1", 26)
        written["channels-h2-vs-h21.jpg"] = save_jpeg(sheet, out / "channels-h2-vs-h21.jpg", max_w=3000)
    return written


def run(run_dir, profile, repo):
    run_dir, repo = Path(run_dir), Path(repo)
    raw = run_dir / "work" / "preview_raw"
    out = run_dir / "preview"
    out.mkdir(parents=True, exist_ok=True)
    tag = "blender (Cycles), студийный свет — не игровой"
    if profile["preview"].get("backface_culling"):
        tag += "; H2/прежний: задние грани отсечены"
    written = {}
    rig = json.loads((run_dir / "reports" / "rig-report.json").read_text(encoding="utf-8"))
    tris = sum(v["triangles"] for k, v in rig["meshes_pre_export"].items() if k != profile["meshes"]["base"])
    prev_run = repo / profile["preview"]["previous_candidate"]["run"]
    prev_tris = "?"
    prev_build = prev_run / "reports" / "build-report.json"
    if prev_build.exists():
        pb = json.loads(prev_build.read_text(encoding="utf-8"))
        prev_tris = "%.1fk" % (sum(v["triangles"] for k, v in pb.get("meshes_pre_export_m", {}).items() if "Base" not in k) / 1000.0)
    h21 = bool(profile["textures"].get("materials"))
    h2_label = "%s игровая модель (%.1fk tris, атлас 4K)" % ("H2.1" if h21 else "H2", tris / 1000.0)
    prev_label = "прежний кандидат W4-B (%s tris, 2K)" % prev_tris
    concepts = profile["preview"]["concepts"]
    for view, cview in (("front", "front"), ("side", "side"), ("back", "back")):
        tiles = [label(Image.open(repo / concepts[cview]).convert("RGB"), "концепт H2 (imagegen): %s" % cview),
                 label(flat(raw / ("ortho-%s-hp.png" % view)), "high-poly Tripo 40c4d1cd (1,86M tris, 8K/PBR) — %s" % tag, 18),
                 label(flat(raw / ("ortho-%s-h2.png" % view)), "%s — %s" % (h2_label, tag), 18),
                 label(flat(raw / ("ortho-%s-prev.png" % view)), "%s — %s" % (prev_label, tag), 18)]
        name = "compare-%s.jpg" % view
        written[name] = save_jpeg(row(tiles, 1100), out / name, max_w=3000)
    pairs = []
    for c in profile["preview"]["closeups"]:
        a = label(flat(raw / ("closeup-%s-hp.png" % c["name"])), "high-poly: %s" % c["name"], 22)
        b = label(flat(raw / ("closeup-%s-h2.png" % c["name"])), "H2 игровая: %s" % c["name"], 22)
        pairs.append(row([a, b], 600))
    grid_w = pairs[0].width * 2
    grid = Image.new("RGB", (grid_w, 600 * ((len(pairs) + 1) // 2) + 50), BG)
    for i, p in enumerate(pairs):
        grid.paste(p, ((i % 2) * pairs[0].width, 50 + (i // 2) * 600))
    label(grid, "крупные планы, ортокамера — %s" % tag, 30)
    written["closeups-hp-vs-h2.jpg"] = save_jpeg(grid, out / "closeups-hp-vs-h2.jpg", max_w=2400)
    for key, crop_px, zoom in (("k2-5x", 640, 1), ("k2-1p6", 220, 3)):
        tiles = []
        for t, name in (("prev", "прежний кандидат W4-B"), ("h2", "H2 игровая модель")):
            im = flat(raw / ("%s-%s.png" % (key, t)))
            cx, cy = im.width // 2, im.height // 2
            c = im.crop((cx - crop_px // 2, cy - crop_px // 2, cx + crop_px // 2, cy + crop_px // 2))
            if zoom > 1:
                c = c.resize((c.width * zoom, c.height * zoom), Image.NEAREST)
            tiles.append(label(c, "%s: %s 1920x1080, FOV 35, −55°, 1:1 px%s" % (name, key.upper(), "" if zoom == 1 else ", ×%d" % zoom), 18))
        sheet = row(tiles, tiles[0].height)
        label(sheet, "игровая камера K2 (%s) — %s" % (key, tag), 22)
        written["compare-%s.jpg" % key] = save_jpeg(sheet, out / ("compare-%s.jpg" % key), max_w=2400)
        full = row([label(flat(raw / ("%s-%s.png" % (key, t))), "%s %s — %s" % (key, t, tag), 22) for t in ("prev", "h2")], 1080)
        written["frame-%s.jpg" % key] = save_jpeg(full, out / ("frame-%s.jpg" % key), max_w=2400)
    for sheet in sorted((run_dir / "work" / "deform").glob("*-sheet.png")):
        name = "deform-%s.jpg" % sheet.stem.replace("-sheet", "")
        written[name] = save_jpeg(Image.open(sheet).convert("RGB"), out / name, max_w=2400)
    seams_raw = run_dir / "work" / "seams_raw"
    scfg = profile.get("seams", {})
    if seams_raw.exists() and scfg.get("frames"):
        magenta = (255, 0, 255)
        stag = scfg.get("frames_label", "blender Workbench, backface culling")
        pairs = []
        for f in scfg["frames"]:
            a = label(flat_on(seams_raw / ("%s-rest-view.png" % f["name"]), magenta), "%s: покой" % f["name"], 20)
            b = label(flat_on(seams_raw / ("%s-%s-view.png" % (f["name"], f["pose"])), magenta),
                      "%s: %s" % (f["name"], f["pose"]), 20)
            pairs.append(row([a, b], 520))
        grid = Image.new("RGB", (pairs[0].width * 2, 520 * ((len(pairs) + 1) // 2) + 50), BG)
        for i, pr in enumerate(pairs):
            grid.paste(pr, ((i % 2) * pairs[0].width, 50 + (i // 2) * 520))
        label(grid, "пробы деформации, контакты: %s" % stag, 26)
        written["probe-culled-closeups.jpg"] = save_jpeg(grid, out / "probe-culled-closeups.jpg", max_w=2400)
        k2s = sorted(seams_raw.glob("k2-*.png"))
        if k2s:
            order = ["rest"] + list(scfg.get("k2_frames", []))
            tiles = []
            for pname in order:
                im = flat_on(seams_raw / ("k2-%s.png" % pname), magenta)
                cx, cy = im.width // 2, im.height // 2
                c = im.crop((cx - 240, cy - 240, cx + 240, cy + 240))
                tiles.append(label(c, "K2 5×: %s" % ("покой" if pname == "rest" else pname), 18))
            per_row = 4
            rows_ = [row(tiles[i:i + per_row], 480) for i in range(0, len(tiles), per_row)]
            sheet = Image.new("RGB", (max(r.width for r in rows_), 480 * len(rows_) + 44), BG)
            for i, r in enumerate(rows_):
                sheet.paste(r, (0, 44 + 480 * i))
            label(sheet, "K2 5× (FOV 35, −55°, 1:1 px, кроп 480): %s" % stag, 22)
            written["probe-culled-k2.jpg"] = save_jpeg(sheet, out / "probe-culled-k2.jpg", max_w=2400)
    if profile["preview"].get("baseline") and (raw / "ortho-front-base.png").exists():
        written.update(h21_sheets(raw, out, repo, profile, tag))
    layout = run_dir / "work" / "uv" / "uv-layout-1024.png"
    if layout.exists():
        written["uv-layout-1024.png"] = {"note": "written by the uv stage"}
    (run_dir / "reports" / "compose-report.json").write_text(
        json.dumps({"stage": "compose", "outputs": written, "label": tag}, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return written
