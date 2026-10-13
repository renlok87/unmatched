"""Scratch measurement of the Leshen bone (MatID class 0 = legacy_bake: deer skull, antlers, pale claws) on the UE
look-dev frames of ue_hero_lookdev.py review, for the iteration decision only (not a tool, not acceptance).

Why: ue_hero_lookdev decodes class 0 as "dark changed pixels" of the DebugView frame against the plate; the skull and
antlers stand against the black backdrop, their dark-grey debug emissive does not differ from it by 18 levels, so the
tool's legacy_bake zone holds only the claws over the floor (pilot F90 again). Here the bone = figure pixels of the
BEAUTY frame (|neutral - plate| > 18) that the debug decode did not give to a library class, above the base top (the
lowest decoded wood row), with the same HSV render gate as the review config. Stats = ue_hero_lookdev.hsv_stats of the
pooled pixels of front/side/back; Y ratio normalised by the wood exposure k of the tool's measure-<tag>.json.

    python bone_measure.py <review out dir> <tag> <review-config.json>
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
sys.path.insert(0, str(REPO / "tools/art/material_library"))
import ue_hero_lookdev as L  # noqa: E402

out, tag, cfg_path = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
meas = json.loads((out / ("measure-%s.json" % tag)).read_text(encoding="utf-8"))
concept = json.loads((REPO / cfg["concept_zones"]).read_text(encoding="utf-8"))["zones"]["legacy_bake"]["concept"]
gate = cfg["render_gates"]["legacy_bake"]
presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json").read_text(encoding="utf-8"))
ids = {c["id"]: c["index"] for c in presets["classes"]}
classes = sorted({ids[z] for z in cfg["zones"]} | {0})
calib = cfg.get("debug_calibration")


def frame(view, var):
    p = out / "frames" / ("%s-%s-%s-%s.png" % (cfg["hero"].lower(), tag, view, var))
    return np.asarray(Image.open(p).convert("RGB")) if p.is_file() else None


res = {"tag": tag, "concept": concept, "gate": gate, "variants": {}, "per_view_pixels": {}}
pooled = {}
for view in ("front", "side", "back"):
    dbg, plate, neu = frame(view, "debug"), frame(view, "plate"), frame(view, "neutral")
    cls, _changed = L.decode_debug(dbg, plate, classes, calib)
    fig = np.abs(neu.astype(np.float32) - plate.astype(np.float32)).max(-1) > 18.0
    wood_rows = np.nonzero((cls == ids["wood"]).any(1))[0]
    above = np.zeros(cls.shape, bool)
    above[: int(wood_rows.max()) - 2, :] = True
    bone = L.erode(fig & (cls < 1) & above, 1)
    res["per_view_pixels"][view] = int(bone.sum())
    for var in ("neutral", "reading", "P1", "P2"):
        b = frame(view, var.lower())
        px = b[bone]
        px = px[L.gate(px, gate)]
        pooled.setdefault(var, []).append(px)
for var, arrs in pooled.items():
    px = np.concatenate(arrs, 0)
    st = L.hsv_stats(px)
    k = (meas.get("exposure") or {}).get(var, {}).get("k_concept_over_ue_geomean_key_zones")
    yr = st["luma_Y_linear"] / max(concept["luma_Y_linear"] / k, 1e-6) if k else None
    dh = ((st["hue_deg"] - concept["hue_deg"] + 180.0) % 360.0) - 180.0
    res["variants"][var] = dict(st, pixels=int(len(px)), k_wood=k, Y_ratio_exposure_normalised=round(yr, 3) if yr else None,
                                dHue_deg=round(dh, 1), dSat=round(st["sat"] - concept["sat"], 3))
    print("%-8s px %6d Y %.4f ratio %s hue %.1f d %+.1f sat %.3f d %+.3f" % (
        var, len(px), st["luma_Y_linear"], res["variants"][var]["Y_ratio_exposure_normalised"], st["hue_deg"], dh,
        st["sat"], st["sat"] - concept["sat"]))
(out / ("bone-measure-%s.json" % tag)).write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
print("pixels per view", res["per_view_pixels"])
