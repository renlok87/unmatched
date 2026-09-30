#!/usr/bin/env python3
"""skeletal-adopt normaliser of a hero LOOK-DEV run (LD-merlin-ue, 2026-09-29): format h2-lookdev-merlin/1.

The look-dev stage of h2_bake_merlin (stages ld_*, run 20260929-h2-lookdev) re-exports the H2.1 rig UNCHANGED (append
of work/h2-rig.blend, only UV1 added) and proves it by read-back against the H2.1 FBX: polygons + UV0, vertices,
bones, weights, triangles (reports/ld-export-report.json checks *_equal_h21). Its own report therefore carries no bone
heads, sockets or round-trip bounds: those are the ones of the H2.1 build report. This normaliser builds the
h2-bake-rig/1 layout of skeletal_adopt from

  build report     reports/ld-export-report.json (look-dev FBX paths/sha256, export settings, equality checks)
  H2.1 report      candidate.h21_build_report {path, sha256} (pinned by sha256 in the profile; its exports must be the
                   H2.1 FBX bytes the look-dev export compared itself with, ld-export-report source.h21_fbx)
  textures report  reports/textures-report.json of the look-dev run (BC/N/ORM/TeamMask/MatID ...; tier "runtime")
  extra report     ue_inputs = ue-inputs/ue-inputs-report.json (tools/art/material_library/lookdev_ue_inputs.py:
                   LUT 16 x 16 DDS, EdgeMask, debug ZoneID; tiers runtime_2k / runtime_lut)
  extra report     ld_report = reports/ld-report.json (all look-dev checks passed)

Only restructuring and re-derivation; no Blender, no UE, no network.
"""

from __future__ import annotations

import json
import struct

LOOKDEV_MERLIN_FORMAT = "h2-lookdev-merlin/1"
UE_INPUTS_SCHEMA = "unmatched.um-v2-lookdev-ue-inputs/1"
EQUALITY_CHECKS = ("geometry_equal_h21", "bones_equal_h21", "weights_equal_h21", "triangles_equal_h21",
                   "source_fbx_sha256", "export_face_plus_x", "uv_layers_uvmap_then_uv1", "material_slot_single")


class NormaliseError(Exception):
    pass


def image_px(path):
    """[w, h] of a PNG or DDS (header only) or None."""
    with open(path, "rb") as handle:
        head = handle.read(32)
    if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
        return list(struct.unpack(">II", head[16:24]))
    if head[:4] == b"DDS ":
        h, w = struct.unpack("<II", head[12:20])
        return [w, h]
    return None


def lookdev_merlin(ld: dict, tex: dict, profile: dict, repo_path, sha256_file) -> tuple:
    c = profile["candidate"]
    base_dir = c["dir"].rstrip("/")
    h21 = c.get("h21_build_report") or {}
    h21_path = repo_path(h21.get("path", ""))
    if not h21.get("path") or not h21_path.is_file():
        raise NormaliseError("candidate.h21_build_report missing: %s" % h21.get("path"))
    h21_sha = sha256_file(h21_path)
    rep = json.loads(h21_path.read_text(encoding="utf-8"))
    extra = {}
    for key in ("ue_inputs", "ld_report"):
        rel = "%s/%s" % (base_dir, c["extra_reports"][key])
        path = repo_path(rel)
        if not path.is_file():
            raise NormaliseError("%s missing: %s" % (key, rel))
        extra[key] = (rel, json.loads(path.read_text(encoding="utf-8")))
    ue_rel, ue_in = extra["ue_inputs"]
    ldr_rel, ldr = extra["ld_report"]

    want_id = c.get("bake_profile_id")
    h21_fbx = (ld.get("source") or {}).get("h21_fbx") or {}
    h21_exports = {rep["exports"][k]["path"]: rep["exports"][k]["sha256"] for k in ("skeletal_fbx", "base_fbx")}
    checks = ld.get("checks") or {}
    eq = {k: (checks.get(k) or {}).get("passed") is True for k in EQUALITY_CHECKS}
    info_checks = {
        "h21_build_report_pinned": {"passed": h21_sha == h21.get("sha256") and rep.get("passed") is True,
                                    "sha256": h21_sha, "expected": h21.get("sha256"), "h21_passed": rep.get("passed")},
        "lookdev_export_compared_with_these_h21_fbx": {"passed": bool(h21_fbx) and h21_fbx == h21_exports,
                                                       "lookdev_source": h21_fbx, "h21_report_exports": h21_exports},
        "lookdev_export_equal_h21": {"passed": all(eq.values()), "checks": eq,
                                     "note": "rig, geometry (positions + UV0), weights, triangles, face +X of the "
                                             "look-dev FBX equal the H2.1 FBX (read-back in the look-dev stage)"},
        "lookdev_report_passed": {"passed": ldr.get("passed") is True and ldr.get("profile_id") == want_id,
                                  "passed_value": ldr.get("passed"), "profile_id": ldr.get("profile_id")},
        "ue_inputs_of_this_lookdev": {"passed": ue_in.get("schema") == UE_INPUTS_SCHEMA and
                                      ue_in.get("profile_id") == want_id,
                                      "schema": ue_in.get("schema"), "profile_id": ue_in.get("profile_id")},
    }
    # the UE inputs must derive from the look-dev bytes now on disk
    stale = sorted(r for r, s in (ue_in.get("inputs") or {}).items()
                   if not repo_path(r).is_file() or sha256_file(repo_path(r)) != s)
    info_checks["ue_inputs_current"] = {"passed": not stale, "stale_or_missing_inputs": stale}
    passed = ld.get("passed") is True and all(v["passed"] for v in info_checks.values())

    rt = json.loads(json.dumps(rep["roundtrip"]))
    readback = ld.get("readback") or {}
    for part in ("skeletal", "base"):
        for name, mesh in (rt[part].get("meshes") or {}).items():
            layers = (readback.get("uv_layers") or {}).get(name)
            if layers is not None:
                mesh["uv_layers"] = layers
    build = {
        "schema": "normalised from ld-export-report (%s) + H2.1 build report" % LOOKDEV_MERLIN_FORMAT,
        "passed": passed,
        "profile_id": ld.get("profile_id"),
        "profile": ld.get("profile"),
        "skeleton": rep.get("skeleton"),
        "armature_object": rep.get("armature_object"),
        "exports": {"skeletal_fbx": dict(ld["exports"]["skeletal_fbx"]), "base_fbx": dict(ld["exports"]["base_fbx"]),
                    "settings": ld["exports"]["settings"]},
        "roundtrip": rt,
        "sockets": rep.get("sockets") or [],
        "measures": rep.get("measures") or {},
        "checks": {"export_face_plus_x": {"passed": (checks.get("export_face_plus_x") or {}).get("passed") is True,
                                          "measured": (checks.get("export_face_plus_x") or {}).get("measured"),
                                          "source": "ld-export-report checks.export_face_plus_x"}},
    }
    textures = {"schema": "normalised from the look-dev textures report + ue-inputs report", "profile_id": None,
                "textures": {}, "conventions": {}}
    tier = c["texture_tier"]
    lookdev_ok = tex.get("profile") == ld.get("profile")
    textures["profile_id"] = ld.get("profile_id") if lookdev_ok else None
    for name, rec in sorted((tex.get("textures") or {}).items()):
        path = repo_path(rec["path"])
        px = image_px(path) if path.is_file() else None
        t = tier if rec.get("tier") == "runtime" and px == [int(c["texture_px"])] * 2 else rec.get("tier")
        textures["textures"][name] = {"path": rec["path"], "sha256": rec["sha256"], "bytes": rec.get("bytes"),
                                      "px": px, "tier": t, "source_tier": rec.get("tier")}
    for name, rec in sorted((ue_in.get("textures") or {}).items()):
        textures["textures"][name] = {k: rec.get(k) for k in ("path", "sha256", "bytes", "px", "tier", "map")}
    conv = dict(tex.get("conventions") or {})
    conv.update(ue_in.get("conventions") or {})
    for key in c["textures"]:
        if key in conv:
            textures["conventions"][key] = conv[key]
    info = {"format": LOOKDEV_MERLIN_FORMAT, "normaliser": "skeletal_adopt_lookdev.lookdev_merlin",
            "sources": {"ld_export_report": "%s/%s" % (base_dir, c["build_report"]),
                        "textures_report": "%s/%s" % (base_dir, c["textures_report"]),
                        "h21_build_report": h21.get("path"), "ue_inputs_report": ue_rel, "ld_report": ldr_rel},
            "checks": info_checks,
            "note": "bones, sockets, round-trip bounds and measures are the H2.1 build report's: the look-dev export "
                    "proved rig/geometry/weights equal to H2.1 by read-back; FBX paths/sha256 and export settings are "
                    "the look-dev export's; UV layers of the look-dev read-back"}
    build["normalised"] = info
    return build, textures, info


# ------------------------------------------------------------------------------------------------------------------
# look-dev C (2026-09-30, group B): King Arthur (h2_bake_arthur ld_* stages) and Harpy (h2_bake_harpy lookdev_*)
LOOKDEV_ARTHUR_FORMAT = "h2-lookdev-arthur/1"
ARTHUR_EQUALITY_CHECKS = ("geometry_equal_h2", "bones_equal_h2", "weights_equal_h2", "triangles_equal_h2",
                          "source_fbx_sha256", "export_front_plus_x", "uv_layers_uvmap_then_uv1", "material_slot_single",
                          "appended_skinning_intact")


def _ue_inputs_checks(ue_in: dict, want_id: str, repo_path, sha256_file) -> dict:
    """The UE inputs report (lookdev_ue_inputs.py) belongs to this look-dev and derives from the bytes on disk."""
    stale = sorted(r for r, s in (ue_in.get("inputs") or {}).items()
                   if not repo_path(r).is_file() or sha256_file(repo_path(r)) != s)
    return {
        "ue_inputs_of_this_lookdev": {"passed": ue_in.get("schema") == UE_INPUTS_SCHEMA and
                                      ue_in.get("profile_id") == want_id,
                                      "schema": ue_in.get("schema"), "profile_id": ue_in.get("profile_id")},
        "ue_inputs_current": {"passed": not stale, "stale_or_missing_inputs": stale,
                              "note": "every input the UE-inputs report hashed (incl. the local work/ zone map) is on "
                                      "disk with that sha256"},
    }


def lookdev_arthur(ld: dict, tex: dict, profile: dict, repo_path, sha256_file) -> tuple:
    """King Arthur look-dev run (h2_bake_arthur ld_*) -> h2-bake-rig/1.

    ld_export re-exports the H2.2 rig of 20260929-h2-bake UNCHANGED (append + UV1) and proves it by read-back against
    the H2 FBX (checks *_equal_h2). Bones, sockets, round-trip bounds and the figure top are therefore the H2 bake's:
    they come from the H2 skeletal-adopt profile (candidate.h2_adopt_profile, pinned by sha256) run through the
    arthur_h2 normaliser of skeletal_adopt_formats (the same view the W5c-A import used). FBX bytes, export settings and
    UV layers are the look-dev export's; the maps are the look-dev textures report's + the UE inputs report's."""
    import skeletal_adopt_formats as saf
    c = profile["candidate"]
    base_dir = c["dir"].rstrip("/")
    want_id = c.get("bake_profile_id")
    h2p = c.get("h2_adopt_profile") or {}
    h2p_path = repo_path(h2p.get("path", ""))
    if not h2p.get("path") or not h2p_path.is_file():
        raise NormaliseError("candidate.h2_adopt_profile missing: %s" % h2p.get("path"))
    h2p_sha = sha256_file(h2p_path)
    h2prof = json.loads(h2p_path.read_text(encoding="utf-8"))
    hc = h2prof["candidate"]
    h2_dir = hc["dir"].rstrip("/")
    rig = json.loads(repo_path("%s/%s" % (h2_dir, hc["build_report"])).read_text(encoding="utf-8"))
    h2tex = json.loads(repo_path("%s/%s" % (h2_dir, hc["textures_report"])).read_text(encoding="utf-8"))
    h2build, h2textures, h2info = saf.arthur_h2(rig, h2tex, h2prof, repo_path, sha256_file)
    extra = {}
    for key in ("ue_inputs", "ld_report", "ld_manifest"):
        rel = "%s/%s" % (base_dir, c["extra_reports"][key])
        path = repo_path(rel)
        if not path.is_file():
            raise NormaliseError("%s missing: %s" % (key, rel))
        extra[key] = (rel, json.loads(path.read_text(encoding="utf-8")))
    ue_rel, ue_in = extra["ue_inputs"]
    ldr_rel, ldr = extra["ld_report"]
    man_rel, man = extra["ld_manifest"]
    ld_prof_path = repo_path(c["bake_profile"])
    ld_prof_sha = sha256_file(ld_prof_path) if ld_prof_path.is_file() else None

    checks = ld.get("checks") or {}
    eq = {k: (checks.get(k) or {}).get("passed") is True for k in ARTHUR_EQUALITY_CHECKS}
    h2_fbx = (ld.get("source") or {}).get("h2_fbx") or {}
    h2_exports = {h2build["exports"][k]["path"]: h2build["exports"][k]["sha256"] for k in ("skeletal_fbx", "base_fbx")}
    listed = {f.get("file"): f.get("sha256") for f in man.get("files") or []}
    want = {ld["exports"][k]["path"]: ld["exports"][k]["sha256"] for k in ("skeletal_fbx", "base_fbx")}
    for key, rel in sorted(c["textures"].items()):
        full = "%s/%s" % (base_dir, rel)
        want[full] = sha256_file(repo_path(full)) if repo_path(full).is_file() else None
    info_checks = {
        "h2_adopt_profile_pinned": {"passed": h2p_sha == h2p.get("sha256"), "sha256": h2p_sha,
                                    "expected": h2p.get("sha256"), "path": h2p.get("path")},
        "h2_bake_normalised_passed": {"passed": h2build.get("passed") is True,
                                      "checks": {k: v.get("passed") for k, v in (h2info.get("checks") or {}).items()},
                                      "normaliser": h2info.get("normaliser")},
        "lookdev_export_compared_with_these_h2_fbx": {"passed": bool(h2_fbx) and h2_fbx == h2_exports,
                                                      "lookdev_source": h2_fbx, "h2_bake_exports": h2_exports},
        "lookdev_export_equal_h2": {"passed": ld.get("passed") is True and all(eq.values()) and
                                    all((v or {}).get("passed") is True for v in checks.values()),
                                    "checks": eq, "all_export_checks": len(checks),
                                    "note": "rig, geometry (positions + UV0), weights, triangles, skinning, front +X of "
                                            "the look-dev FBX equal the H2 FBX (read-back in ld_export)"},
        "lookdev_report_passed": {"passed": ldr.get("passed") is True and ldr.get("profile_id") == want_id,
                                  "passed_value": ldr.get("passed"), "profile_id": ldr.get("profile_id")},
        "lookdev_manifest_lists_the_adopted_bytes": {
            "passed": (man.get("profile") == c["bake_profile"] and man.get("profile_sha256") == ld_prof_sha and
                       all(s and listed.get(f) == s for f, s in want.items())),
            "manifest_profile_sha256": man.get("profile_sha256"), "lookdev_profile_sha256": ld_prof_sha,
            "files": {f: listed.get(f) == s for f, s in sorted(want.items())}},
    }
    info_checks.update(_ue_inputs_checks(ue_in, want_id, repo_path, sha256_file))
    passed = all(v["passed"] for v in info_checks.values())

    build = json.loads(json.dumps(h2build))
    build.pop("normalised", None)
    build.update({"schema": "normalised from ld-export-report (%s) + the H2 bake view (%s)"
                            % (LOOKDEV_ARTHUR_FORMAT, saf.ARTHUR_FORMAT),
                  "passed": passed, "profile_id": ld.get("profile_id"), "profile": ld.get("profile")})
    build["exports"] = {"skeletal_fbx": dict(ld["exports"]["skeletal_fbx"]), "base_fbx": dict(ld["exports"]["base_fbx"]),
                        "settings": ld["exports"]["settings"]}
    readback = ld.get("readback") or {}
    slots = (checks.get("material_slot_single") or {}).get("measured") or {}
    for part in ("skeletal", "base"):
        for name, mesh in (build["roundtrip"][part].get("meshes") or {}).items():
            layers = (readback.get("uv_layers") or {}).get(name)
            if layers is not None:
                mesh["uv_layers"] = layers
            if name in slots:
                mesh["material_slots"] = slots[name]
    face = checks.get("export_front_plus_x") or {}
    build["checks"] = {"export_face_plus_x": {"passed": face.get("passed") is True, "measured": face.get("measured"),
                                              "expected": face.get("expected"),
                                              "source": "ld-export-report checks.export_front_plus_x (front yaw deg "
                                                        "from +X in the export frame)"}}
    textures = {"schema": "normalised from the look-dev textures report + ue-inputs report",
                "profile_id": ld.get("profile_id") if ldr.get("profile_id") == ld.get("profile_id") else None,
                "textures": {}, "conventions": {}}
    size = [int(c["texture_px"])] * 2
    for name, rec in sorted((tex.get("textures") or {}).items()):
        path = rec.get("file") or rec.get("path")
        px = rec.get("px")
        tier = c["texture_tier"] if rec.get("committed") and px == size else ("master_4k" if px == [4096, 4096]
                                                                               else rec.get("tier"))
        textures["textures"][name] = {"path": path, "sha256": rec.get("sha256"), "bytes": rec.get("bytes"),
                                      "px": px, "tier": tier}
    for name, rec in sorted((ue_in.get("textures") or {}).items()):
        # adopt looks maps up by file name: the ue-inputs EdgeMask (the one the profile names) replaces the look-dev
        # EdgeMask of the same name in this view
        textures["textures"][name] = {k: rec.get(k) for k in ("path", "sha256", "bytes", "px", "tier", "map")}
    conv = {k: v for k, v in (h2textures.get("conventions") or {}).items() if k in ("BC", "ORM")}
    conv.update(tex.get("conventions") or {})
    conv.update(ue_in.get("conventions") or {})
    for key in c["textures"]:
        if key in conv:
            textures["conventions"][key] = conv[key]
    info = {"format": LOOKDEV_ARTHUR_FORMAT, "normaliser": "skeletal_adopt_lookdev.lookdev_arthur",
            "sources": {"ld_export_report": "%s/%s" % (base_dir, c["build_report"]),
                        "textures_report": "%s/%s" % (base_dir, c["textures_report"]),
                        "h2_adopt_profile": h2p.get("path"), "h2_rig_report": "%s/%s" % (h2_dir, hc["build_report"]),
                        "ue_inputs_report": ue_rel, "ld_report": ldr_rel, "ld_manifest": man_rel},
            "checks": info_checks,
            "note": "bones, sockets, round-trip bounds and the figure top are the H2 bake's (arthur_h2 view of the W5c-A "
                    "import profile): the look-dev export proved rig/geometry/weights equal to H2 by read-back; FBX "
                    "paths/sha256, export settings, UV layers and material slots are the look-dev export's; BC/ORM "
                    "conventions are the H2 bake's (the look-dev only graded BC and zeroed ORM.B on the cloth)"}
    build["normalised"] = info
    return build, textures, info


LOOKDEV_HARPY_FORMAT = "h3-lookdev-harpy/1"
H3_RIG_SCHEMA = "unmatched.h2-bake.rig-report/1"
HARPY_EQUALITY_CHECKS = ("positions_and_uv0_per_loop_as_h3", "bones_and_parents_as_h3", "bone_heads_tails_as_h3",
                         "weights_as_h3", "triangles_as_h3", "source_fbx_sha256", "uv_layers_order",
                         "export_frame_face_along_plus_x", "appended_skinning_intact")


def lookdev_harpy(ldfbx: dict, ldmaps: dict, profile: dict, repo_path, sha256_file) -> tuple:
    """Harpy look-dev run (h2_bake_harpy lookdev_maps / lookdev_export) -> h2-bake-rig/1.

    ld_fbx re-exports the H3 figure (20260929-h3-bake) with UV1 and proves positions, UV0, bones, heads/tails, weights
    and triangles equal to the H3 FBX. Bones and parents: the rig-contract validation of the H3 FBX
    (validate-skeletal-mesh-v2.json: skeleton_contract pass, no missing / extra / parent mismatch) -> the contract's
    UM_HUMANOID_17_v2 list without the weapon bones (Harpy has none, contract characters.Harpy.weapon_bone = null).
    Body round-trip bounds, the figure top and the sockets: the H3 rig report (checks.roundtrip_bounds_m,
    checks.figure_top_m, sockets). The parametric base has no read-back bounds in any report: its bounds are the
    base_parametric of the H3 bake profile the look-dev pinned (radius_bottom_m, height_m + pips raise_m); UE measures
    the real ones (ue-import base_footprint_pivot). Maps: ld-maps-report textures.2k / base_textures + the hero LUT."""
    c = profile["candidate"]
    base_dir = c["dir"].rstrip("/")
    want_id = c.get("bake_profile_id")
    extra = {}
    for key in ("h3_rig_report", "h3_validate_report", "h3_textures_report"):
        rel = "%s/%s" % (base_dir, c["extra_reports"][key])
        path = repo_path(rel)
        if not path.is_file():
            raise NormaliseError("%s missing: %s" % (key, rel))
        extra[key] = (rel, json.loads(path.read_text(encoding="utf-8")))
    rig_rel, rig = extra["h3_rig_report"]
    val_rel, val = extra["h3_validate_report"]
    h3t_rel, h3t = extra["h3_textures_report"]
    if rig.get("schema") != H3_RIG_SCHEMA:
        raise NormaliseError("H3 rig report schema %r, expected %s" % (rig.get("schema"), H3_RIG_SCHEMA))
    contract_rel = c.get("rig_contract", "docs/art-pipeline/rig/rig-contract.json")
    contract = json.loads(repo_path(contract_rel).read_text(encoding="utf-8"))
    src = ldmaps.get("source") or {}
    bake_prof_rel = src.get("profile")
    bake_prof_path = repo_path(bake_prof_rel or "")
    bake_prof_sha = sha256_file(bake_prof_path) if bake_prof_rel and bake_prof_path.is_file() else None
    bake_prof = json.loads(bake_prof_path.read_text(encoding="utf-8")) if bake_prof_sha else {}
    ld_prof = json.loads(repo_path(c["bake_profile"]).read_text(encoding="utf-8"))

    checks = ldfbx.get("checks") or {}
    eq = {k: (checks.get(k) or {}).get("passed") is True for k in HARPY_EQUALITY_CHECKS}
    rig_exports = {rig["exports"][k]["path"].rsplit("/", 1)[-1]: rig["exports"][k]["sha256"]
                   for k in ("skeletal_fbx", "base_fbx")}
    h3_src = (ldfbx.get("source") or {}).get("h3_fbx") or {}
    rig_checks = rig.get("checks") or {}
    rig_ok = (not rig.get("checks_failed") and all((v or {}).get("passed") is True for v in rig_checks.values())
              and (rig.get("armature") or {}).get("skeleton") == profile["armature"]["skeleton"])
    vchecks = {ch.get("check"): ch for ch in val.get("checks") or []}
    sc = vchecks.get("skeleton_contract") or {}
    val_ok = (val.get("result") == "pass" and not val.get("fails") and val.get("kind") == "skeletal-mesh" and
              val.get("skeleton") == profile["armature"]["skeleton"] and
              val.get("clip_sha256") == rig["exports"]["skeletal_fbx"]["sha256"] and sc.get("status") == "pass" and
              not sc.get("missing") and not sc.get("extra") and not sc.get("parent_mismatch"))
    sk = contract["skeletons"][profile["armature"]["skeleton"]]
    weapon = (sk.get("characters") or {}).get(c.get("character", "Harpy"), {}).get("weapon_bone")
    bones_final = (rig.get("armature") or {}).get("bones_final_m") or {}
    bones = {}
    for b in sk["bones"]:
        if b.get("optional") and b["name"] != weapon:
            continue
        ht = bones_final.get(b["name"]) or [None, None]
        bones[b["name"]] = {"parent": b.get("parent"), "head_m": ht[0], "tail_m": ht[1]}
    bones_ok = sorted(bones) == sorted(bones_final) and \
        (checks.get("bones_and_parents_as_h3") or {}).get("measured") == len(bones)
    maps_checks = {k: (v or {}).get("passed") for k, v in sorted((ldmaps.get("checks") or {}).items())}
    maps_ok = ldmaps.get("passed") is True and all(v is True for v in maps_checks.values()) and \
        ldmaps.get("profile_id") == want_id and ldmaps.get("profile") == c["bake_profile"]
    lut = ldmaps.get("lut") or {}
    # the ld-maps record of the file the profile names as N (an OpenGL map there reads copied_from *_N_OpenGL)
    n_rec = next((r for r in (((ldmaps.get("textures") or {}).get("2k") or {}).values())
                  if r.get("path") == c["textures"].get("N")), {})
    h3_n = ((h3t.get("outputs") or {}).get("runtime") or {}).get("N") or {}
    n_ok = (bool(n_rec.get("copied_from")) and "OpenGL" not in n_rec["copied_from"] and
            n_rec.get("sha256") == h3_n.get("sha256") and bool(h3_n.get("sha256")))
    info_checks = {
        "lookdev_fbx_all_checks_passed": {"passed": ldfbx.get("passed") is True and not ldfbx.get("failed") and
                                          all(eq.values()) and all((v or {}).get("passed") is True
                                                                   for v in checks.values()),
                                          "equality": eq, "all_checks": len(checks)},
        "lookdev_fbx_compared_with_the_h3_fbx_of_the_rig_report": {"passed": bool(h3_src) and h3_src == rig_exports,
                                                                  "lookdev_source": h3_src, "h3_rig_exports": rig_exports},
        "h3_rig_report_all_checks_passed": {"passed": rig_ok, "checks": len(rig_checks),
                                            "checks_failed": rig.get("checks_failed"),
                                            "rig_profile_sha256": rig.get("profile_sha256"),
                                            "bake_profile_sha256_now": bake_prof_sha,
                                            "note": "the H3 bake profile was edited after the rig stage (texture "
                                                    "stages); the rig FBX bytes are pinned by the look-dev export "
                                                    "instead (source.h3_fbx = rig exports)"},
        "h3_rig_contract_validation_pass": {"passed": val_ok, "result": val.get("result"),
                                            "contract_revision": val.get("contract_revision"),
                                            "skeleton_contract": sc},
        "bones_from_contract_equal_h3_rig": {"passed": bones_ok, "bones": len(bones), "weapon_bone": weapon,
                                             "rig_bones": len(bones_final)},
        "lookdev_maps_all_checks_passed": {"passed": maps_ok, "checks": maps_checks,
                                           "profile_id": ldmaps.get("profile_id")},
        "lookdev_maps_pin_this_bake_profile": {"passed": bool(bake_prof_sha) and src.get("profile_sha256") == bake_prof_sha
                                               and (src.get("fbx_sha256") or {}) == rig_exports,
                                               "pinned": src.get("profile_sha256"), "now": bake_prof_sha},
        "normal_is_the_h3_directx_map": {"passed": n_ok, "copied_from": n_rec.get("copied_from"),
                                         "sha256": n_rec.get("sha256"), "h3_sha256": h3_n.get("sha256")},
        "lookdev_profile_is_the_named_one": {"passed": ld_prof.get("profile_id") == want_id,
                                             "profile_id": ld_prof.get("profile_id")},
    }
    passed = all(v["passed"] for v in info_checks.values())
    settings = ldfbx["exports"]["settings"]
    pre = ldfbx.get("meshes_pre_export") or {}
    body_name, base_name = c["body_object"], profile["meshes"]["base"]["object"]
    rb = (rig_checks.get("roundtrip_bounds_m") or {}).get("measured")
    bp = bake_prof.get("base_parametric") or {}
    r = float(bp.get("radius_bottom_m", 0.0))
    base_top = round(float(bp.get("height_m", 0.0)) + float((bp.get("pips") or {}).get("raise_m", 0.0)), 6)

    def mesh(name, bounds):
        m = {k: (pre.get(name) or {}).get(k) for k in ("material_slots", "triangles", "polygons", "vertices", "uv_layers",
                                                       "uv0_in_unit_square", "near_degenerate_triangles",
                                                       "near_degenerate_area_cm2_below", "has_custom_normals",
                                                       "color_attributes")}
        m["uv_layers"] = ((ldfbx.get("readback") or {}).get("uv_layers") or {}).get(name, m["uv_layers"])
        m["bounds_m"] = bounds
        return m

    sk_meshes = {body_name: mesh(body_name, rb)}
    base_meshes = {base_name: mesh(base_name, {"min": [-r, -r, 0.0], "max": [r, r, base_top]})}
    top = (rig_checks.get("figure_top_m") or {}).get("measured")
    face = checks.get("export_frame_face_along_plus_x") or {}
    skin = ((checks.get("appended_skinning_intact") or {}).get("measured") or {}).get(body_name) or []
    build = {
        "schema": "normalised from ld-fbx-report (%s) + H3 rig report + rig-contract validation" % LOOKDEV_HARPY_FORMAT,
        "passed": passed, "profile_id": want_id if maps_ok else None, "profile": c["bake_profile"],
        "skeleton": (rig.get("armature") or {}).get("skeleton"),
        "armature_object": (rig.get("armature") or {}).get("object"),
        "exports": {"skeletal_fbx": dict(ldfbx["exports"]["skeletal_fbx"]), "base_fbx": dict(ldfbx["exports"]["base_fbx"]),
                    "settings": settings},
        "roundtrip": {"skeletal": {"meshes": sk_meshes, "armature_objects": [a[1] for a in skin], "bones": bones},
                      "base": {"meshes": base_meshes, "armature_objects": []},
                      "scale_ratio": [1.0, 1.0, 1.0] if (eq["positions_and_uv0_per_loop_as_h3"] and rb is not None and
                                                         rb == (rig_checks.get("roundtrip_bounds_m") or {}).get("expected"))
                      else None,
                      "scale_ratio_note": "positions per loop equal H3 (max |d| 0) and the H3 round trip equals its "
                                          "authored bounds -> 1:1"},
        "sockets": rig.get("sockets") or [],
        "measures": {"figure_top_uu": round(float(top) * 100.0, 4) if top is not None else None},
        "checks": {"export_face_plus_x": {"passed": face.get("passed") is True, "measured": face.get("measured"),
                                          "expected": face.get("expected"),
                                          "source": "ld-fbx-report checks.export_frame_face_along_plus_x"}},
    }
    textures = {"schema": "normalised from ld-maps-report", "profile_id": want_id if maps_ok else None, "textures": {},
                "conventions": {}}
    size = [int(c["texture_px"])] * 2
    # runtime 2K maps only (the 4K masters carry the same file names and are never imported; adopt keys by name)
    for key, rec in sorted(((ldmaps.get("textures") or {}).get("2k") or {}).items()):
        path = "%s/%s" % (base_dir, rec["path"])
        px = rec.get("size") or (image_px(repo_path(path)) if repo_path(path).is_file() else None)
        textures["textures"][path.rsplit("/", 1)[-1]] = {
            "path": path, "sha256": rec.get("sha256"), "bytes": rec.get("bytes"), "px": px,
            "tier": c["texture_tier"] if px == size else None}
    for key, rec in sorted((ldmaps.get("base_textures") or {}).items()):
        path = "%s/%s" % (base_dir, rec["path"])
        textures["textures"][path.rsplit("/", 1)[-1]] = {"path": path, "sha256": rec.get("sha256"),
                                                         "bytes": rec.get("bytes"), "px": rec.get("size"),
                                                         "tier": "base_1k"}
    if lut.get("dds"):
        p = repo_path(lut["dds"])
        textures["textures"][lut["dds"].rsplit("/", 1)[-1]] = {"path": lut["dds"], "sha256": lut.get("dds_sha256"),
                                                                "px": image_px(p) if p.is_file() else None,
                                                                "tier": "runtime_lut"}
    conv = dict(ldmaps.get("conventions") or {})
    conv.setdefault("BC", "sRGB 8-bit (H3 BC; cord and dielectric clamp per ld_maps)")
    conv["LUT"] = "RGBA16F linear, build_ue_inputs.LUT_ROWS, column = class index (hero slot 5 = horn_claw)"
    conv["BaseBC"] = "sRGB 8-bit (base 1K)"
    conv["BaseN"] = "DirectX (base 1K; N_OpenGL is the Blender copy)"
    conv["BaseORM"] = "linear: R AO, G roughness, B metallic (base 1K)"
    for key in c["textures"]:
        if key in conv:
            textures["conventions"][key] = conv[key]
    info = {"format": LOOKDEV_HARPY_FORMAT, "normaliser": "skeletal_adopt_lookdev.lookdev_harpy",
            "sources": {"ld_fbx_report": "%s/%s" % (base_dir, c["build_report"]),
                        "ld_maps_report": "%s/%s" % (base_dir, c["textures_report"]), "h3_rig_report": rig_rel,
                        "h3_validate_report": val_rel, "h3_textures_report": h3t_rel, "rig_contract": contract_rel,
                        "h3_bake_profile": bake_prof_rel},
            "checks": info_checks,
            "base_bounds_from": {"base_parametric": {"radius_bottom_m": r, "height_m": bp.get("height_m"),
                                                     "pips_raise_m": (bp.get("pips") or {}).get("raise_m")},
                                 "note": "no read-back bounds of the parametric base in the reports; UE measures them"},
            "note": "bones = rig contract (validated on the H3 FBX) with the H3 heads/tails; body bounds, figure top and "
                    "sockets = H3 rig report; FBX bytes, settings, UV layers, triangles and slots = ld-fbx-report"}
    build["normalised"] = info
    return build, textures, info


NORMALISERS = {LOOKDEV_MERLIN_FORMAT: lookdev_merlin, LOOKDEV_ARTHUR_FORMAT: lookdev_arthur,
               LOOKDEV_HARPY_FORMAT: lookdev_harpy}
