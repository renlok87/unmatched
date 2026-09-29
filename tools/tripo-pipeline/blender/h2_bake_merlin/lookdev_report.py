"""Stage `ld_report` (system python): after-metrics, review sheets and the summary of the Merlin look-dev v2 run.

python lookdev_report.py <lookdev profile.json>

- zone medians of the ld_render_after frames (same cameras / zone-ID pass as ld_render_before) against the concept:
  per zone and view luma (model x exposure k of ld_tone, so it is comparable with the concept), hue, saturation,
  before and after -> reports/ld-metrics.json;
- sheets (preview/, every render labelled "blender", EEVEE studio light, not the game light):
  ld_sbs_{front,right,back}.png  concept | H2.1 textures | look-dev textures
  ld_sheet_maps.png              MatID classes on the model | UV1 checker (1 cm) | staff UV1 checker | MatID atlas
- reports/textures-report.json (sha256 of every texture: 2K runtime + MatID + LUT committed, 4K masters local);
- reports/ld-report.json: checks of every look-dev stage + the determinism note.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import lookdev_maps as LM  # noqa: E402
import lookdev_tone as T  # noqa: E402
import maps as M  # noqa: E402

BG = (24, 25, 28)
FG = (235, 235, 235)


def label(im, text, sub=None):
    bar = 44 if sub else 26
    out = Image.new("RGB", (im.width, im.height + bar), BG)
    out.paste(im, (0, bar))
    d = ImageDraw.Draw(out)
    d.text((8, 6), text, fill=FG)
    if sub:
        d.text((8, 24), sub, fill=(170, 170, 170))
    return out


def hstack(images, gap=8):
    h = max(i.height for i in images)
    out = Image.new("RGB", (sum(i.width for i in images) + gap * (len(images) - 1), h), BG)
    x = 0
    for i in images:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def fit(im, h):
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def save(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=False, compress_level=9)
    return {"path": C.rel(path), "sha256": C.sha256(path), "px": list(img.size)}


def zone_medians(rdir, view, tag, order, er):
    from scipy import ndimage
    with Image.open(rdir / ("%s_zone.png" % view)) as im:
        zp = np.asarray(im.convert("RGBA")).astype(np.int32)
    with Image.open(rdir / ("%s_lit_%s.png" % (view, tag))) as im:
        lin = M.srgb_decode(np.asarray(im.convert("RGB")).astype(np.float64) / 255.0)
    ok = (zp[..., 3] == 255) & (np.abs(zp[..., 0] % 16 - 8) <= 2)
    zid = np.where(ok, zp[..., 0] // 16, -1)
    out = {}
    for i, k in enumerate(order):
        m = ndimage.binary_erosion(zid == i, iterations=er)
        out[k] = (int(m.sum()), np.median(lin[m], 0) if m.any() else None)
    return out


def main():
    prof, src = LM.lookdev_profiles(sys.argv[1])
    ld = prof["lookdev"]
    order = ld["zones"]["order"]
    tone = C.load_json(prof.reports / "ld-tone-report.json")
    k = tone["exposure_k"]
    conc, _ov = T.concept_zones(prof, ld)
    rdir = prof.work / "lookdev" / "render"
    er = int(ld["render"]["id_erode_px"])
    nmin = int(ld["tone"]["min_views_pixels"])
    cache = {(rview, tag): zone_medians(rdir, rview, tag, order, er) for rview in T.VIEWS.values() for tag in ("before", "after")}
    metrics = {}
    summary = {}
    for z in order:
        per_view = {}
        agg = {"before": [], "after": []}
        for cview, rview in T.VIEWS.items():
            c = conc[cview].get(z)
            if not c or c["pixels"] < nmin:
                continue
            e = {"concept": T.describe(c["median"])}
            for tag in ("before", "after"):
                n, med = cache[(rview, tag)][z]
                if n < nmin:
                    continue
                d = T.describe(med * k)
                d["pixels"] = n
                d["delta_vs_concept"] = {"luma_ratio": C.r(d["luma_Y"] / max(e["concept"]["luma_Y"], 1e-6), 3),
                                         "hue_deg": C.r(((d["hue_deg"] - e["concept"]["hue_deg"] + 180) % 360) - 180, 1),
                                         "sat": C.r(d["sat"] - e["concept"]["sat"], 3)}
                e[tag] = d
                agg[tag].append(d["delta_vs_concept"])
            per_view[cview] = e
        metrics[z] = per_view
        summary[z] = {tag: ({"luma_ratio_median": C.r(float(np.median([a["luma_ratio"] for a in v])), 3),
                             "hue_deg_median": C.r(float(np.median([a["hue_deg"] for a in v])), 1),
                             "sat_median": C.r(float(np.median([a["sat"] for a in v])), 3), "views": len(v)} if v else None)
                      for tag, v in agg.items()}
    C.write_json(prof.reports / "ld-metrics.json", {
        "stage": "ld_report", "note": "Blender EEVEE studio light (not UE/Lumen, not the board light); model luma x exposure k (ld_tone) so it compares with the concept; hue/sat of the zone median in sRGB HSV; delta = model - concept (luma: ratio)",
        "exposure_k": k, "summary": summary, "zones": metrics})
    # ------------------------------------------------------------------ sheets
    outs = {}
    concepts = {v: C.repo_path(src["concepts"][v]) for v in ("front", "side", "back")}
    for cview, rview in T.VIEWS.items():
        h = 1000
        panels = [label(fit(Image.open(concepts[cview]).convert("RGB"), h), "CONCEPT (imagegen, %s)" % cview, src["concepts"][cview]),
                  label(fit(Image.open(rdir / ("%s_lit_before.png" % rview)).convert("RGB"), h), "BLENDER EEVEE - H2.1 textures (%s)" % rview,
                        "studio light (H2.1 preview), Principled BSDF - not UE, not the board light"),
                  label(fit(Image.open(rdir / ("%s_lit_after.png" % rview)).convert("RGB"), h), "BLENDER EEVEE - look-dev v2 BC + ORM (%s)" % rview,
                        "same light/camera; MatID/LUT/detail/Cloth are UE shader work (not shown)")]
        outs["ld_sbs_%s" % rview] = save(hstack(panels), prof.preview / ("ld_sbs_%s.png" % rview))
    pv = prof.preview
    h = 900
    panels = [label(fit(Image.open(pv / "ld_render_matid_front.png").convert("RGB"), h), "BLENDER - MatID classes (front)",
                    "wool blue, silk/embroidery yellow, leather green, bronze orange, wood brown, skin pink, stone grey, legacy black"),
              label(fit(Image.open(pv / "ld_render_uv1_checker_front.png").convert("RGB"), h), "BLENDER - UV1_m checker 1 cm", "uniform density = metres"),
              label(fit(Image.open(pv / "ld_render_uv1_checker_staff.png").convert("RGB"), h), "BLENDER - staff UV1 checker", "wood islands along U (grain)"),
              label(fit(Image.open(pv / "ld_matid_2K.png").convert("RGB"), h), "MatID atlas 2K (class colours)", "gutters filled with the nearest class")]
    outs["ld_sheet_maps"] = save(hstack(panels), pv / "ld_sheet_maps.png")
    # ------------------------------------------------------------------ textures report
    files = {}
    for p in sorted(prof.textures.iterdir()):
        tier = "master_4k" if p.name.endswith("_4K.png") else "runtime"
        files[p.name] = {"path": C.rel(p), "sha256": C.sha256(p), "bytes": p.stat().st_size, "tier": tier,
                         "git": "local only (ASSET-MERLIN-001/.gitignore)" if tier == "master_4k" else "committed"}
    mrep = C.load_json(prof.reports / "ld-maps-report.json")
    C.write_json(prof.reports / "textures-report.json", {"stage": "ld_report", "profile": C.rel(prof.path), "textures": files,
                                                          "conventions": mrep["conventions"],
                                                          "lut": "see reports/ld-lut.json"})
    # ------------------------------------------------------------------ summary
    stages = {}
    for name in ("ld-export-report.json", "ld-maps-report.json", "ld-render-before-report.json", "ld-tone-report.json",
                 "ld-render-after-report.json"):
        r = C.load_json(prof.reports / name)
        stages[name] = {"passed": r["passed"], "checks": {c: v["passed"] for c, v in r["checks"].items()}}
    report = {"stage": "ld_report", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "asset_id": prof["asset_id"],
              "status": "technically built and measured (Blender); not imported into UE, not art-accepted",
              "stages": stages, "sheets": outs, "metrics_summary": summary,
              "passed": all(s["passed"] for s in stages.values())}
    C.write_json(prof.reports / "ld-report.json", report)
    print("H2_STAGE_OK ld_report passed=%s" % report["passed"])
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
