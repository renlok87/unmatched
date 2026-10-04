"""DE-010 (W-26, 01 F-03): AnimNotify "Contact" in the four LungeAttack clips and the hit tint of M_UM_Figure_v2 (v2.2).

    python tools/art/de010/de010.py capture --tag before   # frames of the four v2 figures with the current assets
    python tools/art/de010/de010.py apply                  # rebuild M_UM_Figure_v2 (v2.2) + Contact notifies, saved
    python tools/art/de010/de010.py capture --tag after --contact
    python tools/art/de010/de010.py compare                # metrics + evidence report (no editor)

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
# key, stage, build profile, contact frame
HEROES = [("KingArthur", "H2LD", "ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json", 7),
          ("Merlin", "H2LD", "ASSET-MERLIN-001/build-profiles/merlin-h2anim.json", 8),
          ("Medusa", "H2LD", "ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json", 8),
          ("Harpy", "H3LD", "ASSET-HARPY-001/build-profiles/harpy-h2anim.json", 7)]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")


def figures() -> list:
    res = []
    for key, stage, _, _ in HEROES:
        root = "/Game/PipelineCandidates/%s/%s" % (key, stage)
        res.append({"key": key, "mesh": "%s/Meshes/SK_%s_%s" % (root, key, stage),
                    "mi": "%s/Materials/MI_%s_%s_P1" % (root, key, stage),
                    "lunge": "/Game/PipelineCandidates/%s/H2Anim/AM_%s_LungeAttack" % (key, key)})
    return res


def clips() -> list:
    """Contact frame per hero, checked against its build profile (fps 24, LungeAttack 14 frames, a key frame)."""
    res = []
    for key, _, profile, frame in HEROES:
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
    res = run_editor(HERE / "de010_capture_ue.py", {"out": str(frames / ("capture-%s.json" % a.tag)),
                                                    "frames": str(frames), "tag": a.tag, "figures": figures(),
                                                    "contact": bool(a.contact)}, frames, "capture-" + a.tag)
    res.update(started_at=now())
    write(frames / ("capture-%s.json" % a.tag), res)
    print(json.dumps(res, indent=1)[:2000])


def cmd_apply(a) -> None:
    frames = Path(a.frames)
    spec = vm.load_spec()
    g = vm.figure_v2_graph(spec)
    sig = vm.graph_signature(g)
    master = {"master": vm.MASTER, "settings": vm.SETTINGS, "nodes": g.nodes, "links": g.links, "attrs": g.attrs,
              "instances": [], "signature": sig, "out": str(frames / "apply-master.json")}
    res = run_editor(HERE / "de010_apply_ue.py", {"out": str(frames / "apply.json"), "master": master,
                                                  "master_script": str(vm.HERE / "ue" / "um_v2_master.py"),
                                                  "clips": clips(), "notify_class": "S08ContactAnimNotify"},
                     frames, "apply")
    res["master"].update(graph_signature=sig, node_count=len(g.nodes), link_count=len(g.links),
                         core_hlsl_sha256=__import__("hashlib").sha256(vm.CORE_HLSL.read_bytes()).hexdigest())
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["capture", "apply", "compare"])
    ap.add_argument("--tag", choices=["before", "before2", "after"])
    ap.add_argument("--contact", action="store_true", help="capture: also the contact pose (after apply)")
    ap.add_argument("--frames", default="C:/tmp/de010", help="lossless frames and editor logs (outside the repo)")
    a = ap.parse_args()
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
