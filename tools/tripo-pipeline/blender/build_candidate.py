"""Stage `build`: segmented Tripo GLB -> skeletal game candidate (body [+ weapon]) and a separate base.

Run only through tripo_pipeline.py, in the isolation modes of import_source.py:
``process`` (headless ``blender -b``, factory-empty scene) or ``live`` (running
Blender GUI via blender_mcp.py ``execute_code``: work happens in temporary scenes,
the user's file is never reset, opened or saved, every datablock created here is
removed again and the FBX exporter patches are reverted).

params.json: {"source": abs GLB, "profile": abs build profile, "atlas_report": abs,
              "textures_dir": abs, "repo_root": abs, "blend_out": abs, "fbx_preset": abs JSON,
              "sk_fbx_out": abs, "base_fbx_out": abs, "report_out": abs,
              "lib_dir": abs dir of this script (candidate_build/ lives there),
              "reference_glb": abs GLB (only for orientation.per_face_reference)}

The algorithm lives in the package candidate_build/ next to this file and is selected and parameterised by
the build profile (build.flow, see candidate_build/profile_schema.py):
  whole-figure  the T4 Medusa candidate (tool 0.4.0 behaviour, byte-identical FBX)
  seated-parts  heroes: figure seated on a normalised or parametric base, weapon split/assembled/none,
                closure caps, per-face orientation vote, heat/rigid/wing/axis weights (replaces the per-hero
                builders art/pipeline-candidates/ASSET-*/scripts/build_*_candidate.py of 2026-09-28, same FBX bytes)
Every FBX follows the verified preset UM_FBX_v1 (blender/_tools/presets/UM_FBX_v1.json, ART-001 PASS,
04-blender-production.md §1/§1.1): authored front -Y is rotated to +X before export.
The report is deterministic (rounded floats, sorted keys, no timestamps).
"""

import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import bpy  # noqa: F401  (the stage runs inside Blender)

LIB_PACKAGE = "tripo_pipeline_candidate_build"
LIB_MODULES = ("core", "measure", "mesh_ops", "weapon", "closure", "rig", "orientation", "base", "anatomy",
               "profile_schema", "flow_whole_figure", "flow_seated")


def load_params():
    injected = globals().get("TRIPO_PIPELINE_PARAMS")
    path = injected if injected else sys.argv[sys.argv.index("--") + 1]
    return json.loads(Path(path).read_text(encoding="utf-8"))


def library_dir(params):
    if params.get("lib_dir"):
        return Path(params["lib_dir"])
    here = globals().get("__file__")
    if here:
        return Path(here).resolve().parent
    raise RuntimeError("params.lib_dir is required when the stage runs without __file__ (live execute_code)")


def unload_library():
    for key in [k for k in list(sys.modules) if k == LIB_PACKAGE or k.startswith(LIB_PACKAGE + ".")]:
        del sys.modules[key]


def load_library(directory):
    """A fresh copy of candidate_build/ on every run (a live Blender session never keeps stale modules)."""
    pkg_dir = Path(directory) / "candidate_build"
    unload_library()
    spec = importlib.util.spec_from_file_location(LIB_PACKAGE, pkg_dir / "__init__.py",
                                                  submodule_search_locations=[str(pkg_dir)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[LIB_PACKAGE] = package
    spec.loader.exec_module(package)
    modules = {name: importlib.import_module("%s.%s" % (LIB_PACKAGE, name)) for name in LIB_MODULES}
    modules["package"] = package
    return modules


def library_hashes(directory):
    out = {}
    for path in sorted((Path(directory) / "candidate_build").glob("*.py")):
        out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def main():
    isolation = globals().get("TRIPO_PIPELINE_ISOLATION", "process")
    params = load_params()
    profile = json.loads(Path(params["profile"]).read_text(encoding="utf-8"))
    directory = library_dir(params)
    lib = load_library(directory)
    try:
        problems = lib["profile_schema"].validate(profile)
        if problems:
            raise RuntimeError("build profile invalid: %s" % "; ".join(problems))
        flow = lib["profile_schema"].flow_of(profile)
        ctx = lib["core"].BuildContext(params, profile, isolation, directory)
        ctx.begin()
        try:
            runner = lib["flow_whole_figure"] if flow == "whole-figure" else lib["flow_seated"]
            report = runner.run(ctx)
        finally:
            removed = ctx.end()
        report["builder"] = {"script": "tools/tripo-pipeline/blender/build_candidate.py",
                             "library": lib["package"].LIB_VERSION, "flow": flow,
                             "library_sha256": library_hashes(directory)}
        ctx.write_report(report)
        if not report["passed"]:
            raise RuntimeError("build checks failed: %s" % sorted(k for k, c in report["checks"].items()
                                                                  if not c["passed"]))
        print(lib["core"].MARKER, "isolation=%s" % isolation, "flow=%s" % flow, "temp_ids_removed=%d" % removed,
              "sk=%s" % report["exports"]["skeletal"]["sha256"][:12],
              "base=%s" % report["exports"]["base"]["sha256"][:12])
    finally:
        unload_library()


main()
