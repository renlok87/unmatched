"""H2 look-dev mode (plain Python: numpy + scipy.ndimage + Pillow; no bpy): material library v1 on the H2.1 game model.

Driver: run_h2_bake.py --mode lookdev --profile <*-h2-lookdev.json> --run-dir <new run> [--stages ...]. The mode never
re-runs the H2 stages: it reads the pinned outputs of a finished H2.1 run (profile source.run: work/uv/*.npy and the 4K
textures, sha256-checked) and writes a NEW run directory. Stages of the mode:

  ld_maps     (this module) MatID (R8, class index x 16 + 8, 4K master + 2K runtime, gutter by nearest-label growth,
              no mips), per-class BaseColor grade (linear gains from the profile, measured against the concept by
              ld_measure), reclassified zones (profile classes.reclass: e.g. sandal straps gold -> leather take BC/ORM
              of the H2 baseline, metallic 0), TeamMask.R restricted to the cloth classes (not the gold trim),
              edge mask (convexity of the baked normal, 1/m, for the wear of the v2 shader), hero LUT
              (the M_UM_Figure v2 LUT builder tools/art/material_library/build_ue_inputs.py, imported: presets + hero
              overrides {bc, ymedClassHero} -> T_UM_MatLUT_<Hero>.dds 16 x 16 RGBA16F + the overrides JSON, so
              `build_ue_inputs.py --hero <Hero> --overrides <json>` reproduces the same bytes), EdgeMask as its own
              texture (EdgeMaskTexture of the v2 master, R8).
              BC/ORM/TeamMask/MatID/Edge 4K + 2K; N / N_OpenGL copied byte for byte ("как были").
  ld_fbx      (st_lookdev.py, Blender) UV1 in metres + UM_FBX_v1 export + read-back (geometry/rig unchanged).
  ld_preview  (st_lookdev.py, Blender) ortho views framed like the concepts: class-ID pass, H2.1 and H2LD beauty.
  ld_measure  (this module) per-zone medians concept | H2.1 | H2LD (luma, hue, saturation) on the class-ID pass,
              suggested gains (concept / H2LD render) -> reports/measure-report.json.
  ld_compose  (this module) sheets concept | H2.1 | H2LD and the class-ID overlay.
Everything is deterministic (no randomness; Pillow PNG without metadata); Cycles frames are editor frames only."""

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent


def load_sibling(name):
    spec = importlib.util.spec_from_file_location("h2ld_" + name, HERE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ue_inputs(repo):
    """The v2 LUT builder (read-only import; its main() is not run: no shared output is touched)."""
    path = Path(repo) / "tools" / "art" / "material_library" / "build_ue_inputs.py"
    spec = importlib.util.spec_from_file_location("um_build_ue_inputs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_exr(path, rgba):
    """rgba [H, W, 4] -> OpenEXR scanline, HALF, NO_COMPRESSION, row 0 = top (preview input for Blender only)."""
    import struct
    rgba = np.asarray(rgba, np.float64)
    h, w = rgba.shape[:2]
    chans = ["A", "B", "G", "R"]

    def attr(name, typ, data):
        return name.encode() + b"\0" + typ.encode() + b"\0" + struct.pack("<i", len(data)) + data
    chlist = b"".join(c.encode() + b"\0" + struct.pack("<i", 1) + b"\0\0\0\0" + struct.pack("<ii", 1, 1) for c in chans) + b"\0"
    box = struct.pack("<iiii", 0, 0, w - 1, h - 1)
    header = (b"\x76\x2f\x31\x01" + struct.pack("<i", 2) + attr("channels", "chlist", chlist)
              + attr("compression", "compression", b"\0") + attr("dataWindow", "box2i", box)
              + attr("displayWindow", "box2i", box) + attr("lineOrder", "lineOrder", b"\0")
              + attr("pixelAspectRatio", "float", struct.pack("<f", 1.0))
              + attr("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
              + attr("screenWindowWidth", "float", struct.pack("<f", 1.0)) + b"\0")
    idx = {"R": 0, "G": 1, "B": 2, "A": 3}
    pos = len(header) + 8 * h
    offsets, blocks = [], []
    for y in range(h):
        data = b"".join(rgba[y, :, idx[c]].astype("<f2").tobytes() for c in chans)
        blocks.append(struct.pack("<ii", y, len(data)) + data)
        offsets.append(pos)
        pos += len(blocks[-1])
    Path(path).write_bytes(header + b"".join(struct.pack("<Q", o) for o in offsets) + b"".join(blocks))


def read_dds_rgba16f(path):
    """DDS DX10 R16G16B16A16_FLOAT, one 2D slice (build_ue_inputs.write_dds) -> [H, W, 4] float32."""
    b = Path(path).read_bytes()
    h, w = np.frombuffer(b[12:20], "<u4")
    return np.frombuffer(b[148:148 + int(h) * int(w) * 8], "<f2").reshape(int(h), int(w), 4).astype(np.float32)


def sha256(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def lin(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def luma(rgb_lin):
    return rgb_lin[..., 0] * 0.2126 + rgb_lin[..., 1] * 0.7152 + rgb_lin[..., 2] * 0.0722


def read_png(path):
    """8-bit PNG -> uint8 array with row 0 = v 0 (the textures-stage convention)."""
    return np.asarray(Image.open(path))[::-1].copy()


SHIFTS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def grow_labels(lab, steps):
    """Gutter: each step, an unlabelled (-1) texel takes the label of its first labelled 8-neighbour (fixed order)."""
    tx = load_sibling("textures")
    lab = lab.copy()
    for _ in range(steps):
        new = np.full(lab.shape, -1, lab.dtype)
        for dy, dx in SHIFTS:
            sh = tx.shift(lab + 1, dy, dx) - 1
            take = (new < 0) & (sh >= 0)
            new[take] = sh[take]
        grow = (lab < 0) & (new >= 0)
        if not grow.any():
            break
        lab[grow] = new[grow]
    return lab


def hsv(rgb):
    return load_sibling("textures").rgb_to_hsv(rgb)


# ------------------------------------------------------------------ classes
def classify(src, cfg, presets):
    """Class index per 4K texel (-1 outside the UV islands) + stats. src: dict of the source-run arrays."""
    idx = {c["id"]: c["index"] for c in presets["classes"]}
    part_ids, metal, pos = src["part_ids"], src["metal"], src["position"]
    bc = src["BC"].astype(np.float32) / 255.0
    h, s, v = hsv(bc)
    lab = np.full(part_ids.shape, -1, np.int16)
    steps = []
    for part, cid in sorted(cfg["part_default"].items(), key=lambda kv: int(kv[0])):
        lab[part_ids == int(part)] = idx[cid]
    steps.append("part_default")
    uv = part_ids >= 0
    for rule in cfg["rules"]:
        m = np.isin(part_ids, rule["parts"]) if "parts" in rule else uv.copy()
        hs = rule.get("hsv")
        if hs:
            if "v_min" in hs:
                m &= v >= hs["v_min"]
            if "v_max" in hs:
                m &= v <= hs["v_max"]
            if "s_min" in hs:
                m &= s >= hs["s_min"]
            if "s_max" in hs:
                m &= s <= hs["s_max"]
            if "hue_deg" in hs:
                m &= (h >= hs["hue_deg"][0]) & (h <= hs["hue_deg"][1])
        if "cloth_weight_min" in rule:
            m &= src["cloth_w"] >= rule["cloth_weight_min"]
        if "cloth_weight_max" in rule:
            m &= src["cloth_w"] < rule["cloth_weight_max"]
        if "metal_min" in rule:
            m &= metal >= rule["metal_min"]
        if "metal_max" in rule:
            m &= metal < rule["metal_max"]
        for hsp in rule.get("half_spaces", []):
            n = np.array(hsp["normal"], np.float64)
            n /= np.linalg.norm(n)
            ys, xs = np.nonzero(m)
            d = (pos[ys, xs].astype(np.float64) - np.array(hsp["point_m"])) @ n
            ok = (d >= hsp["min_m"]) if hsp.get("keep", "ge") == "ge" else (d < hsp["min_m"])
            m[ys[~ok], xs[~ok]] = False
        if "z_max_m" in rule:
            ys, xs = np.nonzero(m)
            bad = pos[ys, xs, 2] > rule["z_max_m"]
            m[ys[bad], xs[bad]] = False
        lab[m] = idx[rule["class"]]
        steps.append({"rule": rule["name"], "texels": int(m.sum())})
    return lab, steps


def clean_labels(lab, cfg, protect):
    """Small connected components of a class (< min_px, 8-connectivity) take the majority label of their 1-px ring.
    protect: class indices never removed (thin gold trim lines are real)."""
    min_px = int(cfg.get("min_component_px", 0))
    if not min_px:
        return lab, {}
    out = lab.copy()
    removed = {}
    st = np.ones((3, 3), bool)
    for c in sorted(set(np.unique(lab).tolist()) - {-1}):
        if c in protect:
            continue
        comp, n = ndimage.label(lab == c, structure=st)
        if not n:
            continue
        sizes = np.bincount(comp.ravel())
        small = np.nonzero(sizes < min_px)[0]
        small = small[small > 0]
        if not len(small):
            continue
        objs = ndimage.find_objects(comp)
        cnt = 0
        for k in small.tolist():
            sl = objs[k - 1]
            sl = tuple(slice(max(a.start - 1, 0), a.stop + 1) for a in sl)
            mine = comp[sl] == k
            ring = ndimage.binary_dilation(mine, structure=st) & ~mine
            vals = lab[sl][ring]
            vals = vals[(vals >= 0) & (vals != c)]
            if not len(vals):
                continue
            new = np.bincount(vals).argmax()
            out[sl][mine] = new
            cnt += int(mine.sum())
        removed[int(c)] = cnt
    return out, removed


def downsample_labels(lab):
    """2x2 majority (ties: the lower class index; -1 only if all four are -1)."""
    h = lab.shape[0] // 2
    blk = lab.reshape(h, 2, h, 2).transpose(0, 2, 1, 3).reshape(h, h, 4)
    best = np.full((h, h), -1, np.int16)
    best_n = np.zeros((h, h), np.int8)
    for c in sorted(set(np.unique(lab).tolist()) - {-1}):
        n = (blk == c).sum(-1).astype(np.int8)
        take = n > best_n
        best[take] = c
        best_n[take] = n[take]
    return best


def encode_matid(lab):
    lab = np.where(lab < 0, 0, lab)
    return (lab.astype(np.int32) * 16 + 8).astype(np.uint8)


# ------------------------------------------------------------------ edge mask
def edge_mask(n_gl8, pos, islands, cfg):
    """Convexity of the baked tangent normal: div(n.xy) per texel / metres per texel -> curvature 1/m (> 0 convex),
    smoothstep(k0, k1). Neighbours across an island border do not count. Returns (mask float32, stats)."""
    n = n_gl8.astype(np.float32) / 127.5 - 1.0
    nx, ny = n[..., 0], n[..., 1]
    same_x = (islands[:, 2:] == islands[:, :-2]) & (islands[:, 1:-1] >= 0)
    same_y = (islands[2:, :] == islands[:-2, :]) & (islands[1:-1, :] >= 0)
    dnx = np.zeros_like(nx)
    dny = np.zeros_like(ny)
    dnx[:, 1:-1] = np.where(same_x, (nx[:, 2:] - nx[:, :-2]) * 0.5, 0.0)
    dny[1:-1, :] = np.where(same_y, (ny[2:, :] - ny[:-2, :]) * 0.5, 0.0)
    # metres per texel per island: median |d position / d x| of the island's interior texels
    dp = np.linalg.norm(pos[:, 2:] - pos[:, :-2], axis=-1) * 0.5
    ok = same_x & (islands[:, 2:] >= 0)
    ids = islands[:, 1:-1][ok]
    vals = dp[ok]
    n_is = int(islands.max()) + 1
    order = np.lexsort((vals, ids))
    ids_s, vals_s = ids[order], vals[order]
    starts = np.searchsorted(ids_s, np.arange(n_is))
    ends = np.searchsorted(ids_s, np.arange(n_is), side="right")
    mpt = np.array([vals_s[(a + b) // 2] if b > a else np.nan for a, b in zip(starts, ends)])
    fallback = float(np.nanmedian(mpt))
    mpt = np.where(np.isfinite(mpt) & (mpt > 0), mpt, fallback)
    mpt_map = np.where(islands >= 0, mpt[np.maximum(islands, 0)], fallback).astype(np.float32)
    k = (dnx + dny) / mpt_map
    k = ndimage.uniform_filter(k, size=int(cfg.get("smooth_px", 3)))
    k0, k1 = cfg["curvature_per_m"]
    t = np.clip((k - k0) / (k1 - k0), 0.0, 1.0)
    e = (t * t * (3 - 2 * t)).astype(np.float32) * (islands >= 0)
    inside = islands >= 0
    stats = {"metres_per_texel_4k_median": round(fallback, 7), "curvature_p50_p90_p99_per_m":
             [round(float(x), 1) for x in np.percentile(k[inside], [50, 90, 99])],
             "edge_share_ge_0.5": round(float((e[inside] >= 0.5).mean()), 4)}
    return e, stats


# ------------------------------------------------------------------ grade
def gain_field(lab, gains, presets, blur_px, bc8=None):
    """Linear RGB gain per texel from the class gains, box-blurred (blur_px radius) so a class border is soft.
    A gain entry with "bc_gate" {hue_deg: [lo, hi], s_min} applies only to texels of the class whose baked BC passes
    the gate (legacy_bake: the green snakes, not the lips, brows and hair of the same class)."""
    byidx = {c["index"]: c["id"] for c in presets["classes"]}
    g = np.ones(lab.shape + (3,), np.float32)
    hsv_bc = hsv(bc8.astype(np.float32) / 255.0) if bc8 is not None else None
    for c in sorted(set(np.unique(lab).tolist()) - {-1}):
        cid = byidx[c]
        if cid in gains:
            m = lab == c
            bg = gains[cid].get("bc_gate")
            if bg:
                h, sat, _v = hsv_bc
                m &= (h >= bg["hue_deg"][0]) & (h <= bg["hue_deg"][1]) & (sat >= bg.get("s_min", 0.0))
            g[m] = np.array(gains[cid]["rgb"], np.float32)
    if blur_px:
        size = 2 * int(blur_px) + 1
        for ch in range(3):
            g[..., ch] = ndimage.uniform_filter(g[..., ch], size=size, mode="nearest")
    return g


def run_maps(run_dir, ld, repo):
    run_dir, repo = Path(run_dir), Path(repo)
    tx = load_sibling("textures")
    UI = ue_inputs(repo)
    presets = UI.load_presets()
    byid = {c["id"]: c for c in presets["classes"]}
    src_run = repo / ld["source"]["run"]
    sp = ld["source"]["prefix"]
    tdir = src_run / "textures"
    # ---- pinned inputs
    pins = {}
    for key, rel in ld["source"]["files"].items():
        p = src_run / rel
        got = sha256(p)
        want = ld["source"]["sha256"][key]
        pins[key] = {"path": (Path(ld["source"]["run"]) / rel).as_posix(), "sha256": got, "pinned": got == want}
        if got != want:
            raise RuntimeError("ld_maps: %s sha256 %s != pinned %s (source run changed)" % (rel, got, want))
    src = {"part_ids": np.load(src_run / "work/uv/part_ids.npy"), "metal": np.load(src_run / "work/uv/metal_mask.npy"),
           "position": np.load(src_run / "work/uv/position.npy"), "islands": np.load(src_run / "work/uv/island_ids.npy"),
           "BC": read_png(tdir / ("%s_BC.png" % sp)), "ORM": read_png(tdir / ("%s_ORM.png" % sp)),
           "TeamMask": read_png(tdir / ("%s_TeamMask.png" % sp)), "N_OpenGL": read_png(tdir / ("%s_N_OpenGL.png" % sp)),
           "BC_base": read_png(src_run / ld["source"]["files"]["baseline_BC"]),
           "ORM_base": read_png(src_run / ld["source"]["files"]["baseline_ORM"])}
    src["cloth_w"] = src["TeamMask"][..., 0].astype(np.float32) / 255.0
    ccfg = ld["classes"]
    lab, steps = classify(src, ccfg, presets)
    protect = {byid[c]["index"] for c in ccfg.get("protect_classes", [])}
    lab, removed = clean_labels(lab, ccfg, protect)
    uv = src["part_ids"] >= 0
    # ---- reclassified zones: BC/ORM from the H2 baseline (before the H2.1 metal remap), metallic 0
    reclass = np.zeros(lab.shape, bool)
    for rc in ccfg.get("reclass_from_baseline", []):
        m = (lab == byid[rc["class"]]["index"]) & (src["metal"] > rc.get("metal_gt", 0.0)) & np.isin(src["part_ids"], rc["parts"])
        reclass |= m
    bc = src["BC"].copy()
    orm = src["ORM"].copy()
    bc[reclass] = src["BC_base"][reclass]
    orm[reclass, 1] = src["ORM_base"][reclass, 1]
    orm[reclass, 2] = 0
    # ---- gutter labels (for MatID and the grade)
    edge_px = int(ld.get("gutter_px", 16))
    lab_g = grow_labels(lab, edge_px)
    # ---- metallic per class (library rule: metallic in {0, 1} per class; legacy_bake keeps the bake)
    metal_idx = [c["index"] for c in presets["classes"] if c["index"] and c["metallic"] == 1]
    diel_idx = [c["index"] for c in presets["classes"] if c["index"] and c["metallic"] == 0]
    orm[..., 2] = np.where(np.isin(lab_g, metal_idx), 255, np.where(np.isin(lab_g, diel_idx), 0, orm[..., 2]))
    # ---- grade: class gains (linear), then the bake-clamped luminance range of the dielectric classes
    #      (the clamp of the v2 shader, done in the texture so the v1 master shows the same colour)
    #      Dark classes: the class median after the gain stays >= median_floor x lo (a concept darker than the
    #      albedo floor is light, not albedo), and the low end goes through a toe f(Y) = lo + Y^2 / (4 lo) for Y < 2 lo
    #      (f(0) = lo, f(2 lo) = 2 lo, slope 1): cavity variation is compressed, not flattened onto the floor.
    gcfg = ld.get("grade", {})
    gains = {k: dict(v) for k, v in gcfg.get("gains", {}).items()}
    bc_lin0 = lin(bc.astype(np.float32) / 255.0)
    floor_f = float(gcfg.get("median_floor", 1.2))
    floor_stats = {}
    for cid, gv in gains.items():
        c = byid[cid]
        if not c["index"] or c["metallic"] == 1 or c["baseColor"]["mode"] != "bake-clamped":
            continue
        m = lab_g == c["index"]
        if not m.any():
            continue
        lo = c["baseColor"]["luminanceRange"][0]
        ymed = float(np.median(luma(bc_lin0[m] * np.array(gv["rgb"], np.float32))))
        if ymed < floor_f * lo:
            f = floor_f * lo / ymed
            gv["rgb"] = [float(x) * f for x in gv["rgb"]]
            floor_stats[cid] = {"median_Y_with_profile_gain": round(ymed, 5), "raised_to": round(floor_f * lo, 5),
                                "gain_used": [round(x, 4) for x in gv["rgb"]]}
    g = gain_field(lab_g, gains, presets, int(gcfg.get("blur_px", 2)), bc)
    bc_lin = bc_lin0 * g
    clamp_stats = {}
    if gcfg.get("clamp_luminance", True):
        for c in presets["classes"]:
            if not c["index"] or c["metallic"] == 1 or c["baseColor"]["mode"] != "bake-clamped":
                continue
            m = lab_g == c["index"]
            if not m.any():
                continue
            lo, hi = c["baseColor"]["luminanceRange"]
            x = bc_lin[m]
            y = luma(x)
            yc = np.where(y < 2 * lo, lo + y * y / (4 * lo), np.minimum(y, hi))
            x = x * (yc / np.maximum(y, 1e-6))[:, None]
            x = np.where(y[:, None] < 1e-6, lo, x)
            x = np.minimum(x, float(c["baseColor"].get("maxChannel", 0.9)))
            bc_lin[m] = x
            clamp_stats[c["id"]] = {"raised_below_min": round(float((y < lo).mean()), 4),
                                    "in_toe_below_2lo": round(float((y < 2 * lo).mean()), 4),
                                    "lowered_above_max": round(float((y > hi).mean()), 4)}
    # look-dev round 2 (2026-09-30, after 5c-B1): final linear BC gains per class AFTER the clamp (profile
    # grade.final_gains_r2: {class: {"bc_gain": [r, g, b], ...}}), fitted on the converged UE frames b1 against the
    # concept (tools/art/material_library/lookdev_r2.py fit -> ratio of the effective albedo; ue_bc_feedback.solve_gain
    # against the UE LUT column of the class -> bc_gain, which differs from the ratio where the UE floor binds)
    final_stats = {}
    for cid, fg in (gcfg.get("final_gains_r2") or {}).items():
        if not isinstance(fg, dict):   # "note"
            continue
        c = byid[cid]
        m = lab_g == c["index"]
        if not m.any():
            continue
        x0 = bc_lin[m]
        x = np.minimum(x0 * np.array(fg["bc_gain"], np.float32), float(c["baseColor"].get("maxChannel", 0.9)))
        bc_lin[m] = x
        final_stats[cid] = {"bc_gain": fg["bc_gain"], "texels_4k": int(m.sum()),
                            "Y_median_before_after": [round(float(np.median(luma(x0))), 5), round(float(np.median(luma(x))), 5)]}
    bc_lin = np.clip(bc_lin, 0.0, 1.0)
    bc8 = tx.to8(srgb(bc_lin))
    # ---- TeamMask: R only on the cloth classes (G, B, A as in H2.1); EdgeMask: own texture (v2 EdgeMaskTexture)
    tm = src["TeamMask"].copy()
    cloth_idx = [byid[c]["index"] for c in ld["team_dye_classes"]]
    in_cloth = np.isin(lab_g, cloth_idx)
    tm[..., 0] = np.where(in_cloth, tm[..., 0], 0)
    e, estats = edge_mask(src["N_OpenGL"], src["position"], src["islands"], ld["edge"])
    e = tx.fill(e[..., None], uv, edge_px)[..., 0]
    edge8 = tx.to8(e)
    matid4 = encode_matid(np.where(lab_g < 0, 0, lab_g))
    lab2 = downsample_labels(lab_g)
    matid2 = encode_matid(np.where(lab2 < 0, 0, lab2))
    # ---- write
    prefix = ld["prefix"]
    out_dir = run_dir / "textures"
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}

    def write(name, arr, mode):
        path = out_dir / ("%s_%s.png" % (prefix, name))
        outputs[path.name] = tx.save_png(arr, path, mode)

    write("BC", bc8, "RGB")
    write("ORM", orm, "RGB")
    write("TeamMask", tm, "RGBA")
    write("MatID", matid4, "L")
    write("Edge", edge8, "L")
    q = lambda a: a.astype(np.float32) / 255.0
    write("2K_BC", tx.to8(tx.box2(q(bc8))), "RGB")
    write("2K_ORM", tx.to8(tx.box2(q(orm))), "RGB")
    write("2K_TeamMask", tx.to8(tx.box2(q(tm))), "RGBA")
    write("2K_MatID", matid2, "L")
    write("2K_Edge", tx.to8(tx.box2(q(edge8)[..., None])[..., 0]), "L")
    for name in ("N", "N_OpenGL", "2K_N", "2K_N_OpenGL"):  # unchanged: byte copies
        dst = out_dir / ("%s_%s.png" % (prefix, name))
        shutil.copyfile(tdir / ("%s_%s.png" % (sp, name)), dst)
        outputs[dst.name] = {"sha256": sha256(dst), "bytes": dst.stat().st_size, "copied_from": "%s_%s.png" % (sp, name)}
    # ---- stats per class (4K, islands only)
    byidx = {c["index"]: c["id"] for c in presets["classes"]}
    bcl = lin(bc8.astype(np.float32) / 255.0)
    bcl_src = lin(src["BC"].astype(np.float32) / 255.0)
    area = {}
    ymed = {}
    for c in sorted(set(np.unique(lab).tolist()) - {-1}):
        m = (lab == c) & uv
        cid = byidx[c]
        y = luma(bcl[m])
        area[cid] = {"texels_4k": int(m.sum()), "share_of_islands": round(float(m.sum() / uv.sum()), 4),
                     "bc_linear_median": [round(float(x), 4) for x in np.median(bcl[m], 0)],
                     "bc_linear_median_before_grade": [round(float(x), 4) for x in np.median(bcl_src[m], 0)],
                     "Y_p5_p50_p95": [round(float(x), 4) for x in np.percentile(y, [5, 50, 95])],
                     "edge_mask_mean": round(float(e[m].mean()), 4),
                     "ymedClassHero": round(float(np.median(y)), 5),
                     "team_r_mean": round(float(tm[..., 0][m].mean() / 255.0), 4)}
        if cid != "legacy_bake":
            ymed[cid] = float(np.median(y))
    # ---- LUT (v2 layout of build_ue_inputs.py: 16 x 16 RGBA16F, rows 0-9)
    ov = {"classes": {k: dict(v) for k, v in ld.get("lut_overrides", {}).items()}}
    for cid, y in sorted(ymed.items()):  # hero statistics row 8: median luminance of the hero bake in the class
        ov["classes"].setdefault(cid, {})["ymedClassHero"] = round(y, 5)
    for cid in sorted(gains):
        if cid not in area or not byid[cid]["index"]:  # legacy_bake: BC grade only, its LUT column stays passthrough
            continue
        # dielectric: typical BC = the class tone after the concept grade (debug view / BakeFromLUT); metal (preset-f0):
        # the hero F0 = the graded class median (antique gold of the concept instead of the table F0 of gold)
        ov["classes"][cid].setdefault("bc", area[cid]["bc_linear_median"])
    ov_doc = {"schema": "unmatched.um-v2-hero-overrides/1", "hero": ld["lut_hero"], "asset_id": ld["asset_id"],
              "generator": "tools/tripo-pipeline/blender/h2_bake/lookdev.py (ld_maps)",
              "rebuild": "python tools/art/material_library/build_ue_inputs.py --skip-arrays --hero %s --overrides <this file>"
                         % ld["lut_hero"],
              "why": {"bc": "тон класса после подгонки к концепту (ld_measure); у металла — F0 героя",
                      "ymedClassHero": "медиана яркости BC героя в классе (README §4)"},
              "classes": ov["classes"]}
    ov_path = out_dir / ("%s.overrides.json" % ld["lut_name"])
    ov_path.write_text(json.dumps(ov_doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    cols = UI.class_columns(presets)
    applied = UI.apply_overrides(cols, ov_doc, presets)
    lut = UI.lut_array(cols)
    dds = out_dir / ("%s.dds" % ld["lut_name"])
    UI.write_dds(dds, [lut.astype(np.float16)], "R16G16B16A16_FLOAT")
    back = read_dds_rgba16f(dds)
    write_exr(run_dir / "work" / ("%s.exr" % ld["lut_name"]), back)  # Blender preview input (Blender reads EXR)
    np.save(run_dir / "work" / ("%s.npy" % ld["lut_name"]), back)
    lut_rep = {"dds": dds.name, "dds_sha256": sha256(dds), "overrides_json": ov_path.name, "overrides_sha256": sha256(ov_path),
               "layout": "build_ue_inputs.LUT_ROWS (rows 0-9, 10-15 reserved), column = class index",
               "builder": "tools/art/material_library/build_ue_inputs.py %s (imported, main() not run)" % UI.GENERATOR_VERSION,
               "applied": applied, "read_back_equals_half": bool(np.array_equal(back, lut.astype(np.float16).astype(np.float32)))}
    for k in (dds.name, ov_path.name):
        outputs[k] = {"sha256": sha256(out_dir / k), "bytes": (out_dir / k).stat().st_size}
    # ---- checks
    checks = {}
    dec4 = matid4.astype(np.int32) * 255 // 255 // 16
    checks["matid_decodes_to_labels_4k"] = {"passed": bool(np.array_equal(dec4[uv], np.where(lab_g < 0, 0, lab_g)[uv])),
                                           "expected": "floor(v / 16) == class index on every island texel"}
    checks["matid_values_valid"] = {"passed": bool(set(np.unique(matid2).tolist()) <= {i * 16 + 8 for i in range(16)}
                                                   and set(np.unique(matid4).tolist()) <= {i * 16 + 8 for i in range(16)}),
                                    "measured": sorted(set(np.unique(matid4).tolist())), "expected": "index * 16 + 8"}
    md = orm[..., 2][np.isin(lab_g, diel_idx)]
    mm_ = orm[..., 2][np.isin(lab_g, metal_idx)]
    checks["orm_metallic_binary_per_class_4k"] = {"passed": bool((md.size == 0 or md.max() == 0) and (mm_.size == 0 or mm_.min() == 255)),
                                                 "expected": "ORM.B = 0 in dielectric classes, 255 in metal classes (4K; 2K = box average)"}
    lum_ok = {}
    for cid, a in area.items():
        if cid == "legacy_bake" or byid[cid]["metallic"] == 1:
            continue
        lo, hi = byid[cid]["baseColor"]["luminanceRange"]
        y5, _y50, y95 = a["Y_p5_p50_p95"]
        yy = luma(bcl[(lab == byid[cid]["index"]) & uv])
        lum_ok[cid] = {"Y_p5_p95": [y5, y95], "range": [lo, hi],  # tolerance: one 8-bit sRGB step at the range ends
                       "share_outside": round(float(((yy < lo * 0.93) | (yy > hi * 1.03)).mean()), 4)}
    checks["dielectric_bc_in_class_luminance_range"] = {
        "passed": all(v["share_outside"] <= 0.05 for v in lum_ok.values()), "measured": lum_ok,
        "expected": "<= 5 % of a class outside the preset luminance range (the v2 shader clamps the rest)"}
    tr = tm[..., 0][uv & ~in_cloth]
    checks["team_mask_only_on_cloth_classes"] = {"passed": bool(tr.max() == 0 if tr.size else True),
                                                "measured": int(tr.max()) if tr.size else 0}
    checks["lut_dds_read_back"] = {"passed": lut_rep["read_back_equals_half"], "measured": {"dds_sha256": lut_rep["dds_sha256"]}}
    mt = {c["id"]: [round(float(x), 4) for x in lut[0, c["index"], :3]] for c in presets["classes"] if c["index"] and c["metallic"] == 1}
    checks["lut_metal_f0_plausible"] = {
        "passed": all(float(luma(np.array(v))) >= 0.45 or byid[k]["baseColor"].get("luminanceBandLinear") or k == "steel_blued"
                      for k, v in mt.items() if k in area) and all(max(v) <= 1.0 for v in mt.values()),
        "measured": {k: {"bc": v, "Y": round(float(luma(np.array(v))), 4)} for k, v in mt.items() if k in area},
        "expected": "metal classes used by the hero: Y(F0) >= 0.45, channels <= 1 (library rule; oxide films excepted)"}
    report = {"stage": "ld_maps", "prefix": prefix, "pins": pins, "classify_steps": steps,
              "small_components_relabelled": {byidx[k]: v for k, v in removed.items()},
              "reclass_from_baseline_texels": int(reclass.sum()),
              "classes": area, "edge_mask": dict(estats, config=ld["edge"]), "grade": dict(gcfg, luminance_clamp=clamp_stats, median_floor_applied=floor_stats, **({"final_gains_r2_applied": final_stats} if final_stats else {})), "lut": lut_rep,
              "matid": {"encoding": "R8 unorm, index * 16 + 8, decode floor(v * 255 / 16)", "master_px": int(matid4.shape[0]),
                        "runtime_px": int(matid2.shape[0]), "gutter_px_4k": edge_px, "downsample": "2x2 majority"},
              "team_mask": {"R": "одежда (TeamColor) только в классах %s" % ld["team_dye_classes"],
                            "G": "полоса подставки (без изменений)", "B": "0 (без изменений)", "A": 255},
              "edge_texture": "%s_{,2K_}Edge.png: R8 (L), маска рёбер для EdgeMaskTexture v2 (линейная, sRGB выкл.)" % prefix,
              "outputs": outputs, "checks": checks, "passed": all(c["passed"] for c in checks.values()), "status": "измерено"}
    np.save(run_dir / "work" / "labels_4k.npy", lab_g)
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports" / "ld-maps-report.json").write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                                              encoding="utf-8")
    debug_sheet(run_dir, lab_g, presets)
    if not report["passed"]:
        raise RuntimeError("ld_maps checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
    return report


CLASS_COLOURS = {0: (90, 90, 90), 1: (40, 60, 110), 2: (200, 200, 220), 3: (120, 120, 130), 4: (235, 180, 40),
                 5: (200, 170, 60), 6: (180, 110, 60), 7: (140, 70, 30), 8: (100, 50, 25), 9: (150, 40, 40),
                 10: (170, 60, 200), 11: (230, 120, 230), 12: (60, 160, 160), 13: (250, 205, 175), 14: (60, 70, 60),
                 15: (90, 150, 40)}


def debug_sheet(run_dir, lab, presets):
    rgb = np.zeros(lab.shape + (3,), np.uint8)
    for c, col in CLASS_COLOURS.items():
        rgb[lab == c] = col
    im = Image.fromarray(rgb[::-1]).resize((1024, 1024), Image.NEAREST)
    d = ImageDraw.Draw(im)
    names = {c["index"]: c["id"] for c in presets["classes"]}
    present = sorted(set(np.unique(lab).tolist()) - {-1})
    for i, c in enumerate(present):
        d.rectangle([8, 8 + 18 * i, 22, 22 + 18 * i], fill=CLASS_COLOURS[c])
        d.text((28, 8 + 18 * i), "%d %s" % (c, names[c]), fill=(255, 255, 255))
    (run_dir / "preview").mkdir(parents=True, exist_ok=True)
    im.save(run_dir / "preview" / "matid-uv-classes.png", format="PNG", compress_level=6)


# ------------------------------------------------------------------ measure (concept vs renders)
def decode_class_pass(img, presets):
    """Class-ID pass (emission of MatID, Standard view) -> class index per pixel (-1 background)."""
    rgb = np.asarray(img.convert("RGBA")).astype(np.float32)
    v = rgb[..., 0] / 255.0
    cand = np.array([srgb(np.array((i * 16 + 8) / 255.0)) for i in range(16)], np.float32)
    raw = np.array([(i * 16 + 8) / 255.0 for i in range(16)], np.float32)
    # the view transform may be Standard (sRGB) or Raw: take the nearest of either table
    d1 = np.abs(v[..., None] - cand[None, None, :])
    d2 = np.abs(v[..., None] - raw[None, None, :])
    k1, k2 = d1.argmin(-1), d2.argmin(-1)
    use1 = d1.min(-1) <= d2.min(-1)
    cls = np.where(use1, k1, k2).astype(np.int16)
    cls[rgb[..., 3] < 250] = -1
    return cls


def hsv_stats(rgb8):
    x = rgb8.astype(np.float32) / 255.0
    med = np.median(x, 0)
    h, s, v = hsv(med[None, :])
    y = float(luma(lin(med[None, :]))[0])
    return {"median_srgb": [round(float(c) * 255, 1) for c in med], "luma_Y_linear": round(y, 4),
            "hue_deg": round(float(h[0]), 1), "sat": round(float(s[0]), 3), "value": round(float(v[0]), 3)}


def gate(rgb8, g):
    """Concept colour gate of a class (profile measure.concept_gates): hue ranges (deg, list of [lo, hi]), s/v bounds."""
    if not g:
        return np.ones(len(rgb8), bool)
    h, s, v = hsv(rgb8.astype(np.float32) / 255.0)
    ok = np.ones(len(rgb8), bool)
    if "hue_deg" in g:
        hm = np.zeros(len(rgb8), bool)
        for lo, hi in g["hue_deg"]:
            hm |= (h >= lo) & (h <= hi)
        ok &= hm
    for key, arr, op in (("s_min", s, np.greater_equal), ("s_max", s, np.less_equal),
                         ("v_min", v, np.greater_equal), ("v_max", v, np.less_equal)):
        if key in g:
            ok &= op(arr, g[key])
    return ok


def run_measure(run_dir, ld, repo):
    """Per class: concept pixels = class mask of the H2LD class-ID pass (dilated or eroded per class) AND the class colour
    gate (the concept is not the model: thin zones - gold, straps, bow - are offset by a few px; the gate keeps the
    concept pixels of that material); render pixels = the exact class mask (1 px erosion against anti-aliasing).
    Exposure: concept and Blender frames have different light; k = Y(concept) / Y(H2LD) of an anchor class (measure.exposure
    mode anchor_class) or the pixel-weighted geometric mean over the library classes (weighted_geomean). Suggested gain (linear, per channel) = (concept / k) / render, i.e. the class keeps the
    concept's relation to the rest of the figure; the grade applies it to the baked BC of the class."""
    run_dir, repo = Path(run_dir), Path(repo)
    presets = ue_inputs(repo).load_presets()
    names = {c["index"]: c["id"] for c in presets["classes"]}
    raw = run_dir / "work" / "ld_preview_raw"
    mcfg = ld["measure"]
    gates = mcfg.get("concept_gates", {})
    maps_rep = json.loads((run_dir / "reports" / "ld-maps-report.json").read_text(encoding="utf-8"))
    views = {}
    pooled = {}
    for view, concept_rel in ld["concepts"].items():
        cls = decode_class_pass(Image.open(raw / ("class-%s.png" % view)), presets)
        W, H = cls.shape[1], cls.shape[0]
        concept = np.asarray(Image.open(repo / concept_rel).convert("RGB").resize((W, H), Image.BILINEAR))
        sets = {"concept": concept}
        for tag in ("h21", "ld"):
            sets[tag] = np.asarray(Image.open(raw / ("beauty-%s-%s.png" % (view, tag))).convert("RGB"))
        row = {}
        for c in sorted(set(np.unique(cls).tolist()) - {-1}):
            cid = names[c]
            g = gates.get(cid, {})
            m = cls == c
            m_r = ndimage.binary_erosion(m, iterations=1)
            if g.get("render_gate"):  # a class that mixes materials (legacy_bake: snakes + hair): gate both sides
                ry, rx = np.nonzero(m_r)
                rk = gate(sets["ld"][ry, rx], g)
                m_r = np.zeros_like(m_r)
                m_r[ry[rk], rx[rk]] = True
            px = int(g.get("mask_px", -int(mcfg.get("erode_px", 4))))
            m_c = ndimage.binary_dilation(m, iterations=px) if px > 0 else ndimage.binary_erosion(m, iterations=-px) if px < 0 else m
            ys, xs = np.nonzero(m_c)
            keep = gate(concept[ys, xs], g)
            n_c = int(keep.sum())
            if n_c < int(mcfg.get("min_px", 200)) or m_r.sum() < int(mcfg.get("min_px", 200)):
                continue
            ent = {"pixels_render": int(m_r.sum()), "pixels_concept": n_c}
            ent["concept"] = hsv_stats(concept[ys[keep], xs[keep]])
            pooled.setdefault((cid, "concept"), []).append(concept[ys[keep], xs[keep]])
            for tag in ("h21", "ld"):
                ent[tag] = hsv_stats(sets[tag][m_r])
                pooled.setdefault((cid, tag), []).append(sets[tag][m_r])
            row[cid] = ent
        views[view] = row
    zones = {}
    for (cid, tag), arrs in sorted(pooled.items()):
        a = np.concatenate(arrs, 0)
        zones.setdefault(cid, {})[tag] = hsv_stats(a)
        zones[cid]["pixels_%s" % tag] = int(len(a))
    lib = [c for c in zones if (c != "legacy_bake" or c in gates) and "ld" in zones[c] and "concept" in zones[c]]
    lib_k = [c for c in lib if c != "legacy_bake"]
    w = np.array([zones[c]["pixels_ld"] for c in lib_k], np.float64)
    lr = np.array([np.log(zones[c]["concept"]["luma_Y_linear"] / max(zones[c]["ld"]["luma_Y_linear"], 1e-5)) for c in lib_k])
    k_geo = float(np.exp((w * lr).sum() / w.sum()))
    exp_cfg = mcfg.get("exposure", {"mode": "weighted_geomean"})
    if exp_cfg["mode"] == "anchor_class":
        a = zones[exp_cfg["class"]]
        k = a["concept"]["luma_Y_linear"] / max(a["ld"]["luma_Y_linear"], 1e-5)
    else:
        k = k_geo
    k = float(k)
    gains_cur = ld.get("grade", {}).get("gains", {})
    suggest = {}
    for cid in lib:
        z = zones[cid]
        c_lin = lin(np.array(z["concept"]["median_srgb"]) / 255.0) / k
        r_lin = lin(np.array(z["ld"]["median_srgb"]) / 255.0)
        ratio = c_lin / np.maximum(r_lin, 1e-4)
        cur = np.array(gains_cur.get(cid, {}).get("rgb", [1.0, 1.0, 1.0]))
        sug = cur * ratio
        entry = {"residual_ratio_concept_over_ld_exposure_normalised": [round(float(x), 3) for x in ratio],
                 "current_gain": [round(float(x), 4) for x in cur]}
        cls_pre = maps_rep["classes"].get(cid, {}).get("bc_linear_median_before_grade")
        byid = {c["id"]: c for c in presets["classes"]}
        if cls_pre and byid[cid].get("metallic") == 1:
            # metal BC = reflectance: the class median keeps its max channel <= metal_max_channel (no clipped gold,
            # the Tripo relief stays in the channel); hue and saturation of the concept are kept
            top = float((np.array(cls_pre) * sug).max())
            cap = float(mcfg.get("metal_max_channel", 0.92))
            if top > cap:
                sug = sug * cap / top
                entry["metal_cap"] = {"max_channel_before": round(top, 4), "cap": cap}
        entry["suggested_gain"] = [round(float(x), 4) for x in sug]
        suggest[cid] = entry
    for cid, z in zones.items():
        for tag in ("h21", "ld"):
            if tag not in z or "concept" not in z:
                continue
            yc = z["concept"]["luma_Y_linear"] / k
            z["delta_%s_vs_concept" % tag] = {
                "Y_ratio_exposure_normalised": round(z[tag]["luma_Y_linear"] / max(yc, 1e-5), 3),
                "dHue_deg": round(((z[tag]["hue_deg"] - z["concept"]["hue_deg"] + 180) % 360) - 180, 1),
                "dSat": round(z[tag]["sat"] - z["concept"]["sat"], 3)}
    report = {"stage": "ld_measure",
              "method": "зоны = проход ID классов H2LD в орто-кадрах, выровненных по концептам; концепт: маска класса "
                        "(дилатация/эрозия mask_px) И цветовые ворота класса (measure.concept_gates), рендер: точная "
                        "маска класса (эрозия 1 px); медианы sRGB по пикселям зоны, три вида вместе; экспозиция k — "
                        "взвешенное по пикселям геометрическое среднее Y(концепт)/Y(H2LD) по классам библиотеки",
              "exposure_k_concept_over_ld": round(k, 4), "exposure": exp_cfg,
              "exposure_k_weighted_geomean_all_classes": round(k_geo, 4),
              "Y_ratio_concept_over_ld_per_class": {c: round(float(np.exp(x)), 3) for c, x in zip(lib_k, lr)},
              "label": "blender (Cycles, AgX), студийный свет — не игровой; концепт — imagegen (свой свет)",
              "gates": gates, "views": views, "zones": zones, "gain_suggestion": suggest, "status": "измерено"}
    (run_dir / "reports" / "measure-report.json").write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                                             encoding="utf-8")
    return report


# ------------------------------------------------------------------ compose
def run_compose(run_dir, ld, repo):
    run_dir, repo = Path(run_dir), Path(repo)
    comp = load_sibling("compose")
    raw = run_dir / "work" / "ld_preview_raw"
    out = run_dir / "preview"
    out.mkdir(parents=True, exist_ok=True)
    f = comp.font(22)
    made = {}
    presets = ue_inputs(repo).load_presets()
    for view, concept_rel in ld["concepts"].items():
        tiles = [(Image.open(repo / concept_rel).convert("RGB").resize((1021, 1540), Image.BILINEAR), "концепт: %s" % view),
                 (Image.open(raw / ("beauty-%s-h21.png" % view)).convert("RGB"), "H2.1 (как в UE сейчас по текстурам)"),
                 (Image.open(raw / ("beauty-%s-ld.png" % view)).convert("RGB"), "H2LD: MatID+LUT (приближение v2)")]
        cls = decode_class_pass(Image.open(raw / ("class-%s.png" % view)), presets)
        rgb = np.full(cls.shape + (3,), 30, np.uint8)
        for c, col in CLASS_COLOURS.items():
            rgb[cls == c] = col
        base = np.asarray(tiles[0][0]).astype(np.float32)
        ov = np.where((cls >= 0)[..., None], base * 0.45 + rgb * 0.55, base * 0.6).astype(np.uint8)
        tiles.append((Image.fromarray(ov), "зоны MatID поверх концепта"))
        sheet = Image.new("RGB", (1021 * len(tiles), 1540 + 34), (40, 42, 46))
        d = ImageDraw.Draw(sheet)
        for i, (im, label) in enumerate(tiles):
            sheet.paste(im, (1021 * i, 34))
            d.text((8 + 1021 * i, 5), label, fill=(235, 235, 235), font=f)
        path = out / ("compare-ld-%s.jpg" % view)
        sheet.save(path, format="JPEG", quality=92)
        made[path.name] = sha256(path)
    for name in ld["preview"].get("closeups", []):
        ims = [Image.open(raw / ("closeup-%s-%s.png" % (name, t))).convert("RGB") for t in ("h21", "ld")]
        sheet = Image.new("RGB", (900 * 2, 934), (40, 42, 46))
        d = ImageDraw.Draw(sheet)
        for i, (im, label) in enumerate(zip(ims, ("H2.1", "H2LD"))):
            sheet.paste(im, (900 * i, 34))
            d.text((8 + 900 * i, 5), "%s — %s (blender, студийный свет)" % (label, name), fill=(235, 235, 235), font=f)
        path = out / ("closeup-ld-%s.jpg" % name)
        sheet.save(path, format="JPEG", quality=92)
        made[path.name] = sha256(path)
    rep = {"stage": "ld_compose", "sheets": made, "status": "измерено"}
    (run_dir / "reports" / "ld-compose-report.json").write_text(json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                                                encoding="utf-8")
    return rep


if __name__ == "__main__":
    sys.exit("use run_h2_bake.py --mode lookdev")
