"""ENV kit orientation check: which way does the Tripo mesh face, compared with its four reference views?

  python tools/art/env_kit/orientation_check.py --params <env-kit-params.json> [--assets A,B] [--sheets]

Input: <scratch_dir>/probe/<ASSET-ID>.npz written by env_kit_build.py --probe (triangles in .blend axes after the
glTF import, before any turn) and the reference images <refs_dir>/<ASSET-ID>/{front,left,right,back}.png that went
into Tripo H3.1 multiview (white background).

Measurement (numpy/PIL on the CPU; silhouette masks and face statistics, no renderer, no GPU):
  - view frames with the front at .blend -Y (Tripo front = glTF +Z = .blend -Y; derived from the cannon and portal
    references: the muzzle / steps sit at frame-left in the 'left' view):
        front: camera at -Y, frame x = +X    back:  camera at +Y, frame x = -X
        left:  camera at +X, frame x = +Y    right: camera at -X, frame x = -Y      (frame y = +Z everywhere)
  - for each candidate turn about +Z (0/90/180/270 deg, counter-clockwise from above) the mesh is turned, each
    view's orthographic silhouette is rasterised (PIL polygon fill of the projected triangles), cropped to its
    bounds and fitted with a uniform scale into a raster_px square; the reference foreground (non-white pixels not
    connected to the image border through near-white pixels) gets the same crop/fit; IoU per view, mean over 4;
  - colour cue (front/back tie-break for mirror-symmetric silhouettes): per view the area-weighted mean base colour
    of the triangles facing that camera (normal . view > 0.35) divided by the mesh's overall mean colour, against
    the reference foreground mean divided by the mean over the four references; mean L1 distance per turn.
Decision: the turn with the best mean IoU is applied only if it beats 0 deg by >= orientation.apply_min_iou_gain;
otherwise 0 deg (the Tripo front) is kept. 'consistent' = 0 deg is the best or within the gain (silhouettes do not
contradict the Tripo front) and the colour cue does not prefer 180 deg by a clear margin.
Writes <run_dir>/reports/orientation-check.json; --sheets writes mask comparison PNGs to <scratch_dir>/orient/.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
VIEWS = ("front", "left", "right", "back")
# frame x axis and camera direction (from the object towards the camera) per view, .blend axes, front = -Y
FRAME = {
    "front": (np.array([1.0, 0.0, 0.0]), np.array([0.0, -1.0, 0.0])),
    "back": (np.array([-1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])),
    "left": (np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0])),
    "right": (np.array([0.0, -1.0, 0.0]), np.array([-1.0, 0.0, 0.0])),
}


def text_sha256_lf(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rot_z(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def fit_mask(mask, n):
    """Crop to bounds, fit into n x n keeping aspect, centred."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return np.zeros((n, n), bool), (0, 0)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = (n - 2) / max(h, w)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR)
    out = np.zeros((n, n), bool)
    x0, y0 = (n - nw) // 2, (n - nh) // 2
    out[y0:y0 + nh, x0:x0 + nw] = np.asarray(im) >= 128
    return out, (w, h)


def ref_mask(path):
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    lo, hi = rgb.min(2), rgb.max(2)
    light = (lo >= 232) & (hi - lo <= 24)
    h, w = light.shape
    border = np.zeros_like(light)
    m = 6  # the prepared inputs carry a 1-3 px grey line on some edges
    border[:m, :] = border[-m:, :] = True
    border[:, :m] = border[:, -m:] = True
    lab, _n = ndimage.label(light | border)
    bg_labels = np.unique(lab[border])
    bg = np.isin(lab, bg_labels[bg_labels > 0])
    fg = ~bg
    fg = ndimage.binary_opening(fg, iterations=1)
    return fg, rgb.astype(np.float64) / 255.0


def mesh_mask(pos, view, raster):
    ax, _cam = FRAME[view]
    x = pos @ ax
    y = pos[..., 2]
    xmin, xmax, ymin, ymax = x.min(), x.max(), y.min(), y.max()
    span = max(xmax - xmin, ymax - ymin)
    big = raster * 4
    s = (big - 4) / span
    img = Image.new("L", (big, big), 0)
    dr = ImageDraw.Draw(img)
    px = (x - xmin) * s + 2
    py = (ymax - y) * s + 2
    for t in range(len(pos)):
        dr.polygon([(px[t, 0], py[t, 0]), (px[t, 1], py[t, 1]), (px[t, 2], py[t, 2])], fill=255)
    return np.asarray(img) > 0


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def facing_colours(pos, nrm, area, colour, deg):
    R = rot_z(deg)
    n = nrm @ R.T
    out = {}
    w_all = area / area.sum()
    mean_all = (colour * w_all[:, None]).sum(0)
    for v in VIEWS:
        cam = FRAME[v][1]
        sel = (n @ cam) > 0.35
        w = area * sel
        out[v] = ((colour * w[:, None]).sum(0) / max(w.sum(), 1e-12)) / np.maximum(mean_all, 1e-6)
    return out


def check_asset(aid, P, sheets):
    scratch = Path(P["scratch_dir"])
    data = np.load(scratch / "probe" / ("%s.npz" % aid))
    pos, nrm, area, colour = data["pos"], data["nrm"], data["area"], data["colour"]
    raster = int(P["orientation"]["raster_px"])
    refs = {}
    ref_col = {}
    for v in VIEWS:
        p = Path(P["refs_dir"]) / aid / ("%s.png" % v)
        fg, rgb = ref_mask(p)
        refs[v] = {"path": p.as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                   "fg": fg, "fit": fit_mask(fg, raster)}
        ref_col[v] = rgb[fg].mean(0)
    ref_mean = np.mean([ref_col[v] for v in VIEWS], axis=0)
    ref_rel = {v: ref_col[v] / np.maximum(ref_mean, 1e-6) for v in VIEWS}
    turns = {}
    fits = {}
    for deg in (0, 90, 180, 270):
        P3 = pos @ rot_z(deg).T
        per = {}
        for v in VIEWS:
            mfit, (mw, mh) = fit_mask(mesh_mask(P3, v, raster), raster)
            fits[(deg, v)] = mfit
            rw, rh = refs[v]["fit"][1]
            per[v] = {"iou": round(iou(mfit, refs[v]["fit"][0]), 4),
                      "aspect_w_over_h_mesh": round(mw / max(mh, 1), 3),
                      "aspect_w_over_h_ref": round(rw / max(rh, 1), 3)}
        fc = facing_colours(pos, nrm, area, colour, deg)
        cdist = float(np.mean([np.abs(fc[v] - ref_rel[v]).sum() for v in VIEWS]))
        turns[deg] = {"mean_iou": round(float(np.mean([per[v]["iou"] for v in VIEWS])), 4), "views": per,
                      "colour_l1": round(cdist, 4),
                      "facing_colour_rel": {v: [round(float(c), 3) for c in fc[v]] for v in VIEWS}}
    gain_min = float(P["orientation"]["apply_min_iou_gain"])
    best = max(turns, key=lambda d: turns[d]["mean_iou"])
    gain = turns[best]["mean_iou"] - turns[0]["mean_iou"]
    yaw = best if (best != 0 and gain >= gain_min) else 0
    col_margin_180 = turns[0]["colour_l1"] - turns[180]["colour_l1"]
    sil_front_back_margin = turns[0]["mean_iou"] - turns[180]["mean_iou"]
    colour_prefers_180 = col_margin_180 > 0.15 and col_margin_180 > 0.25 * turns[0]["colour_l1"]
    consistent = (yaw == 0 and not colour_prefers_180) or (yaw != 0)
    reasons = []
    if yaw != 0:
        reasons.append("turn %d deg beats the Tripo front by %.3f mean IoU (>= %.3f)" % (yaw, gain, gain_min))
    else:
        reasons.append("Tripo front kept: best turn %d deg, gain over 0 deg %.3f < %.3f" % (best, gain, gain_min)
                       if best != 0 else "Tripo front (0 deg) has the best mean silhouette IoU")
    if abs(sil_front_back_margin) < 0.02:
        reasons.append("front/back silhouettes nearly mirror-equal (IoU margin %.3f): colour cue %s"
                       % (sil_front_back_margin, "prefers 0 deg" if col_margin_180 <= 0 else
                          "prefers 180 deg by %.3f" % col_margin_180))
    if colour_prefers_180:
        reasons.append("colour cue prefers 180 deg clearly: inspect before placement")
    rec = {
        "refs": {v: {"path": refs[v]["path"], "sha256": refs[v]["sha256"],
                     "fg_fraction": round(float(refs[v]["fg"].mean()), 4)} for v in VIEWS},
        "turns_deg": {str(k): v for k, v in turns.items()},
        "best_silhouette_turn_deg": best,
        "colour_note": "colour_l1 compares lit reference art with albedo face statistics; it is used only as the "
                       "0 vs 180 deg tie-break (narrow side views make it unreliable for 90/270)",
        "silhouette_margin_0_vs_180": round(sil_front_back_margin, 4),
        "colour_margin_0_vs_180": round(col_margin_180, 4),
        "decision": {"yaw_deg": yaw, "consistent": bool(consistent), "reasons": reasons},
    }
    if sheets:
        out = scratch / "orient"
        out.mkdir(parents=True, exist_ok=True)
        tile = raster
        sheet = Image.new("RGB", (tile * 4 + 10, tile * 5 + 20), (40, 40, 40))
        for c, v in enumerate(VIEWS):
            sheet.paste(Image.fromarray((refs[v]["fit"][0] * 255).astype(np.uint8)).convert("RGB"), (c * tile, 0))
            for rr, deg in enumerate((0, 90, 180, 270)):
                a, b = fits[(deg, v)], refs[v]["fit"][0]
                rgb = np.zeros((tile, tile, 3), np.uint8)
                rgb[a & b] = (230, 230, 230)
                rgb[a & ~b] = (230, 60, 60)
                rgb[~a & b] = (60, 120, 230)
                sheet.paste(Image.fromarray(rgb), (c * tile, (rr + 1) * tile + 20))
        sheet.save(out / ("%s.png" % aid))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True)
    ap.add_argument("--assets", default=None)
    ap.add_argument("--sheets", action="store_true")
    a = ap.parse_args()
    P = json.loads(Path(a.params).read_text(encoding="utf-8"))
    run = REPO / P["run_dir"]
    ids = a.assets.split(",") if a.assets else list(P["assets"])
    out_path = run / "reports" / "orientation-check.json"
    doc = json.loads(out_path.read_text(encoding="utf-8")) if out_path.is_file() else {}
    doc.update({
        "schema": "unmatched.env-kit.orientation-check/1",
        "status": "measured",
        "script": {"path": HERE.relative_to(REPO).as_posix(), "sha256_lf": text_sha256_lf(HERE)},
        "method": ("silhouette IoU of the mesh (PIL polygon fill of orthographic projections) against the reference "
                   "foreground masks, per candidate turn about +Z; colour cue from face statistics; CPU only, "
                   "no renderer"),
        "view_frames_blend": {"front": "camera -Y, frame x +X", "back": "camera +Y, frame x -X",
                              "left": "camera +X, frame x +Y", "right": "camera -X, frame x -Y"},
        "params": P["orientation"],
    })
    doc.setdefault("assets", {})
    for aid in ids:
        rec = check_asset(aid, P, a.sheets)
        doc["assets"][aid] = rec
        d = rec["decision"]
        print("ORIENT %-22s yaw %3d  consistent %-5s  IoU0 %.3f  best %3d (%.3f)  colour 0/180 %.3f/%.3f" % (
            aid, d["yaw_deg"], d["consistent"], rec["turns_deg"]["0"]["mean_iou"], rec["best_silhouette_turn_deg"],
            rec["turns_deg"][str(rec["best_silhouette_turn_deg"])]["mean_iou"], rec["turns_deg"]["0"]["colour_l1"],
            rec["turns_deg"]["180"]["colour_l1"]))
    doc["assets"] = dict(sorted(doc["assets"].items()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
