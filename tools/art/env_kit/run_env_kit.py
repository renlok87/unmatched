"""ENV kit driver: probe -> orientation -> build -> readback -> build-report, one fresh headless Blender per step.

  python tools/art/env_kit/run_env_kit.py --params <env-kit-params.json> [--assets A,B] \
      [--steps probe,orient,build,readback,report] [--blender <blender.exe>]

Steps (all CPU; Blender only with -b --factory-startup, never a GUI session, never a render):
  probe     env_kit_build.py --probe per asset -> <scratch>/probe/<ID>.npz
  orient    orientation_check.py --sheets -> <run>/reports/orientation-check.json (+ mask sheets in scratch)
  build     env_kit_build.py per asset -> <run>/export/SM_Env_<Name>.fbx + T_Env_<Name>_{BC,N,ORM}.png,
            <run>/reports/assets/SM_Env_<Name>.build.json
  readback  tools/tripo-pipeline/blender/check_static_prop_fbx.py per FBX (independent of the build script)
            -> <run>/reports/fbx-readback/SM_Env_<Name>.json
  report    aggregate -> <run>/reports/build-report.json (sha256 of FBX/PNGs, bounds, tris, forward axis, scale)
Logs of every Blender call go to <scratch>/logs/. The working directory of every call is the repository root, so
paths written into reports are repository-relative.
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
BUILD = HERE.parent / "env_kit_build.py"
ORIENT = HERE.parent / "orientation_check.py"
READBACK = REPO / "tools" / "tripo-pipeline" / "blender" / "check_static_prop_fbx.py"
SPC = REPO / "tools" / "tripo-pipeline" / "blender" / "static_prop_candidate.py"
DEFAULT_BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
# Windows: no console window, BELOW_NORMAL priority (the GPU / UE runs of the other tracks keep the machine)
NO_WINDOW = (0x08000000 | 0x00004000) if os.name == "nt" else 0
BLENDER_THREADS = os.environ.get("ENVKIT_BLENDER_THREADS", "4")
ZFRACS = (0.5, 0.45, 0.55, 0.4, 0.6, 0.35, 0.65, 0.3, 0.7)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha256_lf(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rel(p):
    return Path(p).resolve().relative_to(REPO).as_posix()


def run(cmd, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        res = subprocess.run(cmd, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    if res.returncode:
        tail = Path(log).read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        raise SystemExit("FAILED (%d): %s\nlog %s\n%s" % (res.returncode, " ".join(map(str, cmd)), log,
                                                          "\n".join(tail)))
    return res


def blender(bl, script, args, log):
    return run([bl, "-b", "--factory-startup", "-t", BLENDER_THREADS, "--python-exit-code", "1", "--python", rel(script),
                "--"] + args, log)


def aggregate(P, params_path, ids):
    run_dir = REPO / P["run_dir"]
    out = run_dir / "reports" / "build-report.json"
    old = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    assets = dict(old.get("assets", {}))
    findings = []
    for aid in P["assets"]:
        cfg = P["assets"][aid]
        sm = "SM_Env_" + cfg["name"]
        bpath = run_dir / "reports" / "assets" / ("%s.build.json" % sm)
        rpath = run_dir / "reports" / "fbx-readback" / ("%s.json" % sm)
        if not (bpath.is_file() and rpath.is_file()):
            continue
        b = json.loads(bpath.read_text(encoding="utf-8"))
        rb = json.loads(rpath.read_text(encoding="utf-8"))
        fbx = REPO / b["export"]["fbx"]
        tex = {k: REPO / v["path"] for k, v in b["textures"]["outputs"].items()}
        g = b["geometry"]
        st = g["stats_welded_1e-6m_prescale"]
        sh = g["shells_and_holes"]
        dims_rb = rb["dimensions_uu_blender_axes"]
        oc = b["orientation"].get("orientation_check") or {}
        entry = {
            "ue": {"mesh": sm, "textures": ["T_Env_%s_%s" % (cfg["name"], s) for s in ("BC", "N", "ORM")],
                   "material_instance": "MI_Env_%s" % cfg["name"], "fbx_material_slot": b["material_names"],
                   "folder": "/Game/EnvKit/%s/" % cfg["board"]},
            "board": cfg["board"],
            "target": cfg["target"],
            "scale_factor_source_to_final": b["scale_pivot"]["uniform_scale_applied"],
            "yaw_applied_deg": b["orientation"]["yaw_deg_about_plus_z_applied"],
            "forward_axis": {"blend": "-Y", "ue": "+X", "placement": "actor yaw +90 faces the K1 camera (camera yaw -90)",
                             "orientation_check": {"decision": oc.get("decision"),
                                                   "mean_iou_0deg": (oc.get("turns_deg") or {}).get("0", {}).get("mean_iou"),
                                                   "best_silhouette_turn_deg": oc.get("best_silhouette_turn_deg"),
                                                   "silhouette_margin_0_vs_180": oc.get("silhouette_margin_0_vs_180"),
                                                   "colour_margin_0_vs_180": oc.get("colour_margin_0_vs_180")}},
            "fbx": {"path": rel(fbx), "sha256": sha256(fbx), "bytes": fbx.stat().st_size},
            "textures": {k: {"path": rel(p), "sha256": sha256(p), "bytes": p.stat().st_size,
                             "colorspace": b["textures"]["outputs"][k]["colorspace"]} for k, p in tex.items()},
            "readback": {
                "path": rel(rpath), "mesh_objects": rb["mesh_objects"], "triangles": rb["triangles"],
                "materials": rb["material_slots"], "uv_layers": rb["uv_layers"],
                "has_custom_split_normals": rb["has_custom_split_normals"],
                "bounds_min_uu_readback": rb["bounds_min_uu"], "bounds_max_uu_readback": rb["bounds_max_uu"],
                "dimensions_uu_readback_xyz": dims_rb,
                "dimensions_uu_ue": {"X_depth_front_back": dims_rb[0], "Y_width": dims_rb[1], "Z_height": dims_rb[2]},
                "topology_welded_1um": rb["topology_welded_1um"],
                "protrusion_axis_readback": rb["protrusion_axis_blender"],
                "protrusion_z_frac_used": rb.get("protrusion_z_frac_used"),
            },
            "uv0": {k: b["uv0"].get(k) for k in ("islands", "triangles_out_of_0_1", "uv_bounds",
                                                 "overlap_pixels_between_islands", "overlap_pixels_inside_islands_strict",
                                                 "flipped_uv_triangles_vs_island_majority", "zero_area_uv_triangles",
                                                 "uv_area_used_fraction", "texel_density_px_per_m_at_raster",
                                                 "min_gutter_px_estimate", "raster_size_px")},
            "geometry": {
                "closed_manifold_consistent": g["closed_manifold_consistent"],
                "open_edges": st["welded_boundary_edges"], "open_edge_loops": sh["open_edge_loops"],
                "non_manifold_edges": st["welded_non_manifold_edges"],
                "faces_with_inconsistent_winding": st["faces_with_inconsistent_winding"],
                "degenerate_faces": st["degenerate_faces_area_lt_1e-12"], "loose_vertices": st["loose_vertices"],
                "open_edge_loops_by_kind": sh["open_edge_loops_by_kind"],
                "hole_area_uu2_total": sh["hole_area_uu2_total"],
                "shells": sh["shells"], "shells_isolated": sh["shells_isolated"],
                "shells_isolated_off_ground": sh["shells_isolated_off_ground"],
                "shells_inverted_closed": sh["shells_inverted_closed"],
                "signed_volume_m3_prescale": st["signed_volume_m3"],
                "corners_pointing_into_surface": g["corner_normals"]["corners_pointing_into_surface"],
                "ray_escape_faces": g["ray_escape_facing"]["faces"],
                "ray_escape_area_fraction": g["ray_escape_facing"]["area_fraction"],
            },
            "checks_passed": b["checks_passed"], "checks": b["checks"],
            "build_report": rel(bpath),
        }
        # findings (reported, not repaired)
        fl = []
        gg = entry["geometry"]
        if gg["open_edges"]:
            kinds = sh["open_edge_loops_by_kind"]
            big = sh["holes_top10_by_area"][0] if sh["holes_top10_by_area"] else None
            fl.append("open edges %d in %d loop(s): %d zero-width crack(s), %d hole(s)%s" % (
                gg["open_edges"], gg["open_edge_loops"], kinds["crack (zero-width T-junction/sliver)"], kinds["hole"],
                (" totalling %.1f uu2 (largest %.1f uu2, rim %.1f uu, mean width %.2f uu, at z %.0f uu)"
                 % (sh["hole_area_uu2_total"], big["area_uu2"], big["length_uu"], big["mean_width_2A_over_P_uu"],
                    big["centre_uu_prescale_frame"][2]) if big else "")))
        if gg["non_manifold_edges"]:
            fl.append("non-manifold edges %d" % gg["non_manifold_edges"])
        rf, ra = gg["ray_escape_faces"], gg["ray_escape_area_fraction"]
        if rf["inward"]:
            fl.append("faces facing inward by ray escape %d (%.1f %% of area; one-sided material culls them from "
                      "outside)" % (rf["inward"], 100 * ra["inward"]))
        if ra["sheet"] >= 0.02:
            fl.append("open sheet faces seen from both sides %d (%.1f %% of area)" % (rf["sheet"], 100 * ra["sheet"]))
        if gg["faces_with_inconsistent_winding"]:
            fl.append("recalc winding disagreements %d (bmesh on welded mesh; unreliable on open/non-manifold "
                      "meshes, ray escape is the measure)" % gg["faces_with_inconsistent_winding"])
        if gg["shells_inverted_closed"]:
            fl.append("closed shells with negative volume (inside-out) %d" % gg["shells_inverted_closed"])
        if gg["shells_isolated"]:
            fl.append("isolated shells (gap > %.1f uu) %d, off ground %d" % (
                sh["shells_isolated_gap_gt_uu"], gg["shells_isolated"], gg["shells_isolated_off_ground"]))
        if gg["degenerate_faces"]:
            fl.append("degenerate faces %d (UE drops them at build)" % gg["degenerate_faces"])
        if entry["uv0"]["overlap_pixels_between_islands"]:
            fl.append("UV overlap between islands %d px at %d" % (entry["uv0"]["overlap_pixels_between_islands"],
                                                                   entry["uv0"]["raster_size_px"]))
        if entry["uv0"]["triangles_out_of_0_1"]:
            fl.append("UV triangles outside 0-1: %d" % entry["uv0"]["triangles_out_of_0_1"])
        if not (oc.get("decision") or {}).get("consistent", True):
            fl.append("orientation: " + "; ".join(oc["decision"]["reasons"]))
        entry["findings"] = fl
        assets[aid] = entry
        findings += ["%s: %s" % (aid, f) for f in fl]
    scripts = [BUILD, ORIENT, HERE, READBACK, SPC]
    doc = {
        "schema": "unmatched.env-kit.build-report/1",
        "asset": "ASSET-ENV-KIT-001", "runId": Path(P["run_dir"]).name,
        "status": "measured",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False,
                   "note": "technical pipeline output; nothing here is an art decision"},
        "generated": datetime.date.today().isoformat(),
        "params": rel(params_path),
        "scripts_sha256_lf": {rel(s): text_sha256_lf(s) for s in scripts},
        "blender_version": next(iter(json.loads((REPO / v["build_report"]).read_text(encoding="utf-8"))["blender_version"]
                                     for v in assets.values()), None) if assets else None,
        "no_render_policy": ("CPU only: headless Blender -b --factory-startup, no Eevee/Cycles/Workbench render, no AO "
                             "bake, no viewport; orientation verified with silhouette masks (PIL) and face colour "
                             "statistics against the Tripo reference views"),
        "conventions": {
            "units": "FBX numbers are centimetres = UE uu, UnitScaleFactor patched to 1.0 (UM_FBX_v1)",
            "forward_axis": ("front (Tripo 'front' reference view) = glTF +Z = .blend -Y = UE +X (UM_FBX_v1 +90 deg Z "
                             "turn; the FBX readback frame maps .blend -Y -> +X, as for SM_Decor_Barrel/Lantern)"),
            "placement_yaw": "K1 camera yaw -90 looks along -Y: actor yaw +90 turns the front (+X) to the camera",
            "pivot": "base centre: centre of the XY bounds, min Z = 0",
            "ue_import": P["ue"]["import"],
            "textures": P["ue"]["textures"],
            "orm": "R = 1.0 (no AO; Tripo gives no occlusion map and the Cycles bake is not run), G = roughness, B = metallic",
            "normal": "DirectX (green flipped from the glTF OpenGL map), same as SM_Decor_Barrel/Lantern",
            "base_colour": "glTF baseColorFactor 0.8 multiplied in linear light (as the lantern candidate)",
            "memory_rule_note": ("'FBX_SCALE_UNITS + import 100' (S05 memory) belongs to a profile without the "
                                 "UnitScaleFactor patch; with UM_FBX_v1 (lantern/barrel, RIG-CONTRACT.md) UE imports "
                                 "at import_uniform_scale 1.0"),
        },
        "totals": {
            "assets_built": len(assets),
            "triangles": sum(v["readback"]["triangles"] for v in assets.values()),
            "triangles_max": max((v["readback"]["triangles"] for v in assets.values()), default=None),
            "export_bytes": sum(v["fbx"]["bytes"] + sum(t["bytes"] for t in v["textures"].values())
                                for v in assets.values()),
            "checks_passed": all(v["checks_passed"] for v in assets.values()),
        },
        "findings": findings,
        "assets": dict(sorted(assets.items())),
    }
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("BUILD_REPORT", rel(out), json.dumps(doc["totals"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True)
    ap.add_argument("--assets", default=None)
    ap.add_argument("--steps", default="probe,orient,build,readback,report")
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    a = ap.parse_args()
    params_path = Path(a.params).resolve()
    P = json.loads(params_path.read_text(encoding="utf-8"))
    ids = a.assets.split(",") if a.assets else list(P["assets"])
    steps = a.steps.split(",")
    scratch = Path(P["scratch_dir"])
    logs = scratch / "logs"
    run_dir = REPO / P["run_dir"]
    for aid in ids:
        if aid not in P["assets"]:
            raise SystemExit("unknown asset %s" % aid)
    if "probe" in steps:
        for aid in ids:
            blender(a.blender, BUILD, [rel(params_path), aid, "--probe"], logs / ("probe-%s.log" % aid))
            print("probe", aid)
    if "orient" in steps:
        run([sys.executable, rel(ORIENT), "--params", rel(params_path), "--assets", ",".join(ids), "--sheets"],
            logs / "orient.log")
        print(Path(logs / "orient.log").read_text(encoding="utf-8"))
    if "build" in steps:
        for aid in ids:
            blender(a.blender, BUILD, [rel(params_path), aid], logs / ("build-%s.log" % aid))
            print("build", aid)
    if "readback" in steps:
        (run_dir / "reports" / "fbx-readback").mkdir(parents=True, exist_ok=True)
        for aid in ids:
            sm = "SM_Env_" + P["assets"][aid]["name"]
            fbx = run_dir / "export" / ("%s.fbx" % sm)
            out = run_dir / "reports" / "fbx-readback" / ("%s.json" % sm)
            # the readback's informational protrusion band (height fraction +-8 %) needs vertices; long quads
            # (arcade columns) can leave the 0.5 band empty -> the next fraction is tried and recorded
            for zfrac in ZFRACS:
                try:
                    blender(a.blender, READBACK, [rel(fbx), rel(out), str(zfrac)],
                            logs / ("readback-%s.log" % aid))
                except SystemExit as exc:
                    if "max() iterable argument is empty" in str(exc) and zfrac != ZFRACS[-1]:
                        continue
                    raise
                doc = json.loads(out.read_text(encoding="utf-8"))
                doc["protrusion_z_frac_used"] = zfrac
                out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
                break
            print("readback", aid, zfrac)
    if "report" in steps:
        aggregate(P, params_path, ids)


if __name__ == "__main__":
    main()
