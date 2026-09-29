"""Stage sheets (system python, Pillow): labelled JPEG frames and comparison sheets of the H2 bake review.

    python sheets.py <profile.json> <run_dir>

Every Blender render gets a burned-in label "blender · <what>" (Blender EEVEE/Workbench preview, not UE, not the game
light). Outputs in preview/:
  frames/*.jpg                     every review frame (q90), labelled; sha256 of the raw PNG kept in frames-storage.json
  compare_{front,side,back}.jpg    H2 concept (Codex imagegen) | H2 bake render, same aspect
  closeups.jpg                     face / fist + hilt / left hand / blade / torso / cloak / feet / base
  game_scale.jpg                   K1 and K2 crops 1:1 and x4 (nearest), H2 bake next to the previous candidate
  game_K2S05.jpg                   S05 K-2 camera: H2 bake vs previous candidate
  silhouettes.jpg                  K1/K2/K2S05 silhouettes: high-poly vs game mesh vs x0.5 (XOR in red)
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pure as P  # noqa: E402

FONT = "C:/Windows/Fonts/arial.ttf"


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def label(img, text, size=None, pos="top"):
    img = img.convert("RGB")
    size = size or max(14, img.width // 45)
    f = font(size)
    bar = size + 12
    out = Image.new("RGB", (img.width, img.height + bar), (18, 18, 20))
    out.paste(img, (0, bar if pos == "top" else 0))
    d = ImageDraw.Draw(out)
    d.text((8, 5 if pos == "top" else img.height + 5), text, fill=(235, 220, 120), font=f)
    return out


def save_jpg(img, path, q=90):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=q, optimize=False, subsampling=0)
    return {"file": P.rel(path), "sha256": P.sha256(path), "bytes": path.stat().st_size}


def hstack(imgs, gap=6, bg=(18, 18, 20)):
    h = max(i.height for i in imgs)
    w = sum(i.width for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGB", (w, h), bg)
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def vstack(imgs, gap=6, bg=(18, 18, 20)):
    w = max(i.width for i in imgs)
    h = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGB", (w, h), bg)
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def crop_to_content(img, pad=12, thr=20):
    a = np.asarray(img.convert("RGB")).astype(np.int32)
    bgc = a[2, 2]
    diff = np.abs(a - bgc).sum(axis=2) > thr
    ys, xs = np.nonzero(diff)
    if not len(ys):
        return img
    return img.crop((max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad, img.width),
                     min(ys.max() + pad, img.height)))


def main():
    profile = P.load_json(sys.argv[1])
    paths = P.run_paths(sys.argv[2])
    rev = P.load_json(paths["reports"] / "review-report.json")
    tris_k = "%.1fk" % (P.load_json(paths["reports"] / "rig-report.json")["geometry"]["triangles_total"] / 1000.0)
    raw = paths["work"] / "frames_png"
    out_dir = paths["preview"]
    frames_dir = out_dir / "frames"
    storage = {}
    what = {"ortho": "орто", "close": "крупный план", "game": "игровая камера",
            "teamdye": "TeamDye"}
    for name, fr in sorted(rev["frames"].items()):
        png = P.REPO / fr["png"]
        kind = name.split("_")[0]
        cam = ("FOV %s, %.2f m" % (fr["horizontal_fov_deg"], fr["distance_m"])) if fr["horizontal_fov_deg"] else "орто"
        txt = "blender · EEVEE · H2 bake (атлас 2K) · %s · %s · %s" % (what.get(kind, kind), name, cam)
        if "prev" in name:
            txt = txt.replace("H2 bake (атлас 2K)", "прежний кандидат CLI 2026-09-28")
        img = label(Image.open(png), txt)
        storage[name] = {"raw_png_sha256": P.sha256(png), "raw_png_bytes": png.stat().st_size} | save_jpg(img, frames_dir / (name + ".jpg"))
    concepts = profile["sources"]["concepts"]
    sheets = {}
    for view, fname in (("front", "ortho_front"), ("side", "ortho_left"), ("back", "ortho_back")):
        c = Image.open(P.repo_path(concepts[view])).convert("RGB")
        r = Image.open(raw / (fname + ".png")).convert("RGB").resize(c.size, Image.LANCZOS)
        sheet = hstack([label(c, "концепт H2 (Codex imagegen) · %s" % view, 22),
                        label(r, "blender · EEVEE · H2 bake %s tris, атлас 2K · %s" % (tris_k, fname), 22)])
        sheets["compare_" + view] = save_jpg(sheet, out_dir / ("compare_%s.jpg" % view))
    tiles = []
    for name in sorted(n for n in rev["frames"] if n.startswith("close_")):
        tiles.append(label(Image.open(raw / (name + ".png")).resize((450, 450), Image.LANCZOS), "blender · " + name[6:], 15))
    rows = [hstack(tiles[i:i + 5]) for i in range(0, len(tiles), 5)]
    sheets["closeups"] = save_jpg(vstack(rows), out_dir / "closeups.jpg")
    def pair_crop(cam, az, pad=10):
        a = Image.open(raw / ("game_%s_az%d.png" % (cam, az))).convert("RGB")
        b = Image.open(raw / ("game_%s_az%d_prev.png" % (cam, az))).convert("RGB")
        boxes = []
        for im in (a, b):
            arr = np.asarray(im).astype(np.int32)
            diff = np.abs(arr - arr[2, 2]).sum(axis=2) > 20
            ys, xs = np.nonzero(diff)
            boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
        box = (max(min(x[0] for x in boxes) - pad, 0), max(min(x[1] for x in boxes) - pad, 0),
               min(max(x[2] for x in boxes) + pad, a.width), min(max(x[3] for x in boxes) + pad, a.height))
        return a.crop(box), b.crop(box)

    rows = []
    for cam in ("K1", "K2"):
        cells = []
        for az in profile["review"]["game_azimuths"]:
            a, b = pair_crop(cam, az)
            k = 4 if cam == "K1" else 3
            big = hstack([a.resize((a.width * k, a.height * k), Image.NEAREST), b.resize((b.width * k, b.height * k), Image.NEAREST)])
            cells.append(label(vstack([hstack([a, b]), big]),
                               "blender · %s az %d · H2 | прежний CLI 09-28 · 1:1 и x%d (nearest)" % (cam, az, k), 13))
        rows.append(hstack(cells, gap=14))
    sheets["game_scale"] = save_jpg(vstack(rows, gap=14), out_dir / "game_scale.jpg")
    k2 = []
    for az in profile["review"]["game_azimuths"]:
        a, b = pair_crop("K2S05", az)
        k2.append(label(hstack([a, b]), "blender · K2 S05 (FOV 20, 3 m) az %d · H2 | прежний CLI 09-28" % az, 16))
    sheets["game_K2S05"] = save_jpg(vstack(k2, gap=10), out_dir / "game_K2S05.jpg")
    # back views at the game cameras: textured | TeamDye (lerp(BC, blue, TeamMask.R)), same crop
    back_rows = []
    for cam, az in profile["review"].get("game_back", []):
        a = raw / ("game_%s_az%d.png" % (cam, az))
        b = raw / ("teamdye_game_%s_az%d.png" % (cam, az))
        if not a.exists():
            continue
        ia = Image.open(a).convert("RGB")
        arr = np.asarray(ia).astype(np.int32)
        ys, xs = np.nonzero(np.abs(arr - arr[2, 2]).sum(axis=2) > 20)
        box = (max(xs.min() - 10, 0), max(ys.min() - 10, 0), min(xs.max() + 10, ia.width), min(ys.max() + 10, ia.height))
        cells = [label(ia.crop(box), "blender · %s az %d · H2 bake, атлас 2K" % (cam, az), 16)]
        if b.exists():
            cells.append(label(Image.open(b).convert("RGB").crop(box),
                               "blender · %s az %d · TeamDye lerp(BC, синий, TeamMask.R)" % (cam, az), 16))
        back_rows.append(hstack(cells, gap=10))
    for az in profile["review"].get("teamdye", {}).get("close_azimuths", []):
        name = "teamdye_close_%s_az%d" % (profile["review"]["teamdye"]["close_name"], az)
        plain = raw / ("close_%s_az%d.png" % (profile["review"]["teamdye"]["close_name"], az))
        if (raw / (name + ".png")).exists() and plain.exists():
            back_rows.append(hstack([label(Image.open(plain), "blender · %s · H2 bake, атлас 2K" % plain.stem, 16),
                                     label(Image.open(raw / (name + ".png")), "blender · %s · TeamDye" % name, 16)], gap=10))
    if back_rows:
        sheets["back_teamdye"] = save_jpg(vstack(back_rows, gap=10), out_dir / "back_teamdye.jpg")
    # silhouettes: XOR of high vs lod0 / lod1_half in red over the high silhouette in grey
    sil_dir = paths["work"] / "silhouettes_png"
    rows = []
    for key in sorted(rev["silhouettes"]):
        cam, az = key.split("_")
        hi = np.asarray(Image.open(sil_dir / ("sil_%s_%s_high.png" % (cam, az))).convert("L")) > 127
        cells = []
        for lab in ("lod0", "lod1_half"):
            lo = np.asarray(Image.open(sil_dir / ("sil_%s_%s_%s.png" % (cam, az, lab))).convert("L")) > 127
            rgb = np.zeros(hi.shape + (3,), dtype=np.uint8)
            rgb[hi] = (110, 110, 110)
            rgb[hi ^ lo] = (255, 40, 40)
            im = crop_to_content(Image.fromarray(rgb), pad=8, thr=5)
            if im.height < 300:
                im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
            e = rev["silhouettes"][key]
            cells.append(label(im, "blender workbench · %s %s · %s XOR %d px (%.2f %% площади)" %
                               (cam, az, lab, e[lab + "_xor_px"], 100 * e[lab + "_xor_share"]), 14))
        rows.append(hstack(cells, gap=10))
    sheets["silhouettes"] = save_jpg(vstack(rows, gap=10), out_dir / "silhouettes.jpg")
    # inspect sheets (Tripo high-poly as delivered: textured views and part map with the phantom parts marked)
    ins = paths["work"] / "inspect_png"
    if not ins.exists():
        ins = out_dir / "inspect"
    if ins.exists():
        tex = [label(Image.open(ins / ("tex8k_%s.png" % v)), "blender workbench · Tripo tex8k-pbr как выдан (21 часть) · %s" % v, 16)
               for v in ("front", "right", "back", "left")]
        sheets["inspect_tripo_tex8k"] = save_jpg(hstack(tex), out_dir / "inspect_tripo_tex8k.jpg")
        cells = []
        for name, pc in sorted(profile["parts"].items(), key=lambda kv: int(kv[0].rsplit("_", 1)[1])):
            i = name.rsplit("_", 1)[1]
            row = hstack([Image.open(ins / ("part_%s_%s.png" % (i, v))) for v in ("front", "right", "back")], gap=2)
            tag = "ФАНТОМ, удалена" if pc.get("drop") else "оставлена"
            cells.append(label(row, "blender · часть %s · %s · %s" % (i, tag, pc["role"][:48]), 12))
        rows = [hstack(cells[k:k + 3], gap=8) for k in range(0, len(cells), 3)]
        sheets["inspect_parts"] = save_jpg(vstack(rows, gap=8), out_dir / "inspect_parts.jpg")
    P.write_json(out_dir / "frames-storage.json", {"schema": "unmatched.h2-bake.frames/1", "frames": storage,
                                                   "sheets": sheets,
                                                   "note": "raw PNG renders stay in work/ (not committed); JPEG q90 with a burned-in 'blender' label are committed"})
    print(P.STAGE_MARKER, "sheets", len(storage), len(sheets))


if __name__ == "__main__":
    main()
