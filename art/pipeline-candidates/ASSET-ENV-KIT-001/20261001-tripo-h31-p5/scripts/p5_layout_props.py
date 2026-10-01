#!/usr/bin/env python3
"""ENV-MAPS P5 track A: place the P5 props (and the Blender back wall) in the two env layouts - props only.

  python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5/scripts/p5_layout_props.py [--check]

Idempotent: every prop whose id is in P5_PROPS[<map>] is removed and the list is appended again (in this order) after
the existing props; nothing else in the layout changes (tray, apron, lights, the 'ground' section). The notes get one
'P5 track A' paragraph (replaced on a re-run). --check exits 1 when a layout differs from what this script writes.
The positions are validated by tools/art/env_kit/layout_check.py (run it afterwards); a moved prop needs
tools/art/env_kit/ground_splat.py --write-layouts again (the splat rules read the props: splatSha256 / propsSha256).

Sizes at scale 1 (build reports of 20261001-tripo-h31-p5 and the lane-K back-wall report; w = width along local Y,
d = depth along local X = front, h): Barrel 21.4 x 21.4 x 28, CrateStack 49.2 x 22.1 x 45, LanternPost 56.7 x 25.1 x 95,
Banner 57.1 x 19.5 x 120, RockOutcrop 80.6 x 61.3 x 70, Balustrade 150 x 14.4 x 46.1, HedgeBed 150 x 26.7 x 45.5,
BackWall bays 152.3 x 30.8 x 235, centre 186 x 25.3 x 255. Yaw: 90 turns the front (+X) to the K1 camera (+Y).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
BACKWALL_LAYOUT = REPO / "art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/20261001-backwall-v1/reports/backwall-layout.json"
NOTE_MARK = " P5 track A (2026-10-01):"


def prop(pid: str, kit: str, name: str, x: float, y: float, yaw: float, scale: float = 1.0, shadow: bool = True) -> dict:
    return {"id": pid, "mesh": f"/Game/EnvKit/{kit}/SM_Env_{name}", "loc": [float(x), float(y), -3.0],
            "yawDeg": float(yaw), "scale": float(scale), "castShadow": shadow}


def marmoreal() -> list[dict]:
    M = "Marmoreal"
    out = []
    # concept-review gap 12: the back wall behind the arcade, exactly the lane-K layout (y -465.866 = 1 uu behind the
    # arcade / portal backs, key-light shadow tip y -371.6 short of the map frame)
    for p in json.loads(BACKWALL_LAYOUT.read_text(encoding="utf-8"))["props"]:
        out.append({"id": p["id"], "mesh": p["mesh"], "loc": [float(v) for v in p["loc"]], "yawDeg": float(p["yawDeg"]),
                    "scale": float(p["scale"]), "castShadow": bool(p["castShadow"])})
    # gap 6: balustrade runs along the W / E tray edges (front faces the map; 20.8 uu inside the tray edge = out of
    # the T2 rocky lip band), 5 abutting 150-uu segments from the near corner (y 404) to y -346 (the far W / E corners
    # keep the ball-finial posts and the cherry crowns); the near (front) edge only at the two near corners: the near
    # band (|X| < 469.7, Y > 312.7) allows 25 uu, the segment is 46 uu tall
    xs = 752.0
    for i, yc in enumerate((329.0, 179.0, 29.0, -121.0, -271.0), 1):
        out.append(prop(f"balustrade-w{i}", M, "Balustrade", -xs, yc, 0.0))
        out.append(prop(f"balustrade-e{i}", M, "Balustrade", xs, yc, 180.0))
    out.append(prop("balustrade-sw", M, "Balustrade", -670.0, 397.0, 90.0))
    out.append(prop("balustrade-se", M, "Balustrade", 670.0, 397.0, 90.0))
    # gap 6: hedge / flower beds on the dark-earth beds of W / E (mesh only, no light)
    out.append(prop("hedge-w", M, "HedgeBed", -645.0, 30.0, 0.0))
    out.append(prop("hedge-sw", M, "HedgeBed", -640.0, 265.0, 90.0))
    out.append(prop("hedge-e", M, "HedgeBed", 645.0, 20.0, 180.0))
    return out


def sarpedon() -> list[dict]:
    S = "Sarpedon"
    return [
        # gap 4: deck dressing between and beside the 4 cannons (on the deck planks under hull / cannons)
        prop("crate-e1", S, "CrateStack", 520.0, -145.0, 180.0),
        prop("crate-e2", S, "CrateStack", 520.0, 127.0, 185.0),
        prop("crate-e3", S, "CrateStack", 530.0, -280.0, 160.0),
        prop("barrel-e1", S, "Barrel", 546.0, -175.0, 0.0),
        prop("barrel-e2", S, "Barrel", 515.0, -12.0, 30.0),
        prop("barrel-e3", S, "Barrel", 538.0, 6.0, 75.0),
        prop("barrel-e4", S, "Barrel", 520.0, 255.0, 10.0),
        prop("barrel-e5", S, "Barrel", 500.0, -265.0, 55.0),
        prop("barrel-e6", S, "Barrel", 545.0, 280.0, 120.0),
        # gaps 4 + 7: standing lantern posts - deck (bow) and palisade (W gap, N by the fort); emissive glass only, no
        # new point light (the 5 layout lights + 1 profile point stay the 6-point budget)
        prop("lantern-deck", S, "LanternPost", 575.0, -300.0, 180.0),
        prop("lantern-w", S, "LanternPost", -550.0, 135.0, 0.0),
        prop("lantern-n", S, "LanternPost", -492.0, -362.0, 90.0),
        # gap 4: red banners by the fort and at the bow
        prop("banner-fort", S, "Banner", -450.0, -445.0, 90.0),
        prop("banner-bow", S, "Banner", 640.0, -285.0, 150.0),
        # gap 7: rock outcrops in the west forest and along the tray edge (NE / SE corners)
        prop("rock-nw", S, "RockOutcrop", -712.0, -440.0, 90.0),
        prop("rock-w", S, "RockOutcrop", -715.0, 110.0, 90.0, 0.9),
        prop("rock-sw", S, "RockOutcrop", -705.0, 345.0, 110.0),
        prop("rock-ne", S, "RockOutcrop", 700.0, -440.0, 70.0),
        prop("rock-se", S, "RockOutcrop", 690.0, 370.0, 100.0, 0.85),
    ]


P5_PROPS = {"marmoreal": marmoreal, "sarpedon": sarpedon}
NOTES = {
    "marmoreal": (" P5 track A (2026-10-01): + the Blender back wall (ASSET-ENV-M-BACKWALL-001: BayDoor / BayWindows /"
                  " Centre / BayWindows / BayDoor at y -465.866, emissive window glow only), 12 Balustrade segments"
                  " (P5 Tripo, 150 x 46 uu: 5 along each of W / E at |x| 752, one at each near corner y 397 - the near"
                  " band keeps its 25-uu limit), 3 HedgeBed (W, SW, E dark-earth beds); 41 props (layout_check WARN"
                  " guide raised to 10..48), lights unchanged (5)."),
    "sarpedon": (" P5 track A (2026-10-01): + deck dressing (3 CrateStack, 6 Barrel between / beside the cannons), 3"
                 " LanternPost (bow deck, W palisade gap, N by the fort; emissive glass, no new light), 2 Banner (fort,"
                 " bow), 5 RockOutcrop (W forest NW / W / SW, NE / SE tray corners); 43 props (layout_check WARN guide"
                 " raised to 10..48), lights unchanged (5)."),
}


def apply(key: str, layout: dict) -> dict:
    new = P5_PROPS[key]()
    ids = {p["id"] for p in new}
    out = dict(layout)
    out["props"] = [p for p in layout["props"] if p["id"] not in ids] + new
    notes = layout.get("notes", "")
    if NOTE_MARK in notes:
        notes = notes[: notes.index(NOTE_MARK)]
    out["notes"] = notes + NOTES[key]
    return out


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    bad = 0
    for key in P5_PROPS:
        path = LAYOUTS / f"{key}.layout.json"
        old_text = path.read_text(encoding="utf-8")
        new_text = json.dumps(apply(key, json.loads(old_text)), indent=2, ensure_ascii=False) + "\n"
        if old_text.replace("\r\n", "\n") == new_text:
            print(f"{key}: unchanged")
            continue
        if check:
            print(f"{key}: differs from p5_layout_props.py")
            bad += 1
            continue
        path.write_bytes(new_text.encode("utf-8"))
        print(f"{key}: written ({len(json.loads(new_text)['props'])} props)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
