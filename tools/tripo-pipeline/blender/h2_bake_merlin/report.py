"""Aggregate the stage reports of the H2 bake into the machine report docs/art-pipeline/merlin-h2-report.json.

python report.py <profile.json> <out.json> [--determinism <determinism.json>]
Only reads reports/artifacts; writes one JSON (sorted keys). Numbers are measured; budgets are proposals.
--determinism defaults to <run>/reports/determinism.json (committed; its sections are written by determinism.py).
Also scans every artifact (export, textures, reports, preview) for absolute host paths (check artifacts.no_host_paths).
H2.1 (profile h21 block): adds the section `h21` (texel density and atlas before/after against the H2 baseline maps
report restored by the compare stage into work/h2-baseline/, material classes, textures-report, comparison sheets,
UE material notes, the H2.1 commit set `commit`).
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
    "commit (H2.1): the outside-the-run dependencies are already in git (wave 4 W4-D rig contract v2 in 917a524d; H2 "
    "source-spec, tripo-run.json, .gitignore, concepts and the Medusa reference in 9a2a5184; see commit_dependencies). "
    "Commit the H2.1 set of h21.commit by explicit paths (no blanket git add: h21.commit.keep_out lists an untracked "
    "63.8 MB GLB of the older h31 run in the same asset folder)",
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
    "H2.1 crystal glow (UE material decision, not baked): M_UM_Figure has no texture-driven emissive (Emissive = FxFlash + "
    "Rim from Custom Primitive Data). Options: (a) a crystal mask (the tripo_part_7 islands; e.g. TeamMaskRGBA.A, today a "
    "constant 255) + an emissive term BC x mask x CrystalGlow in the master; (b) a point light / VFX on the proposed StaffTip "
    "socket (AD-CNF-59, CUE-008) only while casting. A second material slot for the crystal would break the 1-slot budget",
    "H2.1 UE check: the ORM now carries metallic 1 only on the buckle and roughness 0.12-0.18 on the crystal, 0.55-0.65 on "
    "the gold embroidery; keep M_UM_Figure RoughnessMin/Max at the neutral 0/1 (they remap ORM.G) and verify under DX12 + "
    "Lumen High that the buckle reads as metal and the crystal as a glossy gem (Blender EEVEE frames only so far)",
    "TeamMaskRGBA.B changed in H2.1: the belt, its hanging end and the buckle are no longer marked as gold trim; if wave 4 "
    "adopts TeamMaskRGBA, the B channel is the gold-embroidery class",
    "budget decision GD-058: H2 heroes 30-45k LOD0 + LOD1 x0.5 and 4K master / 2K runtime (proposal, measured basis in k2_basis) "
    "vs 04/17 card 8-15k / 1K for a sidekick",
    "Tripo self-contacts left in the body (6 non-manifold + 13 inconsistent-winding edges at the hood back and the back hem, "
    "marked sharp) and one 3-vertex open chain: split them in the source if clips show shading seams there",
]

COMMIT_DEPENDENCIES = {
    "note": "files outside the run folder that the build or its checks read; state on 2026-09-29 after the H2.1 build "
            "(HEAD 9a2a5184; not queried from git by this script, so the report stays deterministic)",
    "orchestrator_h2_tripo_stage": {
        "files": ["art/pipeline-candidates/ASSET-MERLIN-001/source-specs/tripo-de0654b5-h2.json",
                  "art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-tripo/reports/tripo-run.json",
                  "art/pipeline-candidates/ASSET-MERLIN-001/.gitignore"],
        "state": "tracked since 9a2a5184 (H2 commit); not changed by H2.1"},
    "concepts_and_reference": {
        "files": ["art/imagegen/hero-quality-v1/merlin/merlin-front.png", "art/imagegen/hero-quality-v1/merlin/merlin-side.png",
                  "art/imagegen/hero-quality-v1/merlin/merlin-back.png", "art/imagegen/hero-quality-v1/merlin/prompts.md",
                  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"],
        "state": "tracked since 9a2a5184 (H2 commit); not changed by H2.1 (profile concepts/quality_reference, sheets sbs_* "
                 "and h21_sbs_*, source-spec sha256)"},
    "wave4_w4d_rig_contract_v2": {
        "files": ["tools/tripo-pipeline/anim/validate_clip.py", "tools/tripo-pipeline/anim/rig_rules.py",
                  "docs/art-pipeline/rig/rig-contract.json", "docs/art-pipeline/rig/RIG-CONTRACT.md"],
        "state": "tracked since 917a524d (wave 4 W4-D, rig contract v2); validate_clip at HEAD knows UM_HUMANOID_17_v2"},
    "h2_baseline_for_compare": {
        "files": ["git 9a2a5184: 20260929-h2-bake/export/{SK_Merlin_H2,SM_Merlin_H2_Base}.fbx, "
                  "textures/T_Merlin_H2_{BC,N,ORM,TeamMaskRGBA}_2K.png, reports/maps-report.json (7 files)"],
        "state": "read from git by the compare stage (git show 9a2a5184:<path>, sha256 pinned in profile h21.baseline); "
                 "needs 9a2a5184 in the local history"},
    "raw_sources_not_committed": {
        "files": ["art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-tripo/source/merlin-h2-tripo-de0654b5-parts12.glb",
                  "art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-tripo/source/merlin-h2-tripo-de0654b5-tex8k-pbr.glb"],
        "state": "> 50 MB policy: git-ignored, pinned by sha256/bytes in the source-spec and checked by the source stage"},
}

NOT_DONE = ["UE import and live frames (live UE and Blender :9876 belong to wave 4)", "LOD1", "animation clips",
            "H2.1: crystal emission (UE material decision, recommendation in followups)",
            "H2.1: gold spiral inlay of the concept staff (not in the Tripo BC; no hand-painted texels)",
            "Tripo auto-rig", "art acceptance", "edits of tripo_pipeline.py / candidate_build / candidate/atlas.py / rig contract / "
            "PIPELINE.md / ADDING-AN-ASSET.md / registry (wave 4)"]

# H2.1 commit set (state on 2026-09-29 against HEAD 9a2a5184; written as constants, not queried from git)
_RUN = "art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-bake/"
H21_COMMIT = {
    "note": "58 files; stage them by explicit paths. Not queried from git by this script (the report stays deterministic)",
    "commit": {
        "module": ["tools/tripo-pipeline/blender/h2_bake_merlin/{__init__,maps,report,run,sheets,stage_preview,stage_uv}.py "
                   "(modified)", "tools/tripo-pipeline/blender/h2_bake_merlin/{stage_compare,compare_sheets}.py (new)"],
        "profile": ["art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-segmented-skeletal-h2.json (merlin-h2-bake/2)"],
        "export": [_RUN + "export/SK_Merlin_H2.fbx", _RUN + "export/SM_Merlin_H2_Base.fbx"],
        "textures_2k": [_RUN + "textures/T_Merlin_H2_{BC,N,ORM,TeamMask,TeamMaskRGBA}_2K.png (5)"],
        "reports": [_RUN + "reports/{bake,build,maps,sheets,uv}-report.json, validate-skeletal-mesh.json (modified)",
                    _RUN + "reports/{textures,compare,compare-sheets}-report.json (new)"],
        "preview": [_RUN + "preview/{closeup_*,closeups_sheet,k2_*_h2,ortho_*,sbs_*}.png (22, re-shot on H2.1)",
                    _RUN + "preview/h21_*.png (8, new)"],
        "docs": ["docs/art-pipeline/merlin-h2-report.md", "docs/art-pipeline/merlin-h2-report.json"],
    },
    "local_only": [
        _RUN + "textures/*_4K.png (5 masters; ASSET-MERLIN-001/.gitignore line 17; sha256 in reports/textures-report.json)",
        _RUN + "work/ and " + _RUN + "logs/ (ASSET-MERLIN-001/.gitignore)",
    ],
    "unchanged_bytes": "preview/deform/* (22 probe PNG/JSON) and reports/preview-report.json were rewritten by the H2.1 run "
                       "but are byte-identical to 9a2a5184, so they are not in the change set",
    "keep_out": [{
        "path": "art/pipeline-candidates/ASSET-MERLIN-001/20260928-tripo-h31/source/merlin-tripo-h31-d9ff4260-source.glb",
        "bytes": 63829324,
        "state": "untracked and not git-ignored; raw source of the older 2026-09-28 h31 run (pinned by "
                 "source-specs/tripo-d9ff4260.json), not read by H2 or H2.1, over the 50 MB policy. Not part of the H2.1 "
                 "commit; whether to commit, ignore or keep it local is the user's decision",
    }],
}


def files_in(d, patterns):
    out = []
    for pat in patterns:
        for p in sorted(Path(d).glob(pat)):
            if p.is_file():
                out.append({"path": C.rel(p), "sha256": C.sha256(p), "bytes": p.stat().st_size})
    return out


def h21_section(prof, R):
    """H2.1 before/after: the H2 maps report is the baseline file restored (sha256-checked) by the compare stage."""
    h21 = prof["h21"]
    bfile = h21["baseline"]["files"]["maps_report"]
    bpath = prof.work / "h2-baseline" / Path(bfile["path"]).name
    if C.sha256(bpath) != bfile["sha256"]:
        raise SystemExit("baseline maps report %s does not match its sha256 (run the compare stage)" % bpath)
    before = C.load_json(bpath)
    after = R["maps"]
    td = {}
    for part in sorted(after["texel_density"], key=C.part_index):
        b, a = before["texel_density"][part], after["texel_density"][part]
        td[part] = {"td_priority": [b["td_priority"], a["td_priority"]], "px_per_uu_at_4k": [b["px_per_uu_at_4k"], a["px_per_uu_at_4k"]],
                    "relative_to_robe": [b["relative_to_robe"], a["relative_to_robe"]]}
    mat = dict(after["materials_h21"])
    mat.pop("rules", None)
    textures = prof.reports / "textures-report.json"
    out = {
        "iteration": h21["iteration"], "changes": h21["changes"], "baseline": {"git_rev": h21["baseline"]["git_rev"], "maps_report": bfile},
        "texel_density_before_after": td,
        "atlas_before_after": {"utilisation": [before["utilisation"], after["utilisation"]],
                               "min_island_gap_px": [before["min_island_gap_px"], after["min_island_gap_px"]],
                               "uv_overlap_texels": [before["uv_overlap_texels"], after["uv_overlap_texels"]],
                               "surface_miss_share": {m: [before["misses"][m]["surface_share"], after["misses"][m]["surface_share"]]
                                                      for m in after["misses"]}},
        "part_stats_before_after": {p: {"before": before["part_stats"][p], "after": after["part_stats"][p]} for p in sorted(after["part_stats"], key=C.part_index)},
        "team_mask_coverage_before_after": {p: {"before": before["team_mask_coverage"][p], "after": after["team_mask_coverage"][p]}
                                            for p in sorted(after["team_mask_coverage"], key=C.part_index)},
        "materials": mat,
        "material_rules": "profile maps.materials",
        "textures_report": {"path": C.rel(textures), "sha256": C.sha256(textures)},
        "textures_before_after_sha256": {k: [before["textures"][k]["sha256"], after["textures"][k]["sha256"]] for k in sorted(after["textures"])},
        "ue_material_notes": [
            "M_UM_Figure: Metallic = ORM.B, Roughness = lerp(RoughnessMin, RoughnessMax, ORM.G), AO = ORM.R; keep RoughnessMin/Max 0/1",
            "TeamMask (L) = cloth only: the gold embroidery, belt, buckle, crystal and staff are not team-tinted",
            "crystal: no emission baked; see followups (mask + CrystalGlow in the master, or a StaffTip light/VFX)",
        ],
    }
    if "compare" in R:
        out["compare"] = {"report": C.rel(prof.reports / "compare-report.json"), "lights": R["compare"]["lights"],
                          "env_strength": R["compare"]["env_strength"], "texture_set": R["compare"]["texture_set"],
                          "inputs": R["compare"]["inputs"]}
    if "compare-sheets" in R:
        out["compare_sheets"] = R["compare-sheets"]["outputs"]
    out["commit"] = H21_COMMIT
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
    for n in ("compare", "compare-sheets"):
        if (prof.reports / ("%s-report.json" % n)).exists():
            R[n] = C.load_json(prof.reports / ("%s-report.json" % n))
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
    h21 = prof.get("h21")
    rep = {
        "schema": "unmatched.art-pipeline.h2-candidate-report/1",
        "asset_id": prof["asset_id"], "iteration": h21["iteration"] if h21 else "H2", "date": "2026-09-29",
        "status": "измерено",
        "status_note": ("технический кандидат H2.1 (доводка материалов H2): перепаковка UV с приоритетом посоха/кристалла, полное "
                        "перезапекание на CPU, классы материалов в ORM/BC; сборка, запекание, риг и экспорт измерены в headless "
                        "Blender; UE-импорт не делался (живой UE занят волной 5a); художественной приёмки нет; бюджеты — только "
                        "предложение") if h21 else
                       "технический кандидат H2: сборка, запекание, риг и экспорт измерены в headless Blender; UE-импорт не делался (живой UE занят волной 4); художественной приёмки нет; бюджеты — только предложение",
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
    if h21:
        rep["h21"] = h21_section(prof, R)
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
