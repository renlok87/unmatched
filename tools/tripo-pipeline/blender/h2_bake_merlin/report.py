"""Aggregate the stage reports of the H2 bake into the machine report docs/art-pipeline/merlin-h2-report.json.

python report.py <profile.json> <out.json> [--determinism <determinism.json>]
Only reads reports/artifacts; writes one JSON (sorted keys). Numbers are measured; budgets are proposals.
--determinism defaults to <run>/reports/determinism.json (committed; its sections are written by determinism.py).
Also scans every artifact (export, textures, reports, preview) for absolute host paths (check artifacts.no_host_paths).
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


DEFERRED_UE_STEPS = [
    "UE import (legacy FBX, import_uniform_scale 1.0) of export/SK_Merlin_H2.fbx and export/SM_Merlin_H2_Base.fbx into a new folder "
    "/Game/PipelineCandidates/Merlin/20260929-h2-bake (own Skeleton; bone 0 SKEL_UM_Humanoid, 18 bones in UE)",
    "textures: the 2K runtime set (or the 4K master with MaxTextureSize 2048): BC sRGB TC_Default; N (DirectX) TC_Normalmap "
    "flip_green false; ORM linear TC_Masks; TeamMask linear TC_Grayscale (TeamMaskRGBA only if wave 4 adopts the RGBA contract)",
    "materials: MI of /Game/UM/Materials/M_UM_Figure (route um-master, team_color_mode mask, TeamMask.R = cloth) + team MIs "
    "Gold #E8C06A / Silver #9FC2D8 via FromSRGBColor; base: MI of M_UM_BaseMarker (textures true, SideBandWeight 1)",
    "sockets on the mesh: Weapon -> weapon_R (0,0,0); Head -> head at the predicted (-0.121, -1.448, 2.588); verify live "
    "get_socket_location against target_ue_component_uu +-0.05 uu (build-report sockets)",
    "checks in UE: face +X (capture_ue_axes), hood top 45.0 uu / crystal 49.42 uu, base 24 x 24 x 5 uu, 1 material slot per mesh, "
    "triangles 30 047 + 3 920 / 2 240 after the UE mesh build",
    "P1.7 control scene under DX12 + Lumen (wave 4 render decision): K1, K2 1.6x/5x, front/back 5x, team swap in grey "
    "(team_contrast.py), base_seethrough.py on the H2 FBX pair; compare with the previous CLI candidate frames",
    "LOD1 (x0.5 tris) for K1/K2 1.6x and its K2 frame (not built)",
]

FOLLOWUPS = [
    "commit order: commit this candidate together with or after wave 4 W4-D. validate-skeletal-mesh.json (PASS on "
    "UM_HUMANOID_17_v2) and the probe stage need the uncommitted W4-D files tools/tripo-pipeline/anim/validate_clip.py "
    "(modified), tools/tripo-pipeline/anim/rig_rules.py (untracked) and docs/art-pipeline/rig/rig-contract.json + "
    "RIG-CONTRACT.md (v2); at HEAD validate_clip knows only v1 and fails on --skeleton=UM_HUMANOID_17_v2",
    "commit in the same commit as this manifest (the profile, the source stage and the sheets reference them): "
    "source-specs/tripo-de0654b5-h2.json, 20260929-h2-tripo/reports/tripo-run.json, ASSET-MERLIN-001/.gitignore (ignores "
    "the >50 MB GLBs and 20260929-h2-bake/logs/), art/imagegen/hero-quality-v1/merlin/{merlin-front,merlin-side,merlin-back}.png "
    "+ prompts.md and art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png",
    "merge the per-hero H2 modules (tools/tripo-pipeline/blender/h2_bake_merlin and the parallel h2_bake_<hero>) into one "
    "h2_bake library + a CLI route in tripo_pipeline.py (stages source/retopo/uv/bake/maps/rig/probe/preview) and a "
    "profile_schema validator for unmatched.tripo-pipeline.h2-bake-profile/1 (wave 4 owns tripo_pipeline.py/candidate_build)",
    "TeamMask contract with wave 4: the L TeamMask (= cloth) matches M_UM_Figure lerp by TeamMask.R; decide whether to adopt "
    "TeamMaskRGBA (R cloth, G base band, B gold trim) and document it in ADDING-AN-ASSET §4.2 p.5 / um_masters.py",
    "registry and docs (wave 4 files): asset-registry.json + DIRECTORY-MAP.md entry for run 20260929-h2-bake; PIPELINE.md / "
    "ADDING-AN-ASSET.md section 'H2 bake from a Tripo high-poly' (weld pairs, proxy seams, per-part cage bake, CPU for bytes)",
    "RIG-CONTRACT §12: record that Merlin H2 was built directly on UM_HUMANOID_17_v2 (validate_clip skeletal-mesh PASS, yaw -7.4)",
    "art: gold spiral inlay on the staff, lighter laced boots, rough stone base (all are Tripo BC limits), crystal depth/glow "
    "in the master material (emission/fresnel), blue-grey streaks on the left hand BC; the face under the hood is unreadable "
    "at K2 -55 deg (hood/light decision)",
    "budget decision GD-058: H2 heroes 30-45k LOD0 + LOD1 x0.5 and 4K master / 2K runtime (proposal, measured basis in k2_basis) "
    "vs 04/17 card 8-15k / 1K for a sidekick",
    "Tripo self-contacts left in the body (6 non-manifold + 13 inconsistent-winding edges at the hood back and the back hem, "
    "marked sharp) and one 3-vertex open chain: split them in the source if clips show shading seams there",
]

COMMIT_DEPENDENCIES = {
    "note": "files outside the run folder that the build or its checks read; state on 2026-09-29 (not queried from git "
            "by this script, so the report stays deterministic)",
    "orchestrator_h2_tripo_stage": {
        "files": ["art/pipeline-candidates/ASSET-MERLIN-001/source-specs/tripo-de0654b5-h2.json",
                  "art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-tripo/reports/tripo-run.json",
                  "art/pipeline-candidates/ASSET-MERLIN-001/.gitignore"],
        "state": "untracked / modified; commit with this candidate"},
    "concepts_and_reference": {
        "files": ["art/imagegen/hero-quality-v1/merlin/merlin-front.png", "art/imagegen/hero-quality-v1/merlin/merlin-side.png",
                  "art/imagegen/hero-quality-v1/merlin/merlin-back.png", "art/imagegen/hero-quality-v1/merlin/prompts.md",
                  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"],
        "state": "untracked; commit with this candidate (profile concepts/quality_reference, sheets sbs_*, source-spec sha256)"},
    "wave4_w4d_rig_contract_v2": {
        "files": ["tools/tripo-pipeline/anim/validate_clip.py", "tools/tripo-pipeline/anim/rig_rules.py",
                  "docs/art-pipeline/rig/rig-contract.json", "docs/art-pipeline/rig/RIG-CONTRACT.md"],
        "state": "wave 4 (W4-D), uncommitted; validate_clip v2 PASS is reproducible only with them: commit with or after W4-D"},
    "raw_sources_not_committed": {
        "files": ["art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-tripo/source/merlin-h2-tripo-de0654b5-parts12.glb",
                  "art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-tripo/source/merlin-h2-tripo-de0654b5-tex8k-pbr.glb"],
        "state": "> 50 MB policy: git-ignored, pinned by sha256/bytes in the source-spec and checked by the source stage"},
}

NOT_DONE = ["UE import and live frames (live UE and Blender :9876 belong to wave 4)", "LOD1", "animation clips",
            "Tripo auto-rig", "art acceptance", "edits of tripo_pipeline.py / candidate_build / candidate/atlas.py / rig contract / "
            "PIPELINE.md / ADDING-AN-ASSET.md / registry (wave 4)"]


def files_in(d, patterns):
    out = []
    for pat in patterns:
        for p in sorted(Path(d).glob(pat)):
            if p.is_file():
                out.append({"path": C.rel(p), "sha256": C.sha256(p), "bytes": p.stat().st_size})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("out")
    ap.add_argument("--determinism")
    a = ap.parse_args()
    prof = C.Profile(a.profile)
    R = {n: C.load_json(prof.reports / ("%s-report.json" % n)) for n in
         ("source", "retopo", "uv", "bake", "maps", "build", "preview", "sheets")}
    val = C.load_json(prof.reports / "validate-skeletal-mesh.json")
    probes = {l: C.load_json(prof.preview / "deform" / ("%s-deform.json" % l)) for l in ("merlin-h2-blend", "merlin-h2-fbx")}
    checks = {}
    for n, r in R.items():
        for k, c in (r.get("checks") or {}).items():
            checks["%s.%s" % (n, k)] = c["passed"]
    checks["validate_clip.skeletal_mesh_v2"] = val["result"] == "pass"
    for l, p in probes.items():
        checks["rig_deform_probe.%s_7_of_7" % l] = sum(t["status"] == "plausible" for t in p["tests"]) == 7
    # host-path audit of everything that is committed from the run folder
    audited = [p for d in (prof.export, prof.textures, prof.reports, prof.preview) for p in sorted(d.rglob("*")) if p.is_file()]
    host_hits = {C.rel(p): len(C.host_path_hits(p)) for p in audited}
    host_hits = {k: v for k, v in host_hits.items() if v}
    checks["artifacts.no_host_paths"] = not host_hits
    # K2 arithmetic (proposal basis)
    gc = prof["review"]["game_camera"]
    width = gc["resolution"][0]
    k2 = {}
    td = R["maps"]["texel_density"]
    for tag, d in (("1p6", gc["distance_uu"][0]), ("5x", gc["distance_uu"][1])):
        ppu = width / (2 * d * math.tan(math.radians(gc["horizontal_fov_deg"] / 2)))
        k2[tag] = {"distance_uu": d, "screen_px_per_uu_at_focus": C.r(ppu, 3),
                   "texels_per_screen_px_2k": {p: C.r(td[p]["px_per_uu_at_4k"] / 2 / ppu, 2) for p in ("tripo_part_0", "tripo_part_9", "tripo_part_2")},
                   "texels_per_screen_px_1k_estimate": {p: C.r(td[p]["px_per_uu_at_4k"] / 4 / ppu, 2) for p in ("tripo_part_0", "tripo_part_9", "tripo_part_2")},
                   "retopo_p99_deviation_px": C.r(max(d2["high_to_low"]["p99_mm"] for o in R["retopo"]["objects"].values()
                                                    for d2 in o["deviation_mm_source"].values()) * R["maps"]["game_frame_scale_from_source"] / 10.0 * ppu, 3)}
    b = R["build"]
    rep = {
        "schema": "unmatched.art-pipeline.h2-candidate-report/1",
        "asset_id": prof["asset_id"], "iteration": "H2", "date": "2026-09-29",
        "status": "измерено",
        "status_note": "технический кандидат H2: сборка, запекание, риг и экспорт измерены в headless Blender; UE-импорт не делался (живой UE занят волной 4); художественной приёмки нет; бюджеты — только предложение",
        "profile": {"path": C.rel(prof.path), "sha256": C.sha256(prof.path), "profile_id": prof["profile_id"]},
        "module": {"path": "tools/tripo-pipeline/blender/h2_bake_merlin", "files": files_in(C.HERE, ["*.py"])},
        "sources": R["source"]["files"],
        "source_checks": {k: v["passed"] for k, v in R["source"]["checks"].items()},
        "parts": {n: {"role": p["role"], "object": p["object"], "high_poly_triangles": p["triangles"],
                      "ray_escape_score": p["ray_escape_score"], "tripo_textures_px": {k: v["px"][0] for k, v in p["textures"].items()}}
                  for n, p in R["source"]["parts"].items()},
        "retopo": {"method": R["retopo"]["method"], "figure_triangles": R["retopo"]["figure_triangles"],
                   "base_triangles": R["retopo"]["base_triangles"],
                   "objects": {k: {"triangles_by_part": o["triangles_by_part"], "topology": o["topology"], "weld": o["weld"],
                                   "caps": len([c for c in o["caps"] if c["faces"]]), "bridges": o["bridges"],
                                   "deviation_mm_source": o["deviation_mm_source"], "triangle_quality": o["triangle_quality"],
                                   "sharp_edges": o["sharp_edges"]}
                               for k, o in R["retopo"]["objects"].items()}},
        "uv": {"islands": {k: v["islands"] for k, v in R["uv"]["objects"].items()}, "seams": R["uv"]["seams"],
               "pack_margin_fraction": R["uv"]["pack_margin_fraction"]},
        "bake": {k: R["bake"][k] for k in ("device", "compute_device_type", "atlas_px", "ao_distance_m_source", "cages", "maps")},
        "maps": {k: R["maps"][k] for k in ("utilisation", "uv_overlap_texels", "min_island_gap_px", "texel_density", "misses",
                                            "team_mask_coverage", "part_stats", "conventions", "textures")},
        "rig": {"skeleton": b["skeleton"], "armature_object": b["armature_object"], "weights": b["weights"],
                "sockets": b["sockets"], "export_frame": b["export_frame"], "measures": b["measures"],
                "validate_clip": {"result": val["result"], "checks": val["checks"]},
                "rig_deform_probe": {l: [{"test": t["test"], "status": t["status"], "z_norm": t["centroid_z_norm"], "x_norm": t["centroid_x_norm"]}
                                         for t in p["tests"]] for l, p in probes.items()}},
        "exports": b["exports"],
        "roundtrip_scale_ratio": b["roundtrip"]["scale_ratio"],
        "k2_basis": k2,
        "budget_proposal": prof["budget_proposal"],
        "preview": {"frames": R["preview"]["frames"], "sheets": R["sheets"]["outputs"], "label": "blender (EEVEE, studio light)"},
        "checks": checks, "checks_passed": all(checks.values()),
        "deferred_ue_steps": DEFERRED_UE_STEPS, "followups": FOLLOWUPS, "not_done": NOT_DONE,
        "artifacts": {"export": files_in(prof.export, ["*.fbx"]), "textures": files_in(prof.textures, ["*.png"]),
                      "reports": files_in(prof.reports, ["*.json"])},
        "host_path_audit": {"files_scanned": len(audited), "files_with_host_paths": host_hits,
                            "scope": "export/, textures/, reports/, preview/ of the run: repo root, user home, <drive>:/Users/"},
        "commit_dependencies": COMMIT_DEPENDENCIES,
    }
    det_path = Path(a.determinism) if a.determinism else prof.reports / "determinism.json"
    if det_path.exists():
        det = C.load_json(det_path)
        summary = {"file": C.rel(det_path), "sha256": C.sha256(det_path)}
        for key, sec in sorted(det.items()):
            if isinstance(sec, dict) and sec.get("schema") == "unmatched.art-pipeline.h2-determinism-compare/1":
                summary[key] = {k: sec[k] for k in ("run_a", "run_b", "files", "identical_files", "different_files",
                                                    "only_in_one_run", "note") if k in sec}
                summary[key]["different"] = {f: {k: v for k, v in d.items() if k != "first_10"}
                                             for f, d in sec["different"].items()}
            elif key == "full_cpu_rebuild_before_fix":
                summary[key] = sec
        rep["determinism"] = summary
    C.write_json(a.out, rep)
    print("REPORT_OK", a.out, "checks_passed", rep["checks_passed"], sum(checks.values()), "/", len(checks))


if __name__ == "__main__":
    main()
