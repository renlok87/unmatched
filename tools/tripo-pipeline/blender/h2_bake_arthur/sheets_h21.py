"""Stage sheets_h21 (system python, Pillow): labelled H2 | H2.1 comparison sheets from the raw renders of stage compare.

    python sheets_h21.py <profile.json> <run_dir>

Every panel carries a burned-in "blender · ..." label (Blender EEVEE / Workbench preview, not UE, not the game light).
Outputs in preview/h21/ (JPEG q90):
  compare_{front,side,back}.jpg   H2 concept | H2 textures | H2.1 textures (light studio_env, ortho, concept framing)
  k2_5x.jpg, k2_1p6.jpg           K2 (FOV 35, -55 deg, 386 / 1207 uu): H2 | H2.1 per azimuth, figure crop 1:1 and
                                  enlarged (nearest)
  closeups_materials.jpg          torso, blade, head front/back, legs, left gauntlet: H2 | H2.1
  closeups_residuals.jpg          cloak back, strip fold, medallion hole, right forearm from below: H2 | H2.1
  studio_light.jpg                the same pairs under the H2 review light (dark world, three suns)
  classes.jpg                     material class raster flat on the mesh (legend in the label)
  frames-h21.json                 sha256 of every raw PNG used and of every sheet
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pure as P  # noqa: E402
from sheets import hstack, label, save_jpg, vstack  # noqa: E402

LIGHT = {"studio_env": "свет studio_env (3 солнца + studio.exr)", "studio": "свет H2-ревью (3 солнца, тёмный мир)"}
TEX = {"h2": "H2 (рев. 2, 9a2a5184)", "h21": "H2.1"}


def fig_box(imgs, pad=12, thr=20):
    boxes = []
    for im in imgs:
        a = np.asarray(im).astype(np.int32)
        ys, xs = np.nonzero(np.abs(a - a[2, 2]).sum(axis=2) > thr)
        boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
    w, h = imgs[0].size
    return (max(min(b[0] for b in boxes) - pad, 0), max(min(b[1] for b in boxes) - pad, 0),
            min(max(b[2] for b in boxes) + pad, w), min(max(b[3] for b in boxes) + pad, h))


def main():
    profile = P.load_json(sys.argv[1])
    paths = P.run_paths(sys.argv[2])
    rc = profile["review_h21"]
    raw = paths["work"] / "h21_png"
    out = paths["preview"] / "h21"
    used, sheets = {}, {}

    def img(light, tex, view):
        f = raw / light / tex / (view + ".png")
        used["%s/%s/%s" % (light, tex, view)] = P.sha256(f)
        return Image.open(f).convert("RGB")

    # concept | H2 | H2.1, ortho
    for view, fname in (("front", "ortho_front"), ("side", "ortho_left"), ("back", "ortho_back")):
        c = Image.open(P.repo_path(profile["sources"]["concepts"][view])).convert("RGB")
        panels = [label(c, "концепт H2 (Codex imagegen) · %s" % view, 22)]
        for tex in ("h2", "h21"):
            r = img("studio_env", tex, fname).resize(c.size, Image.LANCZOS)
            panels.append(label(r, "blender · EEVEE · %s · %s · %s" % (TEX[tex], LIGHT["studio_env"], fname), 18))
        sheets["compare_" + view] = save_jpg(hstack(panels), out / ("compare_%s.jpg" % view))
    # K2 5x and 1.6x
    for tag, k in (("5x", 2), ("1p6", 4)):
        rows = []
        for az in rc["k2_azimuths"]:
            v = "k2_%s_az%d" % (tag, az)
            a, b = img("studio_env", "h2", v), img("studio_env", "h21", v)
            box = fig_box([a, b])
            a, b = a.crop(box), b.crop(box)
            big = hstack([a.resize((a.width * k, a.height * k), Image.NEAREST),
                          b.resize((b.width * k, b.height * k), Image.NEAREST)])
            rows.append(label(vstack([hstack([a, b]), big]),
                              "blender · K2 %s (FOV 35, -55°, %d uu) az %d · H2 | H2.1 · 1:1 и x%d (nearest) · %s"
                              % (tag.replace("p", ","), round(rc["k2_distance_m"][tag] * 100), az, k,
                                 LIGHT["studio_env"]), 14))
        sheets["k2_" + tag] = save_jpg(vstack(rows, gap=12), out / ("k2_%s.jpg" % tag))

    def pairs(names, light, size=560):
        rows = []
        for v in names:
            cells = [label(img(light, tex, v).resize((size, size), Image.LANCZOS),
                           "blender · %s · %s" % (TEX[tex], v), 14) for tex in ("h2", "h21")]
            rows.append(hstack(cells, gap=6))
        grid = [hstack(rows[i:i + 2], gap=16) for i in range(0, len(rows), 2)]
        return vstack(grid, gap=10)

    mat_views = ["close_torso_az0", "close_blade_az0", "close_head_az0", "close_head_az180", "close_legs_az0",
                 "close_left_hand_az0"]
    res_views = ["close_cloak_back_az180", "close_strip_az180", "close_strip_az-150", "close_medallion_az180",
                 "close_medallion_az-150", "close_forearm_under_az-90", "close_forearm_under_az-30"]
    sheets["closeups_materials"] = save_jpg(label(pairs(mat_views, "studio_env"),
                                                  "blender · EEVEE · H2 | H2.1 · " + LIGHT["studio_env"], 18),
                                            out / "closeups_materials.jpg")
    sheets["closeups_residuals"] = save_jpg(label(pairs(res_views, "studio_env"),
                                                  "blender · EEVEE · H2 | H2.1 · остатки ревизии 2 · " + LIGHT["studio_env"], 18),
                                            out / "closeups_residuals.jpg")
    rows = []
    for v in rc["studio_views"]:
        a, b = img("studio", "h2", v), img("studio", "h21", v)
        if v.startswith("k2_"):
            box = fig_box([a, b])
            a, b = a.crop(box), b.crop(box)
            a, b = a.resize((a.width * 2, a.height * 2), Image.NEAREST), b.resize((b.width * 2, b.height * 2), Image.NEAREST)
        s = 560 / max(a.height, 1)
        a = a.resize((max(1, round(a.width * s)), 560), Image.LANCZOS)
        b = b.resize((max(1, round(b.width * s)), 560), Image.LANCZOS)
        rows.append(hstack([label(a, "blender · %s · %s" % (TEX["h2"], v), 14), label(b, "blender · %s · %s" % (TEX["h21"], v), 14)]))
    sheets["studio_light"] = save_jpg(label(vstack(rows, gap=10), "blender · EEVEE · " + LIGHT["studio"] +
                                            ": металл отражает почти только солнца", 18), out / "studio_light.jpg")
    cells = []
    for v in rc["classes_views"]:
        im = img("classes", "classes", v)
        s = 700 / im.height
        cells.append(label(im.resize((round(im.width * s), 700), Image.LANCZOS), "blender workbench · " + v, 14))
    sheets["classes"] = save_jpg(label(hstack(cells), "blender workbench · классы материалов (плоский цвет): голубой — сталь, "
                                       "жёлтый — золото, красный — ткань, коричневый — кожа, телесный — голова не металл, "
                                       "тёмно-серый — камень подставки; смеси — мягкие веса", 16), out / "classes.jpg")
    renders = {}
    for light in ("studio_env", "studio", "classes"):
        for f in sorted((raw / light).glob("compare-*.json")):
            meta = P.load_json(f)
            renders[light] = {"light": meta["light"], "engine": meta["engine"], "sets": meta["sets"]}
    P.write_json(out / "frames-h21.json", {"schema": "unmatched.h2-bake.frames-h21/1", "raw_png_sha256": used,
                                           "renders": renders, "sheets": sheets,
                                           "note": "raw PNG renders stay in work/h21_png (not committed); JPEG q90 with a burned-in 'blender' label are committed"})
    print(P.STAGE_MARKER, "sheets_h21", len(used), len(sheets))


if __name__ == "__main__":
    main()
