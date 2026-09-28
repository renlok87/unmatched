"""Read-only preflight of ImageGen reference views before Tripo multi-view.

Builds a manifest of the normalized per-view PNGs in art/imagegen/mvp-v1
(characters + key props), then runs automatic checks per image and across
views of the same set. Nothing in art/imagegen is modified; no network calls;
no Tripo task is created.

Usage (from repo root):
    python tools/tripo-pipeline/check_inputs.py
    python tools/tripo-pipeline/check_inputs.py --compare-root C:/path/to/other/checkout
    python tools/tripo-pipeline/check_inputs.py --check-only   # do not write outputs

Outputs (default):
    docs/art-pipeline/imagegen-inputs/manifest.json
    docs/art-pipeline/imagegen-inputs/checks-report.json

Exit code: 1 if any FAIL on views with status "recommended", on a set, or in the
selection coverage (a view listed in generation-inputs.json -- characters[].views,
characters[].candidateViewsExcluded, props[].referenceViews -- without a
normalization record for the same asset/role or without its file); 0 otherwise.

Thresholds below are PROPOSED technical preflight limits, not approved art
budgets. Passing them proves only raster-level uniformity (canvas, background,
baseline, base width); it does not prove geometric consistency between views.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from pathlib import Path

import numpy as np
import PIL
import scipy
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path("art/imagegen/mvp-v1")
OUT_DIR = Path("docs/art-pipeline/imagegen-inputs")
SCRIPT_VERSION = "1.1.0"

# Mapping of ImageGen reference ids to official asset keys (06-asset-manifest.csv).
ASSET_KEYS = {
    "REF-MEDUSA": ("ASSET-MEDUSA-001", "hero"),
    "REF-KING-ARTHUR": ("ASSET-KING-ARTHUR-001", "hero"),
    "REF-MERLIN": ("ASSET-MERLIN-001", "sidekick"),
    "REF-HARPY": ("ASSET-HARPY-001", "sidekick"),
    "REF-BARREL": ("ASSET-DECOR-KIT-001", "prop:SM_Decor_Barrel"),
    "REF-LANTERN": ("ASSET-DECOR-KIT-001", "prop:SM_Decor_Lantern"),
    "REF-TABLE-BASE": ("ASSET-TABLE-BASE-001", "decor"),
}
# Normalization records (provenance: source file, recorded sha, parameters).
NORMALIZATION_FILES = [
    "normalized-views.json",
    "normalized-v3.json",
    "normalized-v4.json",
    "normalized-environment.json",
]
PROP_IDS = {"REF-BARREL", "REF-LANTERN", "REF-TABLE-BASE"}
# Tripo Studio multi-view has named slots front/left/right/back (see
# docs/game-design/evidence/ART-004/README.md). Other roles have no slot.
TRIPO_SLOTS = {"front", "left", "right", "back"}
# PROPOSED (not executed, not accepted) slot mapping for props; see CONSISTENCY-REVIEW.md.
PROP_SLOT_PROPOSALS = {
    "REF-BARREL": {"front": "ref-barrel-v3-front.png", "left": "ref-barrel-v3-side.png",
                   "note": "rotationally symmetric; bung only on front; top/three-quarter = human reference only"},
    "REF-LANTERN": {"front": "ref-lantern-v3-front.png", "back": "ref-lantern-v3-back.png",
                    "note": "side files left/right appear to use the opposite side convention to the characters "
                            "(door hinges vs latch); side slots empty until resolved by a human"},
    "REF-TABLE-BASE": {"front": "ref-table-base-v3-front.png", "left": "ref-table-base-v3-side.png",
                       "note": "rock underside only; top/frame modeled manually (S04 board contract)"},
}
REVIEW_DOC = "docs/art-pipeline/imagegen-inputs/CONSISTENCY-REVIEW.md"

# ---- PROPOSED preflight thresholds -------------------------------------------------
CANVAS = (1024, 1024)
MAX_BYTES = 20_000_000          # per-file limit observed in Tripo Studio form
BG_RGB = np.array([128, 128, 128], dtype=float)
BG_TOL = 12                      # same as normalize-views.py extraction
BBOX_THRESHOLD = 15              # same as PRODUCTION-NOTES height measurement
MIN_COMPONENT = 24
BORDER = 16
BORDER_UNIFORM_MIN = 0.999       # share of border pixels within BG_TOL of #808080
MARGIN_FAIL = 0.02               # figure touching / cropped at canvas edge
MARGIN_WARN = 0.095              # PRODUCTION-NOTES goal "поля не менее 10%" (1 px rounding)
BASELINE_SPREAD_MAX_PX = 2
BASE_WIDTH_REL_TOL = 0.03        # measured base width vs recorded normalization target
HEIGHT_SPREAD_WARN = 0.03        # relative spread of silhouette heights in a set
ANISOTROPY_WARN = 0.01           # |scaleX/scaleY - 1| from normalization record
LOW_CONTRAST_EDGE_WARN = 0.10    # share of pixels 2-4 px inside the silhouette within 30 of #808080
FG_COLOR_DRIFT_WARN = 30.0       # RGB distance of mean foreground color between views


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_of(path: str) -> int | None:
    m = re.search(r"-v(\d+)-", Path(path).name)
    return int(m.group(1)) if m else None


def load_json(rel: Path) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ---- selection + normalization records ---------------------------------------------
def load_selection() -> tuple[dict, dict[str, dict], dict[str, str]]:
    """generation-inputs.json, normalization rows by path, and replaces-chain (old -> new)."""
    gen = load_json(PACKAGE / "generation-inputs.json")
    norm: dict[str, dict] = {}
    replaced: dict[str, str] = {}
    for name in NORMALIZATION_FILES:
        for row in load_json(PACKAGE / name)["outputs"]:
            norm[row["path"]] = {**row, "normalizationRecord": (PACKAGE / name).as_posix()}
            if row.get("replaces"):
                replaced[row["replaces"]] = row["path"]
    return gen, norm, replaced


def selection_views(gen: dict) -> list[tuple[str, str, str, dict]]:
    """(refId, selection list, status, view) for every view listed in generation-inputs.json."""
    out: list[tuple[str, str, str, dict]] = []
    for char in gen.get("characters", []):
        for v in char.get("views", []):
            out.append((char.get("assetId"), "characters[].views", "recommended", v))
        for v in char.get("candidateViewsExcluded", []):
            out.append((char.get("assetId"), "characters[].candidateViewsExcluded", "candidate-excluded", v))
    for prop in gen.get("props", []):
        for v in prop.get("referenceViews", []):
            out.append((prop.get("assetId"), "props[].referenceViews", "recommended", v))
    return out


def selection_coverage(gen: dict, norm: dict[str, dict], package_root: Path) -> list[dict]:
    """Every selected view must have a normalization record of the same asset/role and an
    existing file. build_manifest() iterates normalization records only, so without this
    check a selected view lacking a record would silently drop out of the manifest."""
    rows = []
    for ref_id, source, status, v in selection_views(gen):
        path = v.get("path")
        problems = []
        if ref_id not in ASSET_KEYS:
            problems.append(f"refId {ref_id!r} is not mapped to an asset key (ASSET_KEYS)")
        rec = norm.get(path) if path else None
        if rec is None:
            problems.append("no normalization record in " + ", ".join(NORMALIZATION_FILES))
        else:
            if rec.get("assetId") != ref_id:
                problems.append(f"normalization record assetId {rec.get('assetId')!r} != {ref_id!r}")
            if v.get("role") and rec.get("role") != v.get("role"):
                problems.append(f"normalization record role {rec.get('role')!r} != selected role {v.get('role')!r}")
        if not path or not (package_root / path).is_file():
            problems.append("file missing")
        rows.append({
            "refId": ref_id,
            "role": v.get("role"),
            "path": (PACKAGE / path).as_posix() if path else None,
            "selectionList": source,
            "status": status,
            "check": "selected-view-has-normalization-record-and-file",
            "result": "FAIL" if problems else "PASS",
            "detail": {"normalizationRecord": rec.get("normalizationRecord") if rec else None,
                       "problems": problems},
        })
    return rows


# ---- manifest ----------------------------------------------------------------------
def build_manifest(gen: dict, norm: dict[str, dict], replaced: dict[str, str]) -> dict:
    status: dict[str, tuple[str, str | None]] = {}
    set_notes: dict[str, str] = {}
    for char in gen["characters"]:
        for v in char["views"]:
            status[v["path"]] = ("recommended", v.get("sha256"))
        for v in char.get("candidateViewsExcluded", []):
            status[v["path"]] = ("candidate-excluded", v.get("sha256"))
        set_notes[char["assetId"]] = char.get("notes", "")
    for prop in gen["props"]:
        for v in prop["referenceViews"]:
            status[v["path"]] = ("recommended", v.get("sha256"))
        set_notes[prop["assetId"]] = prop.get("scope", "")

    views = []
    for path, row in sorted(norm.items()):
        ref_id = row["assetId"]
        if ref_id not in ASSET_KEYS:
            continue  # board / other environment references are out of T2 scope
        st, sel_sha = status.get(path, (None, None))
        if st is None:
            st = "superseded" if path in replaced else "unclassified"
        asset_key, kind = ASSET_KEYS[ref_id]
        params = row.get("parameters", {})
        scale_xy = params.get("scaleXY")
        if scale_xy is None and "scale" in params:
            scale_xy = [params["scale"], params["scale"]]
        views.append({
            "refId": ref_id,
            "assetKey": asset_key,
            "kind": kind,
            "role": row["role"],
            "tripoSlot": row["role"] if (row["role"] in TRIPO_SLOTS and ref_id not in PROP_IDS) else None,
            "version": version_of(path),
            "status": st,
            "supersededBy": replaced.get(path),
            "path": (PACKAGE / path).as_posix(),
            "sha256Recorded": row.get("sha256"),
            "sha256Selection": sel_sha,
            "source": (PACKAGE / row["source"]).as_posix() if row.get("source") else None,
            "sourceSha256Recorded": row.get("sourceSha256"),
            "normalizationRecord": row["normalizationRecord"],
            "normalization": {
                "method": row.get("method"),
                "targetBaseWidthPx": params.get("targetBaseWidthPx") or params.get("targetBaseWidth"),
                "baseDiameterUu": params.get("baseDiameterUu"),
                "scaleXY": scale_xy,
                "baseline": params.get("baseline"),
            },
        })

    sets = []
    for ref_id, (asset_key, kind) in ASSET_KEYS.items():
        own = [v for v in views if v["refId"] == ref_id]
        rec = [v for v in own if v["status"] == "recommended"]
        sets.append({
            "refId": ref_id,
            "assetKey": asset_key,
            "kind": kind,
            "recommendedTripoSlots": {v["tripoSlot"]: v["path"] for v in rec if v["tripoSlot"]},
            "emptyTripoSlots": sorted(TRIPO_SLOTS - {v["tripoSlot"] for v in rec if v["tripoSlot"]})
            if ref_id not in PROP_IDS else None,
            "recommendedViews": [v["path"] for v in rec],
            "candidateViews": [v["path"] for v in own if v["status"] == "candidate-excluded"],
            "supersededViews": [v["path"] for v in own if v["status"] == "superseded"],
            "selectionNote": set_notes.get(ref_id, ""),
            "propTripoSlotProposal": ({"status": "proposed", **PROP_SLOT_PROPOSALS[ref_id]}
                                      if ref_id in PROP_SLOT_PROPOSALS else None),
            "manualReview": f"{REVIEW_DOC}#{ref_id.lower()}",
        })

    return {
        "schema": "unmatched.tripo-pipeline.imagegen-inputs/1",
        "status": "measured; reference selection only, no Tripo upload or generation performed by this manifest",
        "selectionSource": (PACKAGE / "generation-inputs.json").as_posix(),
        "selectionRevision": gen.get("revision"),
        "tripoSlotConvention": (
            "role name == Tripo Studio multi-view slot name (front/left/right/back). "
            "Confirmed only for the Medusa pilot d562f057 (front/left/back, right empty); "
            "not re-verified for other characters."
        ),
        "notes": [
            "Normalization of canvas/base width/baseline does not prove geometric consistency between views.",
            "Medusa right slot intentionally empty: v5/v6 right are not in the recommended 3D set (PRODUCTION-NOTES, ART-004 pilot).",
            "Prop roles side/top/three-quarter have no Tripo multi-view slot; tripoSlot is null until a mapping is decided.",
        ],
        "sets": sets,
        "views": views,
    }


# ---- per-image measurement ---------------------------------------------------------
def extract_mask(rgb: np.ndarray) -> np.ndarray:
    """Boundary-connected background removal, identical to normalize-views.py."""
    edges = np.concatenate([rgb[:BORDER].reshape(-1, 3), rgb[-BORDER:].reshape(-1, 3),
                            rgb[:, :BORDER].reshape(-1, 3), rgb[:, -BORDER:].reshape(-1, 3)])
    bg = np.median(edges, axis=0)
    eligible = np.max(np.abs(rgb.astype(float) - bg), axis=2) < BG_TOL
    seed = np.zeros(eligible.shape, bool)
    seed[[0, -1], :] = eligible[[0, -1], :]
    seed[:, [0, -1]] = eligible[:, [0, -1]]
    fg = ~ndi.binary_propagation(seed, mask=eligible)
    labels, _ = ndi.label(fg)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= MIN_COMPONENT
    keep[0] = False
    return keep[labels]


def measure(path: Path) -> dict:
    with Image.open(path) as im:
        fmt, mode, size = im.format, im.mode, im.size
        info_icc = "icc_profile" in im.info
        rgb = np.asarray(im.convert("RGB"))
    h, w = rgb.shape[:2]
    diff = np.max(np.abs(rgb.astype(float) - BG_RGB), axis=2)
    ring = np.ones((h, w), bool)
    ring[BORDER:-BORDER, BORDER:-BORDER] = False
    border_uniform = float(np.mean(diff[ring] < BG_TOL))
    border_median = np.median(rgb[ring].reshape(-1, 3), axis=0).tolist()

    mask = extract_mask(rgb)
    labels, n_comp = ndi.label(mask)
    comp_sizes = sorted(np.bincount(labels.ravel())[1:].tolist(), reverse=True)
    ys, xs = np.nonzero(mask)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    height = y1 - y0 + 1
    width = x1 - x0 + 1

    # Threshold bbox, comparable with PRODUCTION-NOTES Harpy heights.
    tys, txs = np.nonzero(diff > BBOX_THRESHOLD)
    thr_bbox = [int(txs.min()), int(tys.min()), int(txs.max()), int(tys.max())]

    base_rows = []
    for y in range(max(y0, y1 - 39), y1 + 1):
        xx = np.flatnonzero(mask[y])
        if len(xx):
            base_rows.append((int(xx[-1] - xx[0] + 1), float((xx[-1] + xx[0]) / 2)))
    base_width, base_cx = max(base_rows)

    # Ring 2-4 px inside the silhouette: skips the antialiased rim, measures whether
    # the figure's own edge colors are close to the gray background (risk for
    # Tripo's background removal / silhouette extraction).
    edge = ndi.binary_erosion(mask, iterations=2) & ~ndi.binary_erosion(mask, iterations=4)
    edge_diff = diff[edge]
    low_contrast_edge = float(np.mean(edge_diff < 30)) if edge_diff.size else 0.0
    fg_mean = rgb[mask].reshape(-1, 3).mean(axis=0)

    margins = {"left": x0, "right": w - 1 - x1, "top": y0, "bottom": h - 1 - y1}
    return {
        "format": fmt, "mode": mode, "pixels": list(size), "bytes": path.stat().st_size,
        "hasIccProfile": info_icc,
        "background": {"borderMedianRgb": border_median, "borderUniformShare": round(border_uniform, 5)},
        "silhouette": {
            "bboxXYXYInclusive": [x0, y0, x1, y1],
            "thresholdBboxXYXYInclusive": thr_bbox,
            "heightPx": height, "widthPx": width,
            "heightShareOfCanvas": round(height / h, 4),
            "fillShareOfCanvas": round(float(mask.mean()), 4),
            "fillShareOfBbox": round(float(mask.sum()) / (height * width), 4),
            "marginsPx": margins,
            "minMarginShare": round(min(margins.values()) / min(h, w), 4),
            "baselineY": y1,
            "components": int(n_comp),
            "largestComponentsPx": comp_sizes[:4],
            "baseWidthPx": base_width, "baseCenterX": base_cx,
            "lowContrastEdgeShare": round(low_contrast_edge, 4),
            "foregroundMeanRgb": [round(float(c), 1) for c in fg_mean],
        },
        "_mask": mask,
    }


def aligned_mirror_iou(a: dict, b: dict) -> float:
    """IoU of silhouette A and horizontally mirrored silhouette B, both aligned on
    base center X and baseline. For an orthographic figure, front vs mirrored back
    (and left vs mirrored right) silhouettes coincide. The ImageGen views are
    perspective renders, so this is only a diagnostic, not a geometric proof."""
    ma, mb = a["_mask"], np.fliplr(b["_mask"])
    w = ma.shape[1]
    cb = (w - 1) - b["silhouette"]["baseCenterX"]
    dx = int(round(a["silhouette"]["baseCenterX"] - cb))
    dy = a["silhouette"]["baselineY"] - b["silhouette"]["baselineY"]
    mb = np.roll(np.roll(mb, dx, axis=1), dy, axis=0)
    inter = np.logical_and(ma, mb).sum()
    union = np.logical_or(ma, mb).sum()
    return round(float(inter) / float(union), 4) if union else 0.0


def check_view(v: dict, m: dict, actual_sha: str, compare_sha: str | None) -> list[dict]:
    out: list[dict] = []

    def add(check, level, detail):
        out.append({"check": check, "result": level, "detail": detail})

    add("sha256-matches-normalization-record",
        "PASS" if actual_sha == v["sha256Recorded"] else "FAIL", {"actual": actual_sha, "recorded": v["sha256Recorded"]})
    if v["sha256Selection"]:
        add("sha256-matches-generation-inputs",
            "PASS" if actual_sha == v["sha256Selection"] else "FAIL", {"recorded": v["sha256Selection"]})
    if compare_sha is not None:
        add("sha256-matches-compare-root", "PASS" if compare_sha == actual_sha else "FAIL", {"compare": compare_sha})
    add("format-png", "PASS" if m["format"] == "PNG" else "FAIL", m["format"])
    add("mode-rgb-no-alpha", "PASS" if m["mode"] == "RGB" else "FAIL", m["mode"])
    add("canvas-1024", "PASS" if tuple(m["pixels"]) == CANVAS else "FAIL", m["pixels"])
    add("bytes-le-20MB", "PASS" if m["bytes"] <= MAX_BYTES else "FAIL", m["bytes"])
    bu = m["background"]["borderUniformShare"]
    add("background-808080-uniform", "PASS" if bu >= BORDER_UNIFORM_MIN else "FAIL",
        {"borderUniformShare": bu, "borderMedianRgb": m["background"]["borderMedianRgb"]})
    s = m["silhouette"]
    mm = s["minMarginShare"]
    add("margins", "FAIL" if mm < MARGIN_FAIL else ("WARN" if mm < MARGIN_WARN else "PASS"), s["marginsPx"])
    add("single-connected-figure", "PASS" if s["components"] == 1 else "WARN",
        {"components": s["components"], "largestPx": s["largestComponentsPx"]})
    target = v["normalization"]["targetBaseWidthPx"]
    if target and v["kind"] in ("hero", "sidekick"):
        rel = abs(s["baseWidthPx"] - target) / target
        add("base-width-matches-normalization-target", "PASS" if rel <= BASE_WIDTH_REL_TOL else "FAIL",
            {"measuredPx": s["baseWidthPx"], "targetPx": round(target, 2), "relDiff": round(rel, 4)})
        add("base-centered-x512", "PASS" if abs(s["baseCenterX"] - 511.5) <= 4 else "WARN", s["baseCenterX"])
    sxy = v["normalization"]["scaleXY"]
    if sxy:
        an = abs(sxy[0] / sxy[1] - 1)
        add("normalization-isotropic", "PASS" if an <= ANISOTROPY_WARN else "WARN",
            {"scaleXY": [round(x, 4) for x in sxy], "anisotropy": round(an, 4)})
    lc = s["lowContrastEdgeShare"]
    add("silhouette-edge-contrast-vs-background", "PASS" if lc <= LOW_CONTRAST_EDGE_WARN else "WARN",
        {"shareOfInnerEdgePixelsWithin30OfGray": lc})
    return out


def check_set(ref_id: str, members: list[dict], meas: dict[str, dict]) -> dict:
    """Cross-view checks on the recommended set and on every candidate combined with it."""
    def stats(paths):
        ms = [meas[p]["silhouette"] for p in paths]
        heights = [x["heightPx"] for x in ms]
        base = [x["baseWidthPx"] for x in ms]
        baseline = [x["baselineY"] for x in ms]
        cx = [x["baseCenterX"] for x in ms]
        med = float(np.median(heights))
        cols = np.array([x["foregroundMeanRgb"] for x in ms])
        drift = float(max(np.linalg.norm(a - b) for a in cols for b in cols)) if len(cols) > 1 else 0.0
        return {
            "views": paths,
            "heightsPx": heights,
            "heightSpreadRel": round((max(heights) - min(heights)) / med, 4),
            "baseWidthsPx": base,
            "baseWidthSpreadRel": round((max(base) - min(base)) / float(np.median(base)), 4),
            "baselineYs": baseline,
            "baselineSpreadPx": max(baseline) - min(baseline),
            "baseCenterXs": cx,
            "widthsPx": [x["widthPx"] for x in ms],
            "foregroundMeanColorMaxDrift": round(drift, 1),
        }

    by_role = {}
    rec = [v for v in members if v["status"] == "recommended"]
    for v in rec:
        by_role[v["role"]] = v["path"]
    result = {"refId": ref_id, "checks": []}
    if len(rec) < 2:
        result["checks"].append({"check": "set-size", "result": "FAIL", "detail": len(rec)})
        return result
    st = stats([v["path"] for v in rec])
    result["recommendedSet"] = st
    is_char = rec[0]["kind"] in ("hero", "sidekick")

    def add(check, level, detail):
        result["checks"].append({"check": check, "result": level, "detail": detail})

    if is_char:
        add("front-present", "PASS" if "front" in by_role else "FAIL", sorted(by_role))
        add("baseline-spread", "PASS" if st["baselineSpreadPx"] <= BASELINE_SPREAD_MAX_PX else "FAIL",
            st["baselineYs"])
        add("base-width-spread", "PASS" if st["baseWidthSpreadRel"] <= BASE_WIDTH_REL_TOL else "FAIL",
            st["baseWidthsPx"])
        add("height-spread", "PASS" if st["heightSpreadRel"] <= HEIGHT_SPREAD_WARN else "WARN", st["heightsPx"])
        add("foreground-color-drift", "PASS" if st["foregroundMeanColorMaxDrift"] <= FG_COLOR_DRIFT_WARN else "WARN",
            st["foregroundMeanColorMaxDrift"])
        # Estimated figure height in uu from the base diameter used for normalization.
        diam = rec[0]["normalization"]["baseDiameterUu"]
        if diam:
            est = [round(meas[p]["silhouette"]["heightPx"] / meas[p]["silhouette"]["baseWidthPx"] * diam, 1)
                   for p in st["views"]]
            result["estimatedFigureHeightUu"] = {
                "values": est, "baseDiameterUuUsedForNormalization": diam,
                "note": "measured on 2D perspective reference incl. base; not a model dimension or budget",
            }
    else:
        ortho = [v["path"] for v in rec if v["role"] in ("front", "left", "right", "back", "side")]
        if len(ortho) >= 2:
            so = stats(ortho)
            result["orthographicRoleSubset"] = so
            add("baseline-spread-ortho-roles", "PASS" if so["baselineSpreadPx"] <= BASELINE_SPREAD_MAX_PX else "FAIL",
                so["baselineYs"])
            add("height-spread-ortho-roles", "PASS" if so["heightSpreadRel"] <= HEIGHT_SPREAD_WARN else "WARN",
                so["heightsPx"])
        others = [v["role"] for v in rec if v["role"] not in ("front", "left", "right", "back", "side")]
        if others:
            add("non-multiview-roles-present", "WARN",
                {"roles": others, "note": "no Tripo multi-view slot; use only as human reference"})
    # Mirror silhouette diagnostics across all available current views (recommended + candidates).
    cur = {v["role"]: v["path"] for v in members if v["status"] in ("recommended", "candidate-excluded")}
    mirror = {}
    for a, b in (("front", "back"), ("left", "right")):
        if a in cur and b in cur:
            mirror[f"{a}~mirror({b})"] = {
                "iou": aligned_mirror_iou(meas[cur[a]], meas[cur[b]]),
                "widthsPx": [meas[cur[a]]["silhouette"]["widthPx"], meas[cur[b]]["silhouette"]["widthPx"]],
                "views": [cur[a], cur[b]],
            }
    if mirror:
        result["mirrorSilhouetteDiagnostics"] = {
            "note": "diagnostic only; perspective ImageGen views, low IoU flags pose/prop disagreement, high IoU does not prove 3D consistency",
            "pairs": mirror,
        }
    cands = [v for v in members if v["status"] == "candidate-excluded"]
    if cands:
        result["withCandidates"] = [
            {"candidate": c["path"], **{k: val for k, val in stats([v["path"] for v in rec] + [c["path"]]).items()
                                        if k != "views"}}
            for c in cands
        ]
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--compare-root", default=None,
                    help="another checkout; verify identical sha256 of every listed view there")
    ap.add_argument("--check-only", action="store_true", help="do not write manifest/report")
    args = ap.parse_args()

    gen, norm, replaced = load_selection()
    manifest = build_manifest(gen, norm, replaced)
    coverage = selection_coverage(gen, norm, ROOT / PACKAGE)
    compare_root = Path(args.compare_root) if args.compare_root else None
    meas: dict[str, dict] = {}
    view_reports = []
    for v in manifest["views"]:
        p = ROOT / v["path"]
        if not p.exists():
            view_reports.append({"path": v["path"], "status": v["status"],
                                 "checks": [{"check": "exists", "result": "FAIL", "detail": None}]})
            continue
        actual = sha256(p)
        v["sha256"] = actual
        v["bytes"] = p.stat().st_size
        src = ROOT / v["source"] if v["source"] else None
        v["sourceSha256Actual"] = sha256(src) if src and src.exists() else None
        cmp_sha = None
        if compare_root is not None:
            cp = compare_root / v["path"]
            cmp_sha = sha256(cp) if cp.exists() else "missing"
        m = measure(p)
        meas[v["path"]] = m
        checks = check_view(v, m, actual, cmp_sha)
        if v["sourceSha256Recorded"]:
            checks.append({"check": "source-sha256-matches-record",
                           "result": "PASS" if v["sourceSha256Actual"] == v["sourceSha256Recorded"] else "FAIL",
                           "detail": {"source": v["source"], "actual": v["sourceSha256Actual"]}})
        view_reports.append({
            "path": v["path"], "refId": v["refId"], "role": v["role"], "status": v["status"],
            "measurements": {k: val for k, val in m.items() if k != "_mask"},
            "checks": checks,
        })
        v["pixels"] = m["pixels"]
        v["mode"] = m["mode"]
        v["format"] = m["format"]

    set_reports = []
    for s in manifest["sets"]:
        members = [v for v in manifest["views"] if v["refId"] == s["refId"] and v["path"] in meas]
        set_reports.append(check_set(s["refId"], members, meas))

    def tally(reports, only_status=None):
        t = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for r in reports:
            if only_status and r.get("status") not in only_status:
                continue
            for c in r["checks"]:
                t[c["result"]] += 1
        return t

    fails_recommended = [
        {"path": r["path"], "check": c["check"]}
        for r in view_reports if r["status"] == "recommended"
        for c in r["checks"] if c["result"] == "FAIL"
    ] + [
        {"set": r["refId"], "check": c["check"]}
        for r in set_reports for c in r["checks"] if c["result"] == "FAIL"
    ]
    fails_coverage = [{"path": r["path"], "refId": r["refId"], "check": r["check"], "problems": r["detail"]["problems"]}
                      for r in coverage if r["result"] == "FAIL"]
    coverage_tally = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for r in coverage:
        coverage_tally[r["result"]] += 1
    report = {
        "schema": "unmatched.tripo-pipeline.imagegen-input-checks/1",
        "status": "measured; automatic raster checks only — not geometric consistency, not art acceptance",
        "tool": {
            "script": "tools/tripo-pipeline/check_inputs.py", "version": SCRIPT_VERSION,
            "python": platform.python_version(), "pillow": PIL.__version__,
            "numpy": np.__version__, "scipy": scipy.__version__,
        },
        "compareRoot": compare_root.as_posix() if compare_root else None,
        "thresholdsProposed": {
            "canvas": list(CANVAS), "maxBytes": MAX_BYTES, "backgroundRgb": BG_RGB.astype(int).tolist(),
            "backgroundTolerance": BG_TOL, "borderPx": BORDER, "borderUniformMin": BORDER_UNIFORM_MIN,
            "bboxThreshold": BBOX_THRESHOLD, "minComponentPx": MIN_COMPONENT,
            "marginFail": MARGIN_FAIL, "marginWarn": MARGIN_WARN,
            "baselineSpreadMaxPx": BASELINE_SPREAD_MAX_PX, "baseWidthRelTol": BASE_WIDTH_REL_TOL,
            "heightSpreadWarn": HEIGHT_SPREAD_WARN, "anisotropyWarn": ANISOTROPY_WARN,
            "lowContrastEdgeWarn": LOW_CONTRAST_EDGE_WARN, "fgColorDriftWarn": FG_COLOR_DRIFT_WARN,
        },
        "summary": {
            "views": len(view_reports),
            "recommendedViewChecks": tally(view_reports, {"recommended"}),
            "allViewChecks": tally(view_reports),
            "setChecks": tally(set_reports),
            "selectionCoverageChecks": coverage_tally,
            "failuresOnRecommended": fails_recommended,
            "failuresOnSelectionCoverage": fails_coverage,
            "exitCode": 1 if (fails_recommended or fails_coverage) else 0,
        },
        "selectionCoverage": {
            "note": ("every view listed in generation-inputs.json (characters[].views, "
                     "characters[].candidateViewsExcluded, props[].referenceViews) must have a normalization "
                     "record of the same asset/role and an existing file; otherwise it would be missing "
                     "from manifest.json without any other FAIL"),
            "selectionSource": (PACKAGE / "generation-inputs.json").as_posix(),
            "checks": coverage,
        },
        "sets": set_reports,
        "views": view_reports,
    }

    if not args.check_only:
        out = ROOT / args.out_dir
        out.mkdir(parents=True, exist_ok=True)
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "checks-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = report["summary"]
    print(json.dumps({"views": s["views"], "recommended": s["recommendedViewChecks"], "all": s["allViewChecks"],
                      "sets": s["setChecks"], "selectionCoverage": s["selectionCoverageChecks"],
                      "failuresOnRecommended": len(fails_recommended),
                      "failuresOnSelectionCoverage": len(fails_coverage)}))
    for f in fails_coverage:
        print(f"FAIL selection coverage: {f['path']} ({f['refId']}): {'; '.join(f['problems'])}", file=sys.stderr)
    return s["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
