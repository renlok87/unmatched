#!/usr/bin/env python3
"""ENV-MAPS P5c track F: Fab foliage / props in the two env layouts - props only (never 'lights', 'ground' or 'fx').

  python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/p5c_layout_props.py [--check]
         [--layouts DIR] [--out DIR] [--report]

Idempotent: every prop whose id is in P5C_PROPS[<map>] is removed and the list is appended again (in this order) after
the remaining props; nothing else changes (tray, apron, lights, 'ground', 'fx'). The notes get one 'P5c track F'
paragraph (replaced on a re-run). --check exits 1 when a layout differs from what this script writes (before the
integrate stage runs this script that is expected: the committed layouts are the P5b state). --out DIR writes the
results there instead of over the layouts (scratch validation: layout_check.py --layouts DIR). --report writes
reports/p5c-layout-report.json (instance triangles P5b -> P5c, cherry crown centres, lantern-to-campfire-light distances).

The meshes are the Fab duplicates /Game/EnvKit/Fab/<Map>/SM_EnvFab_<Name> of scripts/fab-picks.json (imported by
tools/art/env_kit/ue_import_fab_picks.py; layout_check.py knows their pack bounds and pivots). The P5b review follow-ups
handled here: the Marmoreal cherries become the pink Forest trees (ids kept: cherry-*; ground_splat keys the petals on
them), the Sarpedon forest becomes the dark Forest oaks / Fantasy_Forest trees + 2 bushes + 2 dark wet rocks, vines on
the Marmoreal back wall (top band) / arcade and the Sarpedon palisade / fort ruin, flower clumps in the urns and along
the hedge beds, the deck barrels / crates re-clustered (bow / mid / stern clumps, varied scale and yaw), lantern-w /
lantern-n moved >= LANTERN_MIN_UU from the campfire point lights. Mounted props (vines, urn flowers) sit above the tray
top (layout_check 11: no base-overlap check). The p5_layout_props.py of the P5 run chains into this script once its
note paragraph is in a layout, so both generators stay idempotent on the merged result.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REPO = HERE.parents[4]
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
PICKS = HERE / "fab-picks.json"
REPORT = RUN / "reports/p5c-layout-report.json"
NOTE_MARK = " P5c track F (2026-10-01):"
TRAY_Z = -3.0
LANTERN_MIN_UU = 120.0  # P5b review: the lantern posts stood 51 / 56 uu from the campfire point lights
# P5b instance triangles (layout_check.tris_report on the committed P5b layouts, 8938a03f / 5c4c14b2)
P5B_TRIS = {"marmoreal": 275773, "sarpedon": 249740}

_PICKS = json.loads(PICKS.read_text(encoding="utf-8"))["meshes"]


def fab(pid: str, name: str, x: float, y: float, yaw: float, scale: float, z: float = TRAY_Z,
        shadow: bool = True) -> dict:
    e = _PICKS[name]
    return {"id": pid, "mesh": e["dest"], "loc": [round(float(x), 2), round(float(y), 2), round(float(z), 2)],
            "yawDeg": float(yaw), "scale": float(scale), "castShadow": shadow}


def kit(pid: str, kit_name: str, name: str, x: float, y: float, yaw: float, scale: float = 1.0,
        shadow: bool = True) -> dict:
    return {"id": pid, "mesh": f"/Game/EnvKit/{kit_name}/SM_Env_{name}", "loc": [float(x), float(y), TRAY_Z],
            "yawDeg": float(yaw), "scale": float(scale), "castShadow": shadow}


def _rot(x: float, y: float, yaw: float) -> tuple[float, float]:
    a = math.radians(yaw)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def crown_centre(name: str, loc_xy, yaw: float, scale: float) -> tuple[float, float]:
    """Board XY of the bounds centre of a Fab mesh placed at loc (the pack pivot)."""
    e = _PICKS[name]
    cx = (e["bboxMin"][0] + e["bboxMax"][0]) / 2 * scale
    cy = (e["bboxMin"][1] + e["bboxMax"][1]) / 2 * scale
    dx, dy = _rot(cx, cy, yaw)
    return loc_xy[0] + dx, loc_xy[1] + dy


def tree_at_crown(pid: str, name: str, crown_xy, yaw: float, scale: float) -> dict:
    """A tree whose crown (bounds centre) lands on crown_xy - the pack pivot is the trunk base, for the twisted cherry
    ~100 uu off the crown centre."""
    cx, cy = crown_centre(name, (0.0, 0.0), yaw, scale)
    return fab(pid, name, crown_xy[0] - cx, crown_xy[1] - cy, yaw, scale)


def on_wall(pid: str, name: str, centre_x: float, face_y: float, top_z: float, scale: float, gap: float = 0.5) -> dict:
    """A vine card (yaw 0: its plane along X, thin along Y) against a wall face at face_y that faces +Y: the card's
    -Y bound lies `gap` in front of the face, its X centre at centre_x, its top at top_z."""
    e = _PICKS[name]
    x0, y0, z1 = e["bboxMin"][0] * scale, e["bboxMin"][1] * scale, e["bboxMax"][2] * scale
    x1 = e["bboxMax"][0] * scale
    return fab(pid, name, centre_x - (x0 + x1) / 2, face_y + gap - y0, 0.0, scale, z=top_z - z1, shadow=False)


def on_face(pid: str, name: str, face_xy, normal_yaw: float, along: float, top_z: float, scale: float,
            gap: float = 0.5) -> dict:
    """A vine card on a vertical face whose outward normal has the yaw normal_yaw (deg): the card's plane runs along
    the face (card yaw = normal_yaw + 90 or - 90, whichever puts the card's thin Y bounds outside the face), `along` uu
    along the face from face_xy, the card's top at top_z, its X centre on the point."""
    e = _PICKS[name]
    s = scale
    nx, ny = math.cos(math.radians(normal_yaw)), math.sin(math.radians(normal_yaw))
    best = None
    for card_yaw in (normal_yaw - 90.0, normal_yaw + 90.0):
        # local +Y of the card in board space; the thin bounds y0 .. y1 must lie outside the face (dot with n > 0)
        ly = (-math.sin(math.radians(card_yaw)), math.cos(math.radians(card_yaw)))
        d = ly[0] * nx + ly[1] * ny  # +1 or -1
        lo = min(e["bboxMin"][1] * s * d, e["bboxMax"][1] * s * d)  # outward offsets of the card's two Y bounds
        cand = (card_yaw % 360.0, d, lo)
        if best is None or lo > best[2]:
            best = cand
    card_yaw, d, lo = best
    push = gap - lo  # move the card out so its nearest Y bound is `gap` in front of the face
    tx, ty = -ny, nx  # along the face
    px, py = face_xy[0] + tx * along + nx * push, face_xy[1] + ty * along + ny * push
    cx = (e["bboxMin"][0] + e["bboxMax"][0]) / 2 * s
    ox, oy = _rot(cx, 0.0, card_yaw)
    return fab(pid, name, px - ox, py - oy, round(card_yaw, 3), s, z=top_z - e["bboxMax"][2] * s, shadow=False)


# ------------------------------------------------------------------------------------------------ Marmoreal
# back wall (lane K, scale 1, yaw 90 = face +Y): bays front y -465.866 + 14.792, centre front y -465.866 + 9.345,
# tops z -3 + 235 / 255; the arcade (scale 1.45) stands in front of it (back y -447.5, top z 185, front y -402.5):
# from the K1 camera the wall shows above z ~140 behind the arcade - the top band the P5b review measured too bright
BAY_FACE_Y, CENTRE_FACE_Y = -465.866 + 14.792, -465.866 + 9.345
BAY_TOP_Z, CENTRE_TOP_Z = -3.0 + 235.0, -3.0 + 255.0
ARCADE_FACE_Y, ARCADE_TOP_Z = -425.0 + 22.5, -3.0 + 188.0


def marmoreal() -> list[dict]:
    out = [
        # sakura (concept-review gap 2 / ENV-U13): the pink Forest trees, crowns on the P4 cherry points (far halves of
        # W / E); the twisted tree leans its crown along the apron (W: towards the far side, E: towards the near side);
        # x0.23 / x0.22 = 215 / 206 uu tall (the concept's trees tower over the 188-uu colonnade; the scout's x0.17 =
        # 159 uu stayed below it), crown 261 / 250 uu along the apron
        tree_at_crown("cherry-nw", "SakuraBirch", (-655.0, -400.0), 235.0, 0.17),
        tree_at_crown("cherry-w", "SakuraTwisted", (-660.0, -183.0), 270.0, 0.23),
        tree_at_crown("cherry-e", "SakuraTwisted", (660.0, -175.0), 90.0, 0.22),
        tree_at_crown("cherry-se", "SakuraBirch", (612.0, 252.0), 40.0, 0.13),
    ]
    # back-wall vines: a garland under the cornice of every module (breaks the bright top band), curtains on the four
    # module joints (VineCurtain on the bay / bay joints, the lighter VineCurtainB on the centre joints)
    for pid, x in (("vine-wall-w2", -321.5), ("vine-wall-w1", -169.2), ("vine-wall-e1", 169.2), ("vine-wall-e2", 321.5)):
        out.append(on_wall(pid, "VineGarland", x, BAY_FACE_Y, BAY_TOP_Z - 6.0, 0.9))
    out.append(on_wall("vine-wall-c", "VineGarland", 0.0, CENTRE_FACE_Y, CENTRE_TOP_Z - 6.0, 1.1))
    out.append(on_wall("vine-joint-w2", "VineCurtain", -245.35, BAY_FACE_Y, BAY_TOP_Z - 4.0, 0.8))
    out.append(on_wall("vine-joint-e2", "VineCurtain", 245.35, BAY_FACE_Y, BAY_TOP_Z - 4.0, 0.75))
    out.append(on_wall("vine-joint-w1", "VineCurtainB", -96.0, BAY_FACE_Y, BAY_TOP_Z - 2.0, 0.6))
    out.append(on_wall("vine-joint-e1", "VineCurtainB", 102.0, BAY_FACE_Y, BAY_TOP_Z - 2.0, 0.55))
    # arcade drapes on the piers (front face y -402.5), alternating sides, hanging from just under the arcade top
    for pid, x, s in (("vine-arcade-w2", -368.0, 0.7), ("vine-arcade-w1", -214.0, 0.62), ("vine-arcade-e1", 222.0, 0.66),
                      ("vine-arcade-e2", 370.0, 0.7)):
        out.append(on_wall(pid, "VineArcade", x, ARCADE_FACE_Y, ARCADE_TOP_Z - 4.0, s))
    # flowers: bouquets in the two urns (urn top z 32), clumps along the hedge-bed fronts (2 per bed), lavender by the
    # side lamps (W / E)
    out += [
        fab("flower-urn-w", "FlowerUrn", -118.0, -372.0, 20.0, 0.26, z=27.0, shadow=False),
        fab("flower-urn-e", "FlowerUrn", 118.0, -372.0, 140.0, 0.26, z=27.0, shadow=False),
        fab("flower-hedge-w1", "FlowerBed", -606.0, -12.0, 15.0, 0.34, shadow=False),
        fab("flower-hedge-w2", "FlowerBedB", -604.0, 62.0, 200.0, 0.32, shadow=False),
        fab("flower-hedge-sw1", "FlowerBedB", -683.0, 304.0, 75.0, 0.33, shadow=False),
        fab("flower-hedge-sw2", "FlowerBed", -604.0, 304.0, 300.0, 0.3, shadow=False),
        fab("flower-hedge-e1", "FlowerBed", 605.0, -22.0, 120.0, 0.33, shadow=False),
        fab("flower-hedge-e2", "FlowerBedB", 603.0, 58.0, 250.0, 0.34, shadow=False),
        fab("flower-lamp-w", "FlowerLavender", -520.0, 94.0, 30.0, 0.6, shadow=False),
        fab("flower-lamp-e", "FlowerLavender", 520.0, 95.0, 210.0, 0.55, shadow=False),
    ]
    return out


# ------------------------------------------------------------------------------------------------ Sarpedon
def sarpedon() -> list[dict]:
    S = "Sarpedon"
    out = [
        # west forest (concept-review gap 7): the 3 big trees = the dark Forest oak, the 5 smaller ones Fantasy_Forest
        # (night MI: one dark green, no position hue), same points as P4, yaw / scale varied
        fab("tree-nw", "OakDark", -700.0, -318.0, 110.0, 0.137),
        fab("tree-w", "OakDark", -690.0, -30.0, 70.0, 0.13),
        fab("tree-w2", "OakDark", -700.0, -190.0, 200.0, 0.11),
        fab("tree-w3", "ForestNarrow", -615.0, -255.0, 40.0, 0.15),
        fab("tree-w4", "ForestNarrow", -625.0, -105.0, 320.0, 0.14),
        fab("tree-w5", "ForestRound", -645.0, 45.0, 150.0, 0.13),
        fab("tree-sw1", "ForestRound", -640.0, 180.0, 300.0, 0.12),
        fab("tree-sw2", "ForestSmall", -615.0, 290.0, 20.0, 0.12),
        # undergrowth: bushes by the fort and in the palisade gap, dark wet rocks at the forest edge
        fab("bush-fort", "Bush", -672.0, -350.0, 30.0, 0.3),
        fab("bush-w", "Bush", -600.0, -5.0, 200.0, 0.27),
        fab("rockwet-w", "RockWet", -570.0, -230.0, 35.0, 0.25),
        fab("rockwet-sw", "RockWet", -590.0, 365.0, 160.0, 0.22),
        # vines: swags / drapes on the palisade fronts, curtains on the fort-ruin wall (fort yaw 82: face normal 82 deg)
        on_face("vine-pal-n1", "VineSwag", (-440.0, -392.0 + 8.8), 90.0, 0.0, 66.0, 0.9),
        on_face("vine-pal-n2", "VinePost", (-361.0 + 8.8 * math.cos(math.radians(94.0)),
                                              -390.0 + 8.8 * math.sin(math.radians(94.0))), 94.0, -22.0, 72.0, 0.55),
        on_face("vine-pal-w1", "VineSwag", (-556.7 + 8.8 * math.cos(math.radians(15.0)),
                                              -72.7 + 8.8 * math.sin(math.radians(15.0))), 15.0, 6.0, 66.0, 0.9),
        on_face("vine-pal-w2", "VinePost", (-536.0 + 8.8 * math.cos(math.radians(15.0)),
                                              -150.0 + 8.8 * math.sin(math.radians(15.0))), 15.0, -20.0, 72.0, 0.55),
        on_face("vine-pal-w3", "VineSwag", (-540.0 + 8.8 * math.cos(math.radians(20.0)),
                                              205.0 + 8.8 * math.sin(math.radians(20.0))), 20.0, 10.0, 66.0, 0.85),
        on_face("vine-fort", "VineFort", (-575.0 + 25.6 * math.cos(math.radians(82.0)),
                                            -418.0 + 25.6 * math.sin(math.radians(82.0))), 82.0, 10.0, 105.0, 0.7),
        on_face("vine-fort-b", "VineFortB", (-575.0 + 25.6 * math.cos(math.radians(82.0)),
                                              -418.0 + 25.6 * math.sin(math.radians(82.0))), 82.0, -55.0, 104.0, 0.6),
        # deck dressing re-clustered (P5b review: one column, brown on brown): a bow clump on the N-E quay beyond the
        # hull's bow (crate + barrel by lantern-deck), a lone barrel at cannon-e1, a mid pair, a 2-barrel knot, a stern
        # pair split across the hull's stern (crate inside, barrel on the S-E quay by rope-se); the gap between
        # cannon-e3 / -e4 keeps the rhythm; scales 1.05-1.25 read above 20-25 px at K1; value separation comes from the
        # looks (crates paler / greyer, barrels darker)
        kit("crate-e3", S, "CrateStack", 600.0, -372.0, 120.0, 1.1),
        kit("barrel-e5", S, "Barrel", 492.0, -258.0, 55.0, 1.2),
        kit("barrel-e1", S, "Barrel", 545.0, -336.0, 10.0, 1.05),
        kit("crate-e1", S, "CrateStack", 523.0, -148.0, 172.0, 1.15),
        kit("barrel-e2", S, "Barrel", 494.0, -118.0, 30.0, 1.25),
        kit("barrel-e3", S, "Barrel", 492.0, -26.0, 75.0, 1.2),
        kit("barrel-e4", S, "Barrel", 521.0, -9.0, 140.0, 1.1),
        kit("crate-e2", S, "CrateStack", 515.0, 272.0, 186.0, 1.1),
        kit("barrel-e6", S, "Barrel", 628.0, 300.0, 120.0, 1.15),
        # lantern posts >= LANTERN_MIN_UU from the campfire lights (P5b: 51 / 56 uu, long hard shadow streaks): W at the
        # S end of the W palisade, N on the beach E of the fort palisade
        kit("lantern-w", S, "LanternPost", -552.0, 280.0, 0.0),
        kit("lantern-n", S, "LanternPost", -372.0, -455.0, 90.0),
    ]
    return out


P5C_PROPS = {"marmoreal": marmoreal, "sarpedon": sarpedon}
NOTES = {
    "marmoreal": (" P5c track F (2026-10-01): the 4 cherries are the pink Forest trees (Fab duplicates"
                  " /Game/EnvKit/Fab/Marmoreal/SM_EnvFab_SakuraTwisted / SakuraBirch, night MI: V x0.78 S x0.85 of the pack"
                  " pink; ids kept, crowns on the P4 points - the twisted tree's pivot is its trunk base ~100 uu off the"
                  " crown), vines (5 garlands under the back-wall cornice, 4 curtains on its module joints, 4 drapes on"
                  " the arcade piers; two-sided night MIs), flowers (2 urn bouquets, 6 clumps along the hedge beds, 2"
                  " lavender by the side lamps); mounted props sit above the tray top (layout_check 11); lights unchanged"
                  " (5). Status: proposed."),
    "sarpedon": (" P5c track F (2026-10-01): the west forest is the dark Forest oak (tree-nw / -w / -w2) and Fantasy_Forest"
                 " trees (night MI: one dark green, no position hue, wind off) + 2 bushes + 2 dark wet rocks; vines on"
                 " the palisade fronts (5) and the fort-ruin wall (2); the deck barrels / crates re-clustered (bow / mid /"
                 " stern clumps, scale 1.05-1.25); lantern-w / lantern-n moved >= 120 uu from the campfire lights (no"
                 " light changed: 5). Status: proposed."),
}


def apply(key: str, layout: dict) -> dict:
    new = P5C_PROPS[key]()
    ids = {p["id"] for p in new}
    out = dict(layout)
    out["props"] = [p for p in layout["props"] if p["id"] not in ids] + new
    notes = layout.get("notes", "")
    if NOTE_MARK in notes:
        notes = notes[: notes.index(NOTE_MARK)]
    out["notes"] = notes + NOTES[key]
    return out


def lantern_distances(layout: dict) -> dict:
    """XY distance of every LanternPost prop to the nearest campfire point light (id campfire-*)."""
    fires = [lt for lt in layout.get("lights", []) if str(lt.get("id", "")).startswith("campfire")]
    out = {}
    for p in layout["props"]:
        if p["mesh"].endswith("/SM_Env_LanternPost") and fires:
            d, lid = min((math.hypot(p["loc"][0] - lt["loc"][0], p["loc"][1] - lt["loc"][1]), lt["id"]) for lt in fires)
            out[p["id"]] = {"light": lid, "uu": round(d, 1)}
    return out


def report(layouts: dict) -> dict:
    sys.path.insert(0, str(REPO / "tools/art/env_kit"))
    import layout_check as lc  # noqa: E402
    out = {"schema": "unmatched.env-p5c-layout-report/1", "tool": "p5c_layout_props.py",
           "status": "предложено (layout_check geometry + LOD0 instance triangles; no UE frame)", "maps": {}}
    for key, lay in layouts.items():
        tr = lc.tris_report(lay)
        crowns = {}
        for p in lay["props"]:
            name = lc.mesh_name(p)
            if p["id"].startswith("cherry") and name.startswith(lc.FAB_PREFIX):
                cx, cy = crown_centre(name[len(lc.FAB_PREFIX):], p["loc"], p["yawDeg"], p["scale"])
                w, d, h = lc.dims(name, p["scale"])
                crowns[p["id"]] = {"trunk": p["loc"][:2], "crownCentre": [round(cx, 1), round(cy, 1)],
                                   "crownSizeUU": [round(d, 1), round(w, 1), round(h, 1)]}
        out["maps"][key] = {"trisP5b": P5B_TRIS[key], "trisP5c": tr["total"], "trisFab": tr["fab"],
                            "deltaVsP5b": tr["total"] - P5B_TRIS[key], "props": tr["props"],
                            "perMesh": tr["perMesh"], "cherryCrowns": crowns,
                            "lanternToCampfireLight": lantern_distances(lay)}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--layouts", default=str(LAYOUTS))
    ap.add_argument("--out", default=None, help="write the layouts here instead (scratch)")
    ap.add_argument("--report", action="store_true", help=f"write {REPORT.relative_to(REPO).as_posix()}")
    a = ap.parse_args(argv if argv is not None else sys.argv[1:])
    bad, results = 0, {}
    for key in P5C_PROPS:
        path = Path(a.layouts) / f"{key}.layout.json"
        old_text = path.read_text(encoding="utf-8")
        new = apply(key, json.loads(old_text))
        results[key] = new
        new_text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
        target = Path(a.out) / f"{key}.layout.json" if a.out else path
        if a.out:
            target.parent.mkdir(parents=True, exist_ok=True)
        if old_text.replace("\r\n", "\n") == new_text and not a.out:
            print(f"{key}: unchanged")
            continue
        if a.check:
            print(f"{key}: differs from p5c_layout_props.py")
            bad += 1
            continue
        target.write_bytes(new_text.encode("utf-8"))
        print(f"{key}: written {target.as_posix()} ({len(new['props'])} props)")
    if a.report and not a.check:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_bytes((json.dumps(report(results), indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
        print(f"report: {REPORT.relative_to(REPO).as_posix()}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
