"""DE-011 (W-27, 01 F-09): the death dissolve of the v2 figures - M_UM_Figure_v2 v2.3 (static switch UseDissolve,
CPD 13 progress / CPD 14 style) and one Masked dissolve MIC per hero body MI.

    python tools/art/de011/de011.py inspect               # hero MI chains, static switches, mesh bounds (no save)
    python tools/art/de011/de011.py capture --tag before  # frames of the four v2 figures with the current assets
    python tools/art/de011/de011.py apply                 # rebuild M_UM_Figure_v2 (v2.3) + the 8 dissolve MICs, saved
    python tools/art/de011/de011.py capture --tag after --dissolve
    python tools/art/de011/de011.py compare               # metrics + evidence report (no editor)

Every editor step is a separate headless UnrealEditor-Cmd of the main checkout's project (the runner of
tools/art/de010/de010.py: -ExecutePythonScript, -RenderOffScreen, no window). Lossless frames go to --frames (outside
the repository), the report and JPEG copies to docs/art-pipeline/evidence/de011-2026-10-04/.

Why a switch + MICs and not a Masked master: the accepted figures stay Opaque (the v1 rule "no Masked" of the
masters, PIPELINE.md; no masked depth pass for living figures). Only the dissolve MIC - a child of the hero MI, so
textures, knobs and the static switches UseUV1Metres / UseTeamAccent are inherited - turns the dissolve on and
overrides the blend mode to Masked. The default permutation compiles the v2.2 graph unchanged.
Durations (01 F-09): 500 ms hero, 400 ms sidekick; the default style is the simple fade, the team-colour ash is a
candidate for the A/B sheet (DE-028). C++: S08HeroesV2.h (DissolveCpdIndex, DissolveMaterialPath, ApplyDissolve).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))
sys.path.insert(0, str(REPO / "tools" / "art" / "de010"))
import de010  # noqa: E402
import ue_v2_master as vm  # noqa: E402

EVIDENCE = REPO / "docs" / "art-pipeline" / "evidence" / "de011-2026-10-04"
DISSOLVE_ROOT = vm.ROOT + "/Dissolve"
LOOKS = ("P1", "P2")
# capture: both team colours side by side (Arthur P1, Merlin P2, Medusa P1, Harpy P2)
CAPTURE_LOOKS = {"KingArthur": "P1", "Merlin": "P2", "Medusa": "P1", "Harpy": "P2"}


def stage_root(key: str, stage: str) -> str:
    return "/Game/PipelineCandidates/%s/%s" % (key, stage)


def body_mi(key: str, stage: str, look: str) -> str:
    return "%s/Materials/MI_%s_%s_%s" % (stage_root(key, stage), key, stage, look)


def dissolve_mi(key: str, stage: str, look: str) -> str:
    """Same name rule as S08HeroesV2::DissolveMaterialPath."""
    return "%s/MI_%s_%s_%s_Dissolve" % (DISSOLVE_ROOT, key, stage, look)


def mics() -> list:
    return [{"asset": dissolve_mi(key, stage, look), "parent": body_mi(key, stage, look)}
            for key, stage, _, _ in de010.HEROES for look in LOOKS]


def figures() -> list:
    res = []
    for key, stage, _, _ in de010.HEROES:
        look = CAPTURE_LOOKS[key]
        root = stage_root(key, stage)
        res.append({"key": key, "look": look, "mesh": "%s/Meshes/SK_%s_%s" % (root, key, stage),
                    "mi": body_mi(key, stage, look), "dissolve_mi": dissolve_mi(key, stage, look),
                    "base": "%s/Meshes/SM_%s_%s_Base" % (root, key, stage),
                    "base_mi": "%s/Materials/MI_%s_%s_Base_%s" % (root, key, stage, look)})
    return res


def cmd_inspect(a) -> None:
    frames = Path(a.frames)
    mats, meshes = [], []
    for key, stage, _, _ in de010.HEROES:
        root = stage_root(key, stage)
        for look in LOOKS:
            mats += [body_mi(key, stage, look), "%s/Materials/MI_%s_%s_Base_%s" % (root, key, stage, look)]
        meshes += ["%s/Meshes/SK_%s_%s" % (root, key, stage), "%s/Meshes/SM_%s_%s_Base" % (root, key, stage)]
    res = de010.run_editor(HERE / "de011_inspect_ue.py", {"out": str(frames / "inspect.json"), "materials": mats,
                                                          "meshes": meshes}, frames, "inspect")
    de010.write(frames / "inspect.json", res)
    for path, m in res["materials"].items():
        print(path.rsplit("/", 1)[1], m["master"], {k: v["mi"] for k, v in m["switches"].items()})


def cmd_capture(a) -> None:
    frames = Path(a.frames)
    res = de010.run_editor(HERE / "de011_capture_ue.py", {"out": str(frames / ("capture-%s.json" % a.tag)),
                                                          "frames": str(frames), "tag": a.tag,
                                                          "figures": figures(), "dissolve": bool(a.dissolve)},
                           frames, "capture-" + a.tag)
    res.update(started_at=de010.now())
    de010.write(frames / ("capture-%s.json" % a.tag), res)
    print(json.dumps(res, indent=1)[:2000])


def cmd_apply(a) -> None:
    frames = Path(a.frames)
    g = vm.figure_v2_graph(vm.load_spec())
    sig = vm.graph_signature(g)
    master = {"master": vm.MASTER, "settings": vm.SETTINGS, "nodes": g.nodes, "links": g.links, "attrs": g.attrs,
              "instances": [], "signature": sig, "out": str(frames / "apply-master.json")}
    res = de010.run_editor(HERE / "de011_apply_ue.py", {"out": str(frames / "apply.json"), "master": master,
                                                        "master_script": str(vm.HERE / "ue" / "um_v2_master.py"),
                                                        "switch": vm.DISSOLVE_SWITCH, "mics": mics()},
                           frames, "apply")
    res["master"].update(graph_signature=sig, node_count=len(g.nodes), link_count=len(g.links),
                         core_hlsl_sha256=hashlib.sha256(vm.CORE_HLSL.read_bytes()).hexdigest(),
                         dissolve_hlsl_sha256=hashlib.sha256(vm.DISSOLVE_HLSL.read_bytes()).hexdigest())
    res["finished_at"] = de010.now()
    de010.write(frames / "apply.json", res)
    m = res["master"]
    print(json.dumps({"compile_errors": m.get("compile_errors"), "expressions": m.get("expressions"),
                      "statistics": m.get("statistics"), "blend_mode": m.get("blend_mode"),
                      "mics": {k.rsplit("/", 1)[1]: {x: v[x] for x in ("blend_mode", "switches", "statistics")}
                               for k, v in res["mics"].items()}}, indent=1))


def figure_pixels(a, b, threshold: int = 8) -> int:
    """Pixels where frame a differs from frame b by more than threshold (a figure against the empty frame)."""
    import numpy as np
    return int((np.abs(de010.img(a) - de010.img(b)).max(axis=2) > threshold).sum())


def cmd_compare(a) -> None:
    from PIL import Image
    frames = Path(a.frames)
    before = json.loads((frames / "capture-before.json").read_text(encoding="utf-8"))
    after = json.loads((frames / "capture-after.json").read_text(encoding="utf-8"))
    apply = json.loads((frames / "apply.json").read_text(encoding="utf-8"))
    fb, fa = before["frames"], after["frames"]
    d = de010.diff
    m = {
        "noise_floor_before_final": d(fb["final-d0"], fb["final-d0-b"]),
        "noise_floor_after_final": d(fa["final-d0"], fa["final-d0-b"]),
        "before_vs_after_base_d0": d(fb["base-d0"], fa["base-d0"]),
        "before_vs_after_final_d0": d(fb["final-d0"], fa["final-d0"]),
        "after_default_ignores_dissolve_slots": d(fa["final-d0"], fa["final-ignore"]),
        "after_mic_p0_vs_mi": d(fa["final-d0"], fa["mic-p0"]),
        "after_fade_p100_vs_empty": d(fa["empty"], fa["fade-p100"]),
        "after_ash_p100_vs_empty": d(fa["empty"], fa["ash-p100"]),
    }
    px = {name: figure_pixels(fa["empty"], fa[name]) for name in
          ("mic-p0", "fade-p35", "fade-p70", "ash-p35", "ash-p70", "fade-p100", "ash-p100")}
    glow = de010.diff(fa["fade-p35"], fa["ash-p35"])
    nf = max(m["noise_floor_before_final"]["mean_abs"], m["noise_floor_after_final"]["mean_abs"])
    mics_ok = {}
    for path, v in apply["mics"].items():
        parent_sw = dict(v["parent_switches"], **{vm.DISSOLVE_SWITCH: True})
        mics_ok[path.rsplit("/", 1)[1]] = {
            "masked": v["blend_override"] and v["blend_mode"].endswith("BLEND_MASKED: 1>"),
            "switches_inherited": v["switches"] == parent_sw, "switches": v["switches"],
            "ps_instructions": v["statistics"].get("num_pixel_shader_instructions"),
            "parent_ps_instructions": v["parent_statistics"].get("num_pixel_shader_instructions")}
    checks = {
        "default_base_identical": m["before_vs_after_base_d0"]["max_abs"] == 0,
        "default_final_within_noise": m["before_vs_after_final_d0"]["mean_abs"] <= nf + 0.05,
        "default_ignores_dissolve_slots": m["after_default_ignores_dissolve_slots"]["mean_abs"] <= nf + 0.05,
        "master_still_opaque": apply["master"].get("blend_mode", "").endswith("BLEND_OPAQUE: 0>"),
        "compile_errors_none": not apply["master"].get("compile_errors"),
        "mics_masked_and_inherit_switches": all(v["masked"] and v["switches_inherited"] for v in mics_ok.values()),
        "mic_progress0_matches_figure": m["after_mic_p0_vs_mi"]["mean_abs"] <= nf + 0.05,
        # the ash front lights dark figure pixels that read as black at p0, so ash-p35 may count more than mic-p0
        "progress_shrinks_figure": px["mic-p0"] > px["fade-p35"] > px["fade-p70"] > px["fade-p100"] and
        px["ash-p35"] > px["ash-p70"] > px["ash-p100"] and px["ash-p70"] < px["mic-p0"],
        "progress1_empty": m["after_fade_p100_vs_empty"]["pixels_gt8"] == 0 and
        m["after_ash_p100_vs_empty"]["pixels_gt8"] == 0,
        "ash_differs_from_fade": glow["pixels_gt8"] > 1000,
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    copies = {}
    for tag, fr in (("before", fb), ("after", fa)):
        for name in fr:
            if name.endswith("-b"):
                continue
            dst = EVIDENCE / ("%s-%s.jpg" % (tag, name))
            Image.open(fr[name]).convert("RGB").save(dst, quality=92)
            copies["%s-%s" % (tag, name)] = dst.relative_to(REPO).as_posix()
    rep = {"schema": "unmatched.de011-evidence/1", "task": "DE-011 (W-27)", "tool": "tools/art/de011/de011.py",
           "created_at": de010.now(), "all_ok": all(checks.values()), "checks": checks, "metrics": m,
           "figure_pixels_vs_empty": px, "ash_vs_fade_p35": glow, "mics": mics_ok,
           "master": {k: apply["master"].get(k) for k in ("graph_signature", "node_count", "link_count",
                                                           "expressions", "statistics", "parameters",
                                                           "compile_errors", "core_hlsl_sha256",
                                                           "dissolve_hlsl_sha256", "blend_mode")},
           "frames": copies,
           "note": "Editor frames (blank map, SceneCapture2D, manual exposure, no temporal AA: the fade dither shows "
                   "as a stipple that TSR resolves in the game): a before/after check of the material at the "
                   "defaults and of the two dissolve styles, not K1-K3 and not artistic acceptance. The packaged K1 "
                   "and render_bench of the run are taken by the A04 acceptance agent."}
    de010.write(EVIDENCE / "de011-report.json", rep)
    print(json.dumps({"all_ok": rep["all_ok"], "checks": checks, "figure_pixels": px}, indent=1))
    if not rep["all_ok"]:
        raise SystemExit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["inspect", "capture", "apply", "compare"])
    ap.add_argument("--tag", choices=["before", "after"])
    ap.add_argument("--dissolve", action="store_true", help="capture: also the dissolve MICs (after apply)")
    ap.add_argument("--frames", default="C:/tmp/de011", help="lossless frames and editor logs (outside the repo)")
    a = ap.parse_args()
    if a.command == "inspect":
        cmd_inspect(a)
    elif a.command == "capture":
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
