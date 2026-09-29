#!/usr/bin/env python3
"""skeletal-adopt report normalisers (tripo-pipeline 0.7.0, W5c-A): hero H2 bakes whose report layout is not the one
skeletal_adopt.REPORT_FORMATS points into.

skeletal_adopt.adopt() reads a bake through RFC 6901 pointers into the layout of the Merlin H2 bake
(h2_bake_merlin: reports/build-report.json with roundtrip/*/meshes[].bounds_m in the authored frame, measures,
scale_ratio; reports/textures-report.json with textures keyed by file name and conventions). Other hero bake modules
write the same facts in another shape. A normaliser converts the raw reports of such a bake into that layout BEFORE
the pointers are applied, so adopt() and every check it runs stay the same for all heroes. It only restructures and
re-derives values from the bake's own reports (no Blender, no UE, no network); integrity checks that the target layout
has no slot for (the bake manifest, the rig-contract validation) fold into the canonical `passed` and are listed,
with measured values, under `normalised`.

NORMALISERS[report_format](build_raw, textures_raw, profile, repo_path, sha256_file) -> (build, textures, info)

  h2-bake-arthur/1   tools/tripo-pipeline/blender/h2_bake_arthur (reports/rig-report.json schema
                     unmatched.h2-bake.rig/1 + reports/textures-report.json schema unmatched.h2-bake.textures/2 +
                     reports/manifest-h2.json + reports/validate-skeletal-mesh-v2.json)
"""

from __future__ import annotations

import json
import math
import re

ARTHUR_FORMAT = "h2-bake-arthur/1"
ARTHUR_RIG_SCHEMA = "unmatched.h2-bake.rig/1"
ARTHUR_TEXTURES_SCHEMA = "unmatched.h2-bake.textures/2"
ARTHUR_MANIFEST_SCHEMA = "unmatched.h2-bake.manifest/1"
BLENDER_DUP_SUFFIX = re.compile(r"\.\d{3}$")  # read-back objects of a session that still holds the authored ones


class NormaliseError(Exception):
    pass


def strip_dup(name: str) -> str:
    """'SK_KingArthur_H2_Body.001' -> 'SK_KingArthur_H2_Body' (the bake reads the FBX back into the session that holds
    the authored objects, so Blender suffixes the read-back names; rig check readback_one_armature_named)."""
    return BLENDER_DUP_SUFFIX.sub("", name)


def export_to_authored(bounds: dict, rotation_z: float) -> dict:
    """AABB in the export frame (FBX read back in Blender) -> AABB in the authored frame (front -Y): rotate the four
    corners by -rotation_z about Z (exact for the 90 deg of UM_FBX_v1)."""
    c, s = round(math.cos(math.radians(-rotation_z)), 12), round(math.sin(math.radians(-rotation_z)), 12)
    lo, hi = bounds["min"], bounds["max"]
    pts = [(c * x - s * y, s * x + c * y) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]
    return {"min": [round(min(p[0] for p in pts) + 0.0, 6), round(min(p[1] for p in pts) + 0.0, 6), lo[2]],
            "max": [round(max(p[0] for p in pts) + 0.0, 6), round(max(p[1] for p in pts) + 0.0, 6), hi[2]]}


def _mesh(rec: dict, rotation_z: float) -> dict:
    out = {k: rec.get(k) for k in ("material_slots", "triangles", "polygons", "vertices", "uv_layers",
                                   "uv0_in_unit_square", "near_degenerate_triangles", "near_degenerate_area_cm2_below",
                                   "has_custom_normals", "color_attributes")}
    out["bounds_m"] = export_to_authored(rec["bounds_m_fbx_frame"], rotation_z)
    out["bounds_m_export_frame"] = rec["bounds_m_fbx_frame"]
    return out


def arthur_h2(rig: dict, tex: dict, profile: dict, repo_path, sha256_file) -> tuple:
    """King Arthur H2 bake (h2_bake_arthur) -> the h2-bake-rig/1 layout of skeletal_adopt."""
    c = profile["candidate"]
    if rig.get("schema") != ARTHUR_RIG_SCHEMA:
        raise NormaliseError("rig report schema %r, expected %s" % (rig.get("schema"), ARTHUR_RIG_SCHEMA))
    if tex.get("schema") != ARTHUR_TEXTURES_SCHEMA:
        raise NormaliseError("textures report schema %r, expected %s" % (tex.get("schema"), ARTHUR_TEXTURES_SCHEMA))
    base_dir = c["dir"].rstrip("/")
    bake_rel = c["bake_profile"]
    bake_path = repo_path(bake_rel)
    if not bake_path.is_file():
        raise NormaliseError("bake profile missing: %s" % bake_rel)
    bake = json.loads(bake_path.read_text(encoding="utf-8"))
    bake_sha = sha256_file(bake_path)
    extra = {}
    for key in ("manifest", "validate_report"):
        rel = "%s/%s" % (base_dir, c["extra_reports"][key])
        path = repo_path(rel)
        if not path.is_file():
            raise NormaliseError("%s missing: %s" % (key, rel))
        extra[key] = (rel, json.loads(path.read_text(encoding="utf-8")))
    manifest_rel, manifest = extra["manifest"]
    validate_rel, validate = extra["validate_report"]

    settings = rig["exports"]["settings"]
    rot = float(settings.get("export_space_rotation_z_degrees", 0.0))
    sk_read, base_read = rig["readback"]["skeletal"], rig["readback"]["base"]
    sk_meshes = {strip_dup(n): _mesh(m, rot) for n, m in sorted(sk_read["meshes"].items())}
    base_meshes = {strip_dup(n): _mesh(m, rot) for n, m in sorted(base_read["meshes"].items())}
    armatures = [strip_dup(a) for a in sk_read.get("armatures") or []]
    bones_final = (rig.get("armature") or {}).get("bones_final_m") or {}
    bones = {}
    for name, rec in sorted(sk_read["bones"].items()):
        head_tail = bones_final.get(name) or [None, None]
        bones[name] = {"parent": rec.get("parent"), "head_m": head_tail[0], "tail_m": head_tail[1]}
    # round-trip scale: the body read back from the FBX (export frame, back in the authored frame) against the body the
    # rig stage measured before export (geometry.bounds_body_m, authored frame)
    body = next((m for n, m in sk_meshes.items() if n == c.get("body_object")), None)
    pre = (rig.get("geometry") or {}).get("bounds_body_m")
    ratio = None
    if body and pre:
        ext_rb = [body["bounds_m"]["max"][i] - body["bounds_m"]["min"][i] for i in range(3)]
        ext_pre = [pre["max"][i] - pre["min"][i] for i in range(3)]
        ratio = [round(a / b, 4) if b else None for a, b in zip(ext_rb, ext_pre)]
    checks = rig.get("checks") or {}
    failed_rig = sorted(k for k, v in checks.items() if not (isinstance(v, dict) and v.get("passed") is True))
    fbx = {k: rig["exports"][k] for k in ("skeletal_fbx", "base_fbx")}

    # integrity the target layout has no slot for
    listed = {f["file"]: f["sha256"] for f in manifest.get("files") or []}
    want = {fbx["skeletal_fbx"]["file"]: fbx["skeletal_fbx"]["sha256"], fbx["base_fbx"]["file"]: fbx["base_fbx"]["sha256"]}
    runtime = (tex.get("outputs") or {}).get(c["texture_tier"]) or {}
    for key in c["textures"]:
        rec = runtime.get(key) or {}
        want[rec.get("file")] = rec.get("sha256")
    manifest_ok = (manifest.get("schema") == ARTHUR_MANIFEST_SCHEMA and manifest.get("profile") == bake_rel and
                   manifest.get("profile_sha256") == bake_sha and all(listed.get(f) == s for f, s in want.items()))
    validate_ok = (validate.get("result") == "pass" and validate.get("kind") == "skeletal-mesh" and
                   validate.get("skeleton") == profile["armature"]["skeleton"] and
                   validate.get("clip") == fbx["skeletal_fbx"]["file"] and
                   validate.get("clip_sha256") == fbx["skeletal_fbx"]["sha256"] and not validate.get("fails"))
    rig_ok = not rig.get("failed") and not failed_rig and rig.get("profile") == bake_rel
    info = {
        "format": ARTHUR_FORMAT, "normaliser": "skeletal_adopt_formats.arthur_h2",
        "sources": {"rig_report": "%s/%s" % (base_dir, c["build_report"]),
                    "textures_report": "%s/%s" % (base_dir, c["textures_report"]),
                    "manifest": manifest_rel, "validate_report": validate_rel, "bake_profile": bake_rel},
        "bake_profile_sha256": bake_sha,
        "checks": {
            "rig_report_all_checks_passed": {"passed": rig_ok, "failed_list": rig.get("failed"),
                                             "failed_checks": failed_rig, "checks": len(checks),
                                             "profile": rig.get("profile")},
            "bake_manifest_lists_the_adopted_bytes": {
                "passed": manifest_ok, "manifest_profile_sha256": manifest.get("profile_sha256"),
                "bake_profile_sha256": bake_sha, "files": {f: listed.get(f) == s for f, s in sorted(want.items())}},
            "rig_contract_validation_pass": {
                "passed": validate_ok, "result": validate.get("result"), "skeleton": validate.get("skeleton"),
                "contract_revision": validate.get("contract_revision"), "clip_sha256": validate.get("clip_sha256")},
        },
        "renamed_readback_objects": {n: strip_dup(n) for n in list(sk_read["meshes"]) + list(base_read["meshes"]) +
                                     list(sk_read.get("armatures") or []) if strip_dup(n) != n},
        "note": "read-back object names lose the '.NNN' suffix Blender adds because the bake reads the FBX back into "
                "the session that still holds the authored objects; mesh bounds go from the export frame back to the "
                "authored frame (rotation %.0f deg about Z)" % rot,
    }
    passed = rig_ok and manifest_ok and validate_ok
    face = checks.get("readback_face_plus_x") or {}
    build = {
        "schema": "normalised from %s" % ARTHUR_RIG_SCHEMA,
        "passed": passed,
        "profile_id": bake.get("profile_id") if rig.get("profile") == bake_rel else None,
        "profile": rig.get("profile"),
        "skeleton": str((rig.get("armature") or {}).get("skeleton") or "").split(" ")[0] or None,
        "armature_object": (rig.get("armature") or {}).get("object"),
        "exports": {"skeletal_fbx": {"path": fbx["skeletal_fbx"]["file"], "sha256": fbx["skeletal_fbx"]["sha256"],
                                     "bytes": fbx["skeletal_fbx"].get("bytes")},
                    "base_fbx": {"path": fbx["base_fbx"]["file"], "sha256": fbx["base_fbx"]["sha256"],
                                 "bytes": fbx["base_fbx"].get("bytes")},
                    "settings": settings},
        "roundtrip": {"skeletal": {"meshes": sk_meshes, "armature_objects": armatures, "bones": bones},
                      "base": {"meshes": base_meshes, "armature_objects": [strip_dup(a) for a in base_read.get("armatures") or []]},
                      "scale_ratio": ratio,
                      "scale_ratio_note": "extent of the read-back body / extent of the body measured before export "
                                          "(rig-report geometry.bounds_body_m), per authored axis"},
        "sockets": rig.get("sockets") or [],
        "measures": {"figure_top_uu": round(float(rig["geometry"]["figure_height_m"]) * 100.0, 4),
                     "sword_tip_uu": round(float(rig["geometry"].get("sword_tip_m") or 0.0) * 100.0, 4),
                     "triangles_total": rig["geometry"].get("triangles_total")},
        "checks": {"export_face_plus_x": {"passed": face.get("passed") is True, "measured": face.get("measured"),
                                          "expected": face.get("expected"), "source": "rig-report checks.readback_face_plus_x"}},
        "normalised": info,
    }
    textures = {"schema": "normalised from %s" % ARTHUR_TEXTURES_SCHEMA, "profile_id": build["profile_id"],
                "textures": {}, "conventions": {}}
    by_path = {}
    for tier, maps in sorted((tex.get("outputs") or {}).items()):
        for key, rec in sorted(maps.items()):
            name = rec["file"].rsplit("/", 1)[-1]
            textures["textures"][name] = {"path": rec["file"], "sha256": rec["sha256"], "bytes": rec.get("bytes"),
                                          "px": rec.get("px"), "tier": tier, "map": key, "colour": rec.get("colour")}
            by_path[rec["file"]] = rec
    # the convention of each map is the one the bake wrote for the FILE the profile names (profile N pointing at
    # T_*_N_OpenGL.png reads "OpenGL/Blender (+Y)" and fails the DirectX requirement of adopt)
    for key, rel in sorted(c["textures"].items()):
        textures["conventions"][key] = (by_path.get("%s/%s" % (base_dir, rel)) or {}).get("colour")
    return build, textures, info


NORMALISERS = {ARTHUR_FORMAT: arthur_h2}
