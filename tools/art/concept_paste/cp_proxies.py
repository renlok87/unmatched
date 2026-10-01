"""ENV-MAPS P7 (ENV-U15) concept paste, track A: proxy meshes + 3D detail meshes (ASSET-ENV-CONCEPT-PASTE-001).

Numpy side (this file) + headless Blender side (blender_cp_assets.py, `blender -b --factory-startup`, CPU only, never
a running Blender GUI / MCP session). Outputs under art/pipeline-candidates/ASSET-ENV-CONCEPT-PASTE-001/<run>/:

  export/SM_<Name>_ConceptSheet.fbx  the depth sheet of design.json 3_projection (relief proxy): a grid in C0 image space
                                 (vertexStepPx) whose vertices lie on C0 rays at the depth of the spec proxies (ground
                                 Z -3, canopy, bay ramp, front cliff, vertical flats; clamped to the sea level); cells
                                 entirely outside the island matte or entirely under the 3D frame are dropped; planar
                                 regions dissolved (angle limit) and triangulated. Board-actor space (pivot = map
                                 centre, identity transform under the board actor). UV0 = plate B UV, UV1 = plate A UV of
                                 the vertex's own C0 pixel (exact AT the vertices only: M_ConceptPaste projects the world
                                 position through C0 - cp_bake.py uvContract)
  (optional, proxies.seaMesh) SM_<Name>_ConceptSea.fbx  the sea layer on a coarser C0 grid (sea plane / sky cylinder);
                                 off by default: S08ConceptPaste builds the sea layer from engine planes
  export/SM_EnvCP_LanternHead.fbx  the hanging lantern of SM_Env_LanternPost (ENV-S-LANTERN-POST, Tripo, our own) without
                                 the post / arm: faces whose centroid lies under the arm on the lantern side; pivot = base
                                 centre; same UVs -> MI_Env_LanternPost (the clean plate keeps the painted posts)
  export/SM_EnvCP_BannerCloth.fbx  the cloth + cross-bar of SM_Env_Banner without the pole foot / spear, the cloth
                                 stretched along Z to the painted aspect; pivot = base centre -> MI_Env_Banner
  reports/build-report.json      sha256, triangles, bounds, pivots, lantern glow offset, cloth metrics, FBX read-back,
                                 UM_FBX_v1 conformance (k_blender.py helpers)

The geometry comes from the committed spec parameters (<map>.paste.json); no image data goes into these meshes, so
they live in git like the other pipeline candidates. The textures stay out of git (cp_bake.py).

  python -B tools/art/concept_paste/cp_proxies.py build [--maps sarpedon,marmoreal] [--blender EXE]
  python -B tools/art/concept_paste/cp_proxies.py check      # sha256 of the FBX against the build report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cp_common as C  # noqa: E402
import paste_proto as pp  # noqa: E402

REPO = C.REPO
ASSET = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-CONCEPT-PASTE-001"
RUN = ASSET / "20261001-p7"
PARAMS = RUN / "scripts" / "cp-assets-params.json"
BLENDER_SCRIPT = HERE / "blender_cp_assets.py"
DEFAULT_BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
EXT = pp.EXT  # (-384, -216, 2304, 1296) C0 px


def load_params(path: Path = PARAMS) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ depth sheet / sea grids (UE numbers)
def grid(step: float):
    gx = np.arange(EXT[0], EXT[2] + step * 0.5, step)
    gy = np.arange(EXT[1], EXT[3] + step * 0.5, step)
    return gx, gy


def uv_of(gx: np.ndarray, gy: np.ndarray, rect) -> tuple[np.ndarray, np.ndarray]:
    x0, y0, x1, y1 = rect
    return (gx - x0) / (x1 - x0), (gy - y0) / (y1 - y0)


def sheet_data(map_key: str, step: float | None = None) -> dict:
    """Vertices (ny, nx, 3), kept cells (ny-1, nx-1), C0 px grid, per-vertex island / under-frame flags."""
    spec = pp.load_spec(map_key)
    cam = C.concept_cam()
    step = float(step or spec["geometry"]["vertexStepPx"])
    gx, gy = grid(step)
    P = pp.sheet_points(spec, cam, gx, gy, "relief")
    island = pp.poly_mask_grid(spec["geometry"]["islandMatte"]["poly"], gx, gy, 2)
    FX, FY = np.meshgrid(gx, gy)
    X, Y = pp.ground_xy(cam, FX, FY, spec["geometry"]["groundZ"])
    u = float(spec["cut"]["underFrameUU"])
    under = (np.abs(X) < C.FRAME_HX - u) & (np.abs(Y) < C.FRAME_HY - u)
    corners = lambda a: np.stack([a[:-1, :-1], a[1:, :-1], a[1:, 1:], a[:-1, 1:]], 0)  # noqa: E731
    in_island = corners(island > 0.0).any(0)
    in_island = ndimage.binary_dilation(in_island, iterations=1)
    all_under = corners(under).all(0)
    keep = in_island & ~all_under
    return {"spec": spec, "cam": cam, "step": step, "gx": gx, "gy": gy, "P": P, "keep": keep,
            "island": island, "under": under}


def sea_data(map_key: str, step: float) -> dict:
    spec = pp.load_spec(map_key)
    cam = C.concept_cam()
    g = spec["geometry"]
    gx, gy = grid(step)
    FX, FY = np.meshgrid(gx, gy)
    d = cam.rays(FX, FY)
    t = (g["seaZ"] - cam.pos[2]) / d[..., 2]
    P = cam.pos + t[..., None] * d
    cyl = g["skyCylinder"]
    cxy = np.array(cyl["centre"], float)
    R = float(cyl["radius"])
    far = (np.hypot(P[..., 0] - cxy[0], P[..., 1] - cxy[1]) > R) | (t <= 0)
    ox, oy = cam.pos[0] - cxy[0], cam.pos[1] - cxy[1]
    a = d[..., 0] ** 2 + d[..., 1] ** 2
    b = 2 * (ox * d[..., 0] + oy * d[..., 1])
    cc = ox * ox + oy * oy - R * R
    tc = (-b + np.sqrt(np.maximum(b * b - 4 * a * cc, 0))) / (2 * a)
    Pc = cam.pos + tc[..., None] * d
    P = np.where(far[..., None], Pc, P)
    keep = np.ones((len(gy) - 1, len(gx) - 1), bool)
    return {"spec": spec, "cam": cam, "step": step, "gx": gx, "gy": gy, "P": P, "keep": keep,
            "onCylinder": int(far.sum())}


def mesh_arrays(data: dict, centre_rect, outer_rect) -> dict:
    """Flat arrays for the Blender side: verts (N, 3) UE numbers, quads (M, 4) CCW seen from the C0 camera (= the
    outward side), uv0 / uv1 per vertex."""
    P, keep, gx, gy = data["P"], data["keep"], data["gx"], data["gy"]
    ny, nx = P.shape[:2]
    used = np.zeros((ny, nx), bool)
    ncell = np.zeros((ny, nx), np.int32)
    jj, ii = np.nonzero(keep)
    for dj, di in ((0, 0), (1, 0), (1, 1), (0, 1)):
        used[jj + dj, ii + di] = True
        np.add.at(ncell, (jj + dj, ii + di), 1)
    index = -np.ones((ny, nx), np.int64)
    index[used] = np.arange(int(used.sum()))
    verts = P[used]
    FX, FY = np.meshgrid(gx, gy)
    u0, v0 = uv_of(FX[used], FY[used], outer_rect)
    u1, v1 = uv_of(FX[used], FY[used], centre_rect)
    # image grid: x right (+X), y down (towards +Y / the camera): TL -> TR -> BR -> BL is counter-clockwise seen from
    # the camera side in right-handed math on the UE numbers (the MeshBuilder convention)
    quads = np.stack([index[jj, ii], index[jj, ii + 1], index[jj + 1, ii + 1], index[jj + 1, ii]], 1)
    # orientation check against the camera (every quad must face C0)
    cam = data["cam"]
    A, B_, D = verts[quads[:, 0]], verts[quads[:, 1]], verts[quads[:, 3]]  # n = (TR - TL) x (BL - TL)
    n = np.cross(B_ - A, D - A)
    facing = np.einsum("ij,ij->i", n, cam.pos[None, :] - A)
    # UV v runs downwards in the image like the texture rows: UE / FBX UV origin conventions are applied in Blender
    return {"verts": verts.astype(np.float64), "quads": quads, "uv0": np.stack([u0, v0], 1),
            "interior": ncell[used] == 4,
            "uv1": np.stack([u1, v1], 1), "facingMin": float(facing.min()), "backFacing": int((facing <= 0).sum()),
            "gridShape": [int(ny), int(nx)], "cellsKept": int(keep.sum()), "cellsTotal": int(keep.size)}


def write_npz(path: Path, arrays: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, verts=arrays["verts"], quads=arrays["quads"], uv0=arrays["uv0"], uv1=arrays["uv1"],
             interior=arrays["interior"])


def prepare(maps: list[str], params: dict) -> dict:
    """Writes the proxy npz files to the scratch folder; returns the per-map numpy-side report."""
    scratch = Path(params["scratch_dir"]) / "work"
    info = {"_camPosUE": [float(v) for v in C.concept_cam().pos]}
    for key in maps:
        spec = pp.load_spec(key)
        tex = spec["bake"]["textures"]
        centre_rect, outer_rect = tex["PlateA"]["rectC0"], tex["PlateB"]["rectC0"]
        pr = params["proxies"]
        sh = sheet_data(key, pr["sheetStepPx"])
        sa = mesh_arrays(sh, centre_rect, outer_rect)
        if sa["backFacing"]:
            raise RuntimeError(f"{key}: {sa['backFacing']} sheet quads face away from C0")
        write_npz(scratch / f"{key}-sheet.npz", sa)
        info[key] = {"name": C.MAPS[key]["name"],
                     "sheet": {"npz": (scratch / f"{key}-sheet.npz").as_posix(), "stepPx": sh["step"],
                               "grid": sa["gridShape"], "cellsKept": sa["cellsKept"], "cellsTotal": sa["cellsTotal"],
                               "zRange": [round(float(sa["verts"][:, 2].min()), 2), round(float(sa["verts"][:, 2].max()), 2)]},
                     "uvRects": {"uv0PlateB": outer_rect, "uv1PlateA": centre_rect}}
        if pr.get("seaMesh"):  # optional: the profile block builds the sea layer from engine planes (S08ConceptPaste)
            se = sea_data(key, pr["seaStepPx"])
            ea = mesh_arrays(se, centre_rect, outer_rect)
            if ea["backFacing"]:
                raise RuntimeError(f"{key}: {ea['backFacing']} sea quads face away from C0")
            write_npz(scratch / f"{key}-sea.npz", ea)
            info[key]["sea"] = {"npz": (scratch / f"{key}-sea.npz").as_posix(), "stepPx": se["step"],
                                "grid": ea["gridShape"], "verticesOnCylinder": se["onCylinder"]}
    return info


def run_blender(blender: str, params_path: Path, prep_path: Path) -> int:
    cmd = [blender, "-b", "--factory-startup", "--python", str(BLENDER_SCRIPT), "--",
           str(params_path), str(prep_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = Path(load_params(params_path)["scratch_dir"]) / "work" / "blender-build.log"
    log.write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr, encoding="utf-8")
    for line in proc.stdout.splitlines():
        if line.startswith(("CP-ASSETS", "Error", "Traceback")):
            print(line)
    return proc.returncode


def check(params_path: Path = PARAMS, verbose: bool = True) -> dict:
    params = load_params(params_path)
    run = REPO / params["run_dir"]
    rep_path = run / "reports" / "build-report.json"
    res = {"ok": True, "errors": [], "exports": {}}
    if not rep_path.is_file():
        res.update(ok=False, errors=[f"{rep_path} missing (run: cp_proxies.py build)"])
    else:
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        for e in rep["exports"]:
            p = REPO / e["fbx"]
            got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
            ok = got == e["sha256"] and all(e.get("checks", {}).values())
            res["exports"][e["name"]] = {"fbx": e["fbx"], "ok": ok}
            if not ok:
                res["ok"] = False
                res["errors"].append(f"{e['name']}: " + ("missing" if got is None else
                                                         "sha256 differs" if got != e["sha256"] else
                                                         f"checks failed {[k for k, v in e['checks'].items() if not v]}"))
        if not rep.get("checks_passed"):
            res["ok"] = False
            res["errors"].append("build report checks_passed is false")
    if verbose:
        print(f"CP-ASSETS-CHECK {'ok' if res['ok'] else 'FAILED'} " + "; ".join(res["errors"]))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--maps", default="sarpedon,marmoreal")
    b.add_argument("--blender", default=DEFAULT_BLENDER)
    b.add_argument("--params", type=Path, default=PARAMS)
    c = sub.add_parser("check")
    c.add_argument("--params", type=Path, default=PARAMS)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return 0 if check(a.params)["ok"] else 1
    params = load_params(a.params)
    maps = [m.strip() for m in a.maps.split(",") if m.strip()]
    info = prepare(maps, params)
    prep_path = Path(params["scratch_dir"]) / "work" / "prepare.json"
    prep_path.write_text(json.dumps(info, indent=1), encoding="utf-8")
    code = run_blender(a.blender, a.params, prep_path)
    if code != 0:
        print(f"blender exited {code}; log: {Path(params['scratch_dir']) / 'work' / 'blender-build.log'}")
        return code
    return 0 if check(a.params)["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
