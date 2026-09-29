#!/usr/bin/env python3
"""Compare a skeletal-candidate run with a reference run (e.g. a CLI rebuild against the committed candidate).

    python tools/tripo-pipeline/review/compare_candidate_runs.py --pair <new run dir> <reference run dir> [...] \
        --out docs/art-pipeline/evidence/<dir>/comparison.json

Per pair (paths repo-relative or absolute; nothing is written into the runs):
  * exports: sha256/bytes of every FBX of the reference run's export/ against the new run;
  * atlas textures: sha256 of every PNG of the reference run's textures/ that the new run's atlas stage produced;
  * build report numbers: geometry (meshes_pre_export_m: vertices, polygons, triangles, near-degenerate triangles,
    UV layers, material slots), UV (per part: triangles, UV area, texel density, overlap), weights (per mesh:
    influences, unweighted, bones used, share), bones (round trip: parent, head, tail), bounds and the UE bounds
    prediction; each number is compared exactly and the differing paths are listed with both values;
  * metadata: top-level report keys only in one report, the builder fields, manifest stage status.
When the FBX bytes are identical, geometry/UV/weights/bones are identical by construction; the numeric comparison
is the independent cross-check of the two build reports. Deterministic output (sorted keys).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NUMERIC_SECTIONS = {
    "geometry": ("meshes_pre_export_m",),
    "uv": ("uv",),
    "weights": ("weights",),
    "bones": ("roundtrip.skeletal.bones", "bones_final_m"),
    "roundtrip_meshes": ("roundtrip.skeletal.meshes", "roundtrip.base.meshes"),
    "bounds": ("bounds_m.skeletal", "bounds_m.base", "expected_ue_bounds_uu_at_import_scale_1"),
    "orientation": ("orientation.flipped_parts", "orientation.after_fix", "orientation.roundtrip"),
    "sockets": ("sockets",),
}
WEIGHT_ALIASES = {"bow": "weapon"}  # whole-figure reports call the weapon mesh "bow"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(p):
    path = Path(p)
    return path if path.is_absolute() else (REPO / path)


def rel(p):
    try:
        return Path(p).resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(p)


def get(data, dotted):
    node = data
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def flatten(value, prefix=""):
    out = {}
    if isinstance(value, dict):
        for k in sorted(value):
            out.update(flatten(value[k], "%s.%s" % (prefix, k) if prefix else str(k)))
    elif isinstance(value, list) and value and all(isinstance(v, (dict, list)) for v in value):
        for i, v in enumerate(value):
            out.update(flatten(v, "%s[%d]" % (prefix, i)))
    else:
        out[prefix] = value
    return out


def compare_values(old, new):
    fo, fn = flatten(old), flatten(new)
    common = sorted(set(fo) & set(fn))
    differing = {k: {"reference": fo[k], "new": fn[k]} for k in common if fo[k] != fn[k]}
    return {"values_compared": len(common), "equal": len(common) - len(differing), "differing": differing,
            "only_in_reference": sorted(set(fo) - set(fn))[:50], "only_in_new": sorted(set(fn) - set(fo))[:50],
            "only_in_reference_count": len(set(fo) - set(fn)), "only_in_new_count": len(set(fn) - set(fo))}


def compare_pair(new_dir, ref_dir):
    new_dir, ref_dir = resolve(new_dir), resolve(ref_dir)
    out = {"new_run": rel(new_dir), "reference_run": rel(ref_dir)}
    exports = {}
    for fbx in sorted((ref_dir / "export").glob("*.fbx")):
        mine = new_dir / "export" / fbx.name
        exports[fbx.name] = {"reference_sha256": sha256(fbx), "reference_bytes": fbx.stat().st_size,
                             "new_sha256": sha256(mine) if mine.is_file() else None,
                             "new_bytes": mine.stat().st_size if mine.is_file() else None}
        exports[fbx.name]["bytes_identical"] = exports[fbx.name]["new_sha256"] == exports[fbx.name]["reference_sha256"]
    out["exports"] = exports
    out["fbx_bytes_identical"] = bool(exports) and all(e["bytes_identical"] for e in exports.values())
    new_manifest = json.loads((new_dir / "manifest.json").read_text(encoding="utf-8"))
    atlas_outputs = sorted(k for k in (new_manifest["stages"].get("atlas") or {}).get("outputs", {}) if k.startswith("textures/"))
    textures = {}
    for key in atlas_outputs:
        ref = ref_dir / key
        textures[key] = {"new_sha256": sha256(new_dir / key),
                         "reference_sha256": sha256(ref) if ref.is_file() else None}
        textures[key]["bytes_identical"] = textures[key]["new_sha256"] == textures[key]["reference_sha256"]
    out["atlas_textures"] = textures
    out["atlas_bytes_identical"] = bool(textures) and all(t["bytes_identical"] for t in textures.values())
    ref_manifest = json.loads((ref_dir / "manifest.json").read_text(encoding="utf-8"))
    out["manifest"] = {
        "new": {"tool": new_manifest["tool"]["version"],
                "stages": {k: v.get("status") for k, v in sorted(new_manifest["stages"].items())},
                "build_profile": new_manifest["config"].get("build_profile")},
        "reference": {"tool": ref_manifest["tool"]["version"],
                      "stages": {k: v.get("status") for k, v in sorted(ref_manifest["stages"].items())},
                      "build_profile": ref_manifest["config"].get("build_profile")}}
    new_rep = json.loads((new_dir / "reports/build-report.json").read_text(encoding="utf-8"))
    ref_rep = json.loads((ref_dir / "reports/build-report.json").read_text(encoding="utf-8"))
    for alias, name in WEIGHT_ALIASES.items():
        for rep in (new_rep, ref_rep):
            if isinstance(rep.get("weights"), dict) and alias in rep["weights"]:
                rep["weights"][name] = rep["weights"].pop(alias)
    numeric = {}
    for section, paths in NUMERIC_SECTIONS.items():
        pairs = {p: (get(ref_rep, p), get(new_rep, p)) for p in paths}
        present = {p: v for p, v in pairs.items() if v[0] is not None and v[1] is not None}
        numeric[section] = {p: compare_values(*v) for p, v in present.items()}
        numeric[section]["_missing_in_one_report"] = sorted(p for p in pairs if p not in present)
    out["build_report_numbers"] = numeric
    out["build_report_numbers_differing"] = sum(len(c["differing"]) for sec in numeric.values()
                                                for k, c in sec.items() if not k.startswith("_"))
    out["build_report_checks"] = {
        "reference": {"passed": ref_rep.get("passed"), "count": len(ref_rep.get("checks") or {}),
                      "failed": sorted(k for k, c in (ref_rep.get("checks") or {}).items() if not c["passed"])},
        "new": {"passed": new_rep.get("passed"), "count": len(new_rep.get("checks") or {}),
                "failed": sorted(k for k, c in (new_rep.get("checks") or {}).items() if not c["passed"])},
        "names_only_in_reference": sorted(set(ref_rep.get("checks") or {}) - set(new_rep.get("checks") or {})),
        "names_only_in_new": sorted(set(new_rep.get("checks") or {}) - set(ref_rep.get("checks") or {}))}
    out["metadata"] = {
        "report_keys_only_in_reference": sorted(set(ref_rep) - set(new_rep)),
        "report_keys_only_in_new": sorted(set(new_rep) - set(ref_rep)),
        "reference_builder": ref_rep.get("builder"), "reference_builder_sha256": ref_rep.get("builder_sha256"),
        "new_builder": new_rep.get("builder"), "reference_profile": ref_rep.get("profile"),
        "new_profile": new_rep.get("profile"), "new_flow": new_rep.get("flow")}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pair", nargs=2, action="append", required=True, metavar=("NEW_RUN", "REFERENCE_RUN"))
    ap.add_argument("--out", help="write the comparison JSON here (default: stdout)")
    args = ap.parse_args(argv)
    pairs = [compare_pair(new, ref) for new, ref in args.pair]
    result = {"schema": "unmatched.tripo-pipeline.run-comparison/1", "pairs": pairs,
              "all_fbx_bytes_identical": all(p["fbx_bytes_identical"] for p in pairs),
              "all_atlas_bytes_identical": all(p["atlas_bytes_identical"] for p in pairs),
              "all_new_builds_completed": all(p["manifest"]["new"]["stages"].get("build") == "completed" for p in pairs)}
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out:
        path = resolve(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("comparison: %d pairs, fbx identical=%s, atlas identical=%s, builds completed=%s -> %s"
              % (len(pairs), result["all_fbx_bytes_identical"], result["all_atlas_bytes_identical"],
                 result["all_new_builds_completed"], rel(path)))
    else:
        sys.stdout.write(text)
    return 0 if result["all_fbx_bytes_identical"] and result["all_new_builds_completed"] else 1


if __name__ == "__main__":
    sys.exit(main())
