"""W5c: editor frames of an H2 hero import on the Cobble control stand (live UnrealEditor via MCP 127.0.0.1:8123).

    python tools/tripo-pipeline/review/h2_ue_frames.py --hero merlin --folder /Game/PipelineCandidates/Merlin/H2 \
        --skeletal SK_Merlin_H2 --base SM_Merlin_H2_Base --mi MI_Merlin_H2 --teams Blue,Red --out <dir> --tag r1
        [--replace merlin] [--cell 3,3] [--normal-texture T_Merlin_H2_N] [--closeups closeups.json]

What it does (in memory only; nothing is saved):
  1. refuses when the open level has unsaved changes (it belongs to someone else's work), records it;
  2. loads the saved P1.7 control level /Game/ArtTests/P17ControlScene/L_P17ControlScene (Cobble board, its
     lights, fixed exposure EV100 1.3 — built by review/control_scene.py, not modified here), hides the level's own
     w4b figure of --replace and spawns the H2 figure + base on its cell (temporary actors);
  3. frames (EditorAppToolset.CaptureViewport, centred 16:9 crop -> 1920x1080, the camera model of control_scene.py):
       k2-1p6 / k2-5x  board camera (FOV 35 horizontal, pitch -55) with the S08 facing rule of the cell, per team;
       turn-5x-{front,side,back}  board camera at 5x, the figure turned to face the camera / its staff side / away;
       eye-{front,side,back}      horizontal camera (pitch -8, FOV 35) for the side-by-side with the Blender frames;
       close-*                    close-ups (--closeups: name, focus, distance, yaw, pitch);
       diagnostics: the DirectX normal A/B (bFlipGreenChannel of the normal texture toggled in memory, then restored
       and verified) and the Metallic / Roughness / BaseColor buffers (r.BufferVisualizationTarget) of the close-ups;
  4. removes the temporary actors and camera, restores show flags / buffer view and re-opens the previous level.
Frames are EDITOR frames (editor-mcp-viewport; DX12/SM6 + Lumen of the editor at its own scalability): diagnostics,
not K1/K2 acceptance, not art acceptance, no RENDER fingerprint (that exists only in the packaged client).
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import control_scene as cs  # noqa: E402  (camera model, Capture, show flags, level paths)
from ue_live import Ue  # noqa: E402

SCHEMA = "unmatched.h2-ue-frames/1"
L_FIG, L_BASE = "W5C %s H2 figure - temporary", "W5C %s H2 base - temporary"
EYE_PITCH, EYE_DIST, EYE_FOCUS_Z = -8.0, 160.0, 26.0
BUFFERS = ("Metallic", "Roughness", "BaseColor")


def pkg_obj(path):
    return "%s.%s" % (path, path.rsplit("/", 1)[-1])


def eye_cam(focus, dist, pitch, yaw_cam=-90.0):
    """Camera on +Y of the focus looking along -Y (the same side as the board camera)."""
    p = math.radians(-pitch)
    return [focus[0], focus[1] + dist * math.cos(p), focus[2] + dist * math.sin(p)], [pitch, yaw_cam, 0.0]


class Shots(cs.Capture):
    """control_scene.Capture with free camera placement (eye level / close-ups) and its own file prefix."""

    def __init__(self, ue, out_dir, tag, prefix):
        super().__init__(ue, out_dir, tag)
        self.prefix = prefix

    def free_shot(self, name, eye, rot, meta):
        cam = self.task("camera", label=cs.L_CAMERA, location=eye, rotation=rot, fov=cs.FOV)["camera"]
        xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        time.sleep(0.5)
        prev, settle = None, []
        import numpy as np
        from PIL import Image
        for attempt in range(3):
            im = self.grab(xform)
            if prev is not None:
                settle.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
            prev = im
            if attempt < 2:
                time.sleep(0.5)
        w, h = im.size
        ch = round(w * 9 / 16)
        box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else ((w - round(h * 16 / 9)) // 2, 0,
                                                                          (w + round(h * 16 / 9)) // 2, h)
        frame = im.crop(box).resize((1920, 1080), Image.LANCZOS)
        fname = "%s-%s-ue-editor.png" % (self.prefix, name)
        path = self.dir / fname
        frame.save(path, optimize=False)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        info = {"camera": cam, "viewport_px": [w, h], "crop_px": list(box), "output_px": [1920, 1080],
                "settle_mean_abs_diff": settle,
                "capture": "EditorAppToolset.CaptureViewport via MCP 127.0.0.1:8123 (piloted CameraActor, FOV 35 "
                           "horizontal, centred 16:9 crop resized to 1920x1080)",
                "exposure": "P17 post-process volume, histogram clamped to EV100 %.1f, bias 0" % cs.EV100, **meta}
        side = {"schema": cs.SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frameSha256": digest, "frame": fname,
                "label": "EDITOR frame (W5c H2 import, P1.7 Cobble stand), diagnostic; not K1/K2 acceptance",
                "run_tag": self.tag, **info}
        path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                              encoding="utf-8", newline="\n")
        self.frames[fname] = dict(info, sha256=digest)
        print(" ", fname, digest[:12], "settle", settle)
        return fname

    def board_shot(self, name, focus, dist, meta):
        eye, rot = cs.board_cam(focus, dist)
        return self.free_shot(name, eye, rot, dict(meta, focus=[round(v, 3) for v in focus], distance_uu=dist,
                                                   camera_model="board (UpdateBoardCamera): FOV 35, pitch -55"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", required=True)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--skeletal", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--mi", required=True, help="figure MI prefix: <mi>_<Team>, base <mi>_Base_<Team>")
    ap.add_argument("--teams", default="Blue,Red")
    ap.add_argument("--replace", default=None, help="P17 subject whose w4b figure is hidden (its cell is used)")
    ap.add_argument("--cell", default=None, help="x,y board cell when --replace is not given")
    ap.add_argument("--normal-texture", default=None, help="texture asset name for the DirectX/OpenGL A/B")
    ap.add_argument("--closeups", default=None, help="JSON list of {name, focus_local, dist, yaw, pitch}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    teams = [t for t in a.teams.split(",") if t]
    folder = a.folder.rstrip("/")
    sk, base = folder + "/Meshes/" + a.skeletal, folder + "/Meshes/" + a.base
    fig_mi = {t: folder + "/Materials/%s_%s" % (a.mi, t) for t in teams}
    base_mi = {t: folder + "/Materials/%s_Base_%s" % (a.mi, t) for t in teams}
    if a.replace:
        cell = cs.SUBJECTS[a.replace]["cell"]
        rule_yaw = cs.SUBJECTS[a.replace]["yaw"]
    else:
        cell = [int(v) for v in a.cell.split(",")]
        rule_yaw = 90 if cs.cell_world(cell)[1] < 0 else -90
    loc = cs.cell_world(cell)
    focus = [loc[0], loc[1], cs.FOCUS_Z]
    out = Path(a.out).resolve() / a.tag
    out.mkdir(parents=True, exist_ok=True)
    closeups = json.loads(Path(a.closeups).read_text(encoding="utf-8")) if a.closeups else []
    ue = Ue()
    cap = Shots(ue, out, a.tag, "w5c-%s-h2" % a.hero)
    lf, lb = L_FIG % a.hero, L_BASE % a.hero
    started = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    for p in [sk, base] + list(fig_mi.values()) + list(base_mi.values()):
        if not ue.call("asset", "exists", {"path": p}, record=False):
            raise SystemExit("asset missing: %s (run ue-import first)" % p)
    report = {"schema": SCHEMA, "tag": a.tag, "hero": a.hero, "started_at": started,
              "tool": "tools/tripo-pipeline/review/h2_ue_frames.py",
              "kind": "EDITOR frames (live UnrealEditor via MCP) on the saved P1.7 Cobble control level; nothing saved; "
                      "not packaged, no HUD, no boardState, no RENDER fingerprint, not K1/K2 acceptance",
              "original_level": original, "level": cs.LEVEL, "assets": {"skeletal": sk, "base": base,
                                                                        "figure_mis": fig_mi, "base_mis": base_mi},
              "cell": cell, "location": loc, "s08_rule_yaw": rule_yaw, "replaced_subject": a.replace,
              "camera_model": {"board": {"fov_horizontal_deg": cs.FOV, "pitch": cs.PITCH, "k2_1p6_uu": cs.K2_1P6,
                                         "k2_5x_uu": cs.K2_5X, "focus_offset_z_uu": cs.FOCUS_Z},
                               "eye": {"fov_horizontal_deg": cs.FOV, "pitch": EYE_PITCH, "distance_uu": EYE_DIST,
                                       "focus_z_uu": EYE_FOCUS_Z}},
              "console": [], "frames": {}}
    temp = [cs.L_CAMERA, lf, lb]
    normal_restore = None
    buffer_on = False
    try:
        ue.call("scene", "load_level", {"level_path": cs.LEVEL})
        time.sleep(3.0)
        report["loaded_level"] = ue.call("scene", "get_current_level", record=False)
        for flag in cs.SHOW_FLAGS_OFF:
            ue.console("ShowFlag.%s 0" % flag)
            report["console"].append("ShowFlag.%s 0" % flag)
        if a.replace:
            cap.task("set", changes=[{"label": lab, "visible": False} for lab in cs.labels(a.replace)])
            report["hidden_level_actors"] = cs.labels(a.replace)
        report["spawn"] = ue.run_task(str(HERE / "ue_py" / "frames_scene.py"), str(out / "_task.json"), timeout=300,
                                      op="setup", actors=[
                                          {"label": lf, "kind": "skeletal", "asset": pkg_obj(sk), "location": loc,
                                           "yaw": rule_yaw},
                                          {"label": lb, "kind": "static", "asset": pkg_obj(base), "location": loc,
                                           "yaw": rule_yaw}])
        report["sockets_world"] = cap.task("bones", label=lf, names=["SKEL_UM_Humanoid", "root", "head", "weapon_R",
                                                                     "hand_R", "Weapon", "Head"])
        time.sleep(8.0)
        # warm-up (streaming / shader compile after the level load): repeat until two captures agree
        eye, rot = cs.board_cam(focus, cs.K2_1P6)
        cap.task("camera", label=cs.L_CAMERA, location=eye, rotation=rot, fov=cs.FOV)
        xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        import numpy as np
        prev, warm = None, []
        for _ in range(20):
            im = cap.grab(xform)
            if prev is not None:
                d = float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean())
                warm.append(round(d, 4))
                if d < 0.02 and len(warm) >= 3:
                    break
            prev = im
            time.sleep(1.5)
        report["warmup_mean_abs_diff"] = warm

        def set_team(team):
            cap.task("set", changes=[{"label": lf, "materials": {"0": fig_mi[team]}},
                                     {"label": lb, "materials": {"0": base_mi[team]}}])

        def set_yaw(yaw):
            cap.task("set", changes=[{"label": lf, "yaw": yaw}, {"label": lb, "yaw": yaw}])

        eye_focus = [loc[0], loc[1], EYE_FOCUS_Z]
        for team in teams:
            set_team(team)
            set_yaw(rule_yaw)
            for tag, dist in (("k2-1p6", cs.K2_1P6), ("k2-5x", cs.K2_5X)):
                cap.board_shot("%s-%s" % (tag, team.lower()), focus, dist,
                               {"set": "k2", "team": team, "yaw": rule_yaw, "facing": "S08 rule of the cell"})
            for side, yaw in (("front", 90), ("side", 0), ("back", -90)):
                set_yaw(yaw)
                cap.board_shot("turn-5x-%s-%s" % (side, team.lower()), focus, cs.K2_5X,
                               {"set": "turn-5x", "team": team, "yaw": yaw, "view": side})
                e, r = eye_cam(eye_focus, EYE_DIST, EYE_PITCH)
                cap.free_shot("eye-%s-%s" % (side, team.lower()), e, r,
                              {"set": "eye", "team": team, "yaw": yaw, "view": side, "focus": eye_focus})
        set_team(teams[0])

        def closeup_shots(suffix, meta):
            names = []
            for c in closeups:
                set_yaw(c.get("yaw", 90))
                f = [loc[0] + c["focus_local"][0], loc[1] + c["focus_local"][1], c["focus_local"][2]]
                e, r = eye_cam(f, c["dist"], c.get("pitch", EYE_PITCH))
                names.append(cap.free_shot("close-%s%s" % (c["name"], suffix), e, r,
                                           dict(meta, set="close", closeup=c, focus=f)))
            return names

        report["closeups"] = closeup_shots("", {"team": teams[0]})
        # DirectX normal A/B: flip the green channel of the imported normal in memory, re-shoot, restore
        if a.normal_texture:
            tex = {"refPath": pkg_obj(folder + "/Textures/" + a.normal_texture)}
            before = ue.call("object", "get_properties", {"instance": tex, "properties": ["bFlipGreenChannel"]})
            before = json.loads(before) if isinstance(before, str) else before
            normal_restore = (tex, bool(before.get("bFlipGreenChannel")))
            ue.call("object", "set_properties", {"instance": tex, "values": json.dumps({"bFlipGreenChannel": True})})
            time.sleep(6.0)
            report["normal_ab"] = {"texture": tex["refPath"], "imported_bFlipGreenChannel": normal_restore[1],
                                   "flipped_frames": closeup_shots("-greenflip", {"team": teams[0],
                                                                                  "diagnostic": "bFlipGreenChannel TRUE "
                                                                                                "(OpenGL reading) in memory"})}
            ue.call("object", "set_properties", {"instance": tex, "values": json.dumps(
                {"bFlipGreenChannel": normal_restore[1]})})
            after = ue.call("object", "get_properties", {"instance": tex, "properties": ["bFlipGreenChannel"]})
            after = json.loads(after) if isinstance(after, str) else after
            report["normal_ab"]["restored_bFlipGreenChannel"] = after.get("bFlipGreenChannel")
            # the texture is this run's own asset: saved again with the imported value so the editor holds no dirty
            # package of ours (the bytes on disk change only by the re-save)
            tex_pkg = folder + "/Textures/" + a.normal_texture
            report["normal_ab"]["resaved"] = ue.call("asset", "save_assets", {"asset_paths": [tex_pkg]})
            normal_restore = None
            time.sleep(6.0)
        # buffer visualization of the close-ups (Metallic / Roughness / BaseColor)
        ue.console("ShowFlag.VisualizeBuffer 1")
        report["console"].append("ShowFlag.VisualizeBuffer 1")
        buffer_on = True
        report["buffers"] = {}
        for buf in BUFFERS:
            ue.console("r.BufferVisualizationTarget %s" % buf)
            report["console"].append("r.BufferVisualizationTarget %s" % buf)
            time.sleep(2.0)
            report["buffers"][buf] = closeup_shots("-buf-%s" % buf.lower(), {"team": teams[0], "buffer": buf})
    finally:
        try:
            if buffer_on:
                ue.console("ShowFlag.VisualizeBuffer 2")
                ue.console("r.BufferVisualizationTarget BaseColor")
                report["console"] += ["ShowFlag.VisualizeBuffer 2", "r.BufferVisualizationTarget BaseColor"]
        except Exception as exc:  # noqa: BLE001 - keep restoring
            report["buffer_restore_error"] = str(exc)
        if normal_restore is not None:
            try:
                ue.call("object", "set_properties", {"instance": normal_restore[0], "values": json.dumps(
                    {"bFlipGreenChannel": normal_restore[1]})})
                report["normal_restored_in_finally"] = True
            except Exception as exc:  # noqa: BLE001
                report["normal_restore_error"] = str(exc)
        try:
            report["cleanup"] = cap.task("cleanup", labels=temp)
        except Exception as exc:  # noqa: BLE001
            report["cleanup_error"] = str(exc)
        try:
            for flag in cs.SHOW_FLAGS_OFF:
                ue.console("ShowFlag.%s 2" % flag)
                report["console"].append("ShowFlag.%s 2" % flag)
        except Exception as exc:  # noqa: BLE001
            report["console_error"] = str(exc)
        ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
        time.sleep(2.0)
        report["restored_level"] = ue.call("scene", "get_current_level", record=False)
        report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]},
                                                 record=False)
        report["control_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": cs.LEVEL},
                                                             record=False)
        report["own_assets_dirty"] = {p: ue.call("asset", "is_dirty", {"asset_path": p}, record=False)
                                      for p in [sk, base, folder + "/Textures/" + (a.normal_texture or "")]
                                      if not p.endswith("/")}
        report["frames"] = cap.frames
        report["finished_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        for tmp in (out / "_task.json",):
            if tmp.exists():
                tmp.unlink()
        (out / "h2-ue-frames-report.json").write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
                                                      + "\n", encoding="utf-8", newline="\n")
        print("restored:", report["restored_level"], "dirty:", report["restored_level_dirty"])


if __name__ == "__main__":
    main()
