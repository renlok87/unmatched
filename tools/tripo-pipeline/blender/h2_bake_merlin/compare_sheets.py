"""Stage `compare_sheets` (system python, Pillow): concept | H2 | H2.1 review sheets from the compare stage frames.
H2.1 iteration (2026-09-29). Every render panel is labelled "blender" (EEVEE, not the game light).

python compare_sheets.py <profile.json>
Inputs: work/compare/*.png (stage compare; studio_env frames are RGBA and are composited on the background colour of
the studio frames), the concepts, profile h21.compare.concept_crops_px.
Output (preview/, committed):
  h21_sbs_{front,right,back}.png   concept | H2 | H2.1, light studio_env (2K runtime set for both)
  h21_sbs_front_studio.png         the same in the studio light of the H2 frames
  h21_sbs_k2_{1p6,5x}.png          K2 crops, rows front / 3q; columns H2 | H2.1 in studio, then in studio_env
  h21_materials.png                rows crystal / buckle / stole / staff; concept crop | H2 | H2.1 (studio_env) |
                                   H2 | H2.1 (studio)
Report: reports/compare-sheets-report.json (inputs and outputs with sha256).
"""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from sheets import BG, hstack, label, fit_h  # noqa: E402

# background of the studio frames: world (0.018, 0.019, 0.022) linear through the Standard (sRGB) view transform
RENDER_BG = (36, 37, 40)


def vstack(images, gap=8):
    w = max(i.width for i in images)
    h = sum(i.height for i in images) + gap * (len(images) - 1)
    out = Image.new("RGB", (w, h), BG)
    y = 0
    for i in images:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def load(path):
    im = Image.open(path)
    if im.mode == "RGBA":
        bg = Image.new("RGBA", im.size, RENDER_BG + (255,))
        return Image.alpha_composite(bg, im).convert("RGB")
    return im.convert("RGB")


def save(im, path, outputs):
    im.save(path, format="PNG", optimize=False, compress_level=9)
    outputs[path.name] = {"path": C.rel(path), "sha256": C.sha256(path), "px": list(im.size)}


def silhouette_box(images):
    boxes = []
    for im in images:
        px = im.load()
        bg = px[2, 2]
        w, h = im.size
        xs, ys = [], []
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                p = px[x, y]
                if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 12:
                    xs.append(x)
                    ys.append(y)
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    side = max(x1 - x0, y1 - y0) + 24
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    return (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side), side, y1 - y0


def main():
    prof = C.Profile(sys.argv[1])
    cmp = prof["h21"]["compare"]
    fr = prof.work / "compare"
    pv = prof.preview
    outputs, inputs = {}, {}
    concept = prof["concepts"]
    rev_label = "H2.1 (profile %s)" % prof["profile_id"]
    base_label = "H2 (git %s)" % prof["h21"]["baseline"]["git_rev"]
    for f in sorted(fr.glob("*.png")):
        inputs[f.name] = C.sha256(f)
    cimgs = {}
    for key in ("front", "side", "back"):
        cpath = C.repo_path(concept[key])
        inputs["concept_" + key] = {"path": concept[key], "sha256": C.sha256(cpath)}
        cimgs[key] = Image.open(cpath).convert("RGB")
    light_txt = {"studio_env": "suns + soft grey environment (reflections)", "studio": "studio suns, near-black world (as the H2 frames)"}
    # ---------------- ortho: concept | H2 | H2.1
    h = 1000
    for view, key, lights in (("front", "front", ("studio_env", "studio")), ("right", "side", ("studio_env",)),
                              ("back", "back", ("studio_env",))):
        for light in lights:
            panels = [label(fit_h(cimgs[key], h), "CONCEPT H2 (imagegen, %s)" % key, concept[key])]
            for which, txt in (("h2", base_label), ("h21", rev_label)):
                panels.append(label(fit_h(load(fr / ("ortho_%s_%s_%s.png" % (view, light, which))), h),
                                    "BLENDER EEVEE - %s, 2K runtime set" % txt, "light: %s - not the game light" % light_txt[light]))
            name = "h21_sbs_%s%s.png" % (view, "" if light == "studio_env" else "_" + light)
            save(hstack(panels), pv / name, outputs)
    # ---------------- K2 crops: rows front / 3q; columns H2 | H2.1 (studio), H2 | H2.1 (studio_env)
    for tag, up, dist in (("1p6", 4, cmp_dist(prof, 0)), ("5x", 2, cmp_dist(prof, 1))):
        rows = []
        for view in ("front", "3q"):
            ims = {(light, which): load(fr / ("k2_%s_%s_%s_%s.png" % (tag, view, light, which)))
                   for light in ("studio", "studio_env") for which in ("h2", "h21")}
            box, side, fig_h = silhouette_box([ims[("studio", "h2")], ims[("studio", "h21")]])
            zoom = "crop %dx%d px of 1920x1080, nearest x%d, figure %d px tall" % (side, side, up, fig_h)
            tiles = []
            for light in ("studio", "studio_env"):
                for which, txt in (("h2", base_label), ("h21", rev_label)):
                    crop = ims[(light, which)].crop(box).resize((side * up, side * up), Image.NEAREST)
                    tiles.append(label(crop, "BLENDER K2 %s %s - %s" % (tag, view, txt), "%s; %s" % (light, zoom)))
            rows.append(hstack(tiles))
        sheet = label(vstack(rows), "game camera K2: horizontal FOV 35, pitch -55, D %s uu; 2K runtime set; Blender EEVEE, not the game light" % dist)
        save(sheet, pv / ("h21_sbs_k2_%s.png" % tag), outputs)
    # ---------------- material close-ups
    crops = cmp["concept_crops_px"]
    rows = []
    t = 400
    for name in cmp["material_closeups"]:
        ck, cx, cy, half = crops[name]
        c = cimgs[ck].crop((cx - half, cy - half, cx + half, cy + half)).resize((t, t), Image.LANCZOS)
        tiles = [label(c, "CONCEPT %s crop: %s" % (ck, name))]
        for light in ("studio_env", "studio"):
            for which, txt in (("h2", "H2"), ("h21", "H2.1")):
                im = load(fr / ("mat_%s_%s_%s.png" % (name, light, which))).resize((t, t), Image.LANCZOS)
                tiles.append(label(im, "BLENDER %s %s" % (txt, name), light))
        rows.append(hstack(tiles))
    sheet = label(vstack(rows), "material close-ups, 2K runtime set, ortho; studio_env = suns + soft grey environment (metal/gem reflect it), studio = the H2 preview light; Blender EEVEE, not the game light")
    save(sheet, pv / "h21_materials.png", outputs)
    C.write_json(prof.reports / "compare-sheets-report.json", {"stage": "compare_sheets", "profile": C.rel(prof.path),
                                                              "inputs": inputs, "outputs": outputs,
                                                              "label": "blender renders (EEVEE) vs imagegen concepts"})
    print("H2_STAGE_OK compare_sheets")


def cmp_dist(prof, i):
    return "%g" % prof["review"]["game_camera"]["distance_uu"][i]


if __name__ == "__main__":
    main()
