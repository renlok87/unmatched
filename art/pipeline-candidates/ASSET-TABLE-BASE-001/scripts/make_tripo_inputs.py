"""Prepare Tripo multi-view inputs for ASSET-TABLE-BASE-001 (rock underside only).

Deterministic, local, free (no SYNTX / imagegen). Source views v3 have an exactly flat
#808080 background (normalisation output), so the background is recovered as the
border-connected region with max|RGB-128| <= TOL. That fixes the T2 WARN
(silhouette-edge-contrast-vs-background: grey rock close to #808080) without redrawing
the rock: interior grey pixels that are not border-connected stay object.

Variants written per view (front <- front, left <- side, as proposed in imagegen-inputs
manifest propTripoSlotProposal):
  rock-white : wooden frame + corner brackets removed (rows above CUT_Y -> background),
               background -> #FFFFFF, RGB. PRIMARY.
  rock-alpha : same cut, background -> alpha 0, RGBA. Alternative if Studio honours alpha.
  full-white : frame kept, background -> #FFFFFF. Fallback (frame then cut in Blender).
Both views get the same vertical shift, so baseline/scale consistency of T2 is preserved.

usage: python make_tripo_inputs.py <out_dir>
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

REPO = Path(__file__).resolve().parents[4]
SRC = {
    "front": ("art/imagegen/mvp-v1/environment/ref-table-base-v3-front.png",
              "b16fb858a6459ff6264f405f1984c43b9e39a8cef0300aa2d113e79ce078e9fc"),
    "left": ("art/imagegen/mvp-v1/environment/ref-table-base-v3-side.png",
             "18f904d67a42c3b9515db51c8de78d966363ea64f5e612241cc3ae70ba286018"),
}
TOL = 2
# first row below the wooden frame and its dark contact shadow (measured: frame rows
# 714-761/758, shadow band 762-766/759-765, rock width narrows at 768/767)
CUT_Y = {"front": 768, "left": 767}
SHIFT_Y = -330  # same for both views: rock band centre ~842 -> ~512


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bg_mask(a):
    near = np.abs(a.astype(int) - 128).max(2) <= TOL
    lab, _ = ndimage.label(near)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    return np.isin(lab, list(border))


def edge_stats(obj):
    inner = obj & ~ndimage.binary_erosion(obj)
    return int(inner.sum())


def main(out_dir):
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema": "unmatched.table-base-tripo-inputs/1", "tolerance": TOL,
              "cutY": CUT_Y, "shiftY": SHIFT_Y, "views": {}}
    for view, (rel, want) in SRC.items():
        p = REPO / rel
        got = sha(p)
        assert got == want, f"{rel}: sha {got} != registry {want}"
        a = np.asarray(Image.open(p).convert("RGB"))
        bg = bg_mask(a)
        obj_full = ~bg
        obj_rock = obj_full.copy()
        obj_rock[: CUT_Y[view]] = False
        # keep only the largest connected component (drop stray pixels left by the cut)
        lab, n = ndimage.label(obj_rock)
        if n > 1:
            sizes = ndimage.sum(obj_rock, lab, range(1, n + 1))
            obj_rock = lab == (int(np.argmax(sizes)) + 1)
        rec = {"source": rel, "sha256": got}
        for name, obj in (("rock", obj_rock), ("full", obj_full)):
            ys, xs = np.where(obj)
            rec[name + "BboxPx"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
            rec[name + "InnerEdgePx"] = edge_stats(obj)
        variants = {
            "rock-white": (obj_rock, "white"),
            "rock-alpha": (obj_rock, "alpha"),
            "full-white": (obj_full, "white"),
        }
        rec["files"] = {}
        for vname, (obj, mode) in variants.items():
            shifted = np.roll(obj, SHIFT_Y, axis=0)
            rgb = np.roll(a, SHIFT_Y, axis=0).copy()
            if SHIFT_Y < 0:
                shifted[SHIFT_Y:] = False
            if mode == "white":
                rgb[~shifted] = 255
                img = Image.fromarray(rgb, "RGB")
            else:
                alpha = np.where(shifted, 255, 0).astype(np.uint8)
                img = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
            fn = out / f"table-base-v3-{view}-{vname}.png"
            img.save(fn, optimize=False)
            # contrast of the new inner edge against the new background
            inner = shifted & ~ndimage.binary_erosion(shifted)
            bgc = 255 if mode == "white" else 128
            close = (np.abs(rgb[inner].astype(int) - bgc).max(1) < 30).mean() if mode == "white" else None
            rec["files"][vname] = {"path": fn.relative_to(REPO).as_posix(), "sha256": sha(fn),
                                   "innerEdgeCloseToBgFrac": None if close is None else round(float(close), 4)}
        # original WARN metric for reference
        inner0 = obj_full & ~ndimage.binary_erosion(obj_full)
        rec["originalInnerEdgeCloseTo808080Frac"] = round(
            float((np.abs(a[inner0].astype(int) - 128).max(1) < 30).mean()), 4)
        report["views"][view] = rec
    (out / "inputs-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
