"""Machine report of an H2 bake run (system Python): gathers the stage reports into one JSON and lists the files
for the commit manifest (sha256, bytes; >= 50 MB never listed).

    python make_report.py <profile.json> <run_dir> <out.json> [--notes notes.json]

--notes: a JSON with the hand-written parts of the report (findings, visual assessment, budgets proposal, followups);
merged under "assessment".
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
profile_path, run, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
notes = json.loads(Path(sys.argv[sys.argv.index("--notes") + 1]).read_text(encoding="utf-8")) if "--notes" in sys.argv else {}
P = json.loads(profile_path.read_text(encoding="utf-8"))


def rel(p):
    return Path(p).resolve().relative_to(REPO).as_posix()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name):
    p = run / "reports" / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


imp, low, uvs, uvr, bake, tex, rig = (load(n) for n in ("h2-import-report.json", "h2-lowpoly-report.json",
                                                        "h2-uv-stage.json", "uv-report.json", "h2-bake-report.json",
                                                        "textures-report.json", "h2-rig-report.json"))
val = load("validate-skeletal-mesh-v2.json")
det = load("determinism.json")
see = load("see-through.json")
k2p = run / "preview" / "k2" / "review-frames-k2.json"
k2frames = json.loads(k2p.read_text(encoding="utf-8"))["frames"] if k2p.exists() else {}
budget = load("budget-probe.json")
shape = json.loads((run / "preview" / "shape" / "preview-lowpoly.json").read_text(encoding="utf-8"))
inst = json.loads((run / "preview" / "instances" / "instances-analysis.json").read_text(encoding="utf-8"))
deform = {}
for lab in ("h2-blend", "h2-fbx"):
    d = json.loads((run / "preview" / "deform" / ("%s-deform.json" % lab)).read_text(encoding="utf-8"))
    deform[lab] = {t["test"]: {"status": t["status"], "moved_vertices": t["moved_vertices"],
                               "centroid_z_norm": t["centroid_z_norm"], "centroid_x_norm": t["centroid_x_norm"]}
                   for t in d["tests"]}

report = {
    "schema": "unmatched.h2-bake.hero-report/1",
    "asset_id": P["asset_id"], "date": "2026-09-29", "iteration": "H2 (проработка героев по концептам hero-quality-v1)",
    "status": "измерено", "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False,
                                     "ue_imported": False},
    "credits": {"tripo": 0, "paid_operations": 0, "note": "only local Blender/Python; the Tripo stage was paid earlier by the orchestrator"},
    "profile": {"path": rel(profile_path), "sha256": sha(profile_path), "profile_id": P["profile_id"]},
    "module": "tools/tripo-pipeline/blender/h2_bake_harpy/",
    "run_dir": rel(run),
    "blender": imp["blender"],
    "sources": imp["sources"],
    "import": {
        "parts": {p: {"triangles": v["triangles_textured"], "bounds_min_m": v["bounds_min_m"], "bounds_max_m": v["bounds_max_m"],
                      "ray_escape_score": v["ray_escape"]["score"], "open_edges": v["topology_textured_welded"]["open_edges"],
                      "shells": v["topology_textured_welded"]["shells"],
                      "non_manifold_edges": v["topology_textured_welded"]["non_manifold_edges"],
                      "corner_normals_against_winding_fraction": v["corner_normals_against_winding_fraction"],
                      "geometry_equals_textured_glb": v["geometry_vs_textured"]["canonical_triangle_sets_equal"],
                      "basecolor_px": next((t["size"] for k, t in v["textures"].items() if "basecolor" in k), None)}
                  for p, v in imp["parts"].items()},
        "geometry_files_match": imp["geometry_files_match"], "triangles_total": imp["totals"]},
    "repair": {"profile": P["repair"], "measured": low["repair"],
               "evidence_frames": sorted(rel(p) for p in (run / "preview" / "evidence").glob("*.jpg"))},
    "game_mesh": {
        "triangles_figure": low["triangles_total"], "triangles_base": rig["measure"]["triangles_base"],
        "parts": {p: {k: v[k] for k in ("role", "side", "target_triangles", "triangles", "vertices", "distance_high_to_low",
                                        "distance_low_to_high", "faces_flipped_vs_highpoly_fraction", "open_edges",
                                        "non_manifold_edges", "inconsistent_winding_edges", "priority_regions",
                                        "vertex_group_factor")}
                  for p, v in low["parts"].items()},
        "settings": low["settings"], "silhouette_iou_vs_highpoly": shape["silhouette_iou"]},
    "uv": {"stage": {k: uvs[k] for k in ("charts", "fallback_smart_project_faces_per_round", "uv_flipped_faces_after",
                                          "uv_self_overlap_faces_after", "islands", "islands_total", "priority_scaled")},
           "check": {k: uvr[k] for k in uvr if k not in ("schema",)}},
    "bake": {k: bake[k] for k in ("device", "size", "cage_extrusion_m", "max_ray_distance_m", "ao_distance_m", "seed",
                                  "occluders", "recolor", "seconds")},
    "bake_passes": {k: {x: v[x] for x in ("type", "samples", "texels_written", "rgb_mean_written")}
                    for k, v in bake["passes"].items()},
    "textures": tex,
    "rig": {k: rig[k] for k in ("seat", "base", "armature", "weights", "seam_gap_probe", "sockets", "measure", "exports",
                                "roundtrip", "checks", "checks_failed")},
    "rig_deform_probe": deform,
    "validate_clip_skeletal_mesh_v2": {"status": "PASS" if val and all(c.get("status") == "pass" for c in val.get("checks", []))
                                       else "see file", "checks": [(c.get("name") or c.get("check"), c.get("status"))
                                                                   for c in (val or {}).get("checks", [])],
                                       "file": rel(run / "reports" / "validate-skeletal-mesh-v2.json")},
    "instances": {name: {"all_distinguishable": f["all_distinguishable"],
                         "per_instance": {k: {"visible_slots": v["visible_slots"], "lit_slots": v["lit_slots"],
                                              "consistent_indices": v["consistent_indices"],
                                              "pip_radius_px": v["pip_radius_px"], "min_lit_delta": v["min_lit_delta"]}
                                          for k, v in f["instances"].items()}}
                  for name, f in inst["frames"].items()},
    "see_through": ({k: see[k] for k in ("gate", "gate_strict", "all_azimuths_worst_px", "all_azimuths_total_px",
                                         "camera", "method", "label")}
                    | {"frames_azimuth_distance_px_components": [(f["azimuth_deg"], f["distance_m"], f["see_through_px"],
                                                                  f["components_px"]) for f in see["frames"]]}) if see else None,
    "stitch": {k: low["stitch"][k] for k in ("vertices_inserted", "vertices_snapped", "junction_vertices", "chains",
                                             "settings")} if low.get("stitch") else None,
    "k2_frames": {n: {k: v for k, v in f.items() if k in ("left_to_right", "azimuth_deg", "distance_m", "label")}
                  for n, f in k2frames.items() if not n.startswith("_")},
    "k2_projection": load("k2-projection.json"),
    "budget_probe": budget,
    "determinism": det,
    "assessment": notes,
}
files = []
skip_dirs = {"work"}
for p in sorted(run.rglob("*")):
    if p.is_dir() or skip_dirs & set(p.relative_to(run).parts):
        continue
    size = p.stat().st_size
    files.append({"path": rel(p), "bytes": size, "sha256": sha(p), "commit": size < 50 * 1024 * 1024})
report["files"] = files
report["files_total_bytes"] = sum(f["bytes"] for f in files)
out.write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
print("REPORT_OK", len(files), report["files_total_bytes"])
