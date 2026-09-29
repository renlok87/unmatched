"""Look-dev v2 of King Arthur (2026-09-29): the H2.2 texel state rebuilt from the source run (system python).

The look-dev stages do not rebake and never write into the H2 bake run: they read its work/bake/*.npy,
work/uv-part-id.npy, work/uv-triangles.npz and work/phantom-points.npy and repeat, step by step, textures.main()
(miss fill, phantom repaint, cloth cleanup, atlas fill, H2.1/H2.2 material pass, TeamMask). textures.py and
materials.py are imported, not changed: the H2.2 run stays byte-identical.

build(profile, run) returns the 4K state; check_against_h22(state, profile, run) writes the 8-bit maps exactly as
textures.main() encodes them and compares them with the H2.2 4K masters on disk (sha256 pinned in the H2.2
textures-report): the look-dev classes sit on exactly the texels H2.2 shipped.

The state is cached in <lookdev run>/work/lookdev/state/*.npy (float32 / uint8; ~1.3 GB, local) with the sha256 of
every input, so the later stages do not repeat the 4-minute rebuild.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import materials as M  # noqa: E402
import pure as P  # noqa: E402
import textures as T  # noqa: E402
import uvcheck  # noqa: E402

KEYS_F32 = ("bc_paint", "bc", "mr", "ao", "normal_enc", "team_r", "band", "pos", "metal", "gold_share", "red", "leather",
            "cloth_hard_f")
KEYS_OTHER = ("pid", "isl", "covered", "group", "steel_override", "hit")


def build(profile, run):
    """textures.main() up to the encoding, returning the float state (arrays: row 0 = top of the atlas image = v 1,
    as textures.py: the UV raster draws (1 - v) * size)."""
    paths = P.run_paths(run)
    tcfg = profile["textures"]
    bake = paths["work"] / "bake"
    size = int(profile["uv"]["atlas_px"])
    pid = np.load(paths["work"] / "uv-part-id.npy").astype(np.int32)
    tri = np.load(paths["work"] / "uv-triangles.npz")
    names = [str(n) for n in tri["names"]]
    isl = uvcheck.rasterise(tri["uv"], tri["island"], size)
    covered = pid > 0
    if not np.array_equal(isl > 0, covered):
        raise RuntimeError("island raster and part raster cover different texels")
    hit = np.load(bake / "HIT.npy").astype(np.float32)[..., 0] > 0.5
    pos = np.load(bake / "POS.npy")
    phantom = np.load(paths["work"] / "phantom-points.npy")
    miss = covered & ~hit
    raw = {key: np.load(bake / ("%s.npy" % key)).astype(np.float32) for key in ("BC", "NORMAL", "AO", "MR")}
    rp = tcfg.get("phantom_repaint")
    rule = tcfg["team_mask"]
    miss_phantom = np.zeros(pid.shape, dtype=bool)
    if rp and rp.get("miss_clusters"):
        miss_phantom, _log = T.phantom_miss_mask(miss, pid, names, pos, phantom, rp["parts"],
                                                 float(rp["miss_clusters"]["max_phantom_dist_m"]))
    valid = hit.copy()
    T.island_fill(raw, valid, miss & ~miss_phantom, isl, pid, pos)
    valid |= miss & ~miss_phantom
    for key in raw:
        raw[key] = T.nearest_fill(raw[key], valid)
    in_zone = np.zeros(pid.shape, dtype=bool)
    if rp:
        cloth_ok, gold_ok, _grey = T.colour_classes(raw["BC"], rule)
        frames = T.pos_frames(pos)
        _log, in_zone = T.repaint(raw, pid, names, valid, pos, phantom, rp, cloth_ok, gold_ok, miss_phantom, frames)
        if rp.get("cloth_cleanup"):
            T.cloth_cleanup(raw, pid, names, pos, valid, in_zone, rp["cloth_cleanup"], rule)
    maps = {key: T.nearest_fill(raw[key], covered) for key in raw}
    maps["NORMAL"] = T.normals_encode(maps["NORMAL"])
    bc_paint = maps["BC"]
    mcfg = tcfg["materials"]
    maps["BC"], maps["MR"], _rep, classes = M.apply_materials(bc_paint, maps["MR"], pid, names, pos, covered, mcfg)
    maps["BC"] = T.nearest_fill(maps["BC"], covered)
    maps["MR"] = T.nearest_fill(maps["MR"], covered)
    # TeamMask (H2.2, deprecated by the look-dev TeamAccent)
    from scipy import ndimage
    cloth_idx = [names.index(p) + 1 for p in rule["cloth_parts"] if p in names]
    in_cloth = np.isin(pid, cloth_idx)
    colour_ok = T.colour_classes(bc_paint, rule)[0]
    cloth_hard = in_cloth & colour_ok
    sigma = float(rule["blur_sigma_px"])
    num = ndimage.gaussian_filter(cloth_hard.astype(np.float32), sigma)
    den = ndimage.gaussian_filter(in_cloth.astype(np.float32), sigma)
    soft = np.where(in_cloth, num / np.maximum(den, 1e-6), 0.0).astype(np.float32)
    team_r = T.nearest_fill(soft, covered)
    band_cfg = rule["base_band"]
    base_i = names.index(band_cfg["part"])
    band = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(band)
    sel = (tri["obj"] == base_i) & (np.abs(tri["nz"]) < float(band_cfg["normal_z_max"]))
    for t in tri["uv"][sel]:
        draw.polygon([(float(u * size - 0.5), float((1.0 - vv) * size - 0.5)) for u, vv in t], fill=255)
    band = ((np.array(band) > 127) & covered).astype(np.float32)
    band = T.nearest_fill(band, covered)
    return {"size": size, "names": names, "pid": pid.astype(np.int16), "isl": isl, "covered": covered, "hit": hit,
            "pos": pos.astype(np.float32), "bc_paint": bc_paint.astype(np.float32), "bc": maps["BC"].astype(np.float32),
            "mr": maps["MR"].astype(np.float32), "ao": maps["AO"][..., 0].astype(np.float32),
            "normal_enc": maps["NORMAL"].astype(np.float32), "team_r": team_r.astype(np.float32),
            "band": band.astype(np.float32), "metal": classes["metal"].astype(np.float32),
            "gold_share": classes["gold_share"].astype(np.float32), "red": classes["red"].astype(np.float32),
            "leather": classes["leather"].astype(np.float32), "group": classes["group"].astype(np.int8),
            "steel_override": classes["steel_override"], "cloth_hard_f": cloth_hard.astype(np.float32)}


def maps8(st):
    """The 8-bit 4K maps exactly as textures.main() encodes them (row 0 = top)."""
    team = np.zeros(st["team_r"].shape + (4,), np.float32)
    team[..., 0] = st["team_r"]
    team[..., 1] = st["band"]
    team[..., 3] = 1.0
    n_gl = T.q8(st["normal_enc"])
    n_dx = n_gl.copy()
    n_dx[..., 1] = 255 - n_dx[..., 1]
    orm = np.stack([st["ao"], st["mr"][..., 1], st["mr"][..., 2]], axis=-1)
    return {"BC": T.q8(T.srgb(st["bc"])), "N_OpenGL": n_gl, "N": n_dx, "ORM": T.q8(orm), "TeamMask": T.q8(team)}


def check_against_h22(st, profile, run):
    paths = P.run_paths(run)
    rep = P.load_json(paths["reports"] / "textures-report.json")["outputs"]["master_4k"]
    prefix = profile["textures"]["prefix"]
    out = {}
    for key, arr in maps8(st).items():
        path = paths["textures"] / "master_4k" / ("%s_%s.png" % (prefix, key))
        disk_sha = P.sha256(path)
        with Image.open(path) as img:
            ref = np.asarray(img)
        same = ref.shape == arr.shape and bool(np.array_equal(ref, arr))
        out[key] = {"file": P.rel(path), "sha256_matches_h22_report": disk_sha == rep[key]["sha256"],
                    "pixels_equal_rebuilt": same,
                    "max_abs_lsb": None if ref.shape != arr.shape else int(np.abs(ref.astype(np.int16) - arr.astype(np.int16)).max())}
    return out


def input_hashes(profile_path, run):
    paths = P.run_paths(run)
    files = [Path(profile_path), paths["work"] / "uv-part-id.npy", paths["work"] / "uv-triangles.npz",
             paths["work"] / "phantom-points.npy"] + [paths["work"] / "bake" / ("%s.npy" % k)
                                                      for k in ("BC", "NORMAL", "AO", "MR", "HIT", "POS")]
    return {P.rel(f): P.sha256(f) for f in files}


def save(st, cache, hashes):
    cache.mkdir(parents=True, exist_ok=True)
    for k in KEYS_F32 + KEYS_OTHER:
        np.save(cache / (k + ".npy"), st[k])
    P.write_json(cache / "inputs.json", {"inputs": hashes, "size": st["size"], "names": st["names"]})


def load(cache, hashes=None):
    meta = P.load_json(cache / "inputs.json")
    if hashes is not None and meta["inputs"] != hashes:
        raise RuntimeError("state cache %s is stale (inputs changed); rerun ld_state" % cache)
    st = {k: np.load(cache / (k + ".npy")) for k in KEYS_F32 + KEYS_OTHER}
    st["size"], st["names"] = int(meta["size"]), list(meta["names"])
    return st


def lookdev_paths(profile_path, run_dir):
    """(look-dev profile, its run paths, source profile, source run dir, state cache dir)."""
    prof = P.load_json(profile_path)
    ld = prof["lookdev"]
    src = P.load_json(P.repo_path(ld["source_profile"]))
    src_run = P.repo_path(ld["source_run"])
    paths = P.run_paths(run_dir)
    return prof, paths, src, src_run, paths["work"] / "lookdev" / "state"


def main():
    """Stage ld_state: rebuild, check against the H2.2 4K masters, cache; reports/ld-state-report.json."""
    import time
    t0 = time.time()
    prof, paths, src, src_run, cache = lookdev_paths(sys.argv[1], sys.argv[2])
    src_path = P.repo_path(prof["lookdev"]["source_profile"])
    hashes = input_hashes(src_path, src_run)
    st = build(src, src_run)
    repro = check_against_h22(st, src, src_run)
    passed = all(v["sha256_matches_h22_report"] and v["pixels_equal_rebuilt"] for v in repro.values())
    save(st, cache, hashes)
    rep = {"stage": "ld_state", "profile": P.rel(sys.argv[1]), "source_profile": P.rel(src_path),
           "source_run": P.rel(src_run), "inputs_sha256": hashes, "cache": P.rel(cache),
           "checks": {"h22_state_reproduced": {"passed": passed, "measured": repro,
                                               "expected": "every H2.2 4K master: sha256 = the H2.2 textures-report, "
                                                           "8-bit maps rebuilt here equal pixel for pixel"}},
           "passed": passed, "seconds": round(time.time() - t0, 1)}
    P.write_json(paths["reports"] / "ld-state-report.json", rep)
    print(P.STAGE_MARKER, "ld_state passed=%s" % passed, rep["seconds"])
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
