#!/usr/bin/env python3
"""Driver of the King Arthur H2 bake (system python; Blender stages run headless, one process at a time).

    python tools/tripo-pipeline/blender/h2_bake_arthur/run.py --profile <profile.json> --run-dir <dir>
        [--stages inspect,lowpoly,uvcheck,bake,textures,rig,probe,review,sheets,compare,sheets_h21,compare_h22,
                  steelcheck,sheets_h22,manifest]
        [--from STAGE]

Every stage writes logs/<stage>.log; a Blender stage counts as done only if its log has the H2_BAKE_STAGE_OK marker
(Blender exits 0 even when the script raised). No paid service is called; the Tripo GLBs are only read.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pure as P  # noqa: E402

ORDER = ["inspect", "lowpoly", "uvcheck", "bake", "textures", "rig", "probe", "review", "sheets", "compare", "sheets_h21",
         "compare_h22", "steelcheck", "sheets_h22", "manifest"]
# default stages of a full run: the H2.1 frames (compare, sheets_h21) are the committed H2.1 record and are not rebuilt
# by default (after H2.2 stage compare renders the H2.1 baseline textures of review_h22.baseline_h21, not the current)
DEFAULT_SKIP = {"inspect", "compare", "sheets_h21"}
BLENDER_STAGES = {"inspect": "stage_inspect.py", "lowpoly": "stage_lowpoly.py", "bake": "stage_bake.py",
                  "rig": "stage_rig.py", "review": "stage_review.py"}
PY_STAGES = {"uvcheck": "uvcheck.py", "textures": "textures.py", "sheets": "sheets.py", "sheets_h21": "sheets_h21.py",
             "steelcheck": "steelcheck.py", "sheets_h22": "sheets_h22.py"}
ANIM = P.REPO / "tools" / "tripo-pipeline" / "anim"
FBX_TO_BLEND = P.REPO / "art" / "pipeline-candidates" / "ASSET-KING-ARTHUR-001" / "scripts" / "fbx_to_authored_blend.py"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(cmd, log, marker=None, ok_codes=(0,)):
    t = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    if proc.returncode not in ok_codes or (marker and marker not in text) or "Traceback" in text:
        raise SystemExit("stage failed (exit %s): %s\n%s" % (proc.returncode, " ".join(map(str, cmd)), text[-3000:]))
    return round(time.time() - t, 1), proc.returncode


def blender(script, *args, threads=None):
    extra = ["--threads", str(threads)] if threads else []
    return [P.BLENDER_EXE, "-b", "--factory-startup", *extra, "--python", str(script), "--", *map(str, args)]


# the bone heat solve and the voxel remesh of the weight proxy are multithreaded: with several threads the weights
# differ run to run by <= 3e-6 (measured 2026-09-29: 513 of 38 336 weights), which changes the FBX bytes
STAGE_THREADS = {"rig": 1}


def stage_probe(profile, paths, logs):
    out = {}
    rc = profile["rig"]
    sk = paths["export"] / rc["exports"]["skeletal_fbx"]
    deform = paths["preview"] / "deform"
    deform.mkdir(parents=True, exist_ok=True)
    fbx_blend = paths["work"] / "probe-fbx-authored.blend"
    out["fbx_to_authored"] = run(blender(FBX_TO_BLEND, sk, fbx_blend), logs / "probe-fbx-to-blend.log", "FBX_AUTHORED_OK")
    for label, src in (("arthur-h2-blend", paths["work"] / "h2-rig-authored.blend"), ("arthur-h2-fbx", fbx_blend)):
        out[label] = run(blender(ANIM / "rig_deform_probe.py", src, deform, label), logs / ("probe-%s.log" % label),
                         "DEFORM_OK")
        run([sys.executable, str(ANIM / "overlay_bones.py"), str(deform), label], logs / ("overlay-%s.log" % label))
    vrep = paths["reports"] / "validate-skeletal-mesh-v2.json"
    out["validate_clip"] = run(blender(ANIM / "validate_clip.py", sk, "--kind=skeletal-mesh", "--character=Arthur",
                                       "--out=%s" % vrep), logs / "validate-clip.log", "CLIP_VALIDATION", ok_codes=(0, 1))
    irep = paths["reports"] / "inspect-rig-SK_KingArthur_H2.json"
    out["inspect_rig"] = run(blender(ANIM / "inspect_rig.py", sk, irep), logs / "inspect-rig.log")
    summary = {}
    for label in ("arthur-h2-blend", "arthur-h2-fbx"):
        rep = P.load_json(deform / ("%s-deform.json" % label))
        summary[label] = {t["test"]: {"status": t["status"], "moved_vertices": t.get("moved_vertices"),
                                      "z_norm": t.get("centroid_z_norm"), "x_norm": t.get("centroid_x_norm")}
                          for t in rep["tests"]}
        summary[label + "_plausible"] = sum(1 for t in rep["tests"] if t["status"] == "plausible")
    v = P.load_json(vrep)
    summary["validate_clip"] = {"result": v.get("result"), "fails": v.get("fails"), "warnings": v.get("warnings"),
                                "checks": {c["check"]: c["status"] for c in v.get("checks", [])}}
    P.write_json(paths["reports"] / "probe-report.json", {"schema": "unmatched.h2-bake.probe/1", "timing_s": out,
                                                          "summary": summary})
    return out


def baseline_dir(profile, paths, base, name):
    """Runtime 2K textures of a committed baseline (git show <commit>:<runtime_2k file>, sha256 checked) ->
    work/<name>/ (kept between runs)."""
    prefix = profile["textures"]["prefix"]
    bdir = paths["work"] / name
    bdir.mkdir(parents=True, exist_ok=True)
    for key, sha in base["runtime_2k_sha256"].items():
        f = bdir / ("%s_%s.png" % (prefix, key))
        if not f.exists() or P.sha256(f) != sha:
            src = "%s:%s" % (base["commit"], P.rel(paths["textures"] / "runtime_2k" / f.name))
            f.write_bytes(subprocess.run(["git", "-C", str(P.REPO), "show", src], capture_output=True, check=True,
                                         creationflags=NO_WINDOW).stdout)
        if P.sha256(f) != sha:
            raise SystemExit("baseline texture %s: sha256 %s, expected %s" % (f, P.sha256(f), sha))
    return bdir


def stage_compare(profile, paths, logs):
    """H2.1 before/after frames (stage_compare.py): the H2 runtime textures of the baseline commit (git show, sha256
    checked against review_h21.baseline) and the H2.1 runtime textures on the same mesh, light and cameras; the
    H2 review light for a few views; the material class raster flat on the mesh. Raw PNG -> work/h21_png/.
    The H2.1 set is the current runtime textures until H2.2, then the committed H2.1 baseline (review_h22)."""
    rc = profile["review_h21"]
    bdir = baseline_dir(profile, paths, rc["baseline"], "h2-baseline-runtime-2k")
    out = paths["work"] / "h21_png"
    cur = (baseline_dir(profile, paths, profile["review_h22"]["baseline_h21"], "h21-baseline-runtime-2k")
           if "review_h22" in profile else paths["textures"] / "runtime_2k")
    script = HERE / "stage_compare.py"
    sets = ["--set", "h2=%s" % bdir, "--set", "h21=%s" % cur]
    t = {"studio_env": run(blender(script, profile["_path"], paths["run"], out / "studio_env", *sets, "--light", "studio_env"),
                           logs / "compare-studio_env.log", P.STAGE_MARKER),
         "studio": run(blender(script, profile["_path"], paths["run"], out / "studio", *sets, "--light", "studio",
                               "--views", ",".join(rc["studio_views"])), logs / "compare-studio.log", P.STAGE_MARKER),
         "classes": run(blender(script, profile["_path"], paths["run"], out / "classes", "--set", "classes=%s" % cur,
                                "--debug-bc", paths["work"] / "materials-classes-2k.png", "--views",
                                ",".join(rc["classes_views"])), logs / "compare-classes.log", P.STAGE_MARKER)}
    return t


def stage_compare_h22(profile, paths, logs):
    """H2.2 frames (stage_compare.py): H2 (9a2a5184), H2.1 (review_h22.baseline_h21) and the current runtime textures on
    the same mesh, light and cameras: studio_env (the H2.1 comparison light) for the ortho / K2 / close-up views, the
    Cobble-light approximation for review_h22.cobble_views, the class raster (plate steel / blade steel separated) for
    the steel masks. Raw PNG -> work/h22_png/."""
    rc = profile["review_h22"]
    h2 = baseline_dir(profile, paths, profile["review_h21"]["baseline"], "h2-baseline-runtime-2k")
    h21 = baseline_dir(profile, paths, rc["baseline_h21"], "h21-baseline-runtime-2k")
    cur = paths["textures"] / "runtime_2k"
    out = paths["work"] / "h22_png"
    script = HERE / "stage_compare.py"
    sets = ["--set", "h2=%s" % h2, "--set", "h21=%s" % h21, "--set", "h22=%s" % cur]
    return {"studio_env": run(blender(script, profile["_path"], paths["run"], out / "studio_env", *sets, "--light",
                                      "studio_env", "--views", ",".join(rc["studio_env_views"])),
                              logs / "compare_h22-studio_env.log", P.STAGE_MARKER),
            "cobble": run(blender(script, profile["_path"], paths["run"], out / "cobble", *sets, "--light", "cobble",
                                  "--views", ",".join(rc["cobble_views"])), logs / "compare_h22-cobble.log", P.STAGE_MARKER),
            "classes": run(blender(script, profile["_path"], paths["run"], out / "classes", "--set", "classes=%s" % cur,
                                   "--debug-bc", paths["work"] / "materials-classes-2k.png", "--views",
                                   ",".join(rc["classes_views"])), logs / "compare_h22-classes.log", P.STAGE_MARKER)}


def stage_manifest(profile, paths):
    files = []
    for sub in ("export", "textures", "reports", "preview"):
        for f in sorted((paths["run"] / sub).rglob("*")):
            if f.is_file():
                files.append({"file": P.rel(f), "sha256": P.sha256(f), "bytes": f.stat().st_size})
    P.write_json(paths["reports"] / "manifest-h2.json", {"schema": "unmatched.h2-bake.manifest/1",
                                                         "profile": P.rel(Path(profile["_path"])),
                                                         "profile_sha256": P.sha256(profile["_path"]),
                                                         "files": [f for f in files if not f["file"].endswith("manifest-h2.json")]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--stages", default=",".join(s for s in ORDER if s not in DEFAULT_SKIP))
    ap.add_argument("--from", dest="from_stage")
    a = ap.parse_args()
    profile_path = Path(a.profile).resolve()
    profile = P.load_json(profile_path)
    profile["_path"] = str(profile_path)
    paths = P.run_paths(a.run_dir)
    for k in ("logs", "reports", "work", "export", "textures", "preview"):
        paths[k].mkdir(parents=True, exist_ok=True)
    stages = [s for s in ORDER if s in a.stages.split(",")]
    if a.from_stage:
        stages = stages[stages.index(a.from_stage):]
    timing = {}
    for st in stages:
        log = paths["logs"] / ("%s.log" % st)
        if st in BLENDER_STAGES:
            timing[st] = run(blender(HERE / BLENDER_STAGES[st], profile_path, paths["run"], threads=STAGE_THREADS.get(st)),
                             log, P.STAGE_MARKER)
        elif st in PY_STAGES:
            timing[st] = run([sys.executable, str(HERE / PY_STAGES[st]), str(profile_path), str(paths["run"])], log,
                             P.STAGE_MARKER)
        elif st == "probe":
            timing[st] = stage_probe(profile, paths, paths["logs"])
        elif st == "compare":
            timing[st] = stage_compare(profile, paths, paths["logs"])
        elif st == "compare_h22":
            timing[st] = stage_compare_h22(profile, paths, paths["logs"])
        elif st == "manifest":
            stage_manifest(profile, paths)
        print("stage", st, timing.get(st), flush=True)
    print(json.dumps(timing))


if __name__ == "__main__":
    main()
