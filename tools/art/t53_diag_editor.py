#!/usr/bin/env python3
"""W5b-R step 2: short diagnostics in the LIVE editor of the main checkout (MCP 127.0.0.1:8123, no mouse/keyboard, no
focus): (a) A/B of the team disc/ring height on a stone tile (z-fighting hypothesis of act T5.2 §4.9), (b) the sRGB
bytes that the unlit game layer really puts on screen for the team fills, the keyline and the zone colours (so the
colour tolerance of the re-shoot is registered BEFORE the shots), (c) a sheet of six figures with the new rings,
zone keylines and the target token for the art look (step 9). Editor frames are diagnostics (class
editor-mcp-viewport), never K1-K3 evidence.

    python tools/art/t53_diag_editor.py run --out <evidence>/diag
    python tools/art/t53_diag_editor.py restore        # back to /Game/S08/S08Arena, drop /Game/ArtTests/T53Diag

Scene: a scratch copy of the (empty) arena level, /Game/ArtTests/T53Diag/L_T53Diag, so the live level never gets dirty.
Light: the forest-probe rig of S08ArtBoardProfiles.json as the packaged client places it (key FRotator(rotation) in lux
with its CSM, the Movable SkyLight TC_S08_AmbientDome, the fixed exposure EV100 1.3) - through t42's Editor helpers.
Tiles: /Engine/BasicShapes/Cube scaled like the client's 'tiles' slab (0.92 x 0.92 x 0.1, top at z = 0) with
M_ART005_Stone_Probe. Camera: the packaged K1 direction (pitch -55, yaw -90); the MCP viewport has a horizontal FOV of
90, so the distance is scaled to the K1 framing of a 7x5/8x5 fixture (1672 uu at FOV 35 -> 527 uu).
Scratch MIs (not saved, deleted by restore): the old disc tint (game-layer 'Tint' (0.02, 0.25, 1.5)), Silver fill.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import t42_sky_calib_editor as K  # noqa: E402  (Editor, color_norm, crop_16_9, write_json)
import t53_team_ring as R  # noqa: E402

SCRATCH = "/Game/ArtTests/T53Diag"
LEVEL = f"{SCRATCH}/L_T53Diag"
HOME = "/Game/S08/S08Arena"
CUBE = "/Engine/BasicShapes/Cube"
CYL = "/Engine/BasicShapes/Cylinder"
STONE = "/Game/ArtTests/ART005/Materials/M_ART005_Stone_Probe"
GAME_LAYER_OLD = "/Game/S08/Render/M_S08_GameLayerUnlit"
MASTER = "/Game/UM/Materials/M_UM_GameLayer"
PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
FOV_RATIO = math.tan(math.radians(17.5)) / math.tan(math.radians(45.0))
K1_DIST = 1672.0  # SetupCameraForBoard of the 8x5 / 7x5 fixtures (FOV 35)


def objp(pkg: str) -> str:
    return "%s.%s" % (pkg, pkg.rsplit("/", 1)[-1])


def lin_hex(hexc: str) -> list[float]:
    return R.hex_to_linear(hexc)


def srgb_bytes_lab(rgb):
    sys.path.insert(0, str(HERE / "qa010"))
    import numpy as np
    from qa010lib import color as C
    a = np.asarray(rgb, dtype=np.uint8).reshape(1, 1, 3)
    return [float(x) for x in C.linear_to_lab(C.u8_to_linear(a))[0, 0]]


def de76(a, b) -> float:
    la, lb = srgb_bytes_lab(a), srgb_bytes_lab(b)
    return round(math.sqrt(sum((x - y) ** 2 for x, y in zip(la, lb))), 2)


def hex_rgb(h: str) -> list[int]:
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


class Diag:
    def __init__(self, out: Path):
        self.ed = K.Editor()
        self.out = out
        self.actors = []
        self.profiles = json.loads(PROFILES.read_text(encoding="utf-8"))

    def mesh_actor(self, name, mesh, loc, scale, material=None, rot=(0.0, 0.0, 0.0)):
        a = self.ed.call("scene", "add_to_scene_from_asset", {
            "asset_path": mesh, "name": name,
            "xform": {"location": dict(zip("xyz", loc)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                      "scale": dict(zip("xyz", scale))}, "parent": None, "snap_to_ground": False})
        a = self.ed.ref(a)
        self.actors.append(a)
        if material:
            comps = [c for c in self.ed.components(a) if "StaticMeshComponent" in c.rsplit(".", 1)[-1]]
            mats = material if isinstance(material, list) else [material]
            self.ed.setp(comps[0], {"OverrideMaterials": [{"refPath": objp(m)} for m in mats]})
        return a

    def scratch_mi(self, name, parent, vectors: dict):
        pkg = f"{SCRATCH}/{name}"
        if not self.ed.call("asset", "exists", {"path": pkg}):
            self.ed.call("instance", "create", {"folder_path": SCRATCH, "asset_name": name,
                                                "parent": {"refPath": objp(parent)}})
        for k, v in vectors.items():
            self.ed.call("instance", "set_vector_parameter", {"instance": {"refPath": objp(pkg)}, "name": k,
                                                               "value": dict(zip("rgba", v))})
        return pkg

    def open(self) -> dict:
        cur = self.ed.call("scene", "get_current_level").split(".")[0]
        if cur != HOME and not cur.startswith(SCRATCH):
            raise SystemExit(f"REFUSED: the live editor shows {cur}, not {HOME} (another session works in it)")
        if self.ed.call("asset", "is_dirty", {"asset_path": HOME}):
            raise SystemExit(f"REFUSED: {HOME} has unsaved changes (another session); nothing touched")
        if not self.ed.call("asset", "exists", {"path": LEVEL}):
            self.ed.call("asset", "duplicate", {"path": HOME, "new_path": LEVEL})
            self.ed.call("asset", "save_assets", {"asset_paths": [LEVEL]})
        self.ed.call("scene", "load_level", {"level_path": LEVEL})
        time.sleep(3.0)
        return {"home": HOME, "scratch": LEVEL}

    def light_rig(self, light_id="forest-probe") -> dict:
        lp = self.profiles["lightProfiles"][light_id]
        d = lp["directional"]
        rot = d["rotation"]
        key = self.ed.spawn("/Script/Engine.DirectionalLight", "T53 key", K.place(d), (rot[0], rot[1], rot[2]))
        self.actors.append(key)
        kc = self.ed.light_component(key)
        self.ed.setp(kc, {"mobility": "Movable", "intensity": float(d["intensity"]),
                          "lightColor": K.color_norm(d.get("colorLinear", [1, 1, 1])), "castShadows": True})
        self.ed.hide_sprites(key)
        s = lp["sky"]
        sky = self.ed.spawn("/Script/Engine.SkyLight", "T53 sky", (0.0, 0.0, -3000.0))
        self.actors.append(sky)
        sc = self.ed.light_component(sky)
        self.ed.setp(sc, {"mobility": "Movable", "sourceType": "SLS_SpecifiedCubemap", "bRealTimeCapture": False,
                          "cubemap": {"refPath": objp(s["cubemap"])}, "intensity": float(s["intensity"]),
                          "lightColor": K.color_norm(s.get("colorLinear", [1, 1, 1]))})
        self.ed.hide_sprites(sky)
        ppv = self.ed.spawn("/Script/Engine.PostProcessVolume", "T53 exposure", (0.0, 0.0, -5000.0))
        self.actors.append(ppv)
        ex = lp["exposure"]
        self.ed.setp(ppv, {"bUnbound": True, "priority": 100.0, "blendWeight": 1.0, "settings": {
            "bOverride_AutoExposureMethod": True, "autoExposureMethod": "AEM_Histogram",
            "bOverride_AutoExposureMinBrightness": True, "autoExposureMinBrightness": ex["minBrightness"],
            "bOverride_AutoExposureMaxBrightness": True, "autoExposureMaxBrightness": ex["maxBrightness"],
            "bOverride_AutoExposureBias": True, "autoExposureBias": ex["bias"]}})
        return {"light": light_id, "keyRotationPYR": rot, "sky": s["intensity"], "exposure": ex}

    def tile(self, name, cx, cy):
        # client 'tiles' slab: centre z -5, scale (0.92, 0.92, 0.1) -> top at z = 0
        return self.mesh_actor(name, CUBE, (cx, cy, -5.0), (0.92, 0.92, 0.1), STONE)

    def camera(self, focus, dist, pitch=-55.0, yaw=-90.0):
        p = math.radians(-pitch)
        return {"location": {"x": focus[0], "y": focus[1] + dist * math.cos(p), "z": focus[2] + dist * math.sin(p)},
                "rotation": {"pitch": pitch, "yaw": yaw, "roll": 0.0}, "scale": {"x": 1, "y": 1, "z": 1}}

    def grab(self, name, xform, settle=6):
        import numpy as np
        prev = None
        for i in range(settle):  # let Lumen / TSR history converge on the view
            im, meta = self.ed.grab(xform)
            if prev is not None and float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()) < 0.05:
                break
            prev = im
            time.sleep(0.5)
        frame, box = K.crop_16_9(im)
        self.out.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        frame.save(buf, format="PNG", optimize=False)
        (self.out / f"{name}.png").write_bytes(buf.getvalue())
        return frame, meta

    def project(self, xform, meta, world):
        """World -> pixel of the 16:9 1920x1080 crop (pinhole, horizontal FOV of the capture)."""
        fov = float(meta.get("cameraFOV") or 90.0)
        loc = xform["location"]
        rot = xform["rotation"]
        cp, sp = math.cos(math.radians(rot["pitch"])), math.sin(math.radians(rot["pitch"]))
        cyw, syw = math.cos(math.radians(rot["yaw"])), math.sin(math.radians(rot["yaw"]))
        fwd = (cp * cyw, cp * syw, sp)
        right = (-syw, cyw, 0.0)
        up = (-sp * cyw, -sp * syw, cp)
        d = [world[i] - [loc["x"], loc["y"], loc["z"]][i] for i in range(3)]
        depth = sum(d[i] * fwd[i] for i in range(3))
        f = 960.0 / math.tan(math.radians(fov) / 2.0)
        return (960.0 + sum(d[i] * right[i] for i in range(3)) / depth * f,
                540.0 - sum(d[i] * up[i] for i in range(3)) / depth * f)

    def cleanup(self):
        for a in list(self.actors):
            try:
                self.ed.remove(a)
            except Exception:  # noqa: BLE001 - best effort, restore reports leftovers
                pass
        self.actors = []


def cmd_run(a) -> int:
    import numpy as np
    out = Path(a.out).resolve()
    dg = Diag(out / "frames")
    rep = {"schema": "unmatched.w5br-editor-diag/1",
           "status": "диагностика (кадры редактора, класс editor-mcp-viewport); не приёмка K1-K3",
           "startedUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "editor": "live UnrealEditor of the main checkout via MCP 127.0.0.1:8123 (no mouse/keyboard/focus)"}
    rep["scene"] = dg.open()
    try:
        rep["light"] = dg.light_rig()
        hexes = R.team_hex()
        old_disc = dg.scratch_mi("MI_T53_OldDiscOwn", GAME_LAYER_OLD, {"Tint": [0.02, 0.25, 1.5, 1.0]})
        silver = dg.scratch_mi("MI_T53_FillP2", MASTER, {"LayerColor": lin_hex(hexes["p2"])})
        # ---- (a) A/B: three stone tiles in a row at x = -100, 0, +100 (y = 0)
        dg.tile("T53 tile A", -100.0, 0.0)
        dg.tile("T53 tile B", 0.0, 0.0)
        dg.tile("T53 tile C", 100.0, 0.0)
        # A: the T5.2 disc (Cylinder 0.4 x 0.4 x 0.02 at z -1: top at z = 0, the old own-team HDR tint)
        dg.mesh_actor("T53 disc z0", CYL, (-100.0, 0.0, -1.0), (0.4, 0.4, 0.02), old_disc)
        # B: the new P1 ring with its top pushed down to z = 0 (actor z -1.2): same coplanarity, new mesh
        dg.mesh_actor("T53 ring P1 top0", R.ring_package("p1"), (0.0, 0.0, -1.2), (1.0, 1.0, 1.0),
                      [R.MI_KEYLINE, R.MI_FILL])
        # C: the new P1 ring as the client places it (actor z 0: top at +1.2)
        dg.mesh_actor("T53 ring P1 lifted", R.ring_package("p1"), (100.0, 0.0, 0.0), (1.0, 1.0, 1.0),
                      [R.MI_KEYLINE, R.MI_FILL])
        time.sleep(2.0)
        x_k1 = dg.camera((0.0, 0.0, 0.0), K1_DIST * FOV_RATIO)
        fk1, mk1 = dg.grab("ab-k1", x_k1)
        x_close = dg.camera((0.0, 0.0, 0.0), 700.0 * FOV_RATIO)
        fcl, mcl = dg.grab("ab-close", x_close)
        rep["ab"] = {"layout": {"A (x=-100)": "T5.2 disc: Cylinder 0.4x0.4x0.02 at z -1, top at z 0 (tile top), old own "
                                              "tint (0.02, 0.25, 1.5) on M_S08_GameLayerUnlit",
                                "B (x=0)": "SM_Marker_TeamRing_P1 with its top forced to z 0 (actor z -1.2)",
                                "C (x=+100)": "SM_Marker_TeamRing_P1 as the client places it (top +1.2)"},
                     "frames": {"k1": "frames/ab-k1.png", "close": "frames/ab-close.png"},
                     "cameraK1": x_k1, "cameraClose": x_close, "metaK1": mk1, "metaClose": mk1}
        # speckle metric: in each ring's fill annulus (23.5..26.5), share of pixels that are NOT fill-coloured
        for tag, frame, meta, xf in (("k1", fk1, mk1, x_k1), ("close", fcl, mcl, x_close)):
            arr = np.asarray(frame).astype(int)
            res = {}
            for label, cx, ztop, r0, r1, colour in (("A disc", -100.0, 0.0, 6.0, 15.0, None),
                                                   ("B ring top0", 0.0, 0.0, 23.9, 26.1, "fill"),
                                                   ("C ring lifted", 100.0, 1.2, 23.9, 26.1, "fill")):
                pts = []
                for i in range(180):
                    t = 2 * math.pi * i / 180
                    for rr in np.linspace(r0, r1, 5):
                        px, py = dg.project(xf, meta, (cx + rr * math.cos(t), rr * math.sin(t), ztop))
                        if 0 <= int(px) < 1920 and 0 <= int(py) < 1080:
                            pts.append(arr[int(py), int(px)])
                pts = np.asarray(pts)
                med = np.median(pts, axis=0)
                spread = np.abs(pts - med).max(axis=1)
                res[label] = {"samples": int(len(pts)), "medianRgb": [int(v) for v in med],
                              "shareFarFromMedian(>40)": round(float((spread > 40).mean()), 4),
                              "p90AbsDev": round(float(np.percentile(spread, 90)), 1)}
            rep["ab"]["speckle_" + tag] = res
        # ---- (b) byte calibration: flat unlit plates at the K1 screen centre (no ring geometry, no tile)
        dg.cleanup()
        rep["light2"] = dg.light_rig()
        plates = [("fill P1 (team.p1)", R.MI_FILL, hexes["p1"]), ("fill P2 (team.p2)", silver, hexes["p2"]),
                  ("keyline (mark.keyline)", R.MI_KEYLINE, hexes["keyline"])]
        zmi = "/Game/ArtTests/ART005/Zones/MI_ART005_Zone_"
        for key, st in sorted(dg.profiles["zoneStyles"].items()):
            plates.append((f"zone {key}", zmi + "".join(p[:1].upper() + p[1:] for p in key.split("-")), st["color"]))
        plates.append(("zone keyline", zmi + "Keyline", dg.profiles["zoneKeyline"]["color"]))
        n = len(plates)
        cols = 5
        spacing = 60.0
        cells = []
        for i, (label, mi, hexc) in enumerate(plates):
            cx = (i % cols - (cols - 1) / 2.0) * spacing
            cy = -((i // cols) - ((n - 1) // cols) / 2.0) * spacing
            dg.mesh_actor(f"T53 plate {i}", CUBE, (cx, cy, 0.0), (0.5, 0.5, 0.01), mi)
            cells.append((label, mi, hexc, cx, cy))
        time.sleep(2.0)
        x_cal = dg.camera((0.0, 0.0, 0.0), 420.0, pitch=-89.9, yaw=-90.0)
        fcal, mcal = dg.grab("calibration-plates", x_cal)
        arr = np.asarray(fcal).astype(int)
        rows = []
        for label, mi, hexc, cx, cy in cells:
            px, py = dg.project(x_cal, mcal, (cx, cy, 0.5))
            x0, y0 = int(px) - 6, int(py) - 6
            patch = arr[max(0, y0):y0 + 13, max(0, x0):x0 + 13].reshape(-1, 3)
            med = [int(v) for v in np.median(patch, axis=0)]
            rows.append({"plate": label, "mi": mi, "hex": hexc, "renderedRgb": med,
                         "renderedHex": "#%02X%02X%02X" % tuple(med), "dE76": de76(med, hex_rgb(hexc)),
                         "screen": [round(px), round(py)], "patchSpread": int(np.ptp(patch, axis=0).max())})
        rep["calibration"] = {"frame": "frames/calibration-plates.png", "camera": x_cal, "meta": mcal,
                              "method": "flat plates (Cube 0.5 x 0.5 x 0.01) with each MI, top-down, 13x13 px median at "
                                        "the plate centre; dE76 of the rendered sRGB bytes against the hex",
                              "rows": rows, "maxDE76": max(r["dE76"] for r in rows)}
        # ---- (c) sheet: six figures (hero/sidekick sizes, P1/P2) on stone tiles with zone marks
        dg.cleanup()
        rep["light3"] = dg.light_rig()
        figs = [("Medusa", "p1", 1.0, "/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate"),
                ("Harpy", "p1", 0.78, "/Game/ArtTests/ART003/Meshes/SM_ART003_Harpy"),
                ("Harpy", "p1", 0.78, "/Game/ArtTests/ART003/Meshes/SM_ART003_Harpy"),
                ("King Arthur", "p2", 1.0, "/Game/ArtTests/ART003/Meshes/SM_ART003_Arthur"),
                ("Merlin", "p2", 0.78, "/Game/ArtTests/ART003/Meshes/SM_ART003_Merlin"),
                ("Harpy", "p2", 0.78, "/Game/ArtTests/ART003/Meshes/SM_ART003_Harpy")]
        for i, (name, slot, fs, mesh) in enumerate(figs):
            cx, cy = (i % 3 - 1) * 100.0, (0.5 - i // 3) * 100.0
            dg.tile(f"T53 sheet tile {i}", cx, cy)
            fill = R.MI_FILL if slot == "p1" else silver
            dg.mesh_actor(f"T53 sheet ring {i}", R.ring_package(slot), (cx, cy, 0.0), (fs, fs, 1.0),
                          [R.MI_KEYLINE, fill])
            dg.mesh_actor(f"T53 sheet fig {i}", mesh, (cx, cy, 0.0), (fs, fs, fs) if "Medusa" in name else (1, 1, 1),
                          None, rot=(0.0, 0.0 if cy < 0 else 180.0, 0.0))
            # one zone glyph + its keyline in the near-left slot, one stroke on the near side
            gx, gy = cx - 32.0, cy + 32.0
            dg.mesh_actor(f"T53 sheet glyphkey {i}", "/Game/ArtTests/ART005/Zones/SM_ART005_ZoneGlyphKey_Bars3",
                          (gx, gy, 0.38), (1, 1, 1), zmi + "Keyline")
            dg.mesh_actor(f"T53 sheet glyph {i}", "/Game/ArtTests/ART005/Zones/SM_ART005_ZoneGlyph_Bars3",
                          (gx, gy, 0.38), (1, 1, 1), zmi + ("BlueGreen" if i % 2 else "Gray"))
            dg.mesh_actor(f"T53 sheet strokekey {i}", CUBE, (cx, cy + 41.5, 0.18), (0.99, 0.07, 0.003), zmi + "Keyline")
            dg.mesh_actor(f"T53 sheet stroke {i}", CUBE, (cx, cy + 41.5, 0.28), (0.96, 0.04, 0.004),
                          zmi + ("BlueGreen" if i % 2 else "Gray"))
        time.sleep(2.0)
        x_sheet = dg.camera((0.0, 0.0, 20.0), K1_DIST * FOV_RATIO * 0.55)
        dg.grab("sheet-six-figures", x_sheet)
        rep["sheet"] = {"frame": "frames/sheet-six-figures.png", "camera": x_sheet,
                        "content": "six stone tiles; P1 = Medusa + 2 Harpy blockouts (gold circle), P2 = Arthur, "
                                   "Merlin, Harpy blockouts (silver hexagon, gaps); one bars3 glyph + keyline and one "
                                   "solid stroke + keyline per tile (gray #7F868E / blue-green); editor frame, "
                                   "diagnostic for the art look (step 9), not K1"}
    finally:
        dg.cleanup()
        rep["finishedUtc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        K.write_json(out / "editor-diag.json", rep)
    print(json.dumps({"ab": {k: v for k, v in rep.get("ab", {}).items() if k.startswith("speckle")},
                      "calibration": [(r["plate"], r["renderedHex"], r["dE76"]) for r in
                                      rep.get("calibration", {}).get("rows", [])]}, ensure_ascii=False, indent=1))
    return 0


def cmd_restore(a) -> int:
    ed = K.Editor()
    cur = ed.call("scene", "get_current_level").split(".")[0]
    if cur.startswith(SCRATCH):
        ed.call("scene", "load_level", {"level_path": HOME})
        time.sleep(3.0)
    deleted = None
    if ed.call("asset", "exists", {"path": SCRATCH}):
        try:
            deleted = ed.call("asset", "delete", {"path": SCRATCH})
        except Exception as e:  # noqa: BLE001
            deleted = f"delete failed (editor may keep the scratch map loaded until restart): {e}"
    print(json.dumps({"level": ed.call("scene", "get_current_level"), "scratchDeleted": deleted,
                      "homeDirty": ed.call("asset", "is_dirty", {"asset_path": HOME})}, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    sub.add_parser("restore")
    a = ap.parse_args(argv)
    return {"run": cmd_run, "restore": cmd_restore}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
