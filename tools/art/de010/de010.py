"""DE-010 (W-26, 01 F-03): AnimNotify "Contact" in the four LungeAttack clips and the hit tint of M_UM_Figure_v2 (v2.2).

    python tools/art/de010/de010.py capture --tag before   # frames of the four v2 figures with the current assets
    python tools/art/de010/de010.py apply                  # rebuild M_UM_Figure_v2 (v2.2) + Contact notifies, saved
    python tools/art/de010/de010.py capture --tag after --contact
    python tools/art/de010/de010.py compare                # metrics + evidence report (no editor)
    python tools/art/de010/de010.py apply --only <Key>[,<Key>...] [--dry-run] [--rebuild-master]

--only (F157, RB-02): apply / capture touch only these HEROES keys (a new hero: --only <Key>); without it apply rewrites
every hero of HEROES and says so on stderr. --dry-run prints the plan (heroes, clips, master skip/rebuild) and starts no
editor. The master: M_UM_Figure_v2 is rebuilt and saved only when its file is not recorded in master-builds.json as
built from the current graph_signature (sha256 of the .uasset -> signature; a rebuild by this tool or de011 appends
the new file); --rebuild-master forces it. So a hero registration does not re-save the binary master any more.

Every editor step is a separate headless UnrealEditor-Cmd (-ExecutePythonScript, -RenderOffScreen, hidden window) of
the main checkout's project; nothing else is open. Lossless frames go to --frames (outside the repository), the
report and JPEG copies to docs/art-pipeline/evidence/de010-2026-10-04/.

Contact frames (24 fps) come from the "design" of the LungeAttack clip in the build profiles
art/pipeline-candidates/ASSET-*/build-profiles/*-h2anim.json and must be one of its key frames:
Arthur k.7 (chop), Merlin k.8 (staff thrust), Medusa k.8 (arrow release), Harpy k.7 (claw strike, window k.7-9).
The same numbers are S08HeroesV2::FHeroSpec::LungeContactFrame (C++), checked by Unmatched.S08.HeroesV2.Contact.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))
import ue_v2_master as vm  # noqa: E402

UPROJECT = REPO / "unreal" / "Unmatched" / "Unmatched.uproject"
ENGINE = Path(os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
EDITOR = ENGINE / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
EVIDENCE = REPO / "docs" / "art-pipeline" / "evidence" / "de010-2026-10-04"
PROFILES = REPO / "art" / "pipeline-candidates"
MASTER_UASSET = REPO / "unreal" / "Unmatched" / "Content" / "UM" / "Materials" / "v2" / "M_UM_Figure_v2.uasset"
MASTER_BUILDS = HERE / "master-builds.json"  # .uasset sha256 -> the graph_signature it was built from
MASTER_BUILDS_KEEP = 20
# key, stage, build profile, contact frame
HEROES = [("KingArthur", "H2LD", "ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json", 7),
          ("Merlin", "H2LD", "ASSET-MERLIN-001/build-profiles/merlin-h2anim.json", 8),
          ("Medusa", "H2LD", "ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json", 8),
          ("Harpy", "H3LD", "ASSET-HARPY-001/build-profiles/harpy-h2anim.json", 7),
          # skill pilot 2026-10-14, stage 7b (registration R7-1): the spec of the clips imported into UE
          ("Angel", "H2LD", "ASSET-ANGEL-001/build-profiles/angel-h2anim-r2.json", 7),
          ("AncientLeshen", "H2LD", "ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2anim-r3.json", 8),
          ("Achilles", "H2LD", "ASSET-ACHILLES-001/build-profiles/achilles-h2anim-r3.json", 7),
          # skill check figure 2026-10-14, stage 7b (registration R7-1)
          ("Beowulf", "H2LD", "ASSET-BEOWULF-001/build-profiles/beowulf-h2anim.json", 7)]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")


def select_heroes(only: str | None = None, heroes: list | None = None) -> list:
    """--only 'A,B' -> the rows of HEROES with these keys (HEROES order); None -> every row. Unknown key -> exit."""
    heroes = HEROES if heroes is None else heroes
    if only is None:
        return list(heroes)
    keys = [k.strip() for k in only.split(",") if k.strip()]
    if not keys:
        raise SystemExit("--only needs a key: --only <Key>[,<Key>...] (HEROES: %s)" % ", ".join(h[0] for h in heroes))
    unknown = [k for k in keys if k not in {h[0] for h in heroes}]
    if unknown:
        raise SystemExit("--only: %s not in HEROES (%s); register the hero first (row R7-1)" % (
            ", ".join(unknown), ", ".join(h[0] for h in heroes)))
    return [h for h in heroes if h[0] in keys]


def warn_all(rows: list, what: str, only: str | None) -> str | None:
    """The stderr warning of an apply without --only (it rewrites every hero)."""
    if only is not None:
        return None
    msg = ("WARNING: no --only: apply rewrites all %d heroes (%s): %s. A new hero: --only <Key>."
           % (len(rows), ", ".join(h[0] for h in rows), what))
    print(msg, file=sys.stderr, flush=True)
    return msg


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def master_builds(record: Path | None = None) -> list:
    record = MASTER_BUILDS if record is None else record
    if not record.is_file():
        return []
    return list(json.loads(record.read_text(encoding="utf-8")).get("builds", []))


def master_plan(sig: str, rebuild: bool = False, uasset: Path | None = None, record: Path | None = None) -> dict:
    """Skip or rebuild M_UM_Figure_v2 (F157): skip only when the .uasset on disk is recorded as built from sig."""
    uasset = MASTER_UASSET if uasset is None else uasset
    record = MASTER_BUILDS if record is None else record
    sha = file_sha256(uasset)
    plan = {"graph_signature": sig, "uasset": uasset.as_posix(), "uasset_sha256": sha}
    if rebuild:
        return dict(plan, action="rebuild", reason="--rebuild-master")
    if sha is None:
        return dict(plan, action="rebuild", reason="no master file %s" % uasset.name)
    built = next((b for b in master_builds(record) if b.get("uasset_sha256") == sha), None)
    if built is None:
        return dict(plan, action="rebuild", reason="the master file (sha256 %s) is not in %s (saved by another tool)"
                    % (sha[:12], record.name))
    if built.get("graph_signature") != sig:
        return dict(plan, action="rebuild", reason="graph changed: the file is graph %s, the current graph %s" % (
            str(built.get("graph_signature"))[:12], sig[:12]))
    return dict(plan, action="skip", reason="the master file is already graph %s (%s, %s)" % (
        sig[:12], built.get("tool", "?"), built.get("recorded_at", "?")))


def record_master_build(sig: str, tool: str, uasset: Path | None = None, record: Path | None = None) -> dict:
    """After a rebuild: the new .uasset sha256 -> sig, newest first, the last MASTER_BUILDS_KEEP files kept."""
    uasset = MASTER_UASSET if uasset is None else uasset
    record = MASTER_BUILDS if record is None else record
    entry = {"uasset_sha256": file_sha256(uasset), "graph_signature": sig, "recorded_at": now(), "tool": tool}
    if entry["uasset_sha256"] is None:
        raise SystemExit("%s: no master file %s after the rebuild" % (tool, uasset))
    builds = [entry] + [b for b in master_builds(record) if b.get("uasset_sha256") != entry["uasset_sha256"]]
    try:
        rel = uasset.resolve().relative_to(REPO).as_posix()
    except ValueError:
        rel = uasset.as_posix()
    write(record, {"schema": "unmatched.figure-master-builds/1", "master": "/Game/UM/Materials/v2/M_UM_Figure_v2",
                   "uasset": rel,
                   "note": "de010/de011 apply skip the master rebuild while the .uasset sha256 is listed here with the "
                           "current graph_signature (tools/art/material_library/ue_v2_master.py graph_signature)",
                   "builds": builds[:MASTER_BUILDS_KEEP]})
    return entry


def master_task(frames: Path, rebuild: bool = False) -> tuple:
    """(ARGS["master"] of the editor task, the skip/rebuild plan, the graph) - shared by de010 / de011 apply."""
    g = vm.figure_v2_graph(vm.load_spec())
    sig = vm.graph_signature(g)
    master = {"master": vm.MASTER, "settings": vm.SETTINGS, "nodes": g.nodes, "links": g.links, "attrs": g.attrs,
              "instances": [], "signature": sig, "out": str(frames / "apply-master.json")}
    return master, master_plan(sig, rebuild), g


def after_master(res: dict, plan: dict, g, tool: str) -> None:
    """Report fields of the master + the master-builds.json record after a clean rebuild."""
    res["master"].update(graph_signature=plan["graph_signature"], node_count=len(g.nodes), link_count=len(g.links),
                         core_hlsl_sha256=hashlib.sha256(vm.CORE_HLSL.read_bytes()).hexdigest(),
                         master_action=plan["action"], master_reason=plan["reason"])
    if plan["action"] == "rebuild" and not res["master"].get("compile_errors"):
        res["master"]["recorded"] = record_master_build(plan["graph_signature"], tool)


def figures(rows: list | None = None) -> list:
    res = []
    for key, stage, _, _ in (HEROES if rows is None else rows):
        root = "/Game/PipelineCandidates/%s/%s" % (key, stage)
        res.append({"key": key, "mesh": "%s/Meshes/SK_%s_%s" % (root, key, stage),
                    "mi": "%s/Materials/MI_%s_%s_P1" % (root, key, stage),
                    "lunge": "/Game/PipelineCandidates/%s/H2Anim/AM_%s_LungeAttack" % (key, key)})
    return res


def clips(rows: list | None = None) -> list:
    """Contact frame per hero, checked against its build profile (fps 24, LungeAttack 14 frames, a key frame)."""
    res = []
    for key, _, profile, frame in (HEROES if rows is None else rows):
        spec = json.loads((PROFILES / profile).read_text(encoding="utf-8"))
        lunge = spec["clips"]["LungeAttack"]
        if spec["fps"] != 24 or lunge["frames"] != 14 or frame not in lunge["key_frames"]:
            raise SystemExit("%s: profile %s does not match (fps %s, frames %s, key frames %s, contact %s)" % (
                key, profile, spec["fps"], lunge["frames"], lunge["key_frames"], frame))
        res.append({"key": key, "path": "/Game/PipelineCandidates/%s/H2Anim/AM_%s_LungeAttack" % (key, key),
                    "frame": frame, "fps": spec["fps"], "profile": "art/pipeline-candidates/" + profile})
    return res


def run_editor(script: Path, args: dict, work: Path, name: str, timeout: int = 1800) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    args_path = work / ("%s.args.json" % name)
    write(args_path, args)
    out = Path(args["out"])
    if out.exists():
        out.unlink()
    log = work / ("%s.log" % name)
    env = dict(os.environ, DE010_ARGS=str(args_path))
    cmd = [str(EDITOR), str(UPROJECT), "-ExecutePythonScript=%s" % script.as_posix(), "-unattended", "-nosplash",
           "-RenderOffScreen", "-stdout", "-FullStdOutLogOutput", "-DisablePlugins=Tripo3DUEBridge",
           "-ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=False"]
    t0 = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT, env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print("UnrealEditor-Cmd pid %d (%s), log %s" % (proc.pid, name, log), flush=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise SystemExit("%s: editor timed out after %ss (killed pid %d), log %s" % (name, timeout, proc.pid, log))
    if not out.is_file():
        raise SystemExit("%s: no report %s (exit %s), log %s" % (name, out, code, log))
    data = json.loads(out.read_text(encoding="utf-8"))
    data["_editor"] = {"exit": code, "seconds": round(time.time() - t0, 1), "log": log.as_posix()}
    if data.get("error"):
        raise SystemExit("%s failed: %s" % (name, data["error"][-3000:]))
    return data


def cmd_capture(a) -> None:
    frames = Path(a.frames)
    rows = select_heroes(getattr(a, "only", None))
    res = run_editor(HERE / "de010_capture_ue.py", {"out": str(frames / ("capture-%s.json" % a.tag)),
                                                    "frames": str(frames), "tag": a.tag, "figures": figures(rows),
                                                    "contact": bool(a.contact)}, frames, "capture-" + a.tag)
    res.update(started_at=now())
    write(frames / ("capture-%s.json" % a.tag), res)
    print(json.dumps(res, indent=1)[:2000])


def apply_plan(a) -> tuple:
    """(plan, ARGS["master"], graph): what apply touches - heroes, Contact clips, master skip / rebuild. No editor."""
    only = getattr(a, "only", None)
    rows = select_heroes(only)
    master, mplan, g = master_task(Path(a.frames), getattr(a, "rebuild_master", False))
    plan = {"tool": "de010 apply", "heroes": [h[0] for h in rows], "clips": clips(rows), "master": mplan,
            "warning": warn_all(rows, "the Contact notify of every LungeAttack is re-set and the clip re-saved", only)}
    return plan, master, g


def cmd_apply(a) -> None:
    frames = Path(a.frames)
    plan, master, g = apply_plan(a)
    if getattr(a, "dry_run", False):
        print(json.dumps(plan, indent=1))
        return
    mplan = plan["master"]
    print("master %s: %s" % (mplan["action"], mplan["reason"]), flush=True)
    res = run_editor(HERE / "de010_apply_ue.py", {"out": str(frames / "apply.json"), "master": master,
                                                  "master_skip": mplan if mplan["action"] == "skip" else None,
                                                  "master_script": str(vm.HERE / "ue" / "um_v2_master.py"),
                                                  "clips": plan["clips"], "notify_class": "S08ContactAnimNotify"},
                     frames, "apply")
    after_master(res, mplan, g, "de010 apply")
    res["heroes"] = plan["heroes"]
    res["finished_at"] = now()
    write(frames / "apply.json", res)
    m = res["master"]
    print(json.dumps({"compile_errors": m.get("compile_errors"), "expressions": m.get("expressions"),
                      "statistics": m.get("statistics"), "clips": {k: {"before": v["before"], "after": v["after"]}
                                                                    for k, v in res["clips"].items()}}, indent=1))


def img(path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def diff(a, b) -> dict:
    import numpy as np
    d = np.abs(img(a) - img(b))
    px = d.max(axis=2)
    return {"mean_abs": round(float(d.mean()), 4), "max_abs": int(d.max()), "pixels_gt2": int((px > 2).sum()),
            "pixels_gt8": int((px > 8).sum()), "pixels": int(px.size)}


def red_shift(a, b) -> dict:
    """Mean (R - (G + B) / 2) over the pixels that changed by > 8 (the figures)."""
    import numpy as np
    A, B = img(a), img(b)
    mask = np.abs(A - B).max(axis=2) > 8
    if not mask.any():
        return {"changed_pixels": 0}

    def redness(x):
        return float((x[..., 0] - (x[..., 1] + x[..., 2]) / 2.0)[mask].mean())
    return {"changed_pixels": int(mask.sum()), "redness_a": round(redness(A), 2), "redness_b": round(redness(B), 2)}


def cmd_compare(a) -> None:
    from PIL import Image
    frames = Path(a.frames)
    before = json.loads((frames / "capture-before.json").read_text(encoding="utf-8"))
    after = json.loads((frames / "capture-after.json").read_text(encoding="utf-8"))
    apply = json.loads((frames / "apply.json").read_text(encoding="utf-8"))
    fb, fa = before["frames"], after["frames"]
    m = {
        "noise_floor_before_final": diff(fb["final-hit0"], fb["final-hit0-b"]),
        "noise_floor_after_final": diff(fa["final-hit0"], fa["final-hit0-b"]),
        "before_vs_after_base_hit0": diff(fb["base-hit0"], fa["base-hit0"]),
        "before_vs_after_final_hit0": diff(fb["final-hit0"], fa["final-hit0"]),
        "before_hit1_vs_hit0_base": diff(fb["base-hit0"], fb["base-hit1"]),
        "after_hit1_vs_hit0_base": diff(fa["base-hit0"], fa["base-hit1"]),
        "after_hit1_vs_hit0_final": diff(fa["final-hit0"], fa["final-hit1"]),
        "after_hit1_red_shift_final": red_shift(fa["final-hit0"], fa["final-hit1"]),
    }
    nf = max(m["noise_floor_before_final"]["mean_abs"], m["noise_floor_after_final"]["mean_abs"])
    clips_ok = {}
    for k, c in apply["clips"].items():
        b, af = c["before"], c["after"]
        contacts = [n for n in af["notifies"] if n["name"] == "Contact"]
        clips_ok[k] = {"length_unchanged": b["play_length"] == af["play_length"] and b["frames"] == af["frames"],
                       "one_contact": len(contacts) == 1 and contacts[0]["class"] == "S08ContactAnimNotify",
                       "contact_ms": round(contacts[0]["time"] * 1000.0, 1) if contacts else None,
                       "profile_ms": round(1000.0 * c["frame"] / c["fps"], 1),
                       "play_length": af["play_length"], "frames": af["frames"]}
    checks = {
        "default_zero_base_identical": m["before_vs_after_base_hit0"]["max_abs"] == 0,
        "default_zero_final_within_noise": m["before_vs_after_final_hit0"]["mean_abs"] <= nf + 0.05,
        "old_material_ignores_slot": m["before_hit1_vs_hit0_base"]["max_abs"] == 0,
        "hit1_tints_red": m["after_hit1_vs_hit0_base"]["pixels_gt8"] > 1000 and
        m["after_hit1_red_shift_final"].get("redness_b", 0) > m["after_hit1_red_shift_final"].get("redness_a", 0) + 20,
        "compile_errors_none": not apply["master"].get("compile_errors"),
        "clips": all(v["length_unchanged"] and v["one_contact"] and abs(v["contact_ms"] - v["profile_ms"]) < 21
                     for v in clips_ok.values()),
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    copies = {}
    for tag, fr in (("before", fb), ("after", fa)):
        for name in ("final-hit0", "final-hit1", "base-hit1", "final-contact"):
            if name in fr:
                dst = EVIDENCE / ("%s-%s.jpg" % (tag, name))
                Image.open(fr[name]).convert("RGB").save(dst, quality=92)
                copies["%s-%s" % (tag, name)] = dst.relative_to(REPO).as_posix()
    rep = {"schema": "unmatched.de010-evidence/1", "task": "DE-010 (W-26)", "tool": "tools/art/de010/de010.py",
           "created_at": now(), "all_ok": all(checks.values()), "checks": checks, "metrics": m, "clips": clips_ok,
           "master": {k: apply["master"].get(k) for k in ("graph_signature", "node_count", "link_count",
                                                           "expressions", "statistics", "parameters",
                                                           "compile_errors", "core_hlsl_sha256")},
           "frames": copies,
           "note": "Editor frames (blank map, SceneCapture2D, manual exposure, reference pose / contact pose): a "
                   "before/after check of the material at CPD_HitTint 0, not K1-K3 and not artistic acceptance. "
                   "The packaged K1 before/after of the run is taken by the A04 acceptance agent."}
    write(EVIDENCE / "de010-report.json", rep)
    print(json.dumps({"all_ok": rep["all_ok"], "checks": checks, "clips": clips_ok}, indent=1))
    if not rep["all_ok"]:
        raise SystemExit(1)


def utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):  # RB-11: the Bash pipe of an agent is cp1251
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: list | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["capture", "apply", "compare"])
    ap.add_argument("--tag", choices=["before", "before2", "after"])
    ap.add_argument("--contact", action="store_true", help="capture: also the contact pose (after apply)")
    ap.add_argument("--frames", default="C:/tmp/de010", help="lossless frames and editor logs (outside the repo)")
    ap.add_argument("--only", default=None, metavar="KEY[,KEY...]",
                    help="apply / capture: only these HEROES keys (a new hero); default every hero, with a warning")
    ap.add_argument("--dry-run", action="store_true", help="apply: print the plan, no editor")
    ap.add_argument("--rebuild-master", action="store_true",
                    help="apply: rebuild M_UM_Figure_v2 even when master-builds.json has its file at this graph")
    a = ap.parse_args(argv)
    if a.command == "capture":
        if not a.tag:
            raise SystemExit("capture needs --tag")
        cmd_capture(a)
    elif a.command == "apply":
        cmd_apply(a)
    else:
        cmd_compare(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
