#!/usr/bin/env python3
"""Wave 5c-B1 (B1-2 / B1-3): diagnostics in the LIVE editor of the art worktree (MCP, UE_MCP_URL=http://127.0.0.1:8124/mcp,
lock UE_EDITOR_LOCK=C:/tmp/ue-editor-8124.lock). Editor frames are diagnostics (class editor-mcp-viewport), never K1-K3
evidence and never acceptance; the packaged re-shoot (B1-7) decides.

    python tools/art/t5cb1_editor.py calib --out <dir>                          # B1-2: screen bytes on flat plates
    python tools/art/t5cb1_editor.py board --board cobble --calib <dir>/calib.json --out <dir>   # B1-3 (+ rimVsTile)
    python tools/art/t5cb1_editor.py board --board forest  ...
    python tools/art/t5cb1_editor.py board --board paddock ...
    python tools/art/t5cb1_editor.py restore                                    # back to /Game/S08/S08Arena

Every command opens a scratch copy of the (empty) arena level (t53_diag_editor: /Game/ArtTests/T53Diag/L_T53Diag), spawns
what it needs, grabs, removes its actors and goes back to /Game/S08/S08Arena, deleting the scratch folder: one command
= one lock hold (run it under tools/art/material_library/ue_lock.py). Nothing is saved except the scratch level copy,
which is deleted again; S08Arena is never saved.

Light: the profile of S08ArtBoardProfiles.json as the packaged client places it (rev 5: key FRotator(rotation) in lux
with its CSM, the Movable SkyLight TC_S08_AmbientDome, the points in candelas, the fixed exposure) - on the editor's
Epic scalability, so luma differs from packaged High (T4.2: ~0.1-1.5 luma). Figures: the Medusa candidate
(SK_Medusa_FaceNeck_v2Candidate + MI_Medusa_P1/_P2 = the look the client picks) and the grey ART003 blockouts.

calib (B1-2): flat unlit plates (Cube 0.5 x 0.5 x 0.01) with every game-layer MI (zones rev 5, zone keyline, ring
keyline / P1 fill / P2 fill (scratch MI) / rim), top-down, 13x13 px median at the plate centre -> screen bytes, dE76 to
the hex and to the model forecast of the 5c-B1 plan (red (225,108,76), gray (104,113,122), rim (217,215,210); <= 8).

board (B1-3): K1 direction (pitch -55, yaw -90), four rings (P1 hero + sidekick, P2 hero + sidekick) with figures on the
board surface of that board (Cobble: the ART-005 slab SM_ART005_BoardStoneV4_WoodUV with its stone/wood materials;
fixtures: stone probe tiles) and zone strokes/glyphs (with keylines) of the board's colours; measured with the SAME
functions the packaged analysis uses (t53_readability.rings_rev3: shape classifier rev 2 with the rim bound, ring tile
reference rev 3, edge = max(keyline, rim) vs tile, >= 10 px core) on a synthetic SHOT (the capture camera), plus the
fill fraction, fill vs keyline and the zone fill vs keyline / keyline vs tile of the placed marks.
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
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))
import t42_sky_calib_editor as K  # noqa: E402
import t53_diag_editor as D  # noqa: E402
import t53_readability as T53  # noqa: E402
import t53_team_ring as R  # noqa: E402

SCHEMA = "unmatched.t5cb1-editor/1"
ZMI = "/Game/ArtTests/ART005/Zones/MI_ART005_Zone_"
FORECAST = {"zone.red": [225, 108, 76], "zone.gray": [104, 113, 122], "team.rim": [217, 215, 210]}
COBBLE_SLAB = "/Game/ArtTests/ART005F/Meshes/SM_ART005_BoardStoneV4_WoodUV"
COBBLE_STONE = "/Game/ArtTests/ART005E/Materials/M_ART005E_Stone_DiffuseOnly_v4"
COBBLE_WOOD = "/Game/ArtTests/ART005G/Materials/M_ART005G_Wood_DiffuseOnly"
MEDUSA_SK = "/Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate"
MEDUSA_BASE = "/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate"
BLOCKOUT = {"Arthur": "/Game/ArtTests/ART003/Meshes/SM_ART003_Arthur",
            "Merlin": "/Game/ArtTests/ART003/Meshes/SM_ART003_Merlin",
            "Harpy": "/Game/ArtTests/ART003/Meshes/SM_ART003_Harpy"}
# board -> light profile, surface, board size (cells), zones of the four fighter cells and one extra mark cell
BOARDS = {
    "cobble": {"light": "cobble-probe", "surface": "cobble", "size": (5, 6), "zones": ["red", "blue"]},
    "forest": {"light": "forest-probe", "surface": "tiles", "size": (8, 5), "zones": ["gray", "light-gray", "brown"]},
    "paddock": {"light": "paddock-probe", "surface": "tiles", "size": (7, 5), "zones": ["gray", "blue", "purple"]},
}
# four fighters on non-adjacent cells of a 5 x 4 patch: (fid, look, cell, figure)
FIGHTERS = [("f-0-hero", "P1", (1, 1), "Medusa"), ("f-0-sk0", "P1", (3, 1), "Harpy"),
            ("f-1-hero", "P2", (1, 3), "Arthur"), ("f-1-sk0", "P2", (3, 3), "Merlin")]
CELL = 100.0


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def mi_of_zone(key: str) -> str:
    return ZMI + "".join(p[:1].upper() + p[1:] for p in key.split("-"))


class Scene(D.Diag):
    """t53_diag_editor.Diag + the rev 5 point lights, surfaces, figures and a grab that keeps the crop geometry."""

    def rig(self, light_id: str) -> dict:
        info = self.light_rig(light_id)
        lp = self.profiles["lightProfiles"][light_id]
        pts = []
        for i, p in enumerate(lp.get("points", [])):
            a = self.ed.spawn("/Script/Engine.PointLight", f"T5CB1 point {i}", K.place(p))
            self.actors.append(a)
            c = self.ed.light_component(a)
            self.ed.setp(c, {"mobility": "Movable", "intensityUnits": "Candelas", "intensity": float(p["intensity"]),
                             "attenuationRadius": float(p["radiusUU"]), "castShadows": False,
                             "lightColor": K.color_norm(p.get("colorLinear", [1, 1, 1]))})
            self.ed.hide_sprites(a)
            pts.append({"name": p["name"], "at": K.place(p), "cd": p["intensity"]})
        info["points"] = pts
        info["pointsNote"] = "fixture points placed with the 5x6 'at' rule of t42 (K.place) - approximate spots"
        return info

    def slot_names(self, mesh: str) -> list[str]:
        return self.ed.call("static", "get_material_slots", {"mesh": {"refPath": D.objp(mesh)}}) or []

    def grab_geo(self, name: str, xform: dict, settle: int = 8):
        """-> (frame 1920x1080 np.uint8, Camera of the frame, meta)."""
        import numpy as np
        from qa010lib.projection import Camera
        prev = None
        for _ in range(settle):
            im, meta = self.ed.grab(xform)
            if prev is not None and float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()) < 0.05:
                break
            prev = im
            time.sleep(0.5)
        w0, h0 = im.size
        frame, box = K.crop_16_9(im)
        self.out.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        frame.save(buf, format="PNG", optimize=False)
        (self.out / f"{name}.png").write_bytes(buf.getvalue())
        hfov = float(meta.get("cameraFOV") or 90.0)
        crop_w = box[2] - box[0]
        if crop_w < w0:  # sides cut: narrower horizontal FOV
            hfov = math.degrees(2 * math.atan(math.tan(math.radians(hfov) / 2) * crop_w / w0))
        loc, rot = xform["location"], xform["rotation"]
        cam = Camera(pos=(loc["x"], loc["y"], loc["z"]), rot=(rot["pitch"], rot["yaw"], rot.get("roll", 0.0)),
                     hfov_deg=hfov, viewport=(1920, 1080))
        return np.asarray(frame).astype(np.uint8), cam, dict(meta, sourceSize=[w0, h0], cropBox=list(box),
                                                            frameHfovDeg=round(hfov, 4))


def cmd_calib(a) -> int:
    import numpy as np
    out = Path(a.out).resolve()
    sc = Scene(out / "frames")
    rep = {"schema": SCHEMA, "kind": "calib", "status": "диагностика (кадры редактора, editor-mcp-viewport); не приёмка",
           "startedUtc": now(), "editor": T53_EDITOR}
    rep["scene"] = sc.open()
    try:
        rep["light"] = sc.rig(a.light)
        hexes = R.team_hex()
        silver = sc.scratch_mi("MI_T5CB1_FillP2", D.MASTER, {"LayerColor": D.lin_hex(hexes["p2"])})
        plates = [("team.p1.fill", R.MI_FILL, hexes["p1"]), ("team.p2.fill", silver, hexes["p2"]),
                  ("mark.keyline", R.MI_KEYLINE, hexes["keyline"]), ("team.rim", R.MI_RIM, hexes["rim"])]
        for key, st in sorted(sc.profiles["zoneStyles"].items()):
            plates.append(("zone." + key, mi_of_zone(key), st["color"]))
        plates.append(("zone.keyline", ZMI + "Keyline", sc.profiles["zoneKeyline"]["color"]))
        n, cols, spacing = len(plates), 5, 60.0
        cells = []
        for i, (label, mi, hexc) in enumerate(plates):
            cx = (i % cols - (cols - 1) / 2.0) * spacing
            cy = -((i // cols) - ((n - 1) // cols) / 2.0) * spacing
            sc.mesh_actor(f"T5CB1 plate {i}", D.CUBE, (cx, cy, 0.0), (0.5, 0.5, 0.01), mi)
            cells.append((label, mi, hexc, cx, cy))
        time.sleep(2.0)
        x_cal = sc.camera((0.0, 0.0, 0.0), 420.0, pitch=-89.9, yaw=-90.0)
        arr, cam, meta = sc.grab_geo("calibration-plates", x_cal)
        prev = T53.load_json(REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29/t53-thresholds.json")
        prev = prev["calibration"]["bytes"]
        rows = {}
        for label, mi, hexc, cx, cy in cells:
            s = cam.project((cx, cy, 0.5))
            x0, y0 = int(s[0]) - 6, int(s[1]) - 6
            patch = arr[max(0, y0):y0 + 13, max(0, x0):x0 + 13].reshape(-1, 3).astype(int)
            med = [int(v) for v in np.median(patch, axis=0)]
            row = {"hex": hexc, "mi": mi, "screen": med, "renderedHex": "#%02X%02X%02X" % tuple(med),
                   "dE76HexToScreen": D.de76(med, D.hex_rgb(hexc)), "patchSpread": int(np.ptp(patch, axis=0).max()),
                   "px": [round(s[0]), round(s[1])]}
            if label in FORECAST:
                row["forecastScreen"] = FORECAST[label]
                row["dE76ToForecast"] = D.de76(med, FORECAST[label])
                row["forecastPass"] = row["dE76ToForecast"] <= 8.0
            p = prev.get(label)
            if p and p.get("hex", "").upper() == hexc.upper():
                row["w5brScreen"] = p["screen"]
                row["dE76ToW5br"] = D.de76(med, p["screen"])
            rows[label] = row
        rep["calibration"] = {"frame": "frames/calibration-plates.png", "camera": x_cal, "meta": meta,
                              "method": "flat plates (Cube 0.5 x 0.5 x 0.01) with each MI, top-down, 13x13 px median at "
                                        "the plate centre (the W5b-R diag method); the game layer is unlit + "
                                        "EyeAdaptationInverse, so these bytes do not depend on the exposure",
                              "bytes": rows}
    finally:
        sc.cleanup()
        rep["restore"] = restore(sc.ed)
        rep["finishedUtc"] = now()
        K.write_json(out / "calib.json", rep)
    print(json.dumps({k: (v["renderedHex"], v["dE76HexToScreen"], v.get("dE76ToForecast"), v.get("dE76ToW5br"))
                      for k, v in rep.get("calibration", {}).get("bytes", {}).items()}, ensure_ascii=False, indent=0))
    return 0


def zone_mark_actors(sc: Scene, cx: float, cy: float, key: str, style: dict, keyline_glyphs: dict, glyphs: dict,
                     tag: str):
    """One near-side stroke (fill + keyline, the W5b-R inset: centre line 42 uu) and the near-left glyph slot (-32, +32)
    of a cell - enough to read the zone fill against its keyline and the keyline against the tile."""
    mi = mi_of_zone(key)
    glyph = style["glyph"]
    gx, gy = cx - 32.0, cy + 32.0
    sc.mesh_actor(f"T5CB1 {tag} glyphkey", keyline_glyphs[glyph], (gx, gy, 0.38), (1, 1, 1), ZMI + "Keyline")
    sc.mesh_actor(f"T5CB1 {tag} glyph", glyphs[glyph], (gx, gy, 0.38), (1, 1, 1), mi)
    sc.mesh_actor(f"T5CB1 {tag} strokekey", D.CUBE, (cx, cy + 42.0, 0.18), (0.86, 0.07, 0.003), ZMI + "Keyline")
    sc.mesh_actor(f"T5CB1 {tag} stroke", D.CUBE, (cx, cy + 42.0, 0.28), (0.83, 0.04, 0.004), mi)
    return {"key": key, "cell": [cx, cy], "stroke": {"centre": [cx, cy + 42.0], "halfLenUU": 41.5, "halfWidthUU": 2.0,
                                                    "keylineHalfWidthUU": 3.5},
            "glyph": {"name": glyph, "centre": [gx, gy]}}


def figure_rect(cam, world, fs: float, height: float) -> tuple:
    xs, ys = [], []
    r = max(b[1] for b in R.RING_SPEC["p1"]["bands"].values()) * fs  # the outer ring edge (rim after B1-3)
    for i in range(16):
        t = 2 * math.pi * i / 16
        for z in (0.0, height):
            s = cam.project((world[0] + r * math.cos(t), world[1] + r * math.sin(t), z))
            if s:
                xs.append(s[0])
                ys.append(s[1])
    return (min(xs), min(ys), max(xs), max(ys))


def make_shot(rgb, cam, fighters: dict, rings: dict, figures: dict):
    """A SHOT-like object for the t53 metrics (T53.Shot without a trace): the capture camera, no UMG."""
    import numpy as np
    from qa010lib import color as C
    s = T53.Shot.__new__(T53.Shot)
    s.png = Path("editor-frame.png")
    s.rgb = rgb
    s.h, s.w = rgb.shape[:2]
    s.np = np
    s.proj = SimpleNamespace(camera=cam)
    s.variants = {"color": rgb, "gray": C.grayscale(rgb), "deuteranopia": C.deuteranopia(rgb)}
    s.lum = {k: C.relative_luminance(v) for k, v in s.variants.items()}
    s.luma_gray = C.luma_u8(s.variants["gray"])
    s.lab = C.linear_to_lab(C.u8_to_linear(rgb))
    s.fighters = fighters
    s.rings = rings
    s.block = SimpleNamespace(widgets=[], panels=[], damage=[], plate=None, icon=None,
                              figures={k: {"bbox": v} for k, v in figures.items()})
    return s


def zone_metrics(shot, marks: list, calib: dict, pde: float) -> list:
    """Zone fill vs its keyline and keyline vs the tile of the placed marks (medians of the classified pixels)."""
    np = shot.np
    cam = shot.proj.camera
    out = []
    key_mask = shot.de_to(calib["zone.keyline"]["screen"]) <= pde
    for m in marks:
        if "zone." + m["key"] not in calib:
            continue
        fill_mask = shot.de_to(calib["zone." + m["key"]]["screen"]) <= pde
        cx, cy = m["cell"]
        sx, sy = m["stroke"]["centre"]

        def area(x0, x1, y0, y1, z):
            pts = [(x, y, z) for x in np.arange(x0, x1, 0.4) for y in np.arange(y0, y1, 0.4)]
            return shot.mask_of(shot.pixels(pts))
        stroke = area(sx - 41.5, sx + 41.5, sy - 3.5, sy + 3.5, 0.3)
        gx, gy = m["glyph"]["centre"]
        glyph = area(gx - 14, gx + 14, gy - 14, gy + 14, 0.5)
        marks_m = stroke | glyph
        fill_px, key_px = marks_m & fill_mask, marks_m & key_mask
        tile = area(cx - 18, cx + 18, cy - 18, cy + 18, 0.0) & ~fill_mask & ~key_mask
        rec = {"key": m["key"], "fillPx": int(fill_px.sum()), "keylinePx": int(key_px.sum()), "tilePx": int(tile.sum())}
        for vn in ("color", "gray", "deuteranopia"):
            lf, lk, lt = shot.med_lum(fill_px, vn), shot.med_lum(key_px, vn), shot.med_lum(tile, vn)
            rec[vn] = {"fillVsKeyline": round(T53.wcag(lf, lk), 3) if lf is not None and lk is not None else None,
                       "keylineVsTile": round(T53.wcag(lk, lt), 3) if lk is not None and lt is not None else None}
        rec["tileMedianRgb"] = shot.med_rgb(tile)
        out.append(rec)
    del cam
    return out


def ring_fraction(shot, fid: str, look: str, calib: dict, pde: float) -> dict:
    f = shot.fighters[fid]
    fs = T53.fighter_scale(fid)
    z = f.world[2] + R.RING_SPEC["zMax"]
    b = T53.ring_bands(look)
    fill_m = shot.mask_of(shot.pixels(T53.band_samples(look, b["fill"][0], b["fill"][1], fs, f.world, z)))
    team = shot.de_to(calib["team.p1.fill" if look == "P1" else "team.p2.fill"]["screen"]) <= pde
    key_m = shot.mask_of(shot.pixels(T53.band_samples(look, b["keylineIn"][0], b["keylineIn"][1], fs, f.world, z)) |
                         shot.pixels(T53.band_samples(look, b["keylineOut"][0], b["keylineOut"][1], fs, f.world, z)))
    key = shot.de_to(calib["mark.keyline"]["screen"]) <= pde
    n = int(fill_m.sum())
    rec = {"fillZonePx": n, "teamPx": int((fill_m & team).sum()),
           "fraction": round(int((fill_m & team).sum()) / n, 4) if n else None}
    for vn in ("color", "gray", "deuteranopia"):
        lf, lk = shot.med_lum(fill_m & team, vn), shot.med_lum(key_m & key & ~fill_m, vn)
        rec[vn] = {"fillVsKeyline": round(T53.wcag(lf, lk), 3) if lf is not None and lk is not None else None}
    return rec


def cmd_board(a) -> int:
    """--rings r3: a CONTROL with the W5b-R r3 one-tone rings (generated from RING_BANDS_R3, imported into the scratch
    folder and deleted with it), measured with the r3 bands - the r3 rings passed in the packaged r3 frames, so a
    failure here is the editor capture, not the 5c-B1 geometry."""
    if a.rings == "r3":
        with R.using_bands(R.RING_BANDS_R3):
            return _cmd_board(a)
    return _cmd_board(a)


def import_control_rings(sc: "Scene", obj_dir: Path) -> dict:
    """The r3 ring meshes as scratch assets (the current RING_SPEC bands must be the r3 ones)."""
    objs = R.write_objs(obj_dir)
    out = {}
    for slot in ("p1", "p2"):
        name = f"SM_T5CB1_RingR3_{slot.upper()}"
        src = (obj_dir / f"SM_Marker_TeamRing_{slot.upper()}.obj").resolve().as_posix()
        sc.ed.call("static", "import_file", {"folder_path": D.SCRATCH, "asset_name": name, "source_file": src,
                                             "import_materials": False, "import_textures": False, "combine_meshes": True})
        pkg = f"{D.SCRATCH}/{name}"
        mesh = {"refPath": D.objp(pkg)}
        if sc.ed.call("static", "is_nanite_enabled", {"mesh": mesh}):
            sc.ed.call("static", "set_nanite_enabled", {"mesh": mesh, "enabled": False})
        out[slot] = {"package": pkg, "obj": objs[slot], "slots": sc.ed.call("static", "get_material_slots", {"mesh": mesh})}
    return out


def _cmd_board(a) -> int:
    import numpy as np
    out = Path(a.out).resolve()
    spec = BOARDS[a.board]
    calib_doc = json.loads(Path(a.calib).read_text(encoding="utf-8"))
    calib = {k: {"screen": v["screen"], "hex": v["hex"]} for k, v in calib_doc["calibration"]["bytes"].items()}
    pde = 15.0
    sc = Scene(out / "frames")
    if a.rings == "r3":
        calib.pop("team.rim", None)  # one-tone control: no rim class
    tag = a.board + ("-r3control" if a.rings == "r3" else "")
    rep = {"schema": SCHEMA, "kind": "board", "board": a.board, "rings": a.rings, "boardSpec": spec,
           "calibFrom": str(Path(a.calib)),
           "status": "диагностика (кадры редактора, editor-mcp-viewport); не приёмка K1", "startedUtc": now(),
           "editor": T53_EDITOR, "ringSpec": {k: R.RING_SPEC[k]["bands"] for k in ("p1", "p2")}}
    rep["scene"] = sc.open()
    try:
        rep["light"] = sc.rig(spec["light"])
        hexes = R.team_hex()
        silver = sc.scratch_mi("MI_T5CB1_FillP2", D.MASTER, {"LayerColor": D.lin_hex(hexes["p2"])})
        control = import_control_rings(sc, out / "obj-r3") if a.rings == "r3" else None
        rep["controlRings"] = control
        # cells of a 5 x 4 patch around the origin (cell centres on the 100-uu grid of the board)
        W, H = spec["size"]
        ox, oy = (W - 1) * 0.5 * CELL, (H - 1) * 0.5 * CELL

        def world(c):
            return (c[0] * CELL - ox + (W // 2 - 2) * CELL, c[1] * CELL - oy + (H // 2 - 2) * CELL, 0.0)
        if spec["surface"] == "cobble":
            slots = sc.slot_names(COBBLE_SLAB)
            mats = [COBBLE_WOOD if "wood" in s.lower() else COBBLE_STONE for s in slots]
            sc.mesh_actor("T5CB1 cobble slab", COBBLE_SLAB, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), mats, rot=(0.0, -90.0, 0.0))
            rep["surface"] = {"mesh": COBBLE_SLAB, "slots": slots, "materials": mats, "rotYaw": -90.0}
        else:
            n = 0
            for cx in range(5):
                for cy in range(4):
                    p = world((cx, cy))
                    sc.tile(f"T5CB1 tile {n}", p[0], p[1])
                    n += 1
            rep["surface"] = {"tiles": n, "material": D.STONE, "note": "client 'tiles' slab (0.92 x 0.92 x 0.1, top z 0)"}
        styles = sc.profiles["zoneStyles"]
        key_glyphs = sc.profiles["zoneKeyline"]["glyphMeshes"]
        glyphs = sc.profiles["glyphMeshes"]
        marks, fighters, rings, figures, cells = [], {}, {}, {}, []
        for i, (fid, look, cell, fig) in enumerate(FIGHTERS):
            w = world(cell)
            fs = T53.fighter_scale(fid)
            fill = R.MI_FILL if look == "P1" else silver
            if control:
                sc.mesh_actor(f"T5CB1 ring {fid}", control[look.lower()]["package"], w, (fs, fs, 1.0), [R.MI_KEYLINE, fill])
            else:
                sc.mesh_actor(f"T5CB1 ring {fid}", R.ring_package(look.lower()), w, (fs, fs, 1.0),
                              [R.MI_KEYLINE, fill, R.MI_RIM])
            yaw = 0.0 if w[1] < 0 else 180.0
            if fig == "Medusa":
                mi = R.MI_MEDUSA["p1" if look == "P1" else "p2"]
                a_sk = sc.ed.call("scene", "add_to_scene_from_asset", {
                    "asset_path": MEDUSA_SK, "name": f"T5CB1 fig {fid}",
                    "xform": {"location": dict(zip("xyz", w)), "rotation": {"pitch": 0.0, "yaw": yaw, "roll": 0.0},
                              "scale": {"x": fs, "y": fs, "z": fs}}, "parent": None, "snap_to_ground": False})
                a_sk = sc.ed.ref(a_sk)
                sc.actors.append(a_sk)
                comps = [c for c in sc.ed.components(a_sk) if "SkeletalMeshComponent" in c.rsplit(".", 1)[-1]]
                if comps:
                    sc.ed.setp(comps[0], {"OverrideMaterials": [{"refPath": D.objp(mi)}]})
                sc.mesh_actor(f"T5CB1 base {fid}", MEDUSA_BASE, w, (fs, fs, fs), None, rot=(0.0, yaw, 0.0))
                height = 60.0
            else:
                sc.mesh_actor(f"T5CB1 fig {fid}", BLOCKOUT[fig], w, (1, 1, 1), None, rot=(0.0, yaw, 0.0))
                height = 60.0 if fs == 1.0 else 45.0
            fighters[fid] = SimpleNamespace(fighter_id=fid, world=w, cell=cell, alive=True)
            rings[fid] = {"look": look, "shown": True, "team": look}
            zk = spec["zones"][i % len(spec["zones"])]
            marks.append(zone_mark_actors(sc, w[0], w[1], zk, styles[zk], key_glyphs, glyphs, f"mark {fid}"))
            cells.append({"x": cell[0], "y": cell[1], "zones": [zk]})
            figures[fid] = height
        # one free cell per zone colour (no fighter) - the zone read without rings
        for j, zk in enumerate(spec["zones"]):
            c = (2, 2) if j == 0 else ((0, 2) if j == 1 else (4, 2))
            w = world(c)
            marks.append(zone_mark_actors(sc, w[0], w[1], zk, styles[zk], key_glyphs, glyphs, f"free {zk}"))
        time.sleep(2.0)
        dist = D.K1_DIST * D.FOV_RATIO
        centre = world((2, 2))
        xf = sc.camera((centre[0], centre[1], 0.0), dist)
        rgb, cam, meta = sc.grab_geo(f"k1-{tag}", xf)
        rects = {fid: figure_rect(cam, f.world, T53.fighter_scale(fid), figures[fid]) for fid, f in fighters.items()}
        shot = make_shot(rgb, cam, fighters, rings, rects)
        ppu = []
        for fid, f in fighters.items():
            p0, p1 = cam.project(f.world), cam.project((f.world[0] + 10.0, f.world[1], f.world[2]))
            ppu.append(round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 10.0, 3))
        rr = T53.rings_rev3(shot, calib, cells, pde)
        for row in rr["fighters"]:
            row["fill"] = ring_fraction(shot, row["fighter"], row["look"], calib, pde)
        rep["frame"] = {"file": f"frames/k1-{tag}.png", "camera": xf, "meta": meta, "pxPerUUTangential": ppu,
                        "figureRects": rects}
        rep["rings"] = rr["fighters"]
        rep["zones"] = zone_metrics(shot, marks, calib, pde)
        rep["marks"] = marks
        rows = rep["rings"]
        rim_vs = [r["tileReference"][vn].get("rimVsTile") for r in rows for vn in ("color", "gray", "deuteranopia")]
        rim_vs = [v for v in rim_vs if v is not None]
        rep["summary"] = {
            "rings": len(rows), "shapeAllVariants": sum(1 for r in rows if r["shapePassAllVariants"]),
            "edgeVsTilePass": sum(1 for r in rows if r["edgeVsTilePass"]),
            "edgeVsTileMin": min((r["tileReference"][vn]["edgeVsTile"] for r in rows for vn in ("color", "gray", "deuteranopia")
                                  if r["tileReference"][vn]["edgeVsTile"] is not None), default=None),
            "keylineVsTileMin": min((r["tileReference"][vn]["keylineVsTile"] for r in rows
                                     for vn in ("color", "gray", "deuteranopia")
                                     if r["tileReference"][vn]["keylineVsTile"] is not None), default=None),
            "rimVsTileMin": min(rim_vs) if rim_vs else None,
            "keylineCorePxMin": min(r["tileReference"]["keylinePx"] for r in rows),
            "rimCorePxMin": min((r["tileReference"]["rimPx"] or 0) for r in rows),
            "tilePxMin": min(r["tileReference"]["tilePx"] for r in rows),
            "fractionMin": {"hero": min((r["fill"]["fraction"] or 0) for r in rows if r["fighter"].endswith("-hero")),
                            "sidekick": min((r["fill"]["fraction"] or 0) for r in rows if not r["fighter"].endswith("-hero"))},
            "fillVsKeylineMin": min((r["fill"][vn]["fillVsKeyline"] for r in rows for vn in ("color", "gray", "deuteranopia")
                                     if r["fill"][vn]["fillVsKeyline"] is not None), default=None),
            "zones": {z["key"]: {vn: z[vn] for vn in ("color", "gray", "deuteranopia")} for z in rep["zones"]},
            "frameLumaGrayP50": float(np.median(shot.luma_gray)),
        }
    finally:
        sc.cleanup()
        rep["restore"] = restore(sc.ed)
        rep["finishedUtc"] = now()
        K.write_json(out / f"board-{tag}.json", rep)
    print(json.dumps(rep.get("summary"), ensure_ascii=False, indent=1))
    return 0


def restore(ed) -> dict:
    cur = ed.call("scene", "get_current_level").split(".")[0]
    if cur.startswith(D.SCRATCH):
        ed.call("scene", "load_level", {"level_path": D.HOME})
        time.sleep(3.0)
    deleted = None
    if ed.call("asset", "exists", {"path": D.SCRATCH}):
        try:
            deleted = ed.call("asset", "delete", {"path": D.SCRATCH})
        except Exception as e:  # noqa: BLE001
            deleted = f"delete failed: {e}"
    return {"level": ed.call("scene", "get_current_level"), "scratchDeleted": deleted,
            "homeDirty": ed.call("asset", "is_dirty", {"asset_path": D.HOME})}


def cmd_restore(a) -> int:
    print(json.dumps(restore(K.Editor()), ensure_ascii=False))
    return 0


T53_EDITOR = "live UnrealEditor of the art worktree via MCP (UE_MCP_URL; 5c-B1: 127.0.0.1:8124), no mouse/keyboard/focus"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calib")
    c.add_argument("--out", required=True)
    c.add_argument("--light", default="cobble-probe")
    b = sub.add_parser("board")
    b.add_argument("--board", required=True, choices=sorted(BOARDS))
    b.add_argument("--calib", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--rings", choices=["b1", "r3"], default="b1", help="r3 = control with the W5b-R one-tone rings")
    sub.add_parser("restore")
    a = ap.parse_args(argv)
    return {"calib": cmd_calib, "board": cmd_board, "restore": cmd_restore}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
