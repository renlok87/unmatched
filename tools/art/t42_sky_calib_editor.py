#!/usr/bin/env python3
"""Stage 3 T4.2 (ART-005, follow-up of W4-A): sky calibration of the Forest / Paddock light profiles rev 2 in EDITOR
scenes through MCP (live UnrealEditor of the main checkout, 127.0.0.1:8123, DX12/SM6 + Lumen since W5).

    python tools/art/t42_sky_calib_editor.py run --out <dir> [--profiles forest,paddock,cobble] [--repeats 3]
        [--sweep 8,12,16] [--refine 2]
    python tools/art/t42_sky_calib_editor.py restore       # back to /Game/S08/S08Arena, drop the scratch folder

Method = W4-A (K1 board luma against a target, 3 repeats, a difference counts only when |delta| > 2 x noise and
> 0.5 luma), done per profile in one editor setup so every number is comparable:
  * scene: a scratch copy (/Game/ArtTests/T42Calib) of the ART-005 review level that carries the profile's DX11-era
    editor probe (cobble <- ART005H/L_ART005H_CornerReview, forest / paddock <- ART005I/L_ART005I_*ReferenceLight:
    same Cobble 5x6 board, figures, zone marks and corners; only lights differ);
  * target ("legacy"): the level's own probe rig as authored (key pitch -55, a point 'fill' ambient in candelas,
    warm / secondary points, colours as the probe script set them), GI and reflections off (post-process override
    None = the DX11 editor had neither), exposure fixed at EV100 1.3 (histogram min = max = 2^1.3, bias 0; the P17
    control-scene exposure and the profile's exposure);
  * candidate ("rev2"): the review lights removed and the profile rev 2 rig placed exactly as the packaged client
    does (S08BoardActor::ApplyArtLights / S08PlaceLights on the 5x6 board: key FRotator(rotation[0..2]) in lux with
    the profile CSM, points in candelas at at*(W,H)*100, colours through FLinearColor::ToFColor(sRGB) like
    SetLightColor, a Movable SkyLight from TC_S08_AmbientDome with the swept intensity), Lumen on (project default),
    the same exposure;
  * frame: EditorAppToolset.CaptureViewport from the board camera direction of the packaged client (pitch -55,
    yaw -90, from +Y). The MCP viewport has a fixed horizontal FOV of 90 (a pilot camera needs editor Python, which
    this script does not use), so the distance is scaled to the same horizontal framing at the focus plane
    (1931 uu x tan 17.5 / tan 45 = 609 uu). Light and camera sprites are hidden (BillboardComponent.bVisible off);
    the frame is the centred 16:9 crop resized to 1920x1080; K1 board luma = p50 of Rec.709 luma in x 600-1360,
    y 700-940 (the W4-A box). Each repeat moves the camera away and back and re-captures until two consecutive
    captures differ by < 0.05 mean |dRGB| (Lumen / TSR history settled).
Editor frames are diagnostics (class editor-mcp-viewport), never K1 acceptance; the packaged confirmation is done
separately (bench with override profiles + a live pair on each board).

Nothing outside /Game/ArtTests/T42Calib is saved: each profile gets a fresh scratch copy (suffix --tag); a dirty
scratch level is saved before the next level switch so the editor never raises a save dialog (a modal would block
MCP). `restore` reloads /Game/S08/S08Arena and deletes the scratch folder; the editor may keep the last scratch map
in memory until it restarts (then the delete is retried by running `restore` again).
The packaged confirmation of the resulting skies is tools/art/t42_bench_confirm.py (the editor viewport runs Epic
scalability, the reference is High).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "tripo-pipeline" / "review"))
from ue_live import Ue, UeError  # noqa: E402

PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
SCRATCH = "/Game/ArtTests/T42Calib"
HOME_LEVEL = "/Game/S08/S08Arena"
SOURCES = {
    "cobble": {"level": "/Game/ArtTests/ART005H/L_ART005H_CornerReview", "light": "cobble-probe",
               "dx11Frame": "docs/game-design/evidence/ART-005/stone-corner-combined-k1-editor-2026-09-28.png"},
    "forest": {"level": "/Game/ArtTests/ART005I/L_ART005I_ForestReferenceLight", "light": "forest-probe",
               "dx11Frame": "docs/game-design/evidence/ART-005/stone-forestProbe-combined-k1-editor-2026-09-28.png"},
    "paddock": {"level": "/Game/ArtTests/ART005I/L_ART005I_PaddockReferenceLight", "light": "paddock-probe",
                "dx11Frame": "docs/game-design/evidence/ART-005/stone-paddockProbe-combined-k1-editor-2026-09-28.png"},
}
REVIEW_LIGHT_LABELS = ("ART005 cool scene key - proposed", "ART005 neutral readability fill - review only",
                       "ART005 warm lantern accent - proposed", "ART005I extra light ")
REVIEW_CAMERA_LABEL = "ART005 K1 review camera"
BOARD_W, BOARD_H, CELL = 5, 6, 100.0  # the Cobble 5x6 board of the ART-005 review levels
FOV_LIVE, K1_LIVE, PITCH, YAW = 35.0, 1931.0, -55.0, -90.0
EXPOSURE = {"min": round(2 ** 1.3, 5), "bias": 0.0}
BOARD_K1_BOX = (600, 700, 1360, 940)
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}
SETTLE_SPAN, SETTLE_MIN, SETTLE_MAX = 0.2, 5, 30
# P17 control stand (T3.1, the W4-A Cobble target): the review fill moved to (0, 100, 500); the ART-005 / ART-005I
# levels keep it at (0, -100, 550). The targets use the P17 stand for all three probes (the W4-A basis); the level
# position is shot once as a sensitivity row.
P17_FILL = (0.0, 100.0, 500.0)
FILL_LABEL = "ART005 neutral readability fill - review only"
LUMA_FLOOR = 0.5
SIDECAR_SCHEMA = "unmatched.evidence-frame/1"
SCHEMA = "unmatched.t42-sky-calib-editor/1"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def srgb_byte_norm(v: float) -> float:
    """FLinearColor::ToFColor(bSRGB = true) channel -> byte / 255 (what SetLightColor stores; the renderer decodes it
    back with the sRGB table, so the light gets the profile's linear colour)."""
    x = min(max(float(v), 0.0), 1.0)
    x = x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1.0 / 2.4) - 0.055
    return math.floor(x * 255.999) / 255.0


def color_norm(lin) -> dict:
    return {"r": srgb_byte_norm(lin[0]), "g": srgb_byte_norm(lin[1]), "b": srgb_byte_norm(lin[2]), "a": 1.0}


def place(spec: dict) -> list[float]:
    """S08PlaceLights for the 5x6 board: posUU as is, else at * (W, H) * 100 and the given z."""
    if "posUU" in spec:
        return [float(v) for v in spec["posUU"]]
    at = spec["at"]
    return [at[0] * BOARD_W * CELL, at[1] * BOARD_H * CELL, float(at[2])]


def board_camera(dist: float) -> dict:
    p = math.radians(-PITCH)
    return {"location": {"x": 0.0, "y": dist * math.cos(p), "z": dist * math.sin(p)},
            "rotation": {"pitch": PITCH, "yaw": YAW, "roll": 0.0}, "scale": {"x": 1, "y": 1, "z": 1}}


def luma_of(im) -> dict:
    import numpy as np
    a = np.asarray(im.convert("RGB")).astype(np.float64)
    L = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    x0, y0, x1, y1 = BOARD_K1_BOX
    roi = L[y0:y1, x0:x1]
    return {"boardK1P50": round(float(np.percentile(roi, 50)), 2), "boardK1Mean": round(float(roi.mean()), 2),
            "boardK1P10": round(float(np.percentile(roi, 10)), 2), "boardK1P90": round(float(np.percentile(roi, 90)), 2),
            "frameP50": round(float(np.percentile(L, 50)), 2)}


class Editor:
    def __init__(self):
        self.ue = Ue()

    def call(self, ts, tool, args=None, record=True):
        return self.ue.call(ts, tool, args or {}, record=record)

    def ref(self, r):
        return r["refPath"] if isinstance(r, dict) else r

    def actors(self, name=""):
        res = self.call("scene", "find_actors", {"root": None, "name": name, "actor_type": None, "tag": None,
                                                 "bounds": None, "collision_channels": None}, record=False)
        return [self.ref(a) for a in res or []]

    def label(self, actor):
        return self.call("actor", "get_label", {"actor": {"refPath": actor}}, record=False)

    def components(self, actor):
        res = self.call("actor", "get_components", {"actor": {"refPath": actor}, "component_type": None}, record=False)
        return [self.ref(c) for c in res or []]

    def setp(self, ref, values: dict):
        return self.call("object", "set_properties", {"instance": {"refPath": ref}, "values": json.dumps(values)})

    def getp(self, ref, names):
        return self.call("object", "get_properties", {"instance": {"refPath": ref}, "properties": names}, record=False)

    def spawn(self, cls, name, loc, rot=(0.0, 0.0, 0.0)):
        a = self.call("scene", "add_to_scene_from_class", {
            "actor_type": {"refPath": cls}, "name": name,
            "xform": {"location": dict(zip("xyz", loc)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                      "scale": {"x": 1, "y": 1, "z": 1}}})
        return self.ref(a)

    def remove(self, actor):
        return self.call("scene", "remove_from_scene", {"actor": {"refPath": actor}})

    def light_component(self, actor):
        for c in self.components(actor):
            leaf = c.rsplit(".", 1)[-1]
            if "LightComponent" in leaf:
                return c
        raise UeError(f"no light component on {actor}")

    def hide_sprites(self, actor):
        hidden = 0
        for c in self.components(actor):
            leaf = c.rsplit(".", 1)[-1]
            if leaf.startswith("BillboardComponent") or leaf == "Sprite" or leaf.startswith("ArrowComponent") \
                    or leaf.startswith("DrawFrustumComponent") or leaf.startswith("CameraProxyMeshComponent"):
                self.setp(c, {"bVisible": False})
                hidden += 1
        return hidden

    def grab(self, xform):
        from PIL import Image
        res = self.call("app", "CaptureViewport", {"captureTransform": xform, "annotations": NOANN, "bShowUI": False},
                        record=False)
        v = res["value"] if isinstance(res, dict) and "value" in res else res
        img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
        meta = {k: v[k] for k in ("cameraLocation", "cameraRotation", "cameraFOV") if isinstance(v, dict) and k in v}
        return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGB"), meta


def crop_16_9(im):
    from PIL import Image
    w, h = im.size
    ch = round(w * 9 / 16)
    box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else ((w - round(h * 16 / 9)) // 2, 0,
                                                                      (w + round(h * 16 / 9)) // 2, h)
    return im.crop(box).resize((1920, 1080), Image.LANCZOS), box


class Calib:
    def __init__(self, ed: Editor, out: Path, profiles: dict, dist: float, tag: str):
        self.ed, self.out, self.profiles, self.dist, self.tag = ed, out, profiles, dist, tag
        self.xform = board_camera(dist)
        self.away = board_camera(dist * 1.6)
        self.frames = []

    # ---------------------------------------------------------------- scene
    def open_level(self, key: str) -> dict:
        src = SOURCES[key]["level"]
        dst = f"{SCRATCH}/L_T42_{key.capitalize()}_{self.tag}"
        cur = self.ed.call("scene", "get_current_level", record=False).split(".")[0]
        if cur.startswith(SCRATCH) and self.ed.call("asset", "is_dirty", {"asset_path": cur}, record=False):
            # a scratch level with in-memory rigs: save it (scratch only) so the level switch never asks the editor
            # user about unsaved changes (a modal dialog would block MCP)
            self.ed.call("asset", "save_assets", {"asset_paths": [cur]})
        if self.ed.call("asset", "exists", {"path": dst}):
            raise SystemExit(f"REFUSED: {dst} exists; use a new --tag")
        self.ed.call("asset", "duplicate", {"path": src, "new_path": dst})
        self.ed.call("asset", "save_assets", {"asset_paths": [dst]})
        self.ed.call("scene", "load_level", {"level_path": dst})
        time.sleep(3.0)
        return {"source": src, "scratch": dst, "fresh": True}

    def common_prep(self) -> dict:
        info = {"hiddenSprites": 0, "removed": [], "reviewLights": {}}
        for a in self.ed.actors():
            lb = self.ed.label(a)
            if lb.startswith(REVIEW_CAMERA_LABEL):
                self.ed.remove(a)
                info["removed"].append(lb)
                continue
            if any(lb.startswith(x) for x in REVIEW_LIGHT_LABELS):
                lc = self.ed.light_component(a)
                info["reviewLights"][lb] = {"actor": a.rsplit(".", 1)[-1], **self.ed.getp(lc, [
                    n for n in ("intensity", "intensityUnits", "lightColor", "attenuationRadius", "castShadows")
                    if not (n in ("intensityUnits", "attenuationRadius") and "Directional" in a)])}
                info["reviewLights"][lb]["transform"] = self.ed.call("actor", "get_actor_transform",
                                                                     {"actor": {"refPath": a}}, record=False)
                info["hiddenSprites"] += self.ed.hide_sprites(a)
        for a in self.ed.actors("T42 "):
            self.ed.remove(a)  # leftovers of an interrupted run (scratch level only)
        self.ppv = self.ed.spawn("/Script/Engine.PostProcessVolume", "T42 exposure EV100 1.3", (0.0, 0.0, -5000.0))
        self.ed.setp(self.ppv, {"bUnbound": True, "priority": 100.0, "blendWeight": 1.0, "settings": {
            "bOverride_AutoExposureMethod": True, "autoExposureMethod": "AEM_Histogram",
            "bOverride_AutoExposureMinBrightness": True, "autoExposureMinBrightness": EXPOSURE["min"],
            "bOverride_AutoExposureMaxBrightness": True, "autoExposureMaxBrightness": EXPOSURE["min"],
            "bOverride_AutoExposureBias": True, "autoExposureBias": EXPOSURE["bias"]}})
        return info

    def set_legacy_gi(self, legacy: bool):
        self.ed.setp(self.ppv, {"settings": {
            "bOverride_AutoExposureMethod": True, "autoExposureMethod": "AEM_Histogram",
            "bOverride_AutoExposureMinBrightness": True, "autoExposureMinBrightness": EXPOSURE["min"],
            "bOverride_AutoExposureMaxBrightness": True, "autoExposureMaxBrightness": EXPOSURE["min"],
            "bOverride_AutoExposureBias": True, "autoExposureBias": EXPOSURE["bias"],
            "bOverride_DynamicGlobalIlluminationMethod": legacy, "dynamicGlobalIlluminationMethod": "None",
            "bOverride_ReflectionMethod": legacy, "reflectionMethod": "None"}})

    def move_fill(self, loc) -> dict:
        for a in self.ed.actors():
            if self.ed.label(a) == FILL_LABEL:
                self.ed.call("actor", "set_actor_transform", {"actor": {"refPath": a}, "worldspace": True,
                                                               "xform": {"location": dict(zip("xyz", loc))}})
                return self.ed.call("actor", "get_actor_transform", {"actor": {"refPath": a}}, record=False)
        raise UeError("fill light not found")

    def remove_review_lights(self) -> list:
        gone = []
        for a in self.ed.actors():
            lb = self.ed.label(a)
            if any(lb.startswith(x) for x in REVIEW_LIGHT_LABELS):
                self.ed.remove(a)
                gone.append(lb)
        return gone

    def spawn_rev2(self, light_id: str, sky_intensity: float, key_rotation=None) -> dict:
        lp = self.profiles["lightProfiles"][light_id]
        d = lp["directional"]
        rot = key_rotation or d.get("rotation", [0, 0, 0])
        # ParseLight: FRotator(rotation[0], rotation[1], rotation[2]) = (Pitch, Yaw, Roll)
        key = self.ed.spawn("/Script/Engine.DirectionalLight", "T42 rev2 key", place(d), (rot[0], rot[1], rot[2]))
        kc = self.ed.light_component(key)
        sh = d.get("shadow") or {}
        self.ed.setp(kc, {"mobility": "Movable", "intensity": float(d["intensity"]),
                          "lightColor": color_norm(d.get("colorLinear", [1, 1, 1])),
                          "castShadows": bool(d.get("castShadows", True)),
                          "dynamicShadowDistanceMovableLight": float(sh.get("distanceUU", 20000.0)),
                          "dynamicShadowCascades": int(sh.get("cascades", 3)),
                          "contactShadowLength": float(sh.get("contactShadowLength", 0.0))})
        self.ed.hide_sprites(key)
        rig = {"key": {"actor": key.rsplit(".", 1)[-1], "pos": place(d), "rotationPYR": rot,
                       "readback": self.ed.getp(kc, ["intensity", "lightColor", "castShadows",
                                                      "dynamicShadowDistanceMovableLight", "dynamicShadowCascades"])},
               "points": []}
        for pt in lp.get("points") or []:
            a = self.ed.spawn("/Script/Engine.PointLight", f"T42 rev2 {pt['name']}", place(pt))
            c = self.ed.light_component(a)
            self.ed.setp(c, {"mobility": "Movable", "intensityUnits": "Candelas", "intensity": float(pt["intensity"]),
                             "attenuationRadius": float(pt["radiusUU"]),
                             "lightColor": color_norm(pt.get("colorLinear", [1, 1, 1])),
                             "castShadows": bool(pt.get("castShadows", False))})
            self.ed.hide_sprites(a)
            rig["points"].append({"name": pt["name"], "pos": place(pt), "readback": self.ed.getp(
                c, ["intensityUnits", "intensity", "attenuationRadius", "lightColor"])})
        s = lp["sky"]
        sky = self.ed.spawn("/Script/Engine.SkyLight", "T42 rev2 sky", (0.0, 0.0, -3000.0))
        self.sky_component = self.ed.light_component(sky)
        cube = s["cubemap"]
        self.ed.setp(self.sky_component, {
            "mobility": "Movable", "sourceType": "SLS_SpecifiedCubemap", "bRealTimeCapture": False,
            "cubemap": {"refPath": "%s.%s" % (cube, cube.rsplit("/", 1)[-1])},
            "bLowerHemisphereIsBlack": bool(s.get("lowerHemisphereIsBlack", False)),
            "lightColor": color_norm(s.get("colorLinear", [1, 1, 1])), "intensity": float(sky_intensity)})
        self.ed.hide_sprites(sky)
        rig["sky"] = {"actor": sky.rsplit(".", 1)[-1], "readback": self.ed.getp(
            self.sky_component, ["sourceType", "cubemap", "intensity", "lightColor", "bLowerHemisphereIsBlack"])}
        self.rig_actors = [key, sky] + [a for a in self.ed.actors("T42 rev2 ") if a not in (key, sky)]
        return rig

    def clear_rev2(self):
        for a in self.ed.actors("T42 rev2 "):
            self.ed.remove(a)

    def set_sky(self, value: float):
        self.ed.setp(self.sky_component, {"intensity": float(value)})

    # ---------------------------------------------------------------- frames
    def settle(self):
        """Capture until the K1 board p50 of the last 3 captures spans < SETTLE_SPAN luma (at least SETTLE_MIN
        captures). Lumen and TSR keep a small per-frame noise in the live viewport (mean |dRGB| 0.1-0.9 between
        consecutive captures, measured 2026-09-29), so pixel identity is never reached; the ROI median is."""
        import numpy as np
        prev, diffs, p50s = None, [], []
        for i in range(SETTLE_MAX):
            im, meta = self.ed.grab(self.xform)
            p50s.append(luma_of(crop_16_9(im)[0])["boardK1P50"])
            if prev is not None:
                diffs.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
            prev = im
            if i + 1 >= SETTLE_MIN and max(p50s[-3:]) - min(p50s[-3:]) < SETTLE_SPAN:
                return im, meta, {"meanAbsDiff": diffs, "p50": p50s}, True
            time.sleep(0.6)
        return im, meta, {"meanAbsDiff": diffs, "p50": p50s}, False

    def shot(self, name: str, meta_extra: dict) -> dict:
        self.ed.grab(self.away)  # break the view history: each repeat re-converges independently
        time.sleep(0.4)
        im, meta, diffs, settled = self.settle()
        frame, box = crop_16_9(im)
        raw = self.out / "frames"
        raw.mkdir(parents=True, exist_ok=True)
        path = raw / f"{name}-ue-editor.png"
        buf = io.BytesIO()
        frame.save(buf, format="PNG", optimize=False)
        data = buf.getvalue()
        path.write_bytes(data)
        lum = luma_of(frame)
        side = {"schema": SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frame": path.name,
                "frameSha256": sha256_bytes(data),
                "label": "EDITOR frame (T4.2 sky calibration scene), diagnostic; not K1 acceptance",
                "capture": "EditorAppToolset.CaptureViewport via MCP 127.0.0.1:8123, level viewport horizontal FOV "
                           f"{meta.get('cameraFOV')}, board camera direction pitch {PITCH} yaw {YAW} at {self.dist:.1f} uu, "
                           "sprites hidden, centred 16:9 crop resized to 1920x1080",
                "viewportPx": list(im.size), "cropPx": list(box), "camera": meta, "settle": diffs,
                "settled": settled, "luma": lum, **meta_extra}
        path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                                encoding="utf-8", newline="\n")
        row = {"frame": path.name, "sha256": side["frameSha256"], "settled": settled, "settleSteps": len(diffs["p50"]),
               **lum, **meta_extra}
        self.frames.append(row)
        print(f"  {name}: K1 p50 {lum['boardK1P50']} mean {lum['boardK1Mean']} settle {len(diffs['p50'])} "
              f"{'ok' if settled else 'NOT SETTLED'}", flush=True)
        return row


def stats(vals: list[float]) -> dict:
    return {"n": len(vals), "mean": round(sum(vals) / len(vals), 3), "min": min(vals), "max": max(vals),
            "noise": round(max(vals) - min(vals), 3), "values": vals}


def interpolate(points: list[tuple[float, float]], target: float) -> float | None:
    """Sky intensity at which the (monotonic) luma curve crosses target, piecewise linear."""
    pts = sorted(points)
    for (s0, l0), (s1, l1) in zip(pts, pts[1:]):
        if (l0 - target) * (l1 - target) <= 0 and l1 != l0:
            return s0 + (target - l0) * (s1 - s0) / (l1 - l0)
    if len(pts) >= 2:  # extrapolate from the nearest segment
        (s0, l0), (s1, l1) = (pts[0], pts[1]) if target < pts[0][1] else (pts[-2], pts[-1])
        if l1 != l0:
            return s0 + (target - l0) * (s1 - s0) / (l1 - l0)
    return None


def dx11_reference(rel: str) -> dict:
    from PIL import Image
    p = REPO / rel
    if not p.is_file():
        return {"frame": rel, "missing": True}
    im = Image.open(p).convert("RGB")
    return {"frame": rel, "sha256": sha256_bytes(p.read_bytes()), **luma_of(im),
            "note": "ART-005/ART-005I DX11 editor frame (SceneCapture FOV 35 from -Y, own exposure): a different "
                    "camera and exposure, so only the ratios between the three probes are comparable"}


def cmd_run(a) -> int:
    profiles = json.loads(Path(a.profiles).read_text(encoding="utf-8"))
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ed = Editor()
    original = ed.call("scene", "get_current_level", record=False)
    if ed.call("asset", "is_dirty", {"asset_path": original.split(".")[0]}, record=False) and \
            not original.split(".")[0].startswith(SCRATCH):
        raise SystemExit(f"REFUSED: the open level {original} has unsaved changes")
    dist = K1_LIVE * math.tan(math.radians(FOV_LIVE / 2)) / math.tan(math.radians(45.0))
    cal = Calib(ed, out, profiles, dist, a.tag)
    sweep = [float(x) for x in a.sweep.split(",")]
    rep = {"schema": SCHEMA, "tool": "tools/art/t42_sky_calib_editor.py run",
           "startedUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "originalLevel": original, "profilesFile": str(Path(a.profiles).relative_to(REPO)).replace("\\", "/"),
           "profilesSha256": sha256_bytes(Path(a.profiles).read_bytes()),
           "camera": {"pitch": PITCH, "yaw": YAW, "distanceUU": round(dist, 2), "viewportFovDeg": 90,
                      "equivalent": f"live K1 FOV {FOV_LIVE} at {K1_LIVE} uu (same horizontal framing at the focus)"},
           "exposure": {"method": "histogram-fixed", "minMaxBrightness": EXPOSURE["min"], "bias": EXPOSURE["bias"],
                        "ev100": 1.3}, "roi": {"boardK1Box": BOARD_K1_BOX}, "repeats": a.repeats,
           "decisionRule": f"match when |rev2 - target| <= 2 x max(noise) and <= {LUMA_FLOOR}... else refine",
           "profiles": {}}
    try:
        for key in [k.strip() for k in a.profiles_list.split(",") if k.strip()]:
            src = SOURCES[key]
            print(f"== {key}", flush=True)
            prof = {"light": src["light"], "level": cal.open_level(key)}
            prof["prep"] = cal.common_prep()
            prof["dx11Reference"] = dx11_reference(src["dx11Frame"])
            # target: the DX11-era probe rig, GI / reflections off; sensitivity row first (level fill position)
            cal.set_legacy_gi(True)
            time.sleep(1.0)
            lv = cal.shot(f"t42-{key}-legacy-levelfill", {"profile": key, "mode": "legacy-probe-level-fill",
                                                          "fill": "level (0,-100,550)", "repeat": 1})["boardK1P50"]
            prof["legacyLevelFill"] = {"fillPosition": [0.0, -100.0, 550.0], "boardK1P50": lv}
            prof["fillMovedTo"] = cal.move_fill(P17_FILL)
            tgt = [cal.shot(f"t42-{key}-legacy-r{r}", {"profile": key, "mode": "legacy-probe", "fill": "P17 (0,100,500)",
                                                      "repeat": r})["boardK1P50"]
                   for r in range(1, a.repeats + 1)]
            prof["target"] = stats(tgt)
            # candidate: packaged-faithful rev 2 rig, Lumen on
            prof["removedReviewLights"] = cal.remove_review_lights()
            cal.set_legacy_gi(False)
            current = float(profiles["lightProfiles"][src["light"]]["sky"]["intensity"])
            prof["rig"] = cal.spawn_rev2(src["light"], sweep[0])
            curve = []
            for s in sorted(set(sweep + [current])):
                cal.set_sky(s)
                v = cal.shot(f"t42-{key}-rev2-sky{s:g}-sweep", {"profile": key, "mode": "rev2", "sky": s,
                                                                "repeat": 1})["boardK1P50"]
                curve.append((s, v))
            target = prof["target"]["mean"]
            for i in range(a.refine):
                s = interpolate(curve, target)
                if s is None:
                    break
                s = round(s, 2)
                if any(abs(s - c[0]) < 0.05 for c in curve):
                    break
                cal.set_sky(s)
                v = cal.shot(f"t42-{key}-rev2-sky{s:g}-refine{i + 1}", {"profile": key, "mode": "rev2", "sky": s,
                                                                         "repeat": 1})["boardK1P50"]
                curve.append((s, v))
            final = round(interpolate(curve, target) or current, 1)
            # one 0.1 step check around the rounded value: keep the closer of the two (curve is monotonic)
            if all(abs(final - c[0]) > 0.01 for c in curve):
                cal.set_sky(final)
                curve.append((final, cal.shot(f"t42-{key}-rev2-sky{final:g}-check", {"profile": key, "mode": "rev2",
                                                                                     "sky": final, "repeat": 1})["boardK1P50"]))
            got = dict(curve)[final]
            nxt = round(final + (0.1 if got < target else -0.1), 1)
            if all(abs(nxt - c[0]) > 0.01 for c in curve):
                cal.set_sky(nxt)
                curve.append((nxt, cal.shot(f"t42-{key}-rev2-sky{nxt:g}-check", {"profile": key, "mode": "rev2",
                                                                                 "sky": nxt, "repeat": 1})["boardK1P50"]))
            final = min((final, nxt), key=lambda s: abs(dict(curve)[s] - target))
            prof["curve"] = [{"sky": s, "boardK1P50": v} for s, v in sorted(curve)]
            cal.set_sky(final)
            fin = [cal.shot(f"t42-{key}-rev2-sky{final:g}-r{r}", {"profile": key, "mode": "rev2-final", "sky": final,
                                                                  "repeat": r})["boardK1P50"]
                   for r in range(1, a.repeats + 1)]
            prof["final"] = {"sky": final, **stats(fin)}
            if key == "cobble":
                cal.set_sky(current)
                cur = [cal.shot(f"t42-{key}-rev2-sky{current:g}-shipped-r{r}", {"profile": key, "mode": "rev2-shipped",
                                                                                  "sky": current, "repeat": r})["boardK1P50"]
                       for r in range(1, a.repeats + 1)]
                prof["shipped"] = {"sky": current, **stats(cur)}
            # diagnostic: the same rig with the editor probe's key orientation (pitch -55, yaw 30)
            if a.key_diagnostic:
                cal.clear_rev2()
                prof["rigKeyPitch55"] = cal.spawn_rev2(src["light"], final, key_rotation=[-55.0, 30.0, 0.0])
                dg = [cal.shot(f"t42-{key}-rev2-sky{final:g}-keypitch55-r{r}", {"profile": key,
                                                                                 "mode": "rev2-key-pitch-55",
                                                                                 "sky": final, "repeat": r})["boardK1P50"]
                      for r in range(1, 2)]
                prof["keyPitch55Diagnostic"] = {"sky": final, **stats(dg)}
            noise = max(prof["target"]["noise"], prof["final"]["noise"])
            delta = round(prof["final"]["mean"] - target, 3)
            prof["verdict"] = {"delta": delta, "threshold": round(max(2 * noise, LUMA_FLOOR), 3),
                               "matched": abs(delta) <= max(2 * noise, LUMA_FLOOR)}
            rep["profiles"][key] = prof
            write_json(out / "t42-sky-calib-editor.json", dict(rep, frames=cal.frames))
    finally:
        rep["frames"] = cal.frames
        rep["finishedUtc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        rep["mcpCalls"] = len(ed.ue.calls)
        write_json(out / "t42-sky-calib-editor.json", rep)
    print(json.dumps({k: {"target": v["target"]["mean"], "final": v.get("final"), "verdict": v.get("verdict")}
                      for k, v in rep["profiles"].items()}, ensure_ascii=False, indent=1))
    return 0


def cmd_restore(a) -> int:
    ed = Editor()
    cur = ed.call("scene", "get_current_level", record=False).split(".")[0]
    steps = {"current": cur}
    if cur.startswith(SCRATCH):
        # the scratch level carries in-memory rigs: save it (scratch only) so the level switch has nothing to ask
        ed.call("asset", "save_assets", {"asset_paths": [cur]})
    ed.call("scene", "load_level", {"level_path": HOME_LEVEL})
    steps["loaded"] = ed.call("scene", "get_current_level", record=False)
    if ed.call("asset", "exists", {"path": SCRATCH}):
        steps["deleted"] = ed.call("asset", "delete", {"path": SCRATCH})
    steps["scratchExists"] = ed.call("asset", "exists", {"path": SCRATCH})
    print(json.dumps(steps, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--profiles", default=str(PROFILES))
    r.add_argument("--profiles-list", default="cobble,forest,paddock")
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--sweep", default="8,12,16")
    r.add_argument("--refine", type=int, default=2)
    r.add_argument("--key-diagnostic", action="store_true")
    r.add_argument("--tag", default=dt.datetime.now().strftime("%H%M%S"), help="suffix of this run's scratch levels")
    sub.add_parser("restore")
    a = ap.parse_args(argv)
    return {"run": cmd_run, "restore": cmd_restore}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
