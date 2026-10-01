"""ENV-MAPS P7 (ENV-U15) concept paste, track A: bake the UE textures of the camera-projected concept surround.

The plates (Codex imagegen edits of the concept, out of git - ENV-U3 / ENV-U7: they are painted over a render of the
original map) are resampled ONCE, with a classic Lanczos-3 kernel (ENV-U6: no AI upscale here), into textures whose
texels are laid out linearly in the concept camera's image plane C0 (pinhole HFOV 35, pitch -55, yaw -90, distance
1.45 x fit, 1920 x 1080; tools/art/concept_paste/cp_common.py). So a material only has to project the world position
through C0 and map the C0 pixel linearly into the texture rect:

    u = (c0x - rect.x0) / (rect.x1 - rect.x0),  v = (c0y - rect.y0) / (rect.y1 - rect.y0)
    c0x = (1 + sx) / 2 * 1920, c0y = (1 - sy) / 2 * 1080, (sx, sy) = C0 NDC of the board-space position

Per texel: C0 pixel -> (frame-band rubber fill on the ground plane, design.json 2_mask) -> registration homography
(C0 px -> plate framing px, tools/art/concept_paste/registration.json) -> plate pixel -> Lanczos-3 (kernel widened by
the minification factor on each axis; edge clamp outside the plate = the Marmoreal edge fill).

Textures per map (the <map>.paste.json "bake" block; T_<Name>_Concept<Key>.png, 8-bit sRGB):
  PlateA  RGBA 4096 x 2048 over the concept frame C0 [0, 1920] x [0, 1080]; RGB = the registered colour plate with the
          painted-frame band filled, A = island matte (3 px feather) x NOT under the 3D frame (cut 2 uu under the outer
          foot of frame-002) -> the masked paste material (opacity mask 0.5)
  PlateB  RGBA 4096 x 2048 over the outpainted range C0 [-384, 2304] x [-216, 1296] (same content, lower density)
  Sea     RGB  2048 x 1024 over the outpainted range: the sea layer (sea plane Z -300 + sky cylinder): the plate outside
          the island matte, inside it the sea-sky plate matched by mean / std (disocclusion fill)
  Water   RGB  2048 x 1024 over the outpainted range (optional, Sarpedon): R painted waterfall, G painted bay surf,
          B open sea (1 - island) - masks for the flow / foam animation of the paste material (overlays of the spec)

Outputs go OUT of git (default <repo>/scraped-data/derived/concept-paste/<map>/, gitignored like the map surfaces);
git holds this script, the parameters and manifest.<map>.json (input / output sha256, texel densities, statistics, the
material contract: identity homography, RectA / RectB as (x0, y0, w, h) in C0 px).
Deterministic (same inputs + parameters -> the same bytes on this machine) and idempotent (an output whose sha256
already equals the manifest is not rewritten unless --force).

  python -B tools/art/concept_paste/cp_bake.py registration           # registration.json from the P7a proto outputs
  python -B tools/art/concept_paste/cp_bake.py bake sarpedon [marmoreal] [--out DIR] [--force]
  python -B tools/art/concept_paste/cp_bake.py check [sarpedon marmoreal] [--out DIR]   # sha256 only, no resample
  python -B tools/art/concept_paste/cp_bake.py contract sarpedon      # the profile-block values (identity H, rects)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cp_common as C  # noqa: E402
import paste_proto as pp  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
REPO = C.REPO
OUT_DEFAULT = REPO / "scraped-data" / "derived" / "concept-paste"
PROTO = Path("C:/tmp/envmaps-research/p7/proto")
REGISTRATION = HERE / "registration.json"
SCHEMA_REG = "unmatched.concept-paste.registrations/1"
SCHEMA_DERIVED = "unmatched.concept-paste.derived/1"
KINDS = ("paste", "sea", "water")
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


# ------------------------------------------------------------------ small helpers
def text_sha256_lf(path: Path) -> str:
    """sha256 of a text file with LF line ends (stable across checkouts with autocrlf)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canon_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def load_spec(map_key: str) -> dict:
    return pp.load_spec(map_key)


def plate_path(spec: dict, entry: dict) -> Path:
    p = Path(entry["file"])
    return p if p.is_absolute() else Path(spec["plates"]["dir"]) / p


def reflect(x, period: float):
    """Mirror coordinates into [0, period] (continuous px)."""
    t = np.mod(np.asarray(x, np.float64), 2 * period)
    return np.where(t > period, 2 * period - t, t)


def smoothstep(e0: float, e1: float, x):
    t = np.clip((np.asarray(x, np.float32) - e0) / max(e1 - e0, 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ registration file (from the P7a proto)
REG_TAGS = {"sarpedon": {"concept": "registration.json", "clean": "registration-clean.json",
                         "plate2x": "registration-plate2x.json", "extended": "registration-extended.json",
                         "extended2x": "registration-extended2x.json"},
            "marmoreal": {"concept": "registration.json"}}


def collect_registration(proto: Path = PROTO) -> dict:
    """registration.json (git): per map and plate tag the homography C0 px -> plate-framing px (1920 x 1080 frame of the
    plate's concept framing, register.py) with the plate sha256 and the residual statistics; the point lists stay in
    the proto folder (out of git)."""
    out = {"schema": SCHEMA_REG, "status": "измерено (P7a register.py, NCC of gradient magnitude, robust homography)",
           "convention": "H maps a true C0 pixel (base render of the original map at the concept camera, continuous px, "
                         "1920 x 1080) to the same point in the plate's concept framing resized to 1920 x 1080 "
                         "(crop = that framing inside a larger plate); plate px = crop.x0 + Hx / 1920 * crop.w",
           "maps": {}}
    for key, tags in REG_TAGS.items():
        out["maps"][key] = {}
        for tag, name in tags.items():
            rep = json.loads((proto / key / name).read_text(encoding="utf-8"))
            con = rep["concept"]
            out["maps"][key][tag] = {
                "plate": con["file"], "sha256": con["sha256"], "crop": con.get("crop"),
                "base": rep["base"]["file"], "baseSha256": rep["base"]["sha256"],
                "H": rep["homography_base_to_concept"],
                "points": rep["points"], "identityErrorPx": rep["identity_error_px"],
                "homographyResidualPx": rep["homography_residual_px"], "homographyLooPx": rep["homography_loo_px"],
                "tpsLooPx": rep["tps_loo_px"], "mapCornerShiftPx": rep["map_corner_shift_px"]}
    return out


def load_registration() -> dict:
    reg = json.loads(REGISTRATION.read_text(encoding="utf-8"))
    if reg.get("schema") != SCHEMA_REG:
        raise RuntimeError(f"{REGISTRATION}: schema {reg.get('schema')!r}")
    return reg


def colour_registration(map_key: str, spec: dict, reg: dict | None = None) -> dict:
    reg = reg or load_registration()
    tag = spec["bake"]["colourTag"]
    entry = reg["maps"][map_key][tag]
    if Path(entry["plate"]).name != Path(spec["plates"]["colour"]["file"]).name:
        raise RuntimeError(f"{map_key}: registration tag {tag} is for {entry['plate']}, the colour plate is "
                           f"{spec['plates']['colour']['file']}")
    x0, y0, rw, rh = spec["plates"]["colour"]["conceptRectPx"]
    crop = entry.get("crop") or [0, 0, *spec["plates"]["colour"]["size"]]
    if [float(v) for v in crop] != [float(x0), float(y0), float(x0 + rw), float(y0 + rh)]:
        raise RuntimeError(f"{map_key}: registration crop {crop} != the spec conceptRectPx {[x0, y0, rw, rh]}")
    return entry


# ------------------------------------------------------------------ Lanczos resampling (classic, ENV-U6)
def lanczos_kernel(x: np.ndarray, a: int) -> np.ndarray:
    x = np.abs(x)
    out = np.where(x < 1e-6, 1.0, a * np.sin(np.pi * x) * np.sin(np.pi * x / a) / np.maximum(np.pi * np.pi * x * x, 1e-12))
    return np.where(x < a, out, 0.0).astype(np.float32)


def lanczos_sample(img: np.ndarray, px: np.ndarray, py: np.ndarray, sx: float = 1.0, sy: float = 1.0,
                   a: int = 3) -> np.ndarray:
    """Sample img (H, W, C) at continuous pixel coordinates (centres at i + 0.5) with a separable Lanczos-a kernel,
    widened by sx / sy >= 1 (source px per output texel) against aliasing when minifying; edge clamp; the weights are
    normalised (no gain change), the result is clipped to [0, 1]."""
    h, w = img.shape[:2]
    sx, sy = max(float(sx), 1.0), max(float(sy), 1.0)
    u = np.asarray(px, np.float64) - 0.5
    v = np.asarray(py, np.float64) - 0.5
    u0, v0 = np.floor(u).astype(np.int64), np.floor(v).astype(np.int64)
    rx, ry = int(math.ceil(a * sx)), int(math.ceil(a * sy))
    wxs, ixs = [], []
    for k in range(-rx + 1, rx + 1):
        xi = u0 + k
        wxs.append(lanczos_kernel((u - xi) / sx, a))
        ixs.append(np.clip(xi, 0, w - 1))
    acc = np.zeros(u.shape + (img.shape[2],), np.float32)
    wsum = np.zeros(u.shape, np.float32)
    for k in range(-ry + 1, ry + 1):
        yi = v0 + k
        wy = lanczos_kernel((v - yi) / sy, a)
        yc = np.clip(yi, 0, h - 1)
        row = np.zeros_like(acc)
        rs = np.zeros(u.shape, np.float32)
        for wx, xc in zip(wxs, ixs):
            row += wx[..., None] * img[yc, xc]
            rs += wx
        acc += wy[..., None] * row
        wsum += wy * rs
    return np.clip(acc / np.where(np.abs(wsum) < 1e-6, 1.0, wsum)[..., None], 0.0, 1.0)


# ------------------------------------------------------------------ texel grids
def texel_c0(rect, size, rows=None):
    """C0 coordinates of the texel centres of a texture (size = (w, h)) laid over rect (x0, y0, x1, y1);
    rows = optional slice of texture rows."""
    x0, y0, x1, y1 = (float(v) for v in rect)
    w, h = size
    xs = x0 + (np.arange(w) + 0.5) * (x1 - x0) / w
    ys = y0 + (np.arange(h) + 0.5) * (y1 - y0) / h
    if rows is not None:
        ys = ys[rows]
    return np.meshgrid(xs, ys)


def island_matte(spec: dict, rect, size) -> np.ndarray:
    """Island matte (C0 polygon, feathered: gaussian of sigma featherPx / 2 C0 px) on the texel grid."""
    im = spec["geometry"]["islandMatte"]
    w, h = size
    x0, y0, x1, y1 = (float(v) for v in rect)
    xs = x0 + (np.arange(w) + 0.5) * (x1 - x0) / w
    ys = y0 + (np.arange(h) + 0.5) * (y1 - y0) / h
    m = pp.poly_mask_grid(im["poly"], xs, ys, 2)
    sig = float(im.get("featherPx", 3)) / 2.0
    return ndimage.gaussian_filter(m, (sig * h / (y1 - y0), sig * w / (x1 - x0))).astype(np.float32)


def under_frame(spec: dict, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    u = float(spec["cut"]["underFrameUU"])
    return (np.abs(X) < C.FRAME_HX - u) & (np.abs(Y) < C.FRAME_HY - u)


def sample_points(spec: dict, cam: C.Cam, FX: np.ndarray, FY: np.ndarray):
    """(C0 x, C0 y) to sample for each texel C0 position + the under-frame flag: the painted-frame band of the ground
    plane is rubber-stretched (paste_proto.frame_band)."""
    gz = float(spec["geometry"]["groundZ"])
    X, Y = pp.ground_xy(cam, FX, FY, gz)
    under, _band, MX, MY = pp.frame_band(spec, X, Y)
    moved = ((np.abs(MX - X) > 1e-3) | (np.abs(MY - Y) > 1e-3)) & ~under
    SX, SY = FX.astype(np.float64).copy(), FY.astype(np.float64).copy()
    if moved.any():
        q = cam.project(np.stack([MX[moved], MY[moved], np.full(int(moved.sum()), gz)], -1))[0]
        SX[moved], SY[moved] = q[:, 0], q[:, 1]
    return SX, SY, under_frame(spec, X, Y), moved


# ------------------------------------------------------------------ bake one texture
def bake_texture(map_key: str, spec: dict, name: str, tex: dict, plates: dict, H: np.ndarray, log=print) -> dict:
    """RGB(A) float image of one texture entry of the bake block."""
    cam = C.concept_cam()
    kind = tex["kind"]
    w, h = tex["size"]
    rect = tex["rectC0"]
    sp = spec["plates"]["colour"]
    plate = plates["colour"]
    ph, pw = plate.shape[:2]
    rw, rh = sp["conceptRectPx"][2], sp["conceptRectPx"][3]
    a = int(spec["bake"].get("lanczosA", 3))
    # source px per texel (constant: linear maps + a near-identity homography)
    sx = (rw / C.W) * (rect[2] - rect[0]) / w
    sy = (rh / C.H) * (rect[3] - rect[1]) / h
    island = island_matte(spec, rect, (w, h))
    chunk = int(spec["bake"].get("chunkRows", 64))
    rgb = np.zeros((h, w, 3), np.float32)
    under_all = np.zeros((h, w), bool)
    moved_n = 0
    t0 = time.time()
    for r0 in range(0, h, chunk):
        rows = slice(r0, min(h, r0 + chunk))
        FX, FY = texel_c0(rect, (w, h), rows)
        SX, SY, under, moved = sample_points(spec, cam, FX, FY)
        PX, PY = pp.c0_to_plate(sp, H, SX, SY)
        rgb[rows] = lanczos_sample(plate, PX, PY, sx, sy, a)
        under_all[rows] = under
        moved_n += int(moved.sum())
    of = spec["bake"].get("outsideFrame")
    if of:  # no outpaint (Marmoreal flag variant): fade the edge clamp outside the concept frame to a dark border tone
        FX, FY = texel_c0(rect, (w, h))
        dist = np.hypot(np.maximum(np.maximum(-FX, FX - C.W), 0), np.maximum(np.maximum(-FY, FY - C.H), 0))
        x0p, y0p, rwp, rhp = (int(v) for v in sp["conceptRectPx"])
        border = np.concatenate([plate[y0p, x0p:x0p + rwp], plate[y0p + rhp - 1, x0p:x0p + rwp],
                                 plate[y0p:y0p + rhp, x0p], plate[y0p:y0p + rhp, x0p + rwp - 1]])
        dark = np.median(border, 0) * float(of["darkGain"])
        t = smoothstep(0.0, float(of["fadePx"]), dist)[..., None]
        blur = ndimage.gaussian_filter(rgb, (float(of["blurTexels"]), float(of["blurTexels"]), 0))
        soft = np.where(dist[..., None] > 0, blur, rgb)
        rgb = (soft * (1 - t) + dark[None, None, :] * t).astype(np.float32)
    stats = {"sourcePxPerTexel": [round(sx, 4), round(sy, 4)],
             "texelsPerC0Px": [round(w / (rect[2] - rect[0]), 4), round(h / (rect[3] - rect[1]), 4)],
             "bandResampledTexels": moved_n}
    log(f"    resampled in {time.time() - t0:.1f} s")
    if kind == "paste":
        alpha = island * (~under_all)
        out = np.dstack([rgb, alpha]).astype(np.float32)
        stats.update(alphaCoverage=round(float((alpha > 0.5).mean()), 4),
                     underFrameTexels=int(under_all.sum()))
        return out, stats
    if kind == "sea":
        sea = rgb
        if plates.get("seaSky") is not None:
            ss = plates["seaSky"]
            FX, FY = texel_c0(rect, (w, h))
            inside = (FX >= 0) & (FX <= C.W) & (FY >= 0) & (FY <= C.H)
            seam = island < 0.5
            ref = rgb[seam & inside]
            # the sea-sky plate is framed like C0 (same camera, no island): outside the C0 frame it is mirrored at the
            # frame edges (plausible waves, no edge-clamp streaks)
            src = lanczos_sample(ss, reflect(FX, C.W) * ss.shape[1] / C.W, reflect(FY, C.H) * ss.shape[0] / C.H,
                                 ss.shape[1] / C.W * (rect[2] - rect[0]) / w, ss.shape[0] / C.H * (rect[3] - rect[1]) / h, a)
            mu_r, sd_r = ref.mean(0), ref.std(0)
            mu_s, sd_s = ss.reshape(-1, 3).mean(0), ss.reshape(-1, 3).std(0)
            matched = np.clip((src - mu_s) / np.maximum(sd_s, 1e-6) * sd_r + mu_r, 0, 1)
            holes = (~seam) & (~inside)
            sea = np.where(seam[..., None], rgb, matched).astype(np.float32)
            stats["seaMatch"] = {"refMean": mu_r.round(4).tolist(), "refStd": sd_r.round(4).tolist(),
                                 "seaSkyMean": mu_s.round(4).tolist(), "seaSkyStd": sd_s.round(4).tolist(),
                                 "mirroredTexels": int(holes.sum())}
        return sea, stats
    if kind == "water":
        P = spec["bake"]["water"]
        FX, FY = texel_c0(rect, (w, h))
        lum = rgb @ LUMA
        sat = rgb.max(-1) - rgb.min(-1)
        blue = rgb[..., 2] - rgb[..., 0]
        water = np.maximum(smoothstep(*P["blueMinusRed"], blue) * smoothstep(*P["lumaWater"], lum),
                           smoothstep(*P["lumaFoam"], lum) * (1 - smoothstep(*P["satFoam"], sat)))
        chans = []
        for ov_id in ("waterfall", "surf-bay"):
            ov = next(o for o in spec["overlays"] if o["id"] == ov_id)
            x0, y0, x1, y1 = ov["pxRect"]
            f = float(P["rectFeatherPx"])
            box = (smoothstep(x0 - f, x0 + f, FX) * (1 - smoothstep(x1 - f, x1 + f, FX)) *
                   smoothstep(y0 - f, y0 + f, FY) * (1 - smoothstep(y1 - f, y1 + f, FY)))
            chans.append(water * box * np.clip(island * 2, 0, 1))
        chans.append(1.0 - island)
        out = np.dstack(chans).astype(np.float32)
        sig = float(P["blurTexels"])
        out = ndimage.gaussian_filter(out, (sig, sig, 0)).astype(np.float32)
        stats["coverage"] = {"waterfall": round(float((out[..., 0] > 0.5).mean()), 4),
                             "surfBay": round(float((out[..., 1] > 0.5).mean()), 4),
                             "sea": round(float((out[..., 2] > 0.5).mean()), 4)}
        return out, stats
    raise ValueError(f"unknown texture kind {kind!r}")


def to_png_bytes_array(img: np.ndarray) -> np.ndarray:
    return np.clip(np.round(np.asarray(img, np.float32) * 255.0), 0, 255).astype(np.uint8)


def save_png(path: Path, arr8: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = {3: "RGB", 4: "RGBA"}[arr8.shape[2]]
    # PIL PNG: deterministic for the same pixels (no time chunk); compress_level fixed
    Image.fromarray(arr8, mode).save(path, format="PNG", compress_level=6)


# ------------------------------------------------------------------ manifests
def derived_path(map_key: str) -> Path:
    """manifest.<map>.json: the git-side record of the out-of-git textures (the profile block's "manifest")."""
    return HERE / f"manifest.{map_key}.json"


def texture_file(spec: dict, name: str) -> str:
    """T_<Name>_Concept<Key>.png = the UE asset name of S08ArtBoardProfiles.json conceptPaste (plateA / plateB /
    seaPlate) without the extension."""
    return f"T_{C.MAPS[spec['map']]['name']}_Concept{name}.png"


def input_list(spec: dict) -> dict:
    out = {}
    for role in ("colour", "seaSky"):
        e = spec["plates"].get(role)
        if e:
            out[role] = {"file": plate_path(spec, e).as_posix(), "size": e["size"]}
    return out


def generator_hashes() -> dict:
    return {rel(p): text_sha256_lf(p) for p in (HERE / "cp_bake.py", HERE / "cp_common.py", HERE / "paste_proto.py")}


UE_FOLDER = "/Game/EnvMaps/{name}/ConceptPaste"
PROFILE_KEYS = {"PlateA": "plateA", "PlateB": "plateB", "Sea": "seaPlate", "Water": "waterMask"}


def material_contract(spec: dict) -> dict:
    """What the profile block conceptPaste / M_ConceptPaste need for these textures (S08ConceptPaste.h): the plates are
    already rectified (identity homography), rectangles as (x0, y0, w, h) in C0 px."""
    name = C.MAPS[spec["map"]]["name"]
    folder = UE_FOLDER.format(name=name)
    out = {"homography": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
           "homographyNote": "the registration H (registration.json) is baked into the texels: C0 px -> plate UV is linear",
           "rects": {}, "assets": {}}
    for key, tex in spec["bake"]["textures"].items():
        x0, y0, x1, y1 = tex["rectC0"]
        out["rects"][PROFILE_KEYS.get(key, key)] = [x0, y0, x1 - x0, y1 - y0]
        out["assets"][PROFILE_KEYS.get(key, key)] = f"{folder}/{Path(texture_file(spec, key)).stem}"
    out["alpha"] = "plateA / plateB A = island matte (featherPx) x NOT under frame-002 (cut underFrameUU); opacity mask 0.5"
    # S08ConceptPaste "outside": clip | clamp (OutsideKeep 0 | 1)
    out["outside"] = "clip" if spec["bake"].get("outsideFrame") is None else "clamp"
    out["outsideNote"] = ("the outpainted plate B covers every game view (K1x0.65: 0 % beyond it)"
                          if spec["bake"].get("outsideFrame") is None else
                          "plate B carries its own blurred / faded edge fill outside the concept frame (outsideFrame); "
                          "beyond its rect the edge clamp continues that dark tone")
    return out


def check(map_key: str, out_root: Path, verbose: bool = True) -> dict:
    """sha256 of the inputs against the spec / registration and of the outputs against manifest.<map>.json."""
    spec = load_spec(map_key)
    res = {"map": map_key, "ok": True, "inputs": {}, "outputs": {}, "errors": []}
    mpath = derived_path(map_key)
    man = json.loads(mpath.read_text(encoding="utf-8")) if mpath.is_file() else None
    if man is None:
        res["ok"] = False
        res["errors"].append(f"{rel(mpath)} missing (run: cp_bake.py bake {map_key})")
    reg = colour_registration(map_key, spec)
    for role, e in input_list(spec).items():
        p = Path(e["file"])
        want = reg["sha256"] if role == "colour" else (spec["plates"][role].get("sha256")
                                                        or (man or {}).get("inputs", {}).get(role, {}).get("sha256"))
        got = C.sha256(p) if p.is_file() else None
        ok = got is not None and (want is None or got == want)
        res["inputs"][role] = {"file": e["file"], "sha256": got, "expected": want, "ok": ok}
        if not ok:
            res["ok"] = False
            res["errors"].append(f"input {role} {e['file']}: " + ("missing" if got is None else "sha256 differs"))
    if man is not None:
        if man.get("paramsSha256") != canon_sha(bake_params(spec)):
            res["ok"] = False
            res["errors"].append("the bake parameters changed since the manifest (re-bake)")
        for name, o in man["outputs"].items():
            p = out_root / map_key / o["file"]
            got = C.sha256(p) if p.is_file() else None
            ok = got == o["sha256"]
            res["outputs"][name] = {"file": p.as_posix(), "ok": ok, "sha256": got}
            if not ok:
                res["ok"] = False
                res["errors"].append(f"output {name} {p}: " + ("missing" if got is None else "sha256 differs"))
    if verbose:
        print(f"CONCEPT-PASTE-BAKE-CHECK {map_key} {'ok' if res['ok'] else 'FAILED'} " + "; ".join(res["errors"]))
    return res


def bake_params(spec: dict) -> dict:
    """Everything of the spec that decides the texture bytes (hashed into the manifest)."""
    g = spec["geometry"]
    return {"bake": spec["bake"], "plates": {k: spec["plates"].get(k) for k in ("colour", "seaSky")},
            "cut": spec["cut"], "islandMatte": g["islandMatte"], "groundZ": g["groundZ"],
            "overlays": [o for o in spec.get("overlays", []) if "pxRect" in o]}


def bake(map_key: str, out_root: Path, force: bool = False, log=print) -> dict:
    t0 = time.time()
    spec = load_spec(map_key)
    reg = colour_registration(map_key, spec)
    H = np.asarray(reg["H"], float)
    cpath = plate_path(spec, spec["plates"]["colour"])
    got = C.sha256(cpath)
    if got != reg["sha256"]:
        raise RuntimeError(f"{cpath}: sha256 {got} differs from registration.json ({reg['sha256']}): re-register")
    plates = {"colour": np.asarray(Image.open(cpath).convert("RGB")).astype(np.float32) / 255.0}
    if tuple(plates["colour"].shape[1::-1]) != tuple(spec["plates"]["colour"]["size"]):
        raise RuntimeError(f"{cpath}: size {plates['colour'].shape[1::-1]} != spec {spec['plates']['colour']['size']}")
    inputs = {"colour": {"file": cpath.as_posix(), "sha256": got, "size": spec["plates"]["colour"]["size"],
                         "registrationTag": spec["bake"]["colourTag"]}}
    ss = spec["plates"].get("seaSky")
    if ss:
        spath = plate_path(spec, ss)
        s_sha = C.sha256(spath)
        if ss.get("sha256") and s_sha != ss["sha256"]:
            raise RuntimeError(f"{spath}: sha256 differs from the spec")
        plates["seaSky"] = np.asarray(Image.open(spath).convert("RGB")).astype(np.float32) / 255.0
        inputs["seaSky"] = {"file": spath.as_posix(), "sha256": s_sha, "size": ss["size"]}
    od = out_root / map_key
    old = json.loads(derived_path(map_key).read_text(encoding="utf-8")) if derived_path(map_key).is_file() else {}
    params_sha = canon_sha(bake_params(spec))
    outputs, stats = {}, {}
    for name, tex in spec["bake"]["textures"].items():
        fname = texture_file(spec, name)
        path = od / fname
        prev = (old.get("outputs") or {}).get(name)
        if (not force and prev and old.get("paramsSha256") == params_sha and old.get("inputs") == inputs
                and old.get("generator") == generator_hashes()
                and path.is_file() and C.sha256(path) == prev["sha256"]):
            outputs[name] = prev
            stats[name] = (old.get("stats") or {}).get(name, {})
            log(f"  {name}: unchanged ({fname})")
            continue
        img, st = bake_texture(map_key, spec, name, tex, plates, H, log)
        arr = to_png_bytes_array(img)
        save_png(path, arr)
        outputs[name] = {"file": fname, "kind": tex["kind"], "size": [int(arr.shape[1]), int(arr.shape[0])],
                         "channels": "RGBA" if arr.shape[2] == 4 else "RGB", "rectC0": tex["rectC0"],
                         "sha256": C.sha256(path), "bytes": path.stat().st_size,
                         "meanSrgb": [round(float(v), 4) for v in arr[..., :3].reshape(-1, 3).mean(0) / 255.0]}
        stats[name] = st
        log(f"  {name}: {fname} {arr.shape[1]}x{arr.shape[0]}")
    man = {"schema": SCHEMA_DERIVED, "map": map_key,
           "status": "измерено (bake); textures OUT of git (ENV-U3 / ENV-U7): only parameters and sha256 here",
           "outDir": rel(od), "spec": f"tools/art/concept_paste/{map_key}.paste.json",
           "registration": {"file": "tools/art/concept_paste/registration.json", "tag": spec["bake"]["colourTag"],
                            "H": reg["H"], "homographyResidualPx": reg["homographyResidualPx"]},
           "camera": C.concept_cam().to_json(),
           "uvContract": "u = (c0x - rectC0[0]) / (rectC0[2] - rectC0[0]), v = (c0y - rectC0[1]) / (rectC0[3] - rectC0[1]); "
                         "c0 = C0 pixel (continuous, 1920 x 1080, y down) of the board-space position",
           "resample": f"Lanczos-{int(spec['bake'].get('lanczosA', 3))} (classic, ENV-U6), widened by the minification, "
                       "edge clamp, weights normalised",
           "materialContract": material_contract(spec),
           "generator": generator_hashes(), "paramsSha256": params_sha, "inputs": inputs, "outputs": outputs,
           "stats": stats}
    C.dump_json(derived_path(map_key), man)  # no timings: the same inputs give the same manifest bytes
    man["seconds"] = round(time.time() - t0, 1)
    return man


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s_reg = sub.add_parser("registration")
    s_reg.add_argument("--proto", type=Path, default=PROTO)
    s_bake = sub.add_parser("bake")
    s_bake.add_argument("maps", nargs="+", choices=sorted(C.MAPS))
    s_bake.add_argument("--out", type=Path, default=OUT_DEFAULT)
    s_bake.add_argument("--force", action="store_true")
    s_con = sub.add_parser("contract", help="print the profile-block values (conceptPaste) for the baked textures")
    s_con.add_argument("maps", nargs="+", choices=sorted(C.MAPS))
    s_chk = sub.add_parser("check")
    s_chk.add_argument("maps", nargs="*", choices=sorted(C.MAPS))
    s_chk.add_argument("--out", type=Path, default=OUT_DEFAULT)
    a = ap.parse_args(argv)
    if a.cmd == "registration":
        C.dump_json(REGISTRATION, collect_registration(a.proto))
        print(f"wrote {rel(REGISTRATION)}")
        return 0
    if a.cmd == "bake":
        for m in a.maps:
            print(f"CONCEPT-PASTE-BAKE {m}")
            man = bake(m, a.out, a.force)
            print(f"CONCEPT-PASTE-BAKE {m} done {man['seconds']} s -> {man['outDir']}")
        return 0 if all(check(m, a.out)["ok"] for m in a.maps) else 1
    if a.cmd == "contract":
        for m in a.maps:
            print(json.dumps({m: material_contract(load_spec(m))}, indent=1))
        return 0
    maps = a.maps or [m for m in sorted(C.MAPS) if derived_path(m).is_file()]
    return 0 if all(check(m, a.out)["ok"] for m in maps) else 1


if __name__ == "__main__":
    sys.exit(main())
