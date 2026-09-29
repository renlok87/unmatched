#!/usr/bin/env python3
"""skeletal-adopt (tripo-pipeline 0.7.0, W5c): adopt an externally built skeletal candidate for the UE stage.

The H2 bake of a hero (tools/tripo-pipeline/blender/h2_bake_*) writes, next to its reports, a skeletal FBX (armature +
body + weapon), a separate base FBX and the 2K runtime atlas (BC / N DirectX / ORM / TeamMask). The run profile
`skeletal-adopt` of tripo_pipeline.py pins those bytes (stage `adopt`) and imports them into UE with the same code as the
skeletal-candidate route (exec_ue_candidate: textures, MI of M_UM_Figure / M_UM_BaseMarker, legacy FbxFactory import,
sockets, contract checks).

This module is stdlib only and never talks to Blender, UE or the network. adopt() reads the bake's reports, checks
them and returns the adopt report with two normalised views:
  views.build  the subset of a CLI build report that exec_ue_candidate reads (expected UE bounds, figure top, material
               slots, triangles, bones, sockets);
  views.atlas  texture files and size.
Nothing is copied: the report records repo-relative paths and SHA-256; ue-import re-hashes them.

The bake's report layout is named by the build profile (candidate.report_format) and located by RFC 6901 JSON pointers
(REPORT_FORMATS; candidate.pointers may override single entries for another hero's bake module).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ADOPT_SKELETAL_LOGIC_VERSION = "adopt-skeletal/1"
KIND = "skeletal-adopt"

# where each value lives in the bake's build report (h2_bake_merlin rig stage, reports/build-report.json) and in its
# textures report (maps stage, reports/textures-report.json)
REPORT_FORMATS = {
    "h2-bake-rig/1": {
        "build": {
            "passed": "/passed",
            "profile_id": "/profile_id",
            "skeleton": "/skeleton",
            "armature_object": "/armature_object",
            "skeletal_fbx_path": "/exports/skeletal_fbx/path",
            "skeletal_fbx_sha256": "/exports/skeletal_fbx/sha256",
            "base_fbx_path": "/exports/base_fbx/path",
            "base_fbx_sha256": "/exports/base_fbx/sha256",
            "export_settings": "/exports/settings",
            "skeletal_meshes": "/roundtrip/skeletal/meshes",
            "base_meshes": "/roundtrip/base/meshes",
            "armature_objects": "/roundtrip/skeletal/armature_objects",
            "bones": "/roundtrip/skeletal/bones",
            "scale_ratio": "/roundtrip/scale_ratio",
            "sockets": "/sockets",
            "figure_top_uu": "/measures/hood_top_uu",
            "export_face_plus_x_passed": "/checks/export_face_plus_x/passed",
        },
        "textures": {
            "profile_id": "/profile_id",
            "files": "/textures",
            "conventions": "/conventions",
        },
    },
}
# W5c-A: bakes whose own report layout differs are first converted into the h2-bake-rig/1 layout by a normaliser of
# skeletal_adopt_formats.py (NORMALISERS); their pointers are those of h2-bake-rig/1 except where noted
REPORT_FORMATS["h2-bake-arthur/1"] = {  # tools/tripo-pipeline/blender/h2_bake_arthur (rig-report + textures-report)
    "build": dict(REPORT_FORMATS["h2-bake-rig/1"]["build"], figure_top_uu="/measures/figure_top_uu"),
    "textures": dict(REPORT_FORMATS["h2-bake-rig/1"]["textures"]),
}


def normaliser(profile: dict):
    """The report normaliser of the profile's report_format (skeletal_adopt_formats.NORMALISERS) or None."""
    import skeletal_adopt_formats
    return skeletal_adopt_formats.NORMALISERS.get(profile["candidate"].get("report_format"))
# FBX export keys the bake must share with the preset (UM_FBX_v1); path_mode / bake_anim may deviate when the bake
# records the deviation (deviations_from_preset): textures reach UE from the atlas, not through the FBX
PRESET_KEYS = ("axis_forward", "axis_up", "export_space_rotation_z_degrees", "apply_unit_scale", "apply_scale_options",
               "use_triangles", "mesh_smooth_type", "add_leaf_bones", "primary_bone_axis", "secondary_bone_axis")
DOCUMENTED_DEVIATION_KEYS = ("path_mode", "bake_anim")


class AdoptError(Exception):
    pass


def pointer(doc, ptr: str):
    """RFC 6901 JSON pointer ('' = the whole document); KeyError-free: raises AdoptError."""
    if ptr in ("", "/"):
        return doc
    cur = doc
    for raw in ptr.lstrip("/").split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except (ValueError, IndexError):
                raise AdoptError("pointer %s: no item %s" % (ptr, key))
        elif isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            raise AdoptError("pointer %s: no key %s" % (ptr, key))
    return cur


def pointers(profile: dict) -> dict:
    c = profile["candidate"]
    fmt = c.get("report_format")
    if fmt not in REPORT_FORMATS:
        raise AdoptError("candidate.report_format must be one of %s (got %r)" % (sorted(REPORT_FORMATS), fmt))
    out = {part: dict(ptrs) for part, ptrs in REPORT_FORMATS[fmt].items()}
    for part, ptrs in (c.get("pointers") or {}).items():
        out.setdefault(part, {}).update(ptrs)
    return out


def candidate_files(profile: dict) -> dict:
    """Repo-relative paths of the adopted candidate: fbx:skeletal, fbx:base, texture:<key>, report:build,
    report:textures."""
    c = profile["candidate"]
    base = c["dir"].rstrip("/")
    files = {"fbx:skeletal": "%s/%s" % (base, c["fbx"]["skeletal"]), "fbx:base": "%s/%s" % (base, c["fbx"]["base"]),
             "report:build": "%s/%s" % (base, c["build_report"]),
             "report:textures": "%s/%s" % (base, c["textures_report"])}
    for key, rel in sorted(c["textures"].items()):
        files["texture:" + key] = "%s/%s" % (base, rel)
    # W5c-A: further reports a normaliser reads (bake manifest, rig-contract validation) and the bake profile are
    # pinned like the rest, so their change re-runs adopt and blocks a stale ue-import
    for key, rel in sorted((c.get("extra_reports") or {}).items()):
        files["report:" + key] = "%s/%s" % (base, rel)
    if c.get("extra_reports") and c.get("bake_profile"):
        files["profile:bake"] = c["bake_profile"]
    return files


def rotate_z(x: float, y: float, degrees: float) -> tuple:
    c, s = round(math.cos(math.radians(degrees)), 12), round(math.sin(math.radians(degrees)), 12)
    return c * x - s * y, s * x + c * y


def frames_of(authored: dict, rotation_z: float) -> dict:
    """Authored Blender bounds (uu, front -Y) -> export frame (rotation about Z, UM_FBX_v1) -> UE (x, -y, z) (ART-001).
    Returns {"blender_axes", "export_frame", "ue_predicted"} with min/max lists."""
    lo, hi = authored["min"], authored["max"]
    pts = [rotate_z(x, y, rotation_z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]
    ex = {"min": [min(p[0] for p in pts), min(p[1] for p in pts), lo[2]],
          "max": [max(p[0] for p in pts), max(p[1] for p in pts), hi[2]]}
    ue = {"min": [ex["min"][0], -ex["max"][1], ex["min"][2]], "max": [ex["max"][0], -ex["min"][1], ex["max"][2]]}

    def rnd(b):
        return {k: [round(v + 0.0, 4) for v in b[k]] for k in ("min", "max")}

    return {"blender_axes": rnd(authored), "export_frame": rnd(ex), "ue_predicted": rnd(ue)}


def union_bounds_uu(meshes: dict) -> dict:
    los = [m["bounds_m"]["min"] for m in meshes.values()]
    his = [m["bounds_m"]["max"] for m in meshes.values()]
    return {"min": [round(min(v[i] for v in los) * 100.0, 4) for i in range(3)],
            "max": [round(max(v[i] for v in his) * 100.0, 4) for i in range(3)]}


def adopt(profile: dict, repo_path, sha256_file, png_pixels, preset: dict) -> dict:
    """Pin and check the external candidate named by profile["candidate"].

    repo_path(rel) -> Path, sha256_file(Path) -> hex, png_pixels(Path) -> [w, h] | None, preset = the FBX preset JSON.
    Returns {"checks", "passed", "inputs", "keys", "views", "bake"}; raises AdoptError on a missing file or an
    unreadable report.
    """
    c = profile["candidate"]
    ptr = pointers(profile)
    files = candidate_files(profile)
    missing = [rel for rel in files.values() if not repo_path(rel).is_file()]
    if missing:
        raise AdoptError("skeletal candidate files missing: %s" % missing)
    hashes = {key: sha256_file(repo_path(rel)) for key, rel in sorted(files.items())}
    build = json.loads(repo_path(files["report:build"]).read_text(encoding="utf-8"))
    tex_report = json.loads(repo_path(files["report:textures"]).read_text(encoding="utf-8"))
    normalised = None
    norm = normaliser(profile)
    if norm is not None:
        # W5c-A: another bake module's layout -> h2-bake-rig/1 (skeletal_adopt_formats.py); its integrity checks fold
        # into the canonical "passed" and are reported under bake.normalised
        try:
            build, tex_report, normalised = norm(build, tex_report, profile, repo_path, sha256_file)
        except Exception as exc:  # noqa: BLE001 - skeletal_adopt_formats.NormaliseError, KeyError of a bad report
            raise AdoptError("normaliser %s: %s: %s" % (c.get("report_format"), type(exc).__name__, exc))

    def b(name):
        return pointer(build, ptr["build"][name])

    def t(name):
        return pointer(tex_report, ptr["textures"][name])

    checks = {}

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    check("bake_report_passed", b("passed") is True, b("passed"), True,
          "the bake's own checks (%s) all passed" % files["report:build"])
    want_id = c.get("bake_profile_id")
    check("bake_reports_are_of_the_named_profile", b("profile_id") == want_id and t("profile_id") == want_id,
          {"build_report": b("profile_id"), "textures_report": t("profile_id")}, want_id)
    fbx = {"skeletal": {"path": b("skeletal_fbx_path"), "sha256": b("skeletal_fbx_sha256")},
           "base": {"path": b("base_fbx_path"), "sha256": b("base_fbx_sha256")}}
    fbx_ok = {k: fbx[k]["path"] == files["fbx:" + k] and fbx[k]["sha256"] == hashes["fbx:" + k] for k in fbx}
    check("fbx_bytes_match_bake_report", all(fbx_ok.values()),
          {k: {"file": hashes["fbx:" + k], "report": fbx[k]["sha256"], "same_path": fbx[k]["path"] == files["fbx:" + k]}
           for k in fbx})
    tex_files = t("files")
    size = int(c["texture_px"])
    tex = {}
    for key in sorted(c["textures"]):
        rel = files["texture:" + key]
        rec = tex_files.get(Path(rel).name) or {}
        px = png_pixels(repo_path(rel))
        tex[key] = {"file": Path(rel).name, "sha256_ok": rec.get("sha256") == hashes["texture:" + key],
                    "same_path": rec.get("path") == rel, "tier": rec.get("tier"), "report_px": rec.get("px"),
                    "png_px": px}
    check("texture_bytes_match_textures_report", all(v["sha256_ok"] and v["same_path"] for v in tex.values()),
          {k: {"sha256_ok": v["sha256_ok"], "same_path": v["same_path"]} for k, v in tex.items()})
    tier = c.get("texture_tier")
    check("textures_are_the_runtime_tier", all(v["tier"] == tier and v["png_px"] == [size, size] and
                                              v["report_px"] == [size, size] for v in tex.values()),
          {k: {"tier": v["tier"], "png_px": v["png_px"]} for k, v in tex.items()}, {"tier": tier, "px": [size, size]},
          "only the committed runtime maps reach UE; the local 4K masters are never imported")
    conv = t("conventions")
    want_conv = c.get("conventions_required") or {}
    conv_ok = {k: isinstance(conv.get(k), str) and want in conv[k] for k, want in sorted(want_conv.items())}
    check("texture_conventions_as_ue_expects", bool(want_conv) and all(conv_ok.values()),
          {k: conv.get(k) for k in want_conv}, want_conv,
          "N DirectX (UE TC_Normalmap, no green flip), ORM R AO / G roughness / B metallic linear, TeamMask linear")
    settings = b("export_settings")
    diffs = {k: [settings.get(k), preset.get(k)] for k in PRESET_KEYS if settings.get(k) != preset.get(k)}
    documented = settings.get("deviations_from_preset") or {}
    undocumented = sorted(k for k in DOCUMENTED_DEVIATION_KEYS
                          if k in preset and settings.get(k) != preset.get(k) and k not in documented)
    check("fbx_export_settings_equal_preset", not diffs and not undocumented and
          (settings.get("preset") or {}).get("name") == preset.get("name"),
          {"differences": diffs, "documented_deviations": documented, "undocumented": undocumented,
           "preset": (settings.get("preset") or {}).get("name")}, preset.get("name"))
    arm = profile["armature"]
    want_bones = {n: p for n, p in ((x[0], x[1]) for x in arm["bones"])}
    bones = b("bones")
    got_bones = {n: v.get("parent") for n, v in bones.items()}
    check("skeleton_contract", b("skeleton") == arm["skeleton"] and b("armature_object") == arm["object"]
          and b("armature_objects") == [arm["object"]] and got_bones == want_bones,
          {"skeleton": b("skeleton"), "armature_object": b("armature_object"), "armature_objects": b("armature_objects"),
           "bones": len(got_bones), "bones_equal_profile": got_bones == want_bones},
          {"skeleton": arm["skeleton"], "armature_object": arm["object"], "bones": len(want_bones)},
          "names and parents of every bone (Blender names; UE turns '.' into '_')")
    check("roundtrip_scale_1", [float(v) for v in b("scale_ratio")] == [1.0, 1.0, 1.0], b("scale_ratio"), [1, 1, 1])
    check("bake_export_face_plus_x", b("export_face_plus_x_passed") is True, b("export_face_plus_x_passed"), True,
          "the bake measured the face ahead of the body along +X in the export frame (UE front +X)")
    sk_meshes, base_meshes = b("skeletal_meshes"), b("base_meshes")
    sk_slots = sorted({s for mesh in sk_meshes.values() for s in mesh["material_slots"]})
    base_obj = profile["meshes"]["base"]["object"]
    exp = profile["expectations"]
    base_rec = base_meshes.get(base_obj) or {}
    check("material_slots_as_profile", len(sk_slots) == exp["skeletal_material_slots"] and
          len(base_rec.get("material_slots") or []) == exp["base_material_slots"],
          {"skeletal_unique": sk_slots, "base": base_rec.get("material_slots")},
          {"skeletal": exp["skeletal_material_slots"], "base": exp["base_material_slots"]})
    tris = {n: m["triangles"] for n, m in sorted(sk_meshes.items())}
    tris[base_obj] = base_rec.get("triangles")
    want_tris = exp.get("triangles") or {}
    check("triangles_as_profile", bool(want_tris) and tris == want_tris, tris, want_tris)
    sockets = {s["name"]: s for s in b("sockets")}
    need = [s["name"] for s in profile["sockets"] if not isinstance(s.get("location_uu"), list)]
    check("sockets_have_bake_predictions", all(isinstance((sockets.get(n) or {}).get("location_uu_for_ue"), list)
                                               for n in need), {n: (sockets.get(n) or {}).get("location_uu_for_ue")
                                                                for n in need},
          note="a profile socket without location_uu takes the bake's UE bone-space prediction (location_uu_for_ue)")

    rot = float(settings.get("export_space_rotation_z_degrees", 0.0))
    sk_frames = frames_of(union_bounds_uu(sk_meshes), rot)
    base_frames = frames_of(union_bounds_uu({base_obj: base_rec}), rot) if base_rec else None
    figure_top_uu = float(b("figure_top_uu"))
    views = {
        "build": {
            "source": "normalised by skeletal_adopt.py from %s (format %s)" % (files["report:build"], c["report_format"]),
            "expected_ue_bounds_uu_at_import_scale_1": {
                "export_rotation_z_degrees": rot,
                "skeletal_blender_axes": sk_frames["blender_axes"], "skeletal_export_frame": sk_frames["export_frame"],
                "skeletal_ue_predicted": sk_frames["ue_predicted"],
                "base_blender_axes": base_frames and base_frames["blender_axes"],
                "base_ue_predicted": base_frames and base_frames["ue_predicted"],
                "note": "union of the bake's round-trip bounds (authored frame, front -Y, cm); export frame rotated "
                        "about Z by the preset; UE = export frame (x, -y, z) (ART-001)"},
            "figure": {"figure_height_m": profile["scale"]["figure_height_m"], "figure_top_m": round(figure_top_uu / 100.0, 6),
                       "top_part": c.get("top_part"), "skeletal_top_m": round(sk_frames["blender_axes"]["max"][2] / 100.0, 6)},
            "checks": {"roundtrip_material_slots": {"measured": {"skeletal_unique": sk_slots,
                                                                 "per_mesh": {n: m["material_slots"] for n, m in
                                                                              sorted(sk_meshes.items())}}}},
            "meshes_pre_export_m": {n: {"triangles": m["triangles"],
                                        "near_degenerate_triangles": m.get("near_degenerate_triangles", 0),
                                        "near_degenerate_area_cm2_below": m.get("near_degenerate_area_cm2_below")}
                                    for n, m in sorted(list(sk_meshes.items()) + [(base_obj, base_rec)])},
            "roundtrip": {"skeletal": {"meshes": {n: {"triangles": m["triangles"], "vertices": m.get("vertices")}
                                                  for n, m in sorted(sk_meshes.items())},
                                       "bones": bones}},
            "sockets": [{k: s.get(k) for k in ("name", "bone", "location_uu_for_ue", "target_ue_component_uu",
                                                "offset_blender_bone_local_uu", "status")}
                        for s in b("sockets")],
            "exports": {"skeletal": files["fbx:skeletal"], "base": files["fbx:base"]},
        },
        "atlas": {"size": size, "files": {k: {"file": Path(files["texture:" + k]).name} for k in sorted(c["textures"])}},
    }
    passed = all(v["passed"] for v in checks.values())
    return {"checks": checks, "passed": passed, "inputs": {files[k]: v for k, v in sorted(hashes.items())},
            "keys": files, "views": views,
            "bake": dict({"report_format": c["report_format"], "profile": c.get("bake_profile"), "profile_id": want_id},
                         **({"normalised": normalised} if normalised is not None else {}))}


def expected_skeletal_triangles(view: dict) -> dict:
    """LOD0 triangle band UE may show for the skeletal mesh: the bake's round-trip sum, minus at most the
    near-degenerate slivers the UE mesh build may drop."""
    meshes = view["meshes_pre_export_m"]
    names = list(view["roundtrip"]["skeletal"]["meshes"])
    total = sum(meshes[n]["triangles"] for n in names)
    slivers = sum(meshes[n].get("near_degenerate_triangles") or 0 for n in names)
    return {"max": total, "min": total - slivers, "meshes": names}
