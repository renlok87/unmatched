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


NORMALISERS = {LOOKDEV_MERLIN_FORMAT: lookdev_merlin}
