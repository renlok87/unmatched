"""Driver of the H2 bake (plain Python 3.10+, numpy + Pillow, scipy for the H2.1 material pass; Blender 5.2 headless
for the Blender stages).

  python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py \
      --profile art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json \
      --run-dir art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake [--stages all|a,b,...] \
      [--blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"] [--compare-with <another run dir>]

Stages: prepare retopo close uv bake aux textures rig probes seams preview compose manifest (`all`); optional: curve (the
exploratory triangles -> deviation curve, reports/decimation-curve.json; run it with --stages curve). Every Blender stage is a separate
`blender -b --factory-startup --python-exit-code 1` process (no live Blender, no network, no paid Tripo call).
Tripo sources are only read (sha256 checked by prepare). The run directory gets export/, textures/, preview/,
reports/ (all deterministic) and work/ (blend files, npy composites, raw frames: not for git).
--compare-with: byte comparison of every output with another run of the same profile (reports/determinism-report.json).

Look-dev mode (material library v1 on a finished H2.1 run; lookdev.py, st_lookdev.py):
  python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --mode lookdev       --profile art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-lookdev.json       --run-dir art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev [--stages ld_maps,ld_fbx,...]
Stages: ld_maps ld_fbx ld_preview ld_measure ld_compose ld_manifest (`all`). The source run is only read (sha256 pins).

TeamAccent mode (team-accent.md: team colour on accents, not on the whole dress; lookdev_accent.py, st_team.py):
  python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --mode teamaccent       --profile art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-lookdev-teamaccent.json       --run-dir art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev [--stages ta_maps,...]
Stages: ta_maps ta_render ta_report ta_manifest (`all`). The look-dev run and its profile are only read (sha256 pins);
new files only (textures/<prefix>_TeamAccent_{2K,4K}.png, reports/ld-team-*.json, preview/ld_team_*).
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
ORDER = ["prepare", "retopo", "close", "uv", "bake", "aux", "textures", "rig", "probes", "seams", "preview", "compose", "manifest"]
OPTIONAL = ["curve"]  # not in `all`
BLENDER_STAGES = {"prepare", "retopo", "close", "uv", "bake", "aux", "rig", "seams", "preview", "curve"}
SCHEMA = "unmatched.h2-bake-run/1"
LD_ORDER = ["ld_maps", "ld_fbx", "ld_preview", "ld_measure", "ld_compose", "ld_manifest"]
LD_BLENDER = {"ld_fbx", "ld_preview"}
LD_SCHEMA = "unmatched.h2-lookdev-run/1"
TA_ORDER = ["ta_maps", "ta_render", "ta_report", "ta_manifest"]
TA_BLENDER = {"ta_render"}


def load_local(name):
    spec = importlib.util.spec_from_file_location("h2_" + name, HERE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def rel(path):
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()


def blender(exe, script, args, log):
    cmd = [exe, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(script), "--"] + [str(a) for a in args]
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise RuntimeError("blender failed (%d): %s — see %s" % (proc.returncode, " ".join(cmd[-3:]), log))


def blender_stage(exe, stage, profile_path, run_dir):
    params = {"stage": stage, "profile": str(Path(profile_path).resolve()), "run_dir": str(Path(run_dir).resolve()),
              "repo_root": str(REPO)}
    pfile = run_dir / "work" / "params" / ("%s.json" % stage)
    pfile.parent.mkdir(parents=True, exist_ok=True)
    pfile.write_text(json.dumps(params, indent=2), encoding="utf-8")
    blender(exe, HERE / "blender_entry.py", [pfile], run_dir / "logs" / ("%s.log" % stage))


def probes(exe, profile, run_dir):
    anim = REPO / "tools" / "tripo-pipeline" / "anim"
    work = run_dir / "work"
    deform = work / "deform"
    if deform.exists():
        shutil.rmtree(deform)
    deform.mkdir(parents=True)
    sk = run_dir / "export" / profile["exports"]["skeletal_fbx"]
    fbx_blend = work / "probe-fbx-authored.blend"
    blender(exe, HERE / "fbx_authored.py", [sk, fbx_blend], run_dir / "logs" / "probe-fbx-authored.log")
    results = {}
    for src, label in ((work / "sk_authored.blend", "medusa-h2-blend"), (fbx_blend, "medusa-h2-fbx")):
        blender(exe, anim / "rig_deform_probe.py", [src, deform, label], run_dir / "logs" / ("probe-%s.log" % label))
        subprocess.run([sys.executable, str(anim / "overlay_bones.py"), str(deform), label], check=True,
                       stdout=subprocess.DEVNULL)
        data = json.loads((deform / ("%s-deform.json" % label)).read_text(encoding="utf-8"))
        data["source"] = "<run>/work/%s" % Path(src).name  # the probe writes an absolute path outside the repo
        out = run_dir / "reports" / "deform" / ("%s-deform.json" % label)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        results[label] = {t["test"]: t["status"] for t in data["tests"]}
    vout = run_dir / "reports" / "validate-skeletal-mesh-v2.json"
    blender(exe, anim / "validate_clip.py", [sk, "--kind=skeletal-mesh", "--character=%s" % profile["rig"]["character"],
                                             "--skeleton=%s" % profile["rig"]["skeleton"], "--out=%s" % vout],
            run_dir / "logs" / "validate-skeletal-mesh.log")
    v = json.loads(vout.read_text(encoding="utf-8"))
    for key in ("clip", "source", "file", "path"):
        if isinstance(v.get(key), str):
            v[key] = "<run>/export/%s" % Path(v[key]).name  # a second run elsewhere writes another path
    vout.write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    plausible = {k: sum(1 for s in r.values() if s == "plausible") for k, r in results.items()}
    summary = {"stage": "probes", "rig_deform_probe": results, "plausible": plausible,
               "validate_clip_v2": {"result": v.get("result"), "fails": v.get("fails"), "warnings": v.get("warnings")},
               "passed": all(n == 7 for n in plausible.values()) and v.get("result") == "pass", "status": "измерено"}
    (run_dir / "reports" / "probes-report.json").write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                                            encoding="utf-8")
    if not summary["passed"]:
        raise RuntimeError("probes failed: %s" % summary)


OUTPUT_DIRS = ("export", "textures", "preview", "reports")
NOT_COMPARED = {"reports/run-manifest.json", "reports/determinism-report.json"}


def outputs(run_dir):
    out = {}
    for d in OUTPUT_DIRS:
        for p in sorted((run_dir / d).rglob("*")):
            if p.is_file():
                out[p.relative_to(run_dir).as_posix()] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    return out


def normalised_json(path, run_dir):
    text = path.read_text(encoding="utf-8")
    for token in (rel(run_dir), str(Path(run_dir).resolve()).replace("\\", "/"), str(Path(run_dir).resolve())):
        text = text.replace(token, "<run>")
    return text


def compare(run_dir, other):
    a, b = outputs(run_dir), outputs(other)
    rows = {}
    for k in sorted(set(a) | set(b)):
        if k in NOT_COMPARED:
            continue
        if k not in a or k not in b:
            rows[k] = {"result": "missing in " + ("this run" if k not in a else "other run")}
            continue
        if a[k]["sha256"] == b[k]["sha256"]:
            rows[k] = {"result": "identical"}
            continue
        item = {"result": "different", "sha256": [a[k]["sha256"], b[k]["sha256"]]}
        if k.endswith(".json") and normalised_json(run_dir / k, run_dir) == normalised_json(other / k, other):
            item["result"] = "identical after run-path normalisation"
        elif k.endswith(".png"):
            import numpy as np
            from PIL import Image
            x = np.asarray(Image.open(run_dir / k)).astype(np.int16)
            y = np.asarray(Image.open(other / k)).astype(np.int16)
            if x.shape == y.shape:
                diff = np.abs(x - y)
                item.update({"differing_values": int((diff > 0).sum()), "max_abs_diff": int(diff.max()),
                             "differing_pixels": int((diff.reshape(diff.shape[0], diff.shape[1], -1).max(-1) > 0).sum())})
        rows[k] = item
    summary = {}
    for v in rows.values():
        summary[v["result"]] = summary.get(v["result"], 0) + 1
    return {"schema": "unmatched.h2-bake-determinism/1", "this_run": rel(run_dir), "other_run": rel(other),
            "summary": summary, "files": rows}


def run_lookdev(a):
    """--mode lookdev: stages of lookdev.py (plain Python) and st_lookdev.py (Blender)."""
    run_dir = Path(a.run_dir).resolve()
    for d in ("work", "logs", "reports", "export", "textures", "preview"):
        (run_dir / d).mkdir(parents=True, exist_ok=True)
    ld = json.loads(Path(a.profile).read_text(encoding="utf-8"))
    if ld.get("schema") != "unmatched.h2-lookdev-profile/1":
        raise ValueError("--mode lookdev needs a unmatched.h2-lookdev-profile/1 profile")
    src_profile = REPO / ld["source"]["profile"]
    profile = load_local("profile").load(src_profile)
    lookdev = load_local("lookdev")
    stages = LD_ORDER if a.stages == "all" else [s for s in LD_ORDER if s in a.stages.split(",")]
    timings = {}
    for stage in stages:
        t0 = time.time()
        print("[h2-lookdev] %s ..." % stage, flush=True)
        if stage in LD_BLENDER:
            params = {"stage": stage, "profile": str(src_profile), "lookdev": str(Path(a.profile).resolve()),
                      "run_dir": str(run_dir), "repo_root": str(REPO), "run_rel": rel(run_dir)}
            pfile = run_dir / "work" / "params" / ("%s.json" % stage)
            pfile.parent.mkdir(parents=True, exist_ok=True)
            pfile.write_text(json.dumps(params, indent=2), encoding="utf-8")
            blender(a.blender, HERE / "blender_entry.py", [pfile], run_dir / "logs" / ("%s.log" % stage))
        elif stage == "ld_maps":
            lookdev.run_maps(run_dir, ld, REPO)
        elif stage == "ld_measure":
            lookdev.run_measure(run_dir, ld, REPO)
        elif stage == "ld_compose":
            lookdev.run_compose(run_dir, ld, REPO)
        elif stage == "ld_manifest":
            ver = subprocess.run([a.blender, "-b", "--factory-startup", "--version"], capture_output=True, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.splitlines()
            lib = REPO / "tools" / "art" / "material_library" / "build_ue_inputs.py"
            manifest = {"schema": LD_SCHEMA, "tool": load_local("__init__").VERSION, "asset_id": ld["asset_id"],
                        "profile": {"path": rel(a.profile), "sha256": sha256(a.profile), "profile_id": ld["profile_id"]},
                        "source_profile": {"path": rel(src_profile), "sha256": sha256(src_profile)},
                        "source_run": {"path": ld["source"]["run"], "pinned_sha256": ld["source"]["sha256"]},
                        "blender": next((l.strip() for l in ver if l.startswith("Blender")), None),
                        "modules": dict({p.name: sha256(p) for p in sorted(HERE.glob("*.py"))}, **{rel(lib): sha256(lib)}),
                        "material_library": {rel(REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json"):
                                             sha256(REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json")},
                        "outputs": {k: v for k, v in outputs(run_dir).items() if k not in NOT_COMPARED},
                        "network": {"tripo_calls": 0, "paid_tasks_created": 0},
                        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
                        "status": "измерено"}
            (run_dir / "reports" / "run-manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        timings[stage] = round(time.time() - t0, 1)
        print("[h2-lookdev] %s done in %.1f s" % (stage, timings[stage]), flush=True)
    (run_dir / "work" / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    if a.compare_with:
        rep = compare(run_dir, Path(a.compare_with).resolve())
        (run_dir / "reports" / "determinism-report.json").write_text(
            json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print("[h2-lookdev] determinism:", rep["summary"], flush=True)


def run_teamaccent(a):
    """--mode teamaccent: stages of lookdev_accent.py (plain Python) and st_team.py (Blender)."""
    run_dir = Path(a.run_dir).resolve()
    for d in ("work", "logs", "reports", "textures", "preview"):
        (run_dir / d).mkdir(parents=True, exist_ok=True)
    ta = json.loads(Path(a.profile).read_text(encoding="utf-8"))
    if ta.get("schema") != "unmatched.h2-lookdev-teamaccent-profile/1":
        raise ValueError("--mode teamaccent needs a unmatched.h2-lookdev-teamaccent-profile/1 profile")
    ld = json.loads((REPO / ta["lookdev_profile"]["path"]).read_text(encoding="utf-8"))
    src_profile = REPO / ld["source"]["profile"]
    acc = load_local("lookdev_accent")
    stages = TA_ORDER if a.stages == "all" else [s for s in TA_ORDER if s in a.stages.split(",")]
    timings = {}
    for stage in stages:
        t0 = time.time()
        print("[h2-teamaccent] %s ..." % stage, flush=True)
        if stage in TA_BLENDER:
            params = {"stage": stage, "profile": str(src_profile), "teamaccent": str(Path(a.profile).resolve()),
                      "run_dir": str(run_dir), "repo_root": str(REPO), "run_rel": rel(run_dir)}
            pfile = run_dir / "work" / "params" / ("%s.json" % stage)
            pfile.parent.mkdir(parents=True, exist_ok=True)
            pfile.write_text(json.dumps(params, indent=2), encoding="utf-8")
            blender(a.blender, HERE / "blender_entry.py", [pfile], run_dir / "logs" / ("%s.log" % stage))
        elif stage == "ta_maps":
            acc.run_maps(run_dir, ta, REPO)
        elif stage == "ta_report":
            acc.run_report(run_dir, ta, REPO)
        elif stage == "ta_manifest":
            ver = subprocess.run([a.blender, "-b", "--factory-startup", "--version"], capture_output=True, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.splitlines()
            acc.run_manifest(run_dir, ta, Path(a.profile).resolve(), REPO,
                             next((l.strip() for l in ver if l.startswith("Blender")), None))
        timings[stage] = round(time.time() - t0, 1)
        print("[h2-teamaccent] %s done in %.1f s" % (stage, timings[stage]), flush=True)
    (run_dir / "work" / "ta").mkdir(parents=True, exist_ok=True)
    (run_dir / "work" / "ta" / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--stages", default="all")
    ap.add_argument("--blender", default=os.environ.get("H2_BAKE_BLENDER", DEFAULT_BLENDER))
    ap.add_argument("--compare-with")
    ap.add_argument("--mode", choices=("h2", "lookdev", "teamaccent"), default="h2")
    a = ap.parse_args()
    if a.mode == "lookdev":
        return run_lookdev(a)
    if a.mode == "teamaccent":
        return run_teamaccent(a)
    run_dir = Path(a.run_dir).resolve()
    for d in ("work", "logs", "reports", "export", "textures", "preview"):
        (run_dir / d).mkdir(parents=True, exist_ok=True)
    prof_mod = load_local("profile")
    profile = prof_mod.load(a.profile)
    stages = ORDER if a.stages == "all" else [s for s in ORDER + OPTIONAL if s in a.stages.split(",")]
    timings = {}
    for stage in stages:
        t0 = time.time()
        print("[h2-bake] %s ..." % stage, flush=True)
        if stage in BLENDER_STAGES:
            blender_stage(a.blender, stage, a.profile, run_dir)
        elif stage == "textures":
            load_local("textures").run(run_dir, profile)
        elif stage == "probes":
            probes(a.blender, profile, run_dir)
        elif stage == "compose":
            load_local("compose").run(run_dir, profile, REPO)
        elif stage == "manifest":
            ver = subprocess.run([a.blender, "-b", "--factory-startup", "--version"], capture_output=True, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.splitlines()
            modules = {p.name: sha256(p) for p in sorted(HERE.glob("*.py"))}
            core = REPO / "tools" / "tripo-pipeline" / "blender" / "candidate_build"
            manifest = {"schema": SCHEMA, "tool": load_local("__init__").VERSION, "asset_id": profile["asset_id"],
                        "profile": {"path": rel(a.profile), "sha256": sha256(a.profile), "profile_id": profile["profile_id"]},
                        "blender": next((l.strip() for l in ver if l.startswith("Blender")), None),
                        "modules": modules,
                        "read_only_dependencies": {rel(p): sha256(p) for p in (core / "core.py", core / "measure.py", core / "closure.py",
                                                                               REPO / profile["exports"]["fbx_preset"])},
                        "sources": {k: {"path": v["path"], "sha256": v["sha256"], "bytes": v["bytes"], "in_git": False}
                                    for k, v in profile["sources"].items() if isinstance(v, dict)},
                        "outputs": {k: v for k, v in outputs(run_dir).items() if k not in NOT_COMPARED},
                        "network": {"tripo_calls": 0, "paid_tasks_created": 0},
                        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
                        "status": "измерено"}
            (run_dir / "reports" / "run-manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        timings[stage] = round(time.time() - t0, 1)
        print("[h2-bake] %s done in %.1f s" % (stage, timings[stage]), flush=True)
    (run_dir / "work" / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    if a.compare_with:
        rep = compare(run_dir, Path(a.compare_with).resolve())
        (run_dir / "reports" / "determinism-report.json").write_text(
            json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print("[h2-bake] determinism:", rep["summary"], flush=True)


if __name__ == "__main__":
    main()
