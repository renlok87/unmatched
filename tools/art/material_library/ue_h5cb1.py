"""Wave 5c-B1, group H (heroes v2) in the LIVE main UnrealEditor (MCP :8123): re-import of the 5c-B0 fixes and the
check of the v2 heroes in the S08 game placement with their H2Anim clips.

    # 1) re-import of the 5c-B0 textures (+ MI dye knobs) over the existing H2LD assets (one editor-lock step per hero)
    python tools/art/material_library/ue_h5cb1.py reimport --hero arthur|harpy|merlin

    # 3) S08-like staging on the P1.7 Cobble control level (nothing saved): 4 heroes + 3 Harpies as ApplyHeroV2 puts
    #    them (S08HeroesV2.h: mesh / pedestal / MI by the team look, yaw = legacy 0|180 + 90, scale = budget / top),
    #    K1 / K2 1.6x / K2 5x frames, then every H2Anim clip at 0 / 50 / 100 % (one lock step per clip)
    python tools/art/material_library/ue_h5cb1.py game --step ref|Idle|LungeAttack|HitReact|DeathSettle
    python tools/art/material_library/ue_h5cb1.py game-sheets        # contact sheets + probe summary (no editor)

Everything in the editor runs under the shared lock (ue_lock.py, C:/tmp/ue-editor.lock; owner UE_LOCK_OWNER, default
"H-heroes"): level switch, temporary actors, frames, cleanup and the previous level restored in ONE step. Frames are
EDITOR frames (class editor-mcp-viewport): diagnostics, not K1/K2 acceptance, no RENDER fingerprint.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REVIEW = REPO / "tools" / "tripo-pipeline" / "review"
sys.path.insert(0, str(REVIEW))
sys.path.insert(0, str(HERE))
os.environ.setdefault("UE_LOCK_OWNER", "H-heroes")

import ue_hero_lookdev as L  # noqa: E402

TASK = HERE / "ue" / "h5cb1_ue.py"
CONTENT = REPO / "unreal" / "Unmatched" / "Content"
ART_WT = Path("C:/Users/ren/.codex/worktrees/art-foundation/unmached")
PC = REPO / "art" / "pipeline-candidates"
TMP = Path("C:/tmp/h5cb1")
EVID = REPO / "docs" / "art-pipeline" / "evidence" / "h5cb1-heroes-game-2026-09-30"

HEROES = {
    "arthur": {
        "key": "KingArthur", "stage": "H2LD", "asset_dir": "ASSET-KING-ARTHUR-001", "run": "20260930-h2ld-5cb1-ue",
        "lookdev": "20260929-h2-lookdev",
        "textures": [
            {"asset": "/Game/PipelineCandidates/KingArthur/H2LD/Textures/T_KingArthur_H2LD_TeamAccent",
             "file": "textures/T_KingArthur_H2LD_TeamAccent_2K.png", "sha": "6b6f007c",
             "settings": {"srgb": False, "compression_settings": "TC_GRAYSCALE"}},
            {"asset": "/Game/PipelineCandidates/KingArthur/H2LD/Textures/T_KingArthur_H2LD_BC",
             "file": "textures/T_KingArthur_H2LD_BC_2K.png", "sha": "e8baac8c",
             "settings": {"srgb": True, "compression_settings": "TC_DEFAULT"}}],
        "mi": {"/Game/PipelineCandidates/KingArthur/H2LD/Materials/MI_KingArthur_H2LD":
               {"scalars": {"TeamDyeGain": 18.8501, "TeamDyeCeiling": 7.6713}}},
    },
    "harpy": {
        "key": "Harpy", "stage": "H3LD", "asset_dir": "ASSET-HARPY-001", "run": "20260930-h3ld-5cb1-ue",
        "lookdev": "20260929-h3-lookdev",
        "textures": [
            {"asset": "/Game/PipelineCandidates/Harpy/H3LD/Textures/T_Harpy_H3LD_BC",
             "file": "textures/2k/T_Harpy_H3LD_BC.png", "sha": "980ecbf3",
             "settings": {"srgb": True, "compression_settings": "TC_DEFAULT"}}],
        "mi": {"/Game/PipelineCandidates/Harpy/H3LD/Materials/MI_Harpy_H3LD": {"scalars": {"TeamDyeCeiling": 37.037}}},
    },
    "merlin": {
        "key": "Merlin", "stage": "H2LD", "asset_dir": "ASSET-MERLIN-001", "run": "20260930-h2ld-5cb1-ue",
        "lookdev": "20260929-h2-lookdev",
        "textures": [
            {"asset": "/Game/PipelineCandidates/Merlin/H2LD/Textures/T_Merlin_H2LD_BC",
             "file": "textures/T_Merlin_H2LD_BC_2K.png", "sha": "a99630dc",
             "settings": {"srgb": True, "compression_settings": "TC_DEFAULT"}},
            {"asset": "/Game/PipelineCandidates/Merlin/H2LD/Textures/T_UM_MatLUT_Merlin",
             "file": "ue-inputs/T_UM_MatLUT_Merlin.dds", "sha": "8cf5b424",
             "settings": {"srgb": False, "compression_settings": "TC_HDR", "filter": "TF_NEAREST",
                          "mip_gen_settings": "TMGS_NO_MIPMAPS", "never_stream": True}}],
        "mi": {"/Game/PipelineCandidates/Merlin/H2LD/Materials/MI_Merlin_H2LD":
               {"scalars": {"TeamDyeGain": 27.027, "TeamDyeCeiling": 8.2949}}},
    },
    "medusa": {"key": "Medusa", "stage": "H2LD", "asset_dir": "ASSET-MEDUSA-001", "run": "20260930-h2ld-5cb1-ue"},
}
# B1-5 review configs (look-dev C runs; reading_bias_ev -0.75 = EV100 2.05 of the rev 5 board light)
REVIEW_RUN = {"arthur": "ASSET-KING-ARTHUR-001/20260929-h2ld-ue", "harpy": "ASSET-HARPY-001/20260929-h3ld-ue",
              "merlin": "ASSET-MERLIN-001/20260930-h2ld-ldc-ue", "medusa": "ASSET-MEDUSA-001/20260930-h2ld-ldc-ue"}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def uasset_file(pkg: str) -> Path:
    assert pkg.startswith("/Game/")
    return CONTENT / (pkg[len("/Game/"):] + ".uasset")


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def folder_of(h):
    return "/Game/PipelineCandidates/%s/%s" % (h["key"], h["stage"])


THROTTLE_REF = {"refPath": "/Script/UnrealEd.Default__EditorPerformanceSettings"}


def throttle(ue, value=None) -> dict:
    """EditorPerformanceSettings.bThrottleCPUWhenNotForeground through the MCP object toolset (in memory, not saved;
    the class is not exposed to editor Python)."""
    def get():
        r = ue.call("object", "get_properties", {"instance": THROTTLE_REF, "properties": ["bThrottleCPUWhenNotForeground"]},
                    record=False)
        return r
    rec = {"before": get()}
    if value is not None:
        ue.call("object", "set_properties", {"instance": THROTTLE_REF,
                                             "values": json.dumps({"bThrottleCPUWhenNotForeground": bool(value)})},
                record=False)
    rec["after"] = get()
    return rec


def throttle_on(rec) -> bool:
    s = json.dumps(rec.get("before"))
    return "true" in s.lower()


def dirty_map(ue, pkgs):
    return {p: ue.call("asset", "is_dirty", {"asset_path": p}, record=False) for p in pkgs}


# ------------------------------------------------------------------ 1) re-import
def cmd_reimport(a) -> dict:
    from ue_live import Ue
    from ue_lock import ue_lock
    h = HEROES[a.hero]
    run = PC / h["asset_dir"] / h["run"]
    ld = PC / h["asset_dir"] / h["lookdev"]
    tmp = TMP / a.hero
    tmp.mkdir(parents=True, exist_ok=True)
    texs, pkgs = [], []
    for t in h["textures"]:
        src = (ld / t["file"]).resolve()
        digest = sha(src)
        if not digest.startswith(t["sha"]):
            raise SystemExit("source %s sha %s != pinned %s" % (src, digest[:12], t["sha"]))
        texs.append({"asset": t["asset"], "source_file": src.as_posix(), "settings": t["settings"], "sha256": digest})
        pkgs.append(t["asset"])
    pkgs += list(h["mi"])
    before = {p: sha(uasset_file(p)) for p in pkgs}
    rep = {"schema": "unmatched.h5cb1-reimport/1", "hero": h["key"], "started_at": now(),
           "tool": "tools/art/material_library/ue_h5cb1.py reimport (ue/h5cb1_ue.py reimport + mi_params + readback)",
           "editor": os.environ.get("UE_MCP_URL", "http://127.0.0.1:8123/mcp"),
           "source": "5c-B0 next_ue_steps (C:/tmp/p0-review/5cb0.json track blender)", "textures": texs,
           "mi_parameters": h["mi"], "uasset_sha256_before": before}
    ue = Ue()
    with ue_lock("h5cb1 reimport %s" % h["key"]) as lock:
        level = ue.call("scene", "get_current_level", record=False)
        rep["level_during"] = level
        rep["dirty_before"] = dirty_map(ue, pkgs)
        r1 = ue.run_task(str(TASK), str(tmp / "_task.json"), timeout=600, op="reimport",
                         textures=[{k: t[k] for k in ("asset", "source_file", "settings")} for t in texs])
        r2 = ue.run_task(str(TASK), str(tmp / "_task.json"), timeout=600, op="mi_params", instances=h["mi"])
        insts = sorted(p for p in json.loads(json.dumps(
            ue.run_task(str(TASK), str(tmp / "_task.json"), timeout=600, op="readback", folder=folder_of(h),
                        textures=[], instances=[])["folder_packages"])) if "/Materials/MI_" in p)
        r3 = ue.run_task(str(TASK), str(tmp / "_task.json"), timeout=600, op="readback", folder=folder_of(h),
                         textures=[t["asset"] for t in texs], instances=insts)
        rep["dirty_after"] = dirty_map(ue, pkgs)
        rep["level_after"] = ue.call("scene", "get_current_level", record=False)
        rep["editor_lock"] = {k: v for k, v in lock.items() if k != "waits"}
    for f in (tmp / "_task.json",):
        if f.exists():
            f.unlink()
    rep["reimport"], rep["mi_params"], rep["readback"] = r1, r2, r3
    after = {p: sha(uasset_file(p)) for p in pkgs}
    rep["uasset_sha256_after"] = after
    checks = {}
    for t in texs:
        rb = r3["textures"][t["asset"]]
        want = t["settings"]
        ok = all((rb.get(k) if k != "srgb" else rb["srgb"]) == v or str(rb.get(k)).upper() == str(v).upper()
                 for k, v in want.items())
        src_ok = any(Path(s).resolve() == Path(t["source_file"]).resolve() for s in rb.get("source_files") or [])
        checks["texture " + t["asset"].rsplit("/", 1)[1]] = {"passed": bool(ok and src_ok), "settings": {
            k: rb.get(k) for k in ("srgb", "compression_settings", "filter", "mip_gen_settings", "never_stream", "size")},
            "source_files": rb.get("source_files"), "changed_uasset": before[t["asset"]] != after[t["asset"]]}
    for p, spec in h["mi"].items():
        eff = r3["instances"][p]["effective"]
        checks["mi " + p.rsplit("/", 1)[1]] = {"passed": all(abs(eff[k] - v) < 1e-3 for k, v in spec["scalars"].items()),
                                               "effective": eff}
    over = {p: {k: v for k, v in r3["instances"][p]["scalars"].items() if k in ("TeamDyeGain", "TeamDyeCeiling")}
            for p in insts if p not in h["mi"]}
    checks["children_do_not_override_dye_knobs"] = {"passed": not any(over.values()), "overrides": over}
    checks["effective_on_team_mis"] = {"passed": True, "values": {p: r3["instances"][p]["effective"] for p in insts}}
    checks["no_numbered_copies"] = {"passed": not r3["numbered_copies"], "numbered": r3["numbered_copies"],
                                    "packages": len(r3["folder_packages"])}
    checks["nothing_dirty_after_save"] = {"passed": not any(rep["dirty_after"].values()), "dirty": rep["dirty_after"]}
    rep["checks"] = checks
    rep["passed"] = all(c["passed"] for c in checks.values())
    rep["finished_at"] = now()
    write_json(run / "reimport-5cb1.json", rep)
    for k, c in checks.items():
        print("%-48s %s" % (k, "PASS" if c["passed"] else "FAIL"))
    print("uasset:", json.dumps({p.rsplit("/", 1)[1]: [before[p][:12], after[p][:12]] for p in pkgs}))
    return rep


# ------------------------------------------------------------------ 3) game staging
BOARD_W, BOARD_H, CELL_UU = 5, 6, 100.0   # the S08 Cobble 5 x 6 board (S08ArtHudTests CobbleBoard)
OVERVIEW = 1931.0                          # CAMERA dist of the 5x6 Cobble board (traces, K1)
FOCUS_Z = 28.0
# S08HeroesV2.cpp Specs(): BudgetUU / FigureTopUU
SPEC = {"KingArthur": (55.0, 55.0), "Merlin": (45.0, 44.986), "Medusa": (55.0, 55.009), "Harpy": (42.0, 42.0)}
# the S08 layout of this check: P1 (Arthur, Merlin) on the negative-Y half, P2 (Medusa, three Harpies) on the far half
LAYOUT = [("KingArthur", "H2LD", 2, 1, "P1"), ("Merlin", "H2LD", 1, 1, "P1"), ("Medusa", "H2LD", 2, 4, "P2"),
          ("Harpy", "H3LD", 1, 4, "P2"), ("Harpy", "H3LD", 3, 4, "P2"), ("Harpy", "H3LD", 4, 5, "P2")]
CLIPS = ["Idle", "LungeAttack", "HitReact", "DeathSettle"]
FRACS = [0.0, 0.5, 1.0]
PREFIX = "H5cb1 "


def cell_world(x, y):
    return [x * CELL_UU - (BOARD_W - 1) * 0.5 * CELL_UU, y * CELL_UU - (BOARD_H - 1) * 0.5 * CELL_UU, 0.0]


# accent check of Arthur's cloak trim (5c-B0 TeamAccent rev 3): P1 and P2 side by side on the host half, seen from the
# joiner side (their backs = the cloak) at K2 1.6x / 5x, where the trim mips (0.8 / 2.5) decide the accent width
LAYOUT_ACCENT = [("KingArthur", "H2LD", 1, 1, "P1"), ("KingArthur", "H2LD", 3, 1, "P2")]


def figures(layout=None):
    out, n = [], {}
    for key, stage, x, y, look in (layout or LAYOUT):
        n[key] = n.get(key, 0) + 1
        loc = cell_world(x, y)
        legacy = 0.0 if loc[1] < 0 else 180.0          # S08HeroesV2::LegacyFigureYawDeg
        yaw = legacy + 90.0                              # FigureYawDeg (FacingYawOffsetDeg +90)
        budget, top = SPEC[key]
        scale = min(max(budget / top, 0.5), 2.0)         # FigureScale
        root = "/Game/PipelineCandidates/%s/%s" % (key, stage)
        out.append({"label": "%s%s %d" % (PREFIX, key, n[key]), "key": key, "cell": [x, y], "look": look,
                    "mesh": "%s/Meshes/SK_%s_%s" % (root, key, stage),
                    "material": "%s/Materials/MI_%s_%s_%s" % (root, key, stage, look),
                    "base": "%s/Meshes/SM_%s_%s_Base" % (root, key, stage),
                    "base_material": "%s/Materials/MI_%s_%s_Base_%s" % (root, key, stage, look),
                    "location": loc, "yaw": yaw, "scale": round(scale, 6)})
    return out


def k_view(focus, dist, name, joiner=False):
    """Game camera (pitch -55): the host looks along -Y from the +Y side, the joiner (P2 look) from the -Y side."""
    p = math.radians(55.0)
    sgn = -1.0 if joiner else 1.0
    return {"eye": [focus[0], focus[1] + sgn * dist * math.cos(p), focus[2] + dist * math.sin(p)],
            "rot": [-55.0, 90.0 if joiner else -90.0, 0.0], "yaw": 0.0, "kind": name + (" (joiner side)" if joiner else "")}


def close_view(f, dist=280.0, az=35.0, z=32.0, pitch=-2.0):
    """3/4 view of one figure from its facing side (rig v2 at yaw Y faces the world direction yaw Y), low enough to
    see the feet on the pedestal."""
    face = math.radians(f["yaw"] + az)
    x, y = f["location"][0] + dist * math.cos(face), f["location"][1] + dist * math.sin(face)
    look_yaw = math.degrees(math.atan2(f["location"][1] - y, f["location"][0] - x))
    return {"eye": [x, y, z], "rot": [pitch, look_yaw, 0.0], "yaw": f["yaw"], "kind": "close 3/4 %s" % f["label"]}


def game_views(figs):
    by = {f["key"]: f for f in reversed(figs)}
    v = {"k1": k_view([0.0, 0.0, 0.0], OVERVIEW, "K1 overview (1931 uu, pitch -55)"),
         "k1-joiner": k_view([0.0, 0.0, 0.0], OVERVIEW, "K1 overview (1931 uu, pitch -55)", joiner=True),
         "k2-1p6": k_view([0.0, 0.0, FOCUS_Z], OVERVIEW / 1.6, "K2 1.6x (1207 uu, pitch -55)")}
    for key in ("KingArthur", "Medusa", "Merlin", "Harpy"):
        f = by[key]
        v["k2-5x-" + key.lower()] = k_view([f["location"][0], f["location"][1], FOCUS_Z], OVERVIEW / 5.0,
                                           "K2 5x on %s (386 uu, pitch -55)" % key, joiner=f["location"][1] > 0)
        v["close-" + key.lower()] = close_view(f)
    return v


def clip_path(key, clip):
    return "/Game/PipelineCandidates/%s/H2Anim/AM_%s_%s" % (key, key, clip)


def cmd_game(a) -> dict:
    from ue_live import Ue
    from ue_lock import ue_lock
    out = TMP / "game"
    (out / "frames").mkdir(parents=True, exist_ok=True)
    figs = figures(LAYOUT_ACCENT if a.step == "accent" else None)
    if a.step == "accent":
        views = {"k2-1p6-joiner": k_view([0.0, -150.0, FOCUS_Z], OVERVIEW / 1.6, "K2 1.6x (1207 uu)", joiner=True)}
        for f in figs:
            v = k_view([f["location"][0], f["location"][1], FOCUS_Z], OVERVIEW / 5.0, "K2 5x back of %s" % f["label"],
                       joiner=True)
            views["k2-5x-back-" + f["look"].lower()] = v
            views["k2-5x-front-" + f["look"].lower()] = k_view([f["location"][0], f["location"][1], FOCUS_Z],
                                                               OVERVIEW / 5.0, "K2 5x front of %s" % f["label"])
    else:
        views = game_views(figs)
    light = json.loads(L.PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"][L.LIGHT_PROFILE]
    ue = Ue()
    ss = L.Session(ue, out, "5cb1", "s08v2")
    rep = {"schema": "unmatched.h5cb1-game/1", "step": a.step, "started_at": now(), "figures": figs, "views": views,
           "kind": "EDITOR frames (live UnrealEditor via MCP) of the S08 ApplyHeroV2 placement on the P1.7 Cobble control "
                   "level: diagnostics, not K1/K2 acceptance, no RENDER fingerprint", "console": []}
    with ue_lock("h5cb1 game %s" % a.step) as lock:
        original = ue.call("scene", "get_current_level", record=False)
        if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
            raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
        if original.split(".")[0] == L.LEVEL:
            raise SystemExit("the control level is open (someone else?); refusing")
        rep["original_level"] = original
        sg_before = {n: L.cvar_value(ue, n) for n in L.SG}
        thr = throttle(ue, False)
        rep["throttle"] = thr
        try:
            ue.call("scene", "load_level", {"level_path": L.LEVEL})
            time.sleep(3.0)
            f0 = figs[0]
            rep["setup"] = ss.task("h2_review_ue.py", "setup", level=L.LEVEL, hide_label_prefixes=["P17 "],
                                   keep_labels=[L.EXPOSURE_LABEL],
                                   lights={"off": [L.FILL_LABEL],
                                           "key": {"label": L.KEY_LABEL, "intensity_lux": light["directional"]["intensity"],
                                                   "shadow_distance_uu": light["directional"]["shadow"]["distanceUU"],
                                                   "cascades": light["directional"]["shadow"]["cascades"],
                                                   "contact_shadow_length": light["directional"]["shadow"]["contactShadowLength"],
                                                   "rotation_pitch_yaw_roll": L.KEY_ROTATION}},
                                   sky={"label": PREFIX + "sky", "cubemap": light["sky"]["cubemap"],
                                        "intensity": light["sky"]["intensity"],
                                        "lower_hemisphere_is_black": light["sky"]["lowerHemisphereIsBlack"],
                                        "color_linear": light["sky"]["colorLinear"]},
                                   figure={"label": f0["label"], "kind": "skeletal", "asset": f0["mesh"],
                                           "location": f0["location"], "yaw": f0["yaw"]})
            for n in L.SG:
                ue.console("%s 2" % n)
                rep["console"].append("%s 2" % n)
            for flag in L.SHOW_FLAGS_OFF:
                ue.console("ShowFlag.%s 0" % flag)
                rep["console"].append("ShowFlag.%s 0" % flag)
            rep["stage"] = ue.run_task(str(TASK), str(out / "_task.json"), op="stage",
                                       figures=[{k: f[k] for k in ("label", "mesh", "material", "base", "base_material",
                                                                   "location", "yaw", "scale")} for f in figs])
            time.sleep(4.0)
            # warm-up (shader permutations, streaming, Lumen)
            v0 = views.get("k2-1p6") or views["k2-1p6-joiner"]
            ss.task("control_scene_ue.py", "camera", label=L.L_CAM, location=v0["eye"], rotation=v0["rot"], fov=L.FOV)
            xform = {"location": dict(zip("xyz", v0["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), v0["rot"])),
                     "scale": {"x": 1, "y": 1, "z": 1}}
            prev, warm = None, []
            for _ in range(40):
                im = ss.grab(xform)
                if prev is not None:
                    warm.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
                    # converged: no change left, or a flat plateau of the TSR/Lumen grain (~0.5-0.6, look-dev C C2)
                    if (warm[-1] < 0.05 and len(warm) >= 3) or (len(warm) >= 6 and warm[-1] < 1.0 and
                                                                  max(warm[-4:]) - min(warm[-4:]) < 0.03):
                        break
                prev = im
                time.sleep(1.5)
            rep["warmup_mean_abs_diff"] = warm
            rep["poses"], rep["probes"] = {}, {}
            if a.step == "accent":
                for vn in views:
                    ss.shot("accent-" + vn, views[vn], {"pose": "reference pose", "exposure": "EV100 1.3"}, grabs=3)
                rep["exposure_rev5"] = ss.task(str(HERE / "ue" / "um_v2_scene_ue.py"), "exposure",
                                               label=L.EXPOSURE_LABEL, bias=-0.75)
                time.sleep(2.0)
                for vn in views:
                    ss.shot("accent-%s-ev205" % vn, views[vn], {"pose": "reference pose",
                                                                "exposure": "EV100 2.05 (rev 5)"}, grabs=3)
                rep["exposure_restored"] = ss.task(str(HERE / "ue" / "um_v2_scene_ue.py"), "exposure",
                                                   label=L.EXPOSURE_LABEL, bias=0.0)
            elif a.step == "ref":
                rep["probes"]["ref"] = ue.run_task(str(TASK), str(out / "_task.json"), op="probe",
                                                   figures=[f["label"] for f in figs])["probe"]
                for vn in ("k1", "k1-joiner", "k2-1p6", "k2-5x-kingarthur", "k2-5x-medusa", "k2-5x-merlin", "k2-5x-harpy",
                           "close-kingarthur", "close-merlin", "close-medusa", "close-harpy"):
                    ss.shot("ref-" + vn, views[vn], {"pose": "reference pose (no clip)", "exposure": "EV100 1.3"}, grabs=3)
                rep["exposure_rev5"] = ss.task(str(HERE / "ue" / "um_v2_scene_ue.py"), "exposure",
                                               label=L.EXPOSURE_LABEL, bias=-0.75)
                time.sleep(2.0)
                for vn in ("k1", "k2-1p6"):
                    ss.shot("ref-%s-ev205" % vn, views[vn], {"pose": "reference pose (no clip)",
                                                            "exposure": "EV100 1.3 + bias -0.75 = 2.05 (rev 5)"}, grabs=3)
                rep["exposure_restored"] = ss.task(str(HERE / "ue" / "um_v2_scene_ue.py"), "exposure",
                                                   label=L.EXPOSURE_LABEL, bias=0.0)
            else:
                clip = a.step
                for frac in FRACS:
                    tag = "%s-%03d" % (clip.lower(), int(frac * 100))
                    lens = {}
                    specs = []
                    for f in figs:
                        specs.append({"label": f["label"], "anim": clip_path(f["key"], clip), "time": 0.0})
                    # play length per clip from a first pose at 0 (read back), then the real time
                    if frac > 0.0:
                        first = rep["poses"].get("%s-000" % clip.lower())
                        lens = {p["label"]: p["play_length"] for p in first["posed"]}
                        for s_ in specs:
                            s_["time"] = round(lens[s_["label"]] * frac, 5)
                    rep["poses"][tag] = ue.run_task(str(TASK), str(out / "_task.json"), op="pose", figures=specs)
                    time.sleep(1.5)
                    rep["probes"][tag] = ue.run_task(str(TASK), str(out / "_task.json"), op="probe",
                                                     figures=[f["label"] for f in figs])["probe"]
                    for vn in ("k2-1p6", "close-kingarthur", "close-merlin", "close-medusa", "close-harpy"):
                        ss.shot("%s-%s" % (tag, vn), views[vn], {"pose": "%s at %d %%" % (clip, int(frac * 100)),
                                                                 "exposure": "EV100 1.3"}, grabs=3)
        finally:
            try:
                rep["cleanup"] = ue.run_task(str(TASK), str(out / "_task.json"), op="cleanup", prefix=PREFIX)
                rep["cleanup_cam"] = ss.task("control_scene_ue.py", "cleanup", labels=[L.L_CAM])
            except Exception as exc:  # noqa: BLE001
                rep["cleanup_error"] = str(exc)
            try:
                for n, v in sg_before.items():
                    if v is not None:
                        ue.console("%s %s" % (n, v))
                        rep["console"].append("%s %s" % (n, v))
                for flag in L.SHOW_FLAGS_OFF:
                    ue.console("ShowFlag.%s 2" % flag)
                    rep["console"].append("ShowFlag.%s 2" % flag)
            except Exception as exc:  # noqa: BLE001
                rep["console_error"] = str(exc)
            ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
            time.sleep(2.0)
            rep["throttle_restored"] = throttle(ue, throttle_on(thr))
            rep["restored_level"] = ue.call("scene", "get_current_level", record=False)
            rep["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": rep["restored_level"]},
                                                  record=False)
            rep["control_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": L.LEVEL},
                                                              record=False)
            rep["editor_lock"] = {k: v for k, v in lock.items() if k != "waits"}
            rep["frames"] = ss.frames
            rep["finished_at"] = now()
            tmpj = out / "_task.json"
            if tmpj.exists():
                tmpj.unlink()
            write_json(out / ("game-%s.json" % a.step.lower()), rep)
    print("restored:", rep.get("restored_level"), "dirty:", rep.get("restored_level_dirty"),
          "warmup:", rep.get("warmup_mean_abs_diff", [])[-3:])
    return rep


# ------------------------------------------------------------------ 2) B1-5 review
def cmd_review(a) -> dict:
    """ue_hero_lookdev review (+ measure, sheets) of one hero under ONE lock step, with the editor's
    bThrottleCPUWhenNotForeground off in memory for the step (a background editor does not converge its Lumen frames:
    look-dev C C2, warm-up >= 1.0 rejected) and restored afterwards."""
    from ue_live import Ue
    from ue_lock import ue_lock
    run = PC / REVIEW_RUN[a.hero]
    cfg = json.loads((run / "review-config.json").read_text(encoding="utf-8"))
    out = run / "review" / a.tag
    out.mkdir(parents=True, exist_ok=True)
    a.out = str(out)
    ue = Ue()
    with ue_lock("h5cb1 review %s %s" % (cfg["hero"], a.tag)) as lock:
        thr = throttle(ue, False)
        try:
            rep = L._cmd_review(a, cfg)
        finally:
            thr2 = throttle(ue, throttle_on(thr))
    rep["editor_lock"] = {k: v for k, v in lock.items() if k != "waits"}
    rep["throttle_cpu_when_not_foreground"] = {"set": thr, "restored": thr2}
    write_json(out / ("review-%s.json" % a.tag), rep)
    print("warmup", rep.get("warmup_mean_abs_diff", [])[-3:])
    L.cmd_measure(a, cfg)
    L.cmd_sheets(a, cfg)
    return rep


def _jpeg(src: Path, dst: Path, size=None, crop=None, q=88) -> str:
    im = Image.open(src).convert("RGB")
    if crop:
        im = im.crop(crop)
    if size:
        im.thumbnail(size, Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=q, optimize=True)
    return sha(dst)


def cmd_game_sheets(a) -> dict:
    """Probe summary + contact sheets of the game staging (no editor): clips move the mesh (max bone displacement
    against the reference pose), the posed skinned bounds against the pedestal top (no sinking), the facing towards
    the board centre (actor yaw = ApplyHeroV2 yaw, rig v2 front +X), and JPEG sheets/key frames into the hero runs."""
    out = TMP / "game"
    steps = {s_: json.loads((out / ("game-%s.json" % s_.lower())).read_text(encoding="utf-8"))
             for s_ in ["ref"] + CLIPS if (out / ("game-%s.json" % s_.lower())).is_file()}
    ref = steps["ref"]["probes"]["ref"]
    figs = steps["ref"]["figures"]
    placed = {p_["label"]: p_ for p_ in steps["ref"]["stage"]["placed"]}
    summary = {"schema": "unmatched.h5cb1-game-summary/1", "at": now(), "figures": {}, "steps": {}}
    for f in figs:
        lab = f["label"]
        c = [-f["location"][0], -f["location"][1]]
        face = [math.cos(math.radians(f["yaw"])), math.sin(math.radians(f["yaw"]))]
        summary["figures"][lab] = {
            "cell": f["cell"], "look": f["look"], "yaw": f["yaw"], "scale": f["scale"], "material": f["material"],
            "base_material": f["base_material"], "placed": placed[lab],
            "faces_board_centre": face[0] * c[0] + face[1] * c[1] > 0,
            "ref_skinned_bounds": ref[lab].get("skinned_bounds_world")}
    for st, rep in steps.items():
        if st == "ref":
            continue
        rows = {}
        for tag, probe in rep["probes"].items():
            for lab, pr in probe.items():
                bones = pr["bones"]
                d = {b: math.dist(v, ref[lab]["bones"][b]) for b, v in bones.items() if b in ref[lab]["bones"]}
                top = placed[lab]["base_top_z"]
                sb = pr.get("skinned_bounds_world") or {}
                low = min(v[2] for b, v in bones.items() if b != "SKEL_UM_Humanoid")
                rows.setdefault(lab, {})[tag] = {
                    "max_bone_displacement_vs_ref_uu": round(max(d.values()), 3) if d else None,
                    "bone_of_max": max(d, key=d.get) if d else None,
                    "lowest_bone_z": round(low, 3), "base_top_z": top,
                    "skinned_min_z": sb.get("min", [None, None, None])[2], "skinned_max_z": sb.get("max", [None, None, None])[2],
                    "skinned_min_below_base_top_uu": (round(top - sb["min"][2], 3) if sb.get("min") else None),
                    "position_read_back": pr.get("position_read_back")}
        summary["steps"][st] = {"poses": {t: [{k: p_[k] for k in ("label", "time", "play_length", "same_skeleton")}
                                              for p_ in v["posed"]] for t, v in rep["poses"].items()},
                                "rows": rows, "warmup": rep.get("warmup_mean_abs_diff", [])[-3:],
                                "restored_level": rep.get("restored_level"),
                                "restored_level_dirty": rep.get("restored_level_dirty")}
    write_json(out / "game-summary.json", summary)
    # sheets
    sheets = {}
    cw, chh, head, lab_h = 480, 270, 50, 28
    for key, hk in (("kingarthur", "arthur"), ("merlin", "merlin"), ("medusa", "medusa"), ("harpy", "harpy")):
        h = HEROES[hk]
        dst = PC / h["asset_dir"] / h["run"] / "game"
        clips = [c for c in CLIPS if c in steps]
        W, H = cw * len(FRACS), head + (lab_h + chh) * len(clips)
        sh = Image.new("RGB", (W, H), (14, 14, 14))
        d = ImageDraw.Draw(sh)
        d.text((10, 12), "%s v2 в постановке S08 (редактор :8123, Cobble EV100 1.3, High): клипы H2Anim 0 / 50 / 100 %%"
               % h["key"], fill=(235, 210, 120), font=L.font(22))
        for r, clip in enumerate(clips):
            for c_, fr in enumerate(FRACS):
                tag = "%s-%03d" % (clip.lower(), int(fr * 100))
                src = out / "frames" / ("s08v2-5cb1-%s-close-%s.png" % (tag, key))
                y = head + r * (lab_h + chh)
                d.text((c_ * cw + 6, y + 4), "%s %d %%" % (clip, int(fr * 100)), fill=(220, 220, 220), font=L.font(18))
                if src.is_file():
                    im = Image.open(src).convert("RGB")
                    w0, h0 = im.size
                    im = im.crop((w0 // 6, h0 // 12, 5 * w0 // 6, 11 * h0 // 12))
                    im.thumbnail((cw, chh), Image.LANCZOS)
                    sh.paste(im, (c_ * cw + (cw - im.width) // 2, y + lab_h))
                    if fr == 0.5:
                        sheets["%s/game/%s" % (h["run"], src.stem + ".jpg")] = _jpeg(src, dst / (src.stem + ".jpg"))
        p_ = dst / ("s08v2-5cb1-clips-%s.jpg" % key)
        dst.mkdir(parents=True, exist_ok=True)
        sh.save(p_, quality=88, optimize=True)
        sheets["%s/game/%s" % (h["run"], p_.name)] = sha(p_)
        for vn in ("k2-5x-" + key, "close-" + key):
            src = out / "frames" / ("s08v2-5cb1-ref-%s.png" % vn)
            if src.is_file():
                sheets["%s/game/%s" % (h["run"], src.stem + ".jpg")] = _jpeg(src, dst / (src.stem + ".jpg"))
    # group frames -> evidence folder
    for src in sorted((out / "frames").glob("s08v2-5cb1-*.png")):
        n = src.stem
        if n.startswith("s08v2-5cb1-ref-k") and "-5x-" not in n or ("-050-k2-1p6" in n):
            sheets["evidence/" + n + ".jpg"] = _jpeg(src, EVID / (n + ".jpg"))
    summary["jpeg"] = sheets
    write_json(out / "game-summary.json", summary)
    write_json(EVID / "game-summary.json", summary)
    for lab, fr in summary["figures"].items():
        print(lab, "faces centre" if fr["faces_board_centre"] else "FACES AWAY", fr["placed"]["base_top_z"])
    for st, v in summary["steps"].items():
        for lab, rows in v["rows"].items():
            print(st, lab, {t: (r["max_bone_displacement_vs_ref_uu"], r["skinned_min_below_base_top_uu"]) for t, r in rows.items()})
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["reimport", "review", "game", "game-sheets"])
    ap.add_argument("--hero", choices=sorted(HEROES))
    ap.add_argument("--step", choices=["ref", "accent"] + CLIPS)
    ap.add_argument("--tag", default="b1")
    a = ap.parse_args()
    if a.command == "reimport":
        cmd_reimport(a)
    elif a.command == "review":
        cmd_review(a)
    elif a.command == "game-sheets":
        cmd_game_sheets(a)
    else:
        cmd_game(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
