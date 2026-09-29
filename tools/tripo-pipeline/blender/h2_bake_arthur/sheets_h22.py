"""Stage sheets_h22 (system python, Pillow): labelled concept | H2 | H2.1 | H2.2 sheets from the raw renders of stage
compare_h22 (work/h22_png/).

    python sheets_h22.py <profile.json> <run_dir>

Every panel carries a burned-in "blender · ..." label (Blender EEVEE / Workbench preview, not UE). Outputs in
preview/h22/ (JPEG q90):
  compare_{front,side,back}.jpg   concept | H2 | H2.1 | H2.2 (light studio_env, ortho, concept framing)
  k2_5x.jpg, k2_1p6.jpg           K2 (FOV 35, -55 deg, 386 / 1207 uu): H2 | H2.1 | H2.2 per azimuth, 1:1 and enlarged
  closeups_steel.jpg              torso, blade, head, legs, left gauntlet: H2 | H2.1 | H2.2 (studio_env)
  cobble_light.jpg                the one frame in the Cobble-light approximation (K2 5x, az 0 and -40): H2.1 | H2.2
                                  (+ H2), figure crop 1:1 and x2 - does the dark steel turn white from the sky?
  frames-h22.json                 sha256 of every raw PNG used and of every sheet
(steel_masks.jpg is written by stage steelcheck.)
"""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pure as P  # noqa: E402
from sheets import hstack, label, save_jpg, vstack  # noqa: E402
from sheets_h21 import fig_box  # noqa: E402

LIGHT = {"studio_env": "свет studio_env (3 солнца + studio.exr)",
         "cobble": "свет ≈ Cobble (ключ 4,5 lx, купол неба ×11,2, EV100 1,3, AgX; приближение, не UE)"}
TEX = {"h2": "H2 (9a2a5184)", "h21": "H2.1 (c6068808)", "h22": "H2.2 ред. 2"}
SETS = ("h2", "h21", "h22")


def main():
    profile = P.load_json(sys.argv[1])
    paths = P.run_paths(sys.argv[2])
    rc = profile["review_h22"]
    raw = paths["work"] / "h22_png"
    out = paths["preview"] / "h22"
    used, sheets = {}, {}

    def img(light, tex, view):
        f = raw / light / tex / (view + ".png")
        used["%s/%s/%s" % (light, tex, view)] = P.sha256(f)
        return Image.open(f).convert("RGB")

    for view, fname in (("front", "ortho_front"), ("side", "ortho_left"), ("back", "ortho_back")):
        c = Image.open(P.repo_path(profile["sources"]["concepts"][view])).convert("RGB")
        panels = [label(c, "концепт H2 (Codex imagegen) · %s" % view, 22)]
        for tex in SETS:
            r = img("studio_env", tex, fname).resize(c.size, Image.LANCZOS)
            panels.append(label(r, "blender · EEVEE · %s · %s · %s" % (TEX[tex], LIGHT["studio_env"], fname), 16))
        sheets["compare_" + view] = save_jpg(hstack(panels), out / ("compare_%s.jpg" % view))
    for tag, k in (("5x", 2), ("1p6", 4)):
        rows = []
        for az in profile["review_h21"]["k2_azimuths"]:
            v = "k2_%s_az%d" % (tag, az)
            ims = [img("studio_env", t, v) for t in SETS]
            box = fig_box(ims)
            ims = [i.crop(box) for i in ims]
            big = hstack([i.resize((i.width * k, i.height * k), Image.NEAREST) for i in ims])
            rows.append(label(vstack([hstack(ims), big]),
                              "blender · K2 %s (FOV 35, -55°, %d uu) az %d · H2 | H2.1 | H2.2 · 1:1 и x%d (nearest) · %s"
                              % (tag.replace("p", ","), round(profile["review_h21"]["k2_distance_m"][tag] * 100), az, k,
                                 LIGHT["studio_env"]), 14))
        sheets["k2_" + tag] = save_jpg(vstack(rows, gap=12), out / ("k2_%s.jpg" % tag))
    rows = []
    for v in [x for x in rc["studio_env_views"] if x.startswith("close_")]:
        rows.append(hstack([label(img("studio_env", t, v).resize((520, 520), Image.LANCZOS),
                                  "blender · %s · %s" % (TEX[t], v), 14) for t in SETS], gap=6))
    sheets["closeups_steel"] = save_jpg(label(vstack(rows, gap=10), "blender · EEVEE · H2 | H2.1 | H2.2 · " +
                                              LIGHT["studio_env"], 18), out / "closeups_steel.jpg")
    rows = []
    for v in rc["cobble_views"]:
        ims = [img("cobble", t, v) for t in SETS]
        box = fig_box(ims, pad=40)
        ims = [i.crop(box) for i in ims]
        cells = [label(i.resize((i.width * 2, i.height * 2), Image.LANCZOS), "blender · %s · %s · x2" % (TEX[t], v), 14)
                 for t, i in zip(SETS, ims)]
        rows.append(hstack(cells, gap=6))
    sheets["cobble_light"] = save_jpg(label(vstack(rows, gap=10), "blender · EEVEE · " + LIGHT["cobble"] +
                                            " · H2 | H2.1 | H2.2 · проверка: сталь не белеет от неба", 18),
                                      out / "cobble_light.jpg")
    renders = {}
    for light in ("studio_env", "cobble", "classes"):
        for f in sorted((raw / light).glob("compare-*.json")):
            meta = P.load_json(f)
            renders[light] = {"light": meta["light"], "engine": meta["engine"], "sets": meta["sets"]}
    P.write_json(out / "frames-h22.json", {"schema": "unmatched.h2-bake.frames-h22/1", "raw_png_sha256": used,
                                           "renders": renders, "sheets": sheets,
                                           "note": "raw PNG renders stay in work/h22_png (not committed); JPEG q90 with a burned-in 'blender' label are committed"})
    print(P.STAGE_MARKER, "sheets_h22", len(used), len(sheets))


if __name__ == "__main__":
    main()
