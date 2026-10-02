"""ENV-MAPS P8.1 (track A): the env-layout overlay of the P8 lit 3D scene - EnvLayouts/sarpedon.scene.layout.json.

  python -B tools/art/concept_scene/scene_layout.py            # write
  python -B tools/art/concept_scene/scene_layout.py --check    # compare with a fresh generation + validate

Schema unmatched.env-layout-overlay/1, variant 'scene' (S08EnvLayout MergeOverlay: props / fx {remove, replace, add};
an overlay may not change lights / ground / tray / apron). Built from
  * the base layout sarpedon.layout.json: every P5c prop is removed (the island, the ship, the fort and the props below
    replace them; fx anchored on removed props go with them), the forest fireflies move over the painted canopy, the
    beach fireflies go (as in the P7 concept overlay);
  * the scene meshes (tools/art/concept_scene: island, ship, fort, palisade, piles, banner) at their pivots, yaw 0,
    scale 1 (the vertices are authored in board space), castShadow per params;
  * pack props placed by C0 pixels of the de-lit / albedo plate on the island mesh (cs_geom.Ground): 12-18 trees
    (Fab duplicates SM_EnvFab_OakDark / ForestRound / ForestNarrow / ForestSmall + bushes) whose crowns sit on the
    painted crowns (greedy disc packing of the painted canopy inside heightZones forest-canopy), 20-60 rocks
    (SM_EnvFab_RockWet / SM_Env_RockOutcrop) on the cliff ledges and the rim of the visible sides and by the
    waterfall, barrels / crates / rope coils at the painted ones on the dock and the beach; each with the optional
    "material" override = a projected-albedo MI MI_EnvScene_Proj_<Look> (track B creates them; manifest 'looks');
  * the details of design.json 5_elements: 6 lanterns (x1.2 the P7c size) hanging on their real hosts (piles / posts /
    crates / the ship rail), 2 fires (fort campfire pit + brazier, NS_Env_ConceptFire), 3 cannons on the dock,
    the banner hanging vertically from the ship rail (SM_Env_S_Banner, 320 uu).

P9 (F1 / F2 / F4 / F5): the frame band, the cascade sheets and foam (scene meshes); the dock props re-picked on the
painting and kept clear of the frame band and the ship's hull side (shifted towards the board when they would cut
into it); barrels on the ship deck; the cannons in the ship's gun ports (barrel axis through the port, out of the
hull); the rail lantern on its post arm; the banner flat against the hull side; the fx plan of track B
(fx-plan.sarpedon.json: layered fires at the brazier / fort pit, mist / spray at the cascade tiers) merged when present
- its fires replace the P8 NS_Env_ConceptFire entries; without it the P8 fx stay. The fx anchors (brazier, fort pit,
cascade tiers) are written to the overlay's conceptScene.fxAnchors.

Validation: the Python twin of MergeOverlay (tools/art/concept_paste/cp_layout.merge) + scene rules (unique ids, roots
/Game/EnvKit/ or /Game/EnvMaps/Sarpedon/Scene/, no NoAI / user mesh, material paths, Fab scale ranges, pivots off the
map, fx anchors) + tools/art/env_kit/layout_check.check_scene (cell occlusion rule 6 and key-light shadow rule 7 on
every prop incl. the new meshes; trees within 60 uu of the frame cast no shadow). Deterministic.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cs_common as CS  # noqa: E402
import cs_geom as G  # noqa: E402
import ship_build as SB  # noqa: E402
import frame_band_build as FBB  # noqa: E402

sys.path.insert(0, str(CS.REPO / "tools" / "art" / "env_kit"))
import cp_layout as CPL  # noqa: E402  (tools/art/concept_paste on the path via cs_common)
import layout_check as LC  # noqa: E402

OVERLAY_SCHEMA = "unmatched.env-layout-overlay/1"
SCENE_MESHES = ("Island", "Ship", "Fort", "Palisade", "Piles", "FrameBand", "Cascade", "CascadeFoam")
FX_PLAN = HERE / "fx-plan.sarpedon.json"  # track B (F5 fires, F4 mist / spray); merged when present
FX_PLAN_SCHEMA = "unmatched.concept-scene-fx/1"
MATERIAL_RE = re.compile(r"^/Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_(Proj_[A-Za-z]+|LanternHead)$")
SCENE_MESH_RE = re.compile(r"^/Game/EnvMaps/Sarpedon/Scene/SM_Env_S_[A-Za-z]+$")


def r2(v):
    return round(float(v) + 0.0, 2)


def seed_of(fid: str) -> int:
    return zlib.crc32(fid.encode("utf-8")) & 0x7FFFFFFF


def rot_yaw(v, yaw_deg):
    a = math.radians(yaw_deg)
    x, y, z = (float(c) for c in v)
    return np.array([x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z])


def mesh_path(name: str) -> str:
    return f"{CS.UE_DIR}/SM_Env_S_{name}"


def look(name: str) -> str:
    return f"{CS.UE_DIR}/MI_EnvScene_Proj_{name}"


def load_meshes():
    out = {}
    for n in (*SCENE_MESHES, "Banner"):
        p = CS.WORK / f"SM_Env_S_{n}.npz"
        out[n] = CS.Mesh.load(p)
    return out


# ------------------------------------------------------------------ trees from the painted canopy
def canopy_discs(L: dict):
    """Greedy disc packing of the painted canopy (green, inside the forest-canopy zone) at C0: [(cx, cy, r px)]."""
    T = L["trees"]
    rect = (-384.0, -216.0, 1000.0, 1100.0)
    k = T["maskPxPerC0"]
    w, h = int((rect[2] - rect[0]) * k), int((rect[3] - rect[1]) * k)
    img = CS.plate_c0(rect, w, h)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    mx, mn = img.max(-1), img.min(-1)
    lum = img @ np.array([0.2126, 0.7152, 0.0722])
    green = (g > r * T["greenOverRed"]) & (g > b * T["greenOverBlue"]) & ((mx - mn) > T["minChroma"]) &         (lum > T["luma"][0]) & (lum < T["luma"][1])
    zone = CS.poly_mask(CS.spec()["geometry"]["heightZones"][0]["poly"], w, h, rect)
    for extra in T.get("extraZonesPx", []):
        zone |= CS.poly_mask(extra, w, h, rect)
    for ex in T.get("excludePx", []):
        zone &= ~CS.poly_mask(ex, w, h, rect)
    m = ndimage.gaussian_filter((green & zone).astype(np.float32), T["blurC0Px"] * k) > T["blurThreshold"]
    m = ndimage.binary_opening(m, iterations=2) & zone
    dist = ndimage.distance_transform_edt(m)
    out = []
    for _ in range(T["maxCrowns"]):
        i = int(np.argmax(dist))
        rr = float(dist.flat[i])
        if rr < T["minRadiusPx"] * k:
            break
        y, x = divmod(i, w)
        out.append((rect[0] + (x + 0.5) / k, rect[1] + (y + 0.5) / k, rr / k))
        yy, xx = np.ogrid[:h, :w]
        dist[(xx - x) ** 2 + (yy - y) ** 2 <= (rr * T["suppress"]) ** 2] = 0
    return out


def painted_rock_discs(RP: dict):
    """Greedy disc packing of the painted grey boulders (low chroma, mid luma) inside the zones (C0 px)."""
    rect = (-384.0, -216.0, 2304.0, 1296.0)
    k = RP["maskPxPerC0"]
    w, h = int((rect[2] - rect[0]) * k), int((rect[3] - rect[1]) * k)
    img = CS.plate_c0(rect, w, h)
    lum = img @ np.array([0.2126, 0.7152, 0.0722])
    chroma = img.max(-1) - img.min(-1)
    grey = (chroma < RP["maxChroma"]) & (lum > RP["luma"][0]) & (lum < RP["luma"][1])
    zone = np.zeros((h, w), bool)
    for z in RP["zonesPx"]:
        zone |= CS.poly_mask(z, w, h, rect)
    m = ndimage.gaussian_filter((grey & zone).astype(np.float32), RP["blurC0Px"] * k) > RP["blurThreshold"]
    m = ndimage.binary_opening(m, iterations=1) & zone
    dist = ndimage.distance_transform_edt(m)
    out = []
    for _ in range(RP["max"]):
        i = int(np.argmax(dist))
        rr = float(dist.flat[i])
        if rr < RP["minRadiusPx"] * k:
            break
        y, x = divmod(i, w)
        out.append((rect[0] + (x + 0.5) / k, rect[1] + (y + 0.5) / k, rr / k))
        yy, xx = np.ogrid[:h, :w]
        dist[(xx - x) ** 2 + (yy - y) ** 2 <= (rr * 1.6) ** 2] = 0
    return out


def place_tree(cx, cy, rpx, pick: dict, ground: G.Ground, crown_frac: float, scale_mul: float):
    """Foot on the island below the painted crown centre: the C0 ray point Q with Q.z - ground(Q) = crown_frac x H,
    H = the pick's height x s, s from the painted crown radius / the pick's crown radius."""
    cam = CS.cam0()
    d = cam.rays(np.array(float(cx)), np.array(float(cy)))
    d = d / np.linalg.norm(d)
    (x0, y0, z0), (x1, y1, z1) = pick["bboxMin"], pick["bboxMax"]
    crown_r = 0.25 * ((x1 - x0) + (y1 - y0))
    t_hit = G.ray_mesh(cam.pos, d, ground.P, ground.F)
    lo, hi = t_hit - 1500.0, t_hit
    s = 0.1
    for _ in range(50):
        t = (lo + hi) / 2
        Q = cam.pos + t * d
        depth = float((Q - cam.pos) @ cam.fwd)
        s = rpx * depth / cam.f_px / crown_r * scale_mul
        try:
            gz = ground.height_at(Q[0], Q[1])
        except ValueError:
            gz = -3.0
        if Q[2] - gz > crown_frac * (z1 - z0) * s:
            lo = t
        else:
            hi = t
    Q = cam.pos + lo * d
    gz = ground.height_at(Q[0], Q[1])
    return np.array([Q[0], Q[1], gz]), s


# ------------------------------------------------------------------ build
def build(base: dict, meshes: dict):
    allp = CS.params()
    L = allp["layout"]
    rng = np.random.default_rng(L["seed"])
    island = meshes["Island"]
    ground = G.Ground([island])
    cam = CS.cam0()
    fab = LC.FAB
    add, add_fx = [], []
    info = {}

    # scene meshes
    for n in SCENE_MESHES:
        m = meshes[n]
        add.append({"id": f"scene-{n.lower()}", "mesh": mesh_path(n), "loc": [r2(v) for v in m.pivot], "yawDeg": 0.0,
                    "scale": 1.0, "castShadow": bool(L["castShadow"][n])})
    wall = SB.Wall(allp["ship"])
    ship_rep = CS.load_json(CS.RUNS["ship"] / "reports" / "ship-build.json")
    band = FBB.outer_extents(allp["frameBand"])
    # P8.3: rocks at the sea level filling the ground sea ring's inner hole where the island foot does not cover it
    # (the ring's hole = tray outline - 40 uu; lit3d moves the ring to seaZUU -300; W-front corner showed black void)
    for r in L.get("footRocks") or []:
        # P9 tune: an entry may name its mesh (the Fab wet rock for the cascade rocks breaking its outline)
        mesh = r.get("mesh") or f"/Game/EnvKit/Sarpedon/SM_Env_{r['kit']}"
        add.append({"id": r["id"], "mesh": mesh, "loc": [r2(v) for v in r["loc"]],
                    "yawDeg": float(r["yawDeg"]), "scale": float(r["scale"]), "castShadow": False,
                    "material": look(r["look"])})

    # trees
    T = L["trees"]
    discs = canopy_discs(L)
    trees = []
    kinds = T["cycle"]
    k_tree = 0
    for i, (cx, cy, rpx) in enumerate(discs):
        if rpx < T["bushMaxRadiusPx"]:
            kind = "Bush"
        else:
            kind = kinds[k_tree % len(kinds)]
            k_tree += 1
        pick = fab[kind]
        foot, s = place_tree(cx, cy, rpx, pick, ground, T["crownFrac"], T["scaleMul"])
        lo_s, hi_s = pick["scaleRange"]
        s = min(max(s, lo_s), hi_s)
        trees.append((kind, foot, s, (cx, cy, rpx)))
    n_tree = 0
    for i, (kind, foot, s, disc) in enumerate(trees):
        dfr = LC_rect_dist(foot[0], foot[1])
        is_bush = kind == "Bush"
        pid = f"{'bush' if is_bush else 'tree'}-{i:02d}"
        n_tree += 0 if is_bush else 1
        add.append({"id": pid, "mesh": f"/Game/EnvKit/Fab/Sarpedon/SM_EnvFab_{kind}",
                    "loc": [r2(foot[0]), r2(foot[1]), r2(foot[2] - T["sinkUU"])],
                    "yawDeg": r2(rng.uniform(0, 360)), "scale": round(float(s), 3),
                    "castShadow": bool(dfr > T["noShadowNearFrameUU"]),
                    "material": look("Foliage")})
    info["trees"] = {"crowns": len(discs), "trees": n_tree, "bushes": len(trees) - n_tree}

    # rocks on ledges / rim
    rimd = np.load(CS.WORK / "island_rim.npz")
    rings, R = rimd["rings"], rimd["R"]
    nrm = CS.vertex_normals_2d(R)
    Rk = L["rocks"]
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([R, R[:1]]), axis=0), axis=1))][:-1]
    rocks = []
    last = -1e9
    matte = np.asarray(CS.spec()["geometry"]["islandMatte"]["poly"], float)
    canopy = [np.asarray(CS.spec()["geometry"]["heightZones"][0]["poly"], float)] +         [np.asarray(z, float) for z in T.get("extraZonesPx", [])]
    ship_px = np.asarray(Rk["shipExcludePx"], float)  # the painted ship incl. its outpainted extension (P8 targetPx)
    for i in np.argsort(arc):
        if arc[i] - last < Rk["spacingUU"]:
            continue
        nx, ny = nrm[i]
        visible_side = ny > Rk["minFacingY"] or nx < -Rk["minFacingWest"] or (nx > 0.6 and R[i, 1] > 0)
        if not visible_side:
            continue
        if Rk["fallGapX"][0] < R[i, 0] < Rk["fallGapX"][1] and R[i, 1] > 300:
            continue  # the waterfall itself stays free
        if LC_rect_dist(R[i, 0], R[i, 1]) < Rk["minFrameDistUU"]:
            continue
        ring = Rk["ledgeRings"][len(rocks) % len(Rk["ledgeRings"])]
        Q = rings[ring, i]
        # only where the painting shows the island at C0 (inside the island matte, off the painted ship): the rock's
        # projected albedo must be painted rock / ground, not sea or sky
        q = cam.project(Q + np.array([0.0, 0.0, 20.0]))[0]
        if not (CS.inside(matte, q[None])[0] and not CS.inside(ship_px, q[None])[0]
                and CS.seg_dist(q[None], matte)[0] > Rk["matteMarginPx"]):
            continue
        if any(CS.inside(z, q[None])[0] for z in canopy):
            continue  # painted crowns there, not rock
        rocks.append((Q, i))
        last = arc[i]
    for j, (Q, i) in enumerate(rocks[:Rk["max"]]):
        wet = j % 2 == 0
        if wet:
            s = rng.uniform(*Rk["wetScale"])
            z = Q[2] + 83.5 * s * Rk["wetBury"]
            mesh = "/Game/EnvKit/Fab/Sarpedon/SM_EnvFab_RockWet"
        else:
            s = rng.uniform(*Rk["outcropScale"])
            z = Q[2] - Rk["outcropSinkUU"]
            mesh = "/Game/EnvKit/Sarpedon/SM_Env_RockOutcrop"
        add.append({"id": f"rock-{j:02d}", "mesh": mesh, "loc": [r2(Q[0]), r2(Q[1]), r2(z)],
                    "yawDeg": r2(rng.uniform(0, 360)), "scale": round(float(s), 3), "castShadow": True,
                    "material": look("RockWet" if Q[2] < Rk["wetBelowZ"] else "Rock")})
    for j, px in enumerate(Rk["extraPx"]):
        Q = ground.hit_px(*px)
        s = rng.uniform(*Rk["wetScale"])
        add.append({"id": f"rock-x{j}", "mesh": "/Game/EnvKit/Fab/Sarpedon/SM_EnvFab_RockWet",
                    "loc": [r2(Q[0]), r2(Q[1]), r2(Q[2] + 83.5 * s * Rk["wetBury"])],
                    "yawDeg": r2(rng.uniform(0, 360)), "scale": round(float(s), 3), "castShadow": True,
                    "material": look("Rock")})
    # the painted boulders on the plateau (grey, low chroma blobs inside rocksPainted.zonesPx): a rock prop on each
    RP = Rk["painted"]
    n_painted = 0
    for j, (cx, cy, rpx) in enumerate(painted_rock_discs(RP)):
        try:
            Q = ground.hit_px(cx, cy + rpx * 0.5)
        except ValueError:
            continue
        depth = float((Q - cam.pos) @ cam.fwd)
        r_uu = rpx * depth / cam.f_px
        s = min(max(r_uu / RP["meshRadiusUU"], Rk["wetScale"][0]), RP["maxScale"])
        add.append({"id": f"rock-p{j:02d}", "mesh": "/Game/EnvKit/Fab/Sarpedon/SM_EnvFab_RockWet",
                    "loc": [r2(Q[0]), r2(Q[1]), r2(Q[2] + 83.5 * s * RP["bury"])],
                    "yawDeg": r2(rng.uniform(0, 360)), "scale": round(float(s), 3), "castShadow": True,
                    "material": look("Rock")})
        n_painted += 1
    info["rocks"] = min(len(rocks), Rk["max"]) + len(Rk["extraPx"]) + n_painted
    info["paintedRocks"] = n_painted

    # barrels / crates / rope coils at the painted ones (P9: clear of the frame band and the ship's hull side)
    shifts = {}
    for p in L["props"]:
        Q = ground.hit_px(*p["footPx"])
        name = p["kit"]
        hpx = p["heightPx"]
        depth = float((Q - cam.pos) @ cam.fwd)
        # painted height in uu (vertical extent foreshortened by cos 55 at C0) / the kit height
        h_uu = hpx * depth / cam.f_px / math.cos(math.radians(55.0))
        _, _, h1 = LC.dims(name, 1.0)
        s = h_uu / h1 if p.get("byHeight", True) else p["scale"]
        s = min(max(s, p.get("scaleRange", [0.5, 3.0])[0]), p.get("scaleRange", [0.5, 3.0])[1])
        prop = {"id": p["id"], "mesh": f"/Game/EnvKit/Sarpedon/SM_Env_{name}", "loc": [r2(Q[0]), r2(Q[1]), r2(Q[2] - 1.0)],
                "yawDeg": float(p.get("yawDeg", rng.uniform(0, 360))), "scale": round(float(s), 3),
                "castShadow": True, "material": look("Wood")}
        moved = clear_of_band_and_hull(prop, band, wall, ship_rep, L["propClearance"], ground)
        if moved:
            shifts[p["id"]] = moved
        add.append(prop)
    info["propShifts"] = shifts
    # P9 F1: barrels on the ship deck behind the rail (painted above the rail line)
    deck = {}
    for p in L.get("shipDeckProps", []):
        prop, moved = deck_prop(p, wall, ship_rep, allp["ship"])
        add.append(prop)
        deck[prop["id"]] = {"movedOnDeckUU": moved}
    info["shipDeckProps"] = deck

    # details: lanterns / cannons / banner / fires
    D = L["details"]
    p7 = CPL.load(CPL.BUILD_REPORT)
    lant = CPL.export_of(p7, "SM_EnvCP_LanternHead")
    head_h = float(lant["boundsUeLocalUU"]["size"][2])
    glow = np.array(lant["glowOffsetUU"], float)
    hosts = host_points(meshes, add)
    spec = CS.spec()
    det = {d["id"]: d for d in spec["details"]}
    placed = {}
    for lid, cfg in D["lanterns"].items():
        d = det[lid]
        ray = cam.rays(np.array(float(d["px"][0])), np.array(float(d["px"][1])))
        ray = ray / np.linalg.norm(ray)
        if cfg["host"] == "ship":
            # P9: hangs from the rail post's arm (ship_build.lantern_rail: the painted pixel's ray on the plane of
            # the arm tip, outside the hull side; the post's arm sits over the lantern head's top)
            W = np.array(ship_rep["info"]["lanternRail"]["glow"], float)
        else:
            hp = hosts[cfg["host"]]
            yplane = hp[1] + cfg.get("frontUU", 12.0)
            t = (yplane - cam.pos[1]) / ray[1]
            W = cam.pos + t * ray
        depth = float((W - cam.pos) @ cam.fwd)
        size_uu = d["sizePx"][1] * depth / cam.f_px
        s = size_uu * D["lanternSizeMul"] / head_h
        yaw = 90.0
        loc = W - rot_yaw(glow * s, yaw)
        lp = {"id": lid, "mesh": "/Game/EnvKit/ConceptPaste/SM_EnvCP_LanternHead", "loc": [r2(v) for v in loc],
              "yawDeg": yaw, "scale": round(s, 3), "castShadow": False}
        if D.get("lanternMaterial"):  # P8.3: the lit3d glass (a child MI of the P7c lantern MI, ue_scene_material)
            lp["material"] = f"{CS.UE_DIR}/{D['lanternMaterial']}"
        add.append(lp)
        add_fx.append({"id": "flame-" + lid, "system": "/Game/EnvKit/FX/NS_Env_LanternFlame", "anchor": lid,
                       "loc": [r2(v) for v in glow * s], "yawDeg": 0.0, "scale": round(s, 3),
                       "seed": seed_of("flame-" + lid), "warmupS": 1.5})
        placed[lid] = {"glowWorld": [r2(v) for v in W], "scale": round(s, 3), "host": cfg["host"]}
    can = p7["kitMeasurements"]["SM_Env_Cannon"]
    axis = np.array([0.0, float(can["barrelAxisYUU"]), float(can["barrelAxisZUU"])])
    ports = {pt["cannon"]: pt for pt in ship_rep["info"]["ports"]}
    for cid in ("cannon-1", "cannon-2", "cannon-3"):
        d = det[cid]
        # P9 F1: the cannons sit in the ship's gun ports (ship_build.ports_of: the painted muzzle on the plane just
        # outside the hull side, only the bare barrel out, the carriage inside the port / hull)
        pt = ports[cid]
        P = np.array(pt["axisPoint"], float)
        s = float(pt["scale"])
        yaw = float(pt["yawDeg"])
        loc = P - rot_yaw(axis * s, yaw)
        add.append({"id": cid, "mesh": "/Game/EnvKit/ConceptPaste/SM_EnvCP_Cannon", "loc": [r2(v) for v in loc],
                    "yawDeg": yaw, "scale": round(s, 3), "castShadow": True})
        placed[cid] = {"barrelWorld": [r2(v) for v in P], "scale": round(s, 3), "port": pt["centre"]}
    bd = det["banner-ship"]
    ray = cam.rays(np.array(float(bd["px"][0])), np.array(float(bd["px"][1])))
    ray = ray / np.linalg.norm(ray)
    # P9: flat against the hull side, bannerOutUU outside it, the painted top pixel on that plane
    top = wall.on_plane(bd["px"][0], bd["px"][1], -D["bannerOutUU"])
    s_b = D["bannerLengthUU"] / CS.params()["banner"]["lengthUU"]
    add.append({"id": "banner-ship", "mesh": mesh_path("Banner"), "loc": [r2(v) for v in top],
                "yawDeg": round(wall.out_yaw_deg(), 3), "scale": round(s_b, 3), "castShadow": True})
    # the cloth must not cut into the dock / island (vertices below the island top under them)
    yb = math.radians(wall.out_yaw_deg())
    Rb = np.array([[math.cos(yb), -math.sin(yb), 0.0], [math.sin(yb), math.cos(yb), 0.0], [0.0, 0.0, 1.0]])
    Vb = meshes["Banner"].V * s_b @ Rb.T + top
    cut = 0
    for v in Vb[Vb[:, 2] < 0.0]:
        try:
            cut += int(ground.height_at(v[0], v[1]) > v[2] + 0.5)
        except ValueError:
            pass
    if cut:
        raise SystemExit(f"banner-ship: {cut} cloth vertices inside the island (cliff / dock under the hem)")
    placed["banner-ship"] = {"topWorld": [r2(v) for v in top], "lengthUU": round(s_b * float(np.ptp(meshes["Banner"].V[:, 2])), 1),
                             "widthUU": round(s_b * CS.params()["banner"]["widthUU"], 1), "hang": "vertical",
                             "clothVerticesInIsland": cut}
    anchors = {}
    p8_fires = []
    for fid in ("fire-fort", "fire-brazier"):
        cfg = D["fires"][fid]
        hit = ground.hit_px(*det[fid]["px"])
        ray = cam.rays(np.array(float(det[fid]["px"][0])), np.array(float(det[fid]["px"][1])))
        t = (hit[2] + cfg["heightUU"] - cam.pos[2]) / ray[2]
        Q = cam.pos + t * ray + np.array([0.0, 0.0, cfg["dz"]])
        if cfg.get("pitKit"):
            add.append({"id": fid + "-pit", "mesh": f"/Game/EnvKit/Sarpedon/SM_Env_{cfg['pitKit']}",
                        "loc": [r2(hit[0]), r2(hit[1]), r2(hit[2] - 1.0)], "yawDeg": 0.0, "scale": cfg["pitScale"],
                        "castShadow": False, "material": look("Rock")})
        p8_fires.append({"id": fid, "system": "/Game/EnvKit/FX/NS_Env_ConceptFire", "loc": [r2(v) for v in Q],
                         "yawDeg": 0.0, "scale": cfg["scale"], "seed": seed_of(fid), "warmupS": 1.5})
        placed[fid] = {"fxWorld": [r2(v) for v in Q]}
        anchors["fort-pit" if fid == "fire-fort" else "brazier"] = {
            "loc": [r2(v) for v in Q], "ground": [r2(v) for v in hit], "kind": "fire",
            "note": "the P8 fire point (the painted fire pixel's ray at heightUU above the ground hit)"}
    casc = CS.load_json(CS.RUNS["props"] / "reports" / "cascade-build.json")
    for t_ in casc["info"]["tiers"]:
        anchors[f"falls-tier-{t_['tier']}"] = {"loc": t_["landing"], "widthUU": t_["widthUU"], "sea": t_["sea"],
                                               "kind": "falls", "tier": t_["tier"]}
    plan, plan_info = fx_plan(anchors)
    add_fx += p8_fires if plan is None else plan
    info["fxPlan"] = plan_info
    info["fxAnchors"] = anchors
    info["details"] = placed

    # overlay
    base_fx = {f["id"]: f for f in base.get("fx", [])}
    ff = L["fireflies"]
    fx_ops = {"remove": [i for i in ff["remove"] if i in base_fx],
              "replace": [{"id": i, "loc": [r2(v) for v in loc]} for i, loc in ff["replace"].items() if i in base_fx],
              "add": add_fx}
    lights_ref = []
    for lt in L["lights"]:
        P = np.array(placed[lt["on"]].get("glowWorld") or placed[lt["on"]].get("fxWorld"), float)
        lights_ref.append({"id": lt["id"], "loc": [r2(P[0]), r2(P[1]), r2(P[2] + lt["dz"])],
                           "colorSrgb": lt["colorSrgb"], "intensityCd": lt["intensityCd"], "radius": lt["radius"]})
    overlay = {"schema": OVERLAY_SCHEMA, "map": "sarpedon", "variant": "scene", "boardId": base["boardId"],
               "props": {"remove": [p["id"] for p in base["props"]], "add": add}, "fx": fx_ops,
               "conceptScene": {
                   "manifest": "tools/art/concept_scene/manifest.sarpedon.json",
                   "fxAnchors": anchors,
                   "fxPlan": plan_info,
                   "lit3dHide": {"waterfalls": True,
                                 "note": "P9 F4: the cascade (scene-cascade / scene-cascadefoam) replaces the P5c ground "
                                         "waterfall in lit3d (the island's waterfall tongue is gone): the profile's lit3d "
                                         "'hide' must list 'waterfalls' (track B); P5c / paste unchanged"},
                   "params": "tools/art/concept_scene/scene-params.sarpedon.json",
                   "materialOverride": "optional prop field 'material' = a projected-albedo MI (MI_EnvScene_Proj_<Look>, "
                                       "manifest 'looks'); track B: applied to ALL mesh slots of that prop",
                   "seaZ": allp["seaZ"],
                   "seaNote": "the island cliffs and the ship's waterline reach Z -300 (task R3); the base ground.sea "
                              "ring stays at -172 unless the profile lowers it (overlays may not change 'ground'): "
                              "the cliffs simply continue under the opaque sea",
                   "lights": {"mode": "profile", "reference": lights_ref,
                              "note": "informational: the profile block conceptPaste (mode lit3d) carries the 5 points "
                                      "(+ the moon-pool = 6); positions = the real fire / lantern points of this layout"}},
               "notes": ("ENV-MAPS P8 lit 3D scene (path 1), variant 'scene', written by tools/art/concept_scene/"
                         "scene_layout.py. Status: предложено (CREATE stage, nothing rendered in UE yet).")}
    return overlay, info


def clear_of_band_and_hull(prop: dict, band: dict, wall, ship_rep: dict, C: dict, ground: G.Ground):
    """P9: a dock prop's footprint must keep C['bandUU'] from the frame band's outer rectangle and C['hullUU'] off the
    hull side (the outermost wale / clinker) along the hull's length; else it moves towards the board along the hull's
    outward normal (then away from the band along X), its Z re-read on the island. Returns the shift (uu) or None."""
    out = np.asarray(wall.out2, float)
    s_n, s_s = ship_rep["info"]["sNorth"], ship_rep["info"]["sSouth"] + ship_rep["info"]["bowUU"]
    rect = np.array([[band["westX"], band["farY"]], [band["eastX"], band["farY"]], [band["eastX"], band["nearY"]],
                     [band["westX"], band["nearY"]]])
    moved = np.zeros(2)
    for _ in range(40):
        fp = LC.footprint(prop)
        s_c = (fp - wall.F0) @ wall.u2
        d_c = (fp - wall.F0) @ wall.in2
        along = (s_c > s_n - C["hullUU"]) & (s_c < s_s)
        need_hull = float(np.max(d_c[along] + C["hullUU"])) if along.any() else -1.0
        cl = LC.poly_clearance(fp, rect)
        if need_hull <= 0 and cl >= C["bandUU"]:
            break
        if need_hull > 0:
            step = out * (need_hull + 0.5)
        else:
            # away from the band across its nearest outer edge
            c = fp.mean(0)
            edges = {(1.0, 0.0): band["eastX"] - c[0], (-1.0, 0.0): c[0] - band["westX"],
                     (0.0, -1.0): c[1] - band["farY"], (0.0, 1.0): band["nearY"] - c[1]}
            dirn = np.array(min(edges, key=lambda k: abs(edges[k])))
            step = dirn * (C["bandUU"] - cl + 0.5)
        moved += step
        prop["loc"][0] = r2(prop["loc"][0] + step[0])
        prop["loc"][1] = r2(prop["loc"][1] + step[1])
    else:
        raise SystemExit(f"prop {prop['id']}: no place between the frame band and the hull")
    if not moved.any():
        return None
    prop["loc"][2] = r2(ground.height_at(prop["loc"][0], prop["loc"][1]) - 1.0)
    return [r2(moved[0]), r2(moved[1])]


def deck_prop(p: dict, wall, ship_rep: dict, SP: dict) -> dict:
    """A kit prop on the ship deck at its painted centre pixel: the pixel's ray on the plane deck + h / 2 (h = the
    painted height at that depth), kept inside the bulwarks."""
    cam = CS.cam0()
    H = SP["hull"]
    name = p["kit"]
    _, _, h1 = LC.dims(name, 1.0)
    w1, d1, _ = LC.dims(name, 1.0)
    s_mid = 0.5 * (ship_rep["info"]["sNorth"] + ship_rep["info"]["sSouth"])
    zd = float(wall.rail_z(s_mid)) - float(H["deckDropUU"])
    s = 1.0
    Q = None
    for _ in range(20):
        Q = CS.ray_z(p["centrePx"][0], p["centrePx"][1], zd + 0.5 * h1 * s)
        depth = float((Q - cam.pos) @ cam.fwd)
        s = p["heightPx"] * depth / cam.f_px / math.cos(math.radians(55.0)) / h1
        s = min(max(s, p["scaleRange"][0]), p["scaleRange"][1])
    s_q, d_q, _ = wall.sdz(Q)
    r = 0.5 * max(w1, d1) * s
    t, B = float(H["wallThickUU"]), float(H["beamUU"])
    # on the deck: inside the bulwarks and between the stern transom and the bow
    s_in = min(max(s_q, ship_rep["info"]["sNorth"] + r + 1.0), ship_rep["info"]["sSouth"] - r - 1.0)
    d_in = min(max(d_q, t + r + 1.0), B - t - r - 1.0)
    zd = float(wall.rail_z(s_in)) - float(H["deckDropUU"])
    P = wall.P(s_in, d_in, zd)
    moved = float(np.hypot(s_in - s_q, d_in - d_q))
    return {"id": p["id"], "mesh": f"/Game/EnvKit/Sarpedon/SM_Env_{name}", "loc": [r2(P[0]), r2(P[1]), r2(zd - 0.5)],
            "yawDeg": float(p.get("yawDeg", 0.0)), "scale": round(float(s), 3), "castShadow": True,
            "material": look("Wood")}, round(moved, 1)


def fx_plan(anchors: dict, path: Path | None = None):
    """Track B's fx plan (fx-plan.sarpedon.json, schema unmatched.concept-scene-fx/1): fires [{id, system, anchor
    brazier | fort-pit, offsetUU, scale, yawDeg}] and waterfall [{id, system, tier, scale, offsetUU?}] resolved on the
    anchors to absolute fx entries. (None, info) when the file is absent."""
    path = FX_PLAN if path is None else Path(path)
    if not path.is_file():
        return None, {"file": CS.rel(path), "present": False,
                      "note": "absent: the P8 NS_Env_ConceptFire fires stay; no cascade mist"}
    plan = CS.load_json(path)
    if plan.get("schema") != FX_PLAN_SCHEMA:
        raise SystemExit(f"{CS.rel(path)}: schema {plan.get('schema')!r} != {FX_PLAN_SCHEMA}")
    out = []
    for f in plan.get("fires", []):
        a = anchors.get(f["anchor"])
        if a is None or a["kind"] != "fire":
            raise SystemExit(f"fx plan {f['id']}: anchor {f['anchor']!r} is not brazier | fort-pit")
        loc = np.asarray(a["loc"], float) + np.asarray(f.get("offsetUU", [0.0, 0.0, 0.0]), float)
        out.append({"id": f["id"], "system": f["system"], "loc": [r2(v) for v in loc],
                    "yawDeg": float(f.get("yawDeg", 0.0)), "scale": float(f.get("scale", 1.0)),
                    "seed": seed_of(f["id"]), "warmupS": float(f.get("warmupS", 1.5))})
    dropped = []
    for f in plan.get("waterfall", []):
        a = anchors.get(f"falls-tier-{int(f['tier'])}")
        if a is None:  # a tier the cascade does not have (the plan's contract: dropped, reported)
            dropped.append(f["id"])
            continue
        loc = np.asarray(a["loc"], float) + np.asarray(f.get("offsetUU", [0.0, 0.0, 0.0]), float)
        out.append({"id": f["id"], "system": f["system"], "loc": [r2(v) for v in loc],
                    "yawDeg": float(f.get("yawDeg", 0.0)), "scale": float(f.get("scale", 1.0)),
                    "seed": seed_of(f["id"]), "warmupS": float(f.get("warmupS", 1.5))})
    return out, {"file": CS.rel(path), "present": True, "sha256": CS.text_sha256_lf(path),
                 "fires": len(plan.get("fires", [])), "waterfall": len(plan.get("waterfall", [])) - len(dropped),
                 "droppedTiers": dropped}


def LC_rect_dist(x, y):
    return float(LC_rect(x, y))


def LC_rect(x, y):
    dx = abs(x) - CS.C.FRAME_HX
    dy = abs(y) - CS.C.FRAME_HY
    return math.hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0)


def host_points(meshes, add):
    """Board points of the lantern hosts: the piles / palisade build reports (group feet) and the placed crates."""
    hosts = {}
    for rep in ("piles-build.json", "palisade-build.json"):
        d = CS.load_json(CS.RUNS["props"] / "reports" / rep)
        for g in d["info"]["groups"]:
            hosts[g["id"]] = np.array(g["feet"][0], float)
    for p in add:
        if p["id"].startswith("crate-"):
            hosts[p["id"]] = np.array(p["loc"], float)
    return hosts


# ------------------------------------------------------------------ geometry proxies for layout_check rule 12
PROXIES = HERE / "scene-proxies.sarpedon.json"


def proxies_of(meshes: dict, cell: float = 90.0, sample: float = 40.0) -> dict:
    """Per scene mesh: the 3D convex hulls (vertices, local to the pivot) of its surface ABOVE Z 0, clustered in
    `cell`-uu cubes; large triangles are sampled every `sample` uu so long faces (masts, walls) are covered."""
    from scipy.spatial import ConvexHull, QhullError
    out = {}
    for n, m in meshes.items():
        B = m.board()
        T = B[m.F]
        pts = [B]
        e = np.max(np.linalg.norm(T - np.roll(T, 1, axis=1), axis=2), axis=1)
        for k in np.unique(np.ceil(e[e > sample] / sample).astype(int)):
            sel = T[np.ceil(e / sample).astype(int) == k]
            sel = sel[(sel[:, :, 2] > 0).any(1)]
            if not len(sel):
                continue
            ij = [(i, j) for i in range(k + 1) for j in range(k + 1 - i)]
            W = np.array([(i / k, j / k, 1 - (i + j) / k) for i, j in ij])
            pts.append(np.einsum("wk,tkd->twd", W, sel).reshape(-1, 3))
        P = np.vstack(pts)
        if not np.allclose(m.pivot, 0.0) or n != "Banner":
            P = P[P[:, 2] > 0.0]  # authored in board space: only the part above the map plane matters
        # (the banner is authored local to its rod: all points, layout_check clips after the placement)
        clusters = []
        if len(P):
            key = np.floor(P / cell).astype(np.int64)
            order = np.lexsort((key[:, 2], key[:, 1], key[:, 0]))
            key, P = key[order], P[order]
            brk = np.r_[0, np.nonzero(np.any(np.diff(key, axis=0) != 0, axis=1))[0] + 1, len(P)]
            for a, b in zip(brk[:-1], brk[1:]):
                Q = np.unique(np.round(P[a:b], 1), axis=0)
                if len(Q) >= 5:
                    try:
                        Q = Q[ConvexHull(Q, qhull_options="QJ").vertices]
                    except QhullError:
                        pass
                clusters.append(np.round(Q - m.pivot, 1).tolist())
        out[n] = {"pivot": [round(float(v), 3) for v in m.pivot], "clusters": clusters,
                  "aboveZ0Points": int(len(P)), "maxZ": round(float(B[:, 2].max()), 1)}
    return {"schema": "unmatched.concept-scene.proxies/1", "cellUU": cell, "sampleUU": sample,
            "note": "written by tools/art/concept_scene/scene_layout.py from the exported meshes; read by "
                    "tools/art/env_kit/layout_check.py check_scene (rule 12: occlusion / key-light shadow of the scene "
                    "meshes by their geometry above the map plane)", "meshes": out}


# ------------------------------------------------------------------ validation
def validate(base: dict, overlay: dict) -> list[str]:
    err = []
    try:
        merged = CPL.merge(base, overlay)
    except ValueError as exc:
        return [f"merge: {exc}"]
    ids = [p["id"] for p in merged["props"]]
    if len(ids) != len(set(ids)):
        err.append("duplicate prop ids")
    fx_ids = [f["id"] for f in merged.get("fx", [])]
    if len(fx_ids) != len(set(fx_ids)):
        err.append("duplicate fx ids")
    for p in merged["props"]:
        m = p["mesh"]
        if not (m.startswith("/Game/EnvKit/") or SCENE_MESH_RE.match(m)):
            err.append(f"prop {p['id']}: mesh {m} outside /Game/EnvKit/ and the scene folder")
        if any(n in m for n in LC.NOAI_ROOTS) or "/UserFab/" in m:
            err.append(f"prop {p['id']}: NoAI / user mesh")
        if "material" in p and not MATERIAL_RE.match(p["material"]):
            err.append(f"prop {p['id']}: material {p['material']} is not a MI_EnvScene_Proj_<Look> / LanternHead path")
        s = float(p.get("scale", 1.0))
        if not (0 < s <= 20):
            err.append(f"prop {p['id']}: scale out of (0, 20]")
        name = LC.mesh_name(p)
        fe = LC.fab_entry(name)
        if fe and not (fe["scaleRange"][0] - 1e-6 <= s <= fe["scaleRange"][1] + 1e-6):
            err.append(f"prop {p['id']}: scale {s} outside the Fab pick range {fe['scaleRange']}")
        x, y = p["loc"][:2]
        if abs(x) < CS.C.MAP_HX and abs(y) < CS.C.MAP_HY:
            err.append(f"prop {p['id']}: pivot on the painted map (S08EnvLayout skips it)")
    for f in merged.get("fx", []):
        if not f["system"].startswith("/Game/EnvKit/"):
            err.append(f"fx {f['id']}: system outside /Game/EnvKit/")
        if f.get("anchor") and f["anchor"] not in ids:
            err.append(f"fx {f['id']}: anchor {f['anchor']} not a prop")
    return err


def text_of(overlay: dict) -> str:
    return json.dumps(overlay, indent=2, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    base = CPL.load(CS.LAYOUTS / "sarpedon.layout.json")
    meshes = load_meshes()
    overlay, info = build(base, meshes)
    errs = validate(base, overlay)
    text = text_of(overlay)
    prox = proxies_of({n: meshes[n] for n in (*SCENE_MESHES, "Banner")})
    # pack trees / bushes / rocks whose key-light shadow comes within SHADOW_WARN_UU of a circle cast none (task R5)
    pre = LC.check_scene("sarpedon", overlay=overlay, proxies=prox["meshes"])
    adjusted = []
    for p in overlay["props"]["add"]:
        sh = pre["info"].get(p["id"], {}).get("shadow_uu")
        if p.get("castShadow") and sh is not None and sh < LC.SHADOW_WARN_UU and \
                re.match(r"^(tree|bush|rock)-", p["id"]):
            p["castShadow"] = False
            adjusted.append(p["id"])
    text = text_of(overlay)
    info["shadowOff"] = adjusted
    prox_text = json.dumps(prox, separators=(",", ":")) + "\n"
    if a.check:
        if not CS.SCENE_LAYOUT.is_file() or CS.SCENE_LAYOUT.read_text(encoding="utf-8") != text:
            errs.append("sarpedon.scene.layout.json differs from a fresh generation (run scene_layout.py)")
        if not PROXIES.is_file() or PROXIES.read_text(encoding="utf-8") != prox_text:
            errs.append("scene-proxies.sarpedon.json differs from a fresh generation (run scene_layout.py)")
    else:
        CS.SCENE_LAYOUT.write_text(text, encoding="utf-8", newline="\n")
        PROXIES.write_text(prox_text, encoding="utf-8", newline="\n")
    res = LC.check_scene("sarpedon", overlay=overlay, proxies=prox["meshes"])
    errs += res["errors"]
    CS.dump_json(CS.WORK / "scene-layout-info.json", {"info": info, "check": {k: v for k, v in res.items() if k != "layout"}})
    print(f"SCENE-LAYOUT {'ok' if not errs else 'FAILED'} props+={len(overlay['props']['add'])} "
          f"fx+={len(overlay['fx']['add'])} trees={info['trees']} rocks={info['rocks']} "
          f"warnings={len(res['warnings'])}" + ("; " + "; ".join(errs) if errs else ""))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
