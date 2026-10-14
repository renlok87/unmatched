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
--compare-with: determinism verdict against another run of the same profile (determinism.py: tolerance table, scope)
  -> reports/determinism-report.json; exit code 1 and the list of failures when a file is outside its tolerance.
--reuse-from <old run> [--reuse-allow-code-drift] (h2 mode, new empty --run-dir, --stages all; reuse.py): stages whose
  profile blocks, input files, Blender and code equal those of the old run are taken over (work/ files hard-linked,
  reports copied with `reused_from`); recomputation starts at the first stage that differs. Plan: work/reuse-plan.json.
Every h2 stage records its fingerprint in work/stages.json (the stage ledger, reuse.py); the manifest copies it.

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


def probe_counts(data, extended_gate=True):
    """Gate of one rig_deform_probe report (RB-08, W1-e). extended_gate (profile_version >= 2, a new hero): n/N of its
    `probes` block — the 7 legacy and the extended probes, skipped ones out of N. Otherwise (profile_version 1: Medusa
    and the pilot, whose committed profiles do not change) only the 7 legacy tests gate; the extended ones are counted
    (`summary`) and a failed one is a warning (`extended_failed`). A report without the block (probe older than the
    extended tests): the 7 legacy tests."""
    n7 = sum(1 for t in data["tests"] if t.get("status") == "plausible")
    pb = data.get("probes")
    full = pb if isinstance(pb, dict) and "total" in pb else None
    failed = [t["test"] for t in data.get("extended_tests", []) if t.get("status") not in ("plausible", "skipped")]
    if extended_gate and full:
        out = {"plausible": int(full["plausible"]), "total": int(full["total"]), "passed": bool(full.get("passed")),
               "gate": "legacy + extended"}
    else:
        out = {"plausible": n7, "total": 7, "passed": n7 == 7, "gate": "legacy 7"}
    out.update(summary=full.get("summary") if full else "%d/7" % n7, extended_failed=failed)
    return out


def probe_verdict(datas, profile, skip, validate):
    """probes-report.json of the probes stage: datas = {label: rig_deform_probe report}, validate = validate_clip v2
    report. plausible / total = the gating n/N per label (validate_card G-RIG compares them), probes = n/N of every
    probe, extended_warnings = failed extended probes that do not gate (profile_version 1)."""
    gate_ext = load_local("profile").is_new_hero_profile(profile)
    counts = {k: probe_counts(d, gate_ext) for k, d in datas.items()}
    results = {k: {t["test"]: t["status"] for t in d["tests"] + d.get("extended_tests", [])} for k, d in datas.items()}
    out = {"stage": "probes", "rig_deform_probe": results,
           "plausible": {k: c["plausible"] for k, c in counts.items()}, "total": {k: c["total"] for k, c in counts.items()},
           "probes": {k: c["summary"] for k, c in counts.items()}, "skipped": skip,
           "gate": "legacy + extended (profile_version >= 2)" if gate_ext else "legacy 7 (profile_version 1)",
           "validate_clip_v2": {"result": validate.get("result"), "fails": validate.get("fails"),
                                "warnings": validate.get("warnings")},
           "passed": all(c["passed"] for c in counts.values()) and validate.get("result") == "pass", "status": "измерено"}
    warn = {k: c["extended_failed"] for k, c in counts.items() if c["extended_failed"] and not gate_ext}
    if warn:
        out["extended_warnings"] = warn
    return out


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
    datas = {}
    prof_mod = load_local("profile")
    key = prof_mod.content_key(profile)  # ASSET-MEDUSA-001 -> medusa (labels medusa-h2-blend / -fbx as before)
    skip = prof_mod.probe_skip(profile)  # rig.probe_skip: extended probes out of N (Leshen: shins, feet)
    extra = ["--skip=%s" % ",".join(skip)] if skip else []
    for src, label in ((work / "sk_authored.blend", "%s-h2-blend" % key), (fbx_blend, "%s-h2-fbx" % key)):
        blender(exe, anim / "rig_deform_probe.py", [src, deform, label] + extra, run_dir / "logs" / ("probe-%s.log" % label))
        subprocess.run([sys.executable, str(anim / "overlay_bones.py"), str(deform), label], check=True,
                       stdout=subprocess.DEVNULL)
        data = json.loads((deform / ("%s-deform.json" % label)).read_text(encoding="utf-8"))
        data["source"] = "<run>/work/%s" % Path(src).name  # the probe writes an absolute path outside the repo
        out = run_dir / "reports" / "deform" / ("%s-deform.json" % label)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        datas[label] = data
    vout = run_dir / "reports" / "validate-skeletal-mesh-v2.json"
    blender(exe, anim / "validate_clip.py", [sk, "--kind=skeletal-mesh", "--character=%s" % profile["rig"]["character"],
                                             "--skeleton=%s" % profile["rig"]["skeleton"], "--out=%s" % vout],
            run_dir / "logs" / "validate-skeletal-mesh.log")
    v = json.loads(vout.read_text(encoding="utf-8"))
    for key in ("clip", "source", "file", "path"):
        if isinstance(v.get(key), str):
            v[key] = "<run>/export/%s" % Path(v[key]).name  # a second run elsewhere writes another path
    vout.write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary = probe_verdict(datas, profile, skip, v)
    if summary.get("extended_warnings"):
        print("[h2-bake] WARN probes: extended probes failed, not gating (profile_version 1): %s"
              % summary["extended_warnings"], flush=True)
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


def reused_stages(run_dir):
    """{stage: source run} of the stages a run took over with --reuse-from (its stage ledger; {} for a full run)."""
    try:
        ledger = load_local("reuse").load_ledger(run_dir)
    except (RuntimeError, ValueError):
        return {}
    if not ledger:
        return {}
    return {s: (e.get("reused_from") or {}).get("run") for s, e in ledger["stages"].items() if e.get("reused_from")}


def determinism(run_dir, other, tag, h2=True):
    """--compare-with: writes reports/determinism-report.json into run_dir, prints the verdict; -> exit code."""
    det, reuse = load_local("determinism"), load_local("reuse")
    other = Path(other).resolve()
    stage_of = (lambda r: reuse.owner(r) or None) if h2 else None
    rep = det.compare(run_dir, other, REPO, stage_of=stage_of,
                      reuse_a=reused_stages(run_dir) if h2 else None, reuse_b=reused_stages(other) if h2 else None)
    (run_dir / "reports" / "determinism-report.json").write_text(
        json.dumps(rep, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    det.print_verdict(rep, tag, lambda s: print(s, flush=True))
    return 1 if rep["verdict"] != "pass" else 0


def blender_version(exe):
    ver = subprocess.run([exe, "-b", "--factory-startup", "--version"], capture_output=True, text=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.splitlines()
    return next((l.strip() for l in ver if l.startswith("Blender")), None)


def merge_timings(path, timings):
    """work/timings.json keeps the stages of earlier invocations (stages run one by one, F87)."""
    old = {}
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
    old.update(timings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(old, indent=2), encoding="utf-8")


def run_lookdev(a):
    """--mode lookdev: stages of lookdev.py (plain Python) and st_lookdev.py (Blender)."""
    run_dir = Path(a.run_dir).resolve()
    for d in ("work", "logs", "reports", "export", "textures", "preview"):
        (run_dir / d).mkdir(parents=True, exist_ok=True)
    ld = json.loads(Path(a.profile).read_text(encoding="utf-8"))
    if ld.get("schema") != "unmatched.h2-lookdev-profile/1":
        raise ValueError("--mode lookdev needs a unmatched.h2-lookdev-profile/1 profile")
    src_profile = REPO / ld["source"]["profile"]
    prof_mod = load_local("profile")
    profile = prof_mod.load(src_profile)
    if prof_mod.is_new_hero_profile(profile) and ld.get("frame") is None:  # RB-15: no silent Medusa canon for a new hero
        raise ValueError("look-dev profile %s: a new hero (source profile_version %s) needs a top-level `frame` "
                         "{\"checks_report\": \"art/imagegen/concept-<key>-codex/checks-report.json\", \"side\": "
                         "\"<SIDE_VIEW>\"}; without it ld_preview / ld_measure use the Medusa canon 1021 x 1540 "
                         "(framing.py, HANDBOOK §4.4)" % (a.profile, prof_mod.profile_version(profile)))
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
    merge_timings(run_dir / "work" / "timings.json", timings)
    if a.compare_with:
        return determinism(run_dir, a.compare_with, "h2-lookdev", h2=False)
    return 0


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
    merge_timings(run_dir / "work" / "ta" / "timings.json", timings)
    if a.compare_with:
        return determinism(run_dir, a.compare_with, "h2-teamaccent", h2=False)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--stages", default="all")
    ap.add_argument("--blender", default=os.environ.get("H2_BAKE_BLENDER", DEFAULT_BLENDER))
    ap.add_argument("--compare-with")
    ap.add_argument("--mode", choices=("h2", "lookdev", "teamaccent"), default="h2")
    ap.add_argument("--reuse-from", help="h2 mode: earlier run of this hero; unchanged stages are taken over (reuse.py)")
    ap.add_argument("--reuse-allow-code-drift", action="store_true",
                    help="reuse stages whose code changed since the old run (then the full determinism repeat is required)")
    a = ap.parse_args()
    if a.mode == "lookdev":
        return run_lookdev(a)
    if a.mode == "teamaccent":
        return run_teamaccent(a)
    run_dir = Path(a.run_dir).resolve()
    prof_mod = load_local("profile")
    reuse = load_local("reuse")
    profile = prof_mod.load(a.profile)
    profile_rel, profile_sha = rel(a.profile), sha256(a.profile)
    bver_cache = []

    def bver():
        if not bver_cache:
            bver_cache.append(blender_version(a.blender))
        return bver_cache[0]

    stages = ORDER if a.stages == "all" else [s for s in ORDER + OPTIONAL if s in a.stages.split(",")]
    plan = None
    if a.reuse_from:
        source = Path(a.reuse_from).resolve()
        if a.stages != "all":
            raise SystemExit("--reuse-from builds a complete run: use it with --stages all")
        if source == run_dir:
            raise SystemExit("--reuse-from: the old run and --run-dir are the same directory")
        if run_dir.exists() and any(p.is_file() for p in run_dir.rglob("*")):
            raise SystemExit("--reuse-from needs a new, empty --run-dir (%s has files)" % run_dir)
        plan = reuse.plan(source, profile, REPO, bver(), prof_mod.load, a.reuse_allow_code_drift)
        reuse.print_plan(plan, lambda s: print(s, flush=True))
    for d in ("work", "logs", "reports", "export", "textures", "preview"):
        (run_dir / d).mkdir(parents=True, exist_ok=True)
    timings = {}
    if plan is not None:
        t0 = time.time()
        carried = reuse.apply(plan, run_dir, REPO)
        src_rel = rel(plan["source"])
        for row in plan["stages"]:
            if row["action"] == "reuse":  # the old fingerprint: the outputs were made with the old code (drift stays visible)
                reuse.record(run_dir, row["stage"], row["old_fingerprint"], profile_rel, profile_sha, 0.0,
                             reused_from={"run": src_rel, "evidence": plan["evidence"], "code_drift": row.get("code_drift") or []})
        timings["reuse_apply"] = round(time.time() - t0, 1)
        (run_dir / "work" / "reuse-plan.json").write_text(json.dumps(
            dict(plan, source=src_rel, carried=carried, seconds=timings["reuse_apply"]), indent=1, ensure_ascii=False,
            sort_keys=True) + "\n", encoding="utf-8")
        print("[h2-bake] reused %s in %.1f s: %d links (%.2f GB), %d reports, %d copies, %d unowned copied%s" % (
            ", ".join(plan["reused"]) or "nothing", timings["reuse_apply"], carried["link"], carried["linked_bytes"] / 1e9,
            carried["report"], carried["copy"], carried["unowned_copied"],
            (" (%s)" % ", ".join(carried["unowned"][:8])) if carried["unowned"] else ""), flush=True)
        stages = [s for s in stages if s in plan["recomputed"]]
    for stage in stages:
        t0 = time.time()
        print("[h2-bake] %s ..." % stage, flush=True)
        if stage in reuse.REUSABLE:
            reuse.invalidate_from(run_dir, stage)
            n = reuse.unshare(run_dir, stage)
            if n:
                print("[h2-bake]   %d hard links of %s unlinked before the stage writes" % (n, stage), flush=True)
        links = reuse.snapshot_links(run_dir)
        if stage in BLENDER_STAGES:
            blender_stage(a.blender, stage, a.profile, run_dir)
        elif stage == "textures":
            load_local("textures").run(run_dir, profile)
        elif stage == "probes":
            probes(a.blender, profile, run_dir)
        elif stage == "compose":
            load_local("compose").run(run_dir, profile, REPO)
        elif stage == "manifest":
            modules = {p.name: sha256(p) for p in sorted(HERE.glob("*.py"))}
            core = REPO / "tools" / "tripo-pipeline" / "blender" / "candidate_build"
            manifest = {"schema": SCHEMA, "tool": load_local("__init__").VERSION, "asset_id": profile["asset_id"],
                        "profile": {"path": rel(a.profile), "sha256": sha256(a.profile), "profile_id": profile["profile_id"]},
                        "blender": bver(),
                        "stages": stage_block(reuse, run_dir, profile, bver),
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
            if manifest["stages"] and manifest["stages"]["stale"]:
                print("[h2-bake] WARNING stages built from other profile blocks / inputs than the current profile: %s"
                      % manifest["stages"]["stale"], flush=True)
            if manifest["stages"] and manifest["stages"]["code_drift"]:
                print("[h2-bake] note: stages built by other code than this checkout (full determinism repeat "
                      "decides): %s" % manifest["stages"]["code_drift"], flush=True)
        reuse.check_links(run_dir, links, stage)
        timings[stage] = round(time.time() - t0, 1)
        if stage in reuse.REUSABLE:
            spec = reuse.STAGE_INPUTS[stage]
            reuse.record(run_dir, stage, reuse.fingerprint(stage, profile, REPO, bver() if spec.get("blender") else None),
                         profile_rel, profile_sha, timings[stage])
        print("[h2-bake] %s done in %.1f s" % (stage, timings[stage]), flush=True)
    merge_timings(run_dir / "work" / "timings.json", timings)
    if a.compare_with:
        return determinism(run_dir, a.compare_with, "h2-bake")
    return 0


def stage_block(reuse, run_dir, profile, bver):
    """run-manifest.json#stages: the stage ledger (fingerprint chain, reuse, wall time) and the stages whose recorded
    fingerprint differs from the current profile / inputs (`stale`: run again or start a new run). None without a
    ledger (a run made before h2-bake 0.7.0, re-manifested)."""
    ledger = reuse.load_ledger(run_dir)
    if not ledger:
        return None
    fps = {s: e["fingerprint"] for s, e in ledger["stages"].items() if s in reuse.REUSABLE}
    chain = reuse.chain(fps)
    stale, code_drift = {}, {}
    for s, fp in fps.items():
        spec = reuse.STAGE_INPUTS[s]
        changes, drift = reuse.differences(reuse.fingerprint(s, profile, REPO, bver() if spec.get("blender") else None), fp)
        if changes:
            stale[s] = changes
        if drift:
            code_drift[s] = drift
    plan = run_dir / "work" / "reuse-plan.json"
    reuse_info = None
    if plan.is_file():
        p = json.loads(plan.read_text(encoding="utf-8"))
        reuse_info = {"from": p["source"], "evidence": p["evidence"], "reused": p["reused"],
                      "recomputed": p["recomputed"], "code_drift": p["code_drift"],
                      "determinism": "full repeat required (scope full) — code drift in reused stages" if p["code_drift"]
                      else "the run that goes to UE needs the full repeat; otherwise repeat the recomputed stages"}
    return {"ledger": "work/stages.json", "order": [s for s in reuse.REUSABLE if s in fps],
            "per_stage": {s: {"chain_sha256": chain[s], "profile_keys": sorted(fps[s]["profile"]),
                              "seconds": ledger["stages"][s].get("seconds"),
                              "reused_from": (ledger["stages"][s].get("reused_from") or {}).get("run")} for s in fps},
            "stale": stale, "code_drift": code_drift, "reuse": reuse_info}


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
