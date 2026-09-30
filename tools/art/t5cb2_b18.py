#!/usr/bin/env python3
"""Wave 5c-B2, step B1-8 of the 5c-B1 plan: one verdict table for the packaged 5c-B2 frames of the three boards by the
thresholds REGISTERED before the shots (t5cb-thresholds.json, B1-0 + revision 1; the base t53-thresholds.json with its
revision 1 where the 5c-B1 file does not override). Read-only on the frames; it reads what these produced:

    python tools/art/t53_readability.py analyze    --board <b> --evidence <E> --k1-run .. --k3-run .. --probe24-run .. --probe48-run ..
    python tools/art/t53_readability.py rings-rev3 --board <b> --evidence <E> --out <E>/analysis/<b>/rings-rev3.json
    python tools/art/t5cb1_exposure_sim.py packaged --evidence <E> --out <dir>      (forecast vs packaged)

and adds two measurements the analyze step does not write: the team chip SHAPE against the ring shape of the
registered classifier (teamShape rev 2 = rings-rev3), and the gray zone fill against the tile of its own cell
(|dY'|, zones.grayVsTile, record). Comparison columns: W5b-R r3 (docs/.../art3-live-3boards-r2-2026-09-29/analysis,
C:/tmp/p0-review/5cb1-sim/rings-rev3-*.json = the 5c-B1 methods on the r3 frames) and the forecast of the plan
(t5cb-thresholds.json acceptance).

    python tools/art/t5cb2_b18.py --evidence <E> --out <E>/analysis/b18-summary.json [--sim <packaged-vs-forecast.json>]

Statuses: «измерено»; nothing here is an artistic acceptance.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))

BOARDS = ("cobble-5x6", "sherwood-forest-8x5", "t-rex-paddock-7x5")
R3 = REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29"
R3_RINGS_REV3 = Path("C:/tmp/p0-review/5cb1-sim")
VARS = ("color", "gray", "deuteranopia")


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def rng(vals):
    v = [x for x in vals if x is not None]
    return [round(min(v), 3), round(max(v), 3)] if v else None


def gray_vs_tile(evidence: Path, key: str, summ: dict, th: dict) -> dict:
    """zones.grayVsTile (record): |dY'| between the gray fill of each gray slot and the tile of its own cell (the
    +-18 uu centre square; for an occupied cell the free cells of the same zone), grey variant luma, K1 joiner."""
    import numpy as np
    import t52_art3_live as T52
    import t53_readability as T53
    calib = th["calibration"]["bytes"]
    pde = th["calibration"]["pixelDeltaE"]
    png = REPO / summ["frames"]["K1_joiner"]
    shot = T53.Shot(png, T53._trace_for(png))
    cells = T52.board_cells(T53.T52_EVIDENCE if key == "cobble-5x6" else evidence, key)
    if not any("gray" in c["zones"] for c in cells):
        return {"slots": 0, "note": "на доске нет зоны gray"}
    occupied = {tuple(f.cell) for f in shot.fighters.values()}
    gray_m = shot.de_to(calib["zone.gray"]["screen"]) <= pde
    key_m = shot.de_to(calib["zone.keyline"]["screen"]) <= pde

    def square(cl):
        pts = []
        for (x, y) in cl:
            c = shot.board.cell_center(x, y)
            for a in np.arange(-18.0, 18.5, 1.0):
                for b in np.arange(-18.0, 18.5, 1.0):
                    pts.append((c[0] + a, c[1] + b, 0.0))
        return shot.mask_of(shot.pixels(pts)) & ~key_m & ~gray_m

    free_gray = [(c["x"], c["y"]) for c in cells if "gray" in c["zones"] and not c["obstacle"]
                 and (c["x"], c["y"]) not in occupied]
    rows = []
    for c in cells:
        if c["obstacle"] or "gray" not in c["zones"]:
            continue
        i = c["zones"].index("gray")
        cc = shot.board.cell_center(c["x"], c["y"])
        fm = shot.mask_of(shot.pixels(T53.slot_points(cc[0], cc[1], i))) & gray_m
        own = (c["x"], c["y"]) not in occupied
        tm = square([(c["x"], c["y"])] if own else free_gray)
        if not fm.any() or not tm.any():
            continue
        yf = float(np.median(shot.luma_gray[fm]))
        yt = float(np.median(shot.luma_gray[tm]))
        rows.append({"cell": [c["x"], c["y"]], "fillPx": int(fm.sum()), "tilePx": int(tm.sum()), "tileOwnCell": own,
                     "fillY": round(yf, 1), "tileY": round(yt, 1), "absDeltaY": round(abs(yf - yt), 1)})
    need = 35.0
    return {"slots": len(rows), "min": min((r["absDeltaY"] for r in rows), default=None),
            "median": float(np.median([r["absDeltaY"] for r in rows])) if rows else None,
            "atLeast35": sum(1 for r in rows if r["absDeltaY"] >= need), "rows": rows,
            "rule": th["zones"].get("grayVsTile"), "status": "запись, не гейт"}


def board_entry(evidence: Path, key: str, th: dict) -> dict:
    an = evidence / "analysis" / key
    s = load(an / "summary.json")
    r3 = load(an / "rings-rev3.json")
    tr = load(an / "team-rings-r2.json")
    zc = load(an / "zone-contrast-r2.json")
    lum = load(an / "luma-sections.json")["frames"]["K1_joiner"]["passable"]["color"]
    rows = [r for f in r3["frames"].values() for r in f["fighters"]]
    # rings rev 3 (registered): shape rev 2 classifier, edge = max(keyline, rim) vs tile rev 3, >= 10 px core
    edge_side = {"keyline": 0, "rim": 0}
    for r in rows:
        t = r["tileReference"]
        for vn in VARS:
            kv, rv = t[vn].get("keylineVsTile"), t[vn].get("rimVsTile")
            if t[vn].get("edgeVsTile") is None:
                continue
            edge_side["rim" if (rv is not None and (kv is None or rv >= kv)) else "keyline"] += 1
    shape_fail = [f"{r['name']} {tag}: {r['shape']}" for tag, f in r3["frames"].items() for r in f["fighters"]
                  if not r["shapePassAllVariants"]]
    fr = [(tag, r) for tag, f in tr["frames"].items() for r in f["fighters"] if "fraction" in r]
    frac_hero = [r["fraction"] for _, r in fr if r["fighter"].endswith("-hero")]
    frac_sk = [r["fraction"] for _, r in fr if not r["fighter"].endswith("-hero")]
    fvk = [r["variants"][vn]["fillVsKeyline"] for _, r in fr for vn in VARS]
    # chips: colour (analyze, dE76 <= 6) + shape against the registered classifier (rings-rev3, colour variant)
    shape_of = {(tag, r["fighter"]): r["shape"]["color"] for tag, f in r3["frames"].items() for r in f["fighters"]}
    chips = []
    for tag, lst in tr["chips"].items():
        for c in lst:
            ring = shape_of.get((tag, c["fighter"]))
            want = "circle" if c.get("shapeTrace") == "circle" else "hexagon"
            chips.append({"frame": tag, "fighter": c["fighter"], "kind": c["kind"], "deltaE76": c.get("deltaE76"),
                          "colourPass": bool(c.get("colourPass")), "shapeTrace": c.get("shapeTrace"), "ringShapeRev3": ring,
                          "shapePass": ring == want})
    # zones rev 3 (= rev 2 rules with the rev 5 colours): per slot, K1 joiner; mins over the variants
    zj = zc["frames"]["K1_joiner"]
    zones = {}
    for z, v in zj["zones"].items():
        slots = [sl for sl in zj["slots"] if sl["zone"] == z and not sl["occupied"]]
        zones[z] = {"pass": f"{v['pass']}/{v['slots']}",
                    "keylineVsTile": {vn: rng([sl["variants"][vn]["keylineVsTile"] for sl in slots]) for vn in VARS},
                    "fillVsKeyline": {vn: rng([sl["variants"][vn]["fillVsKeyline"] for sl in slots]) for vn in VARS},
                    "median": {vn: v["variants"][vn] for vn in VARS}}
    gvt = gray_vs_tile(evidence, key, s, th)
    td = s["tags"]
    tb = s.get("tagBinding") or {}
    return {
        "frames": s["frames"], "classify": {"exit": s["classify"]["exit"], "n": len(s["classify"]["frames"]),
                                            "strict": sum(1 for f in s["classify"]["frames"] if f["grade"] == "strict"
                                                          and f["class"] == "packaged-live" and f["S6"])},
        "render": {k: v["reference"] for k, v in s["render"].items()},
        "rings": {"n": len(rows),
                  "fractionHero": rng(frac_hero), "fractionSidekick": rng(frac_sk),
                  "fractionFail": s["rings"]["fractionFail"],
                  "shapeRev3Color": sum(1 for r in rows if r["shapePass"]["color"]),
                  "shapeRev3AllVariants": sum(1 for r in rows if r["shapePassAllVariants"]),
                  "shapeFail": shape_fail,
                  "edgeRev3Pass": sum(1 for r in rows if r["edgeVsTilePass"]),
                  "edgeRev3Min": r3["summary"]["edgeVsTileRev3Min"], "tilePxMin": r3["summary"]["tilePxMin"],
                  "edgeCarriedBy": edge_side,
                  "keylineVsTileRev3Range": rng([r["tileReference"][vn].get("keylineVsTile") for r in rows for vn in VARS]),
                  "rimVsTileRange": rng([r["tileReference"][vn].get("rimVsTile") for r in rows for vn in VARS]),
                  "fillVsKeylineRange": rng(fvk), "fillVsKeylineFail": s["rings"]["fillVsKeylineFail"],
                  "viewIndependenceFail": len(s["rings"]["viewIndependenceFail"]),
                  "sameColourFail": len(s["rings"]["sameColourFail"]),
                  "rev2ShapeUnclassified": len(s["rings"]["shapeFail"]),
                  "rev2KeylineVsTileFail": len(s["rings"]["keylineVsTileFail"])},
        "teams": s["rings"]["teams"],
        "chips": {"n": len(chips), "colourPass": sum(c["colourPass"] for c in chips),
                  "shapePass": sum(c["shapePass"] for c in chips),
                  "deltaE76Max": max((c["deltaE76"] for c in chips if c["deltaE76"] is not None), default=None),
                  "fail": [c for c in chips if not (c["colourPass"] and c["shapePass"])]},
        "zones": zones,
        "multizone": {k: f"{v['pass']}/{v['cells']}" for k, v in s["multizone"].items()},
        "grayVsTile": gvt,
        "tags": {"painted": td["tags"], "fail": len(td["fail"]), "minText": td["minText"],
                 "binding": f"{tb.get('paintedTags', 0) - len(tb.get('bindingFail') or [])}/{tb.get('paintedTags')}",
                 "plateOwnerModeFail": len(tb.get("plateOwnerModeFail") or []), "sections": tb.get("sections")},
        "damage": [{"frame": d["frame"], "name": d["name"], "amount": d["amount"], "seq": d["seq"],
                    "text": [d["contrast"].get(vn) for vn in VARS], "binding": d["bindingPass"],
                    "overlapPass": d["overlapPass"]} for d in s["damage"]],
        "icon": {k: {"size": v.get("size"), "result": v.get("result"),
                     "glyphVsBody": [v["glyphVsBody"].get(vn) for vn in VARS], "edge": [v["edge"].get(vn) for vn in VARS],
                     "ncc": (v.get("guard") or {}).get("ncc"), "iou": (v.get("guard") or {}).get("iou"),
                     "anchor": v.get("anchor"), "binding": v.get("bindingPass"), "overlap": v.get("overlapPass")}
                 for k, v in s["icon"].items()},
        "iconPresence": s["iconPresence"],
        "k3Panels": s["k3Panels"],
        "plate": {"vsFigures": s["plateVsFigures"].get("pass"), "vsReachable": s["plateVsReachable"],
                  "bound": (s["plateVsFigures"].get("binding") or {}).get("bound"),
                  "gapToOwner": (s["plateVsFigures"].get("binding") or {}).get("gapToOwner")},
        "k1PassableLuma": {"p50": round(lum["luma_p50"], 1), "p90": round(lum["luma_p90"], 1),
                           "registeredRange": th["acceptance"]["boardLumaK1JoinerPassableP50"][key]},
        "c9": {k: v.get("dEV") for k, v in s["c9"].items()},
        "medusaMi": sorted({m.split(" mi=")[1].split(" ")[0] + " " + m.split("miSha256=")[1][:12] for m in s["medusaMi"]}),
    }


def r3_entry(key: str) -> dict:
    """W5b-R r3 numbers of the same board (registered rev 2 verdicts + the 5c-B1 methods on the r3 frames)."""
    s = load(R3 / "analysis" / key / "summary.json")
    zc = load(R3 / "analysis" / key / "zone-contrast-r2.json")["frames"]["K1_joiner"]
    rr = R3_RINGS_REV3 / f"rings-rev3-{key}.json"
    r3m = load(rr)["summary"] if rr.is_file() else None
    zones = {}
    for z, v in zc["zones"].items():
        slots = [sl for sl in zc["slots"] if sl["zone"] == z and not sl["occupied"]]
        zones[z] = {"pass": f"{v['pass']}/{v['slots']}",
                    "keylineVsTile": {vn: rng([sl["variants"][vn]["keylineVsTile"] for sl in slots]) for vn in VARS},
                    "fillVsKeyline": {vn: rng([sl["variants"][vn]["fillVsKeyline"] for sl in slots]) for vn in VARS}}
    lum = load(R3 / "analysis" / key / "luma-sections.json")["frames"]["K1_joiner"]["passable"]["color"]
    return {"rings": {"fractionRange": s["rings"]["fractionRange"],
                      "shapeRev1Unclassified": len(s["rings"]["shapeFail"]),
                      "keylineVsTileRev2Fail": len(s["rings"]["keylineVsTileFail"]),
                      "rev3MethodsOnR3Frames": r3m},
            "zones": zones, "multizone": {k: f"{v['pass']}/{v['cells']}" for k, v in s["multizone"].items()},
            "k1PassableLumaP50": round(lum["luma_p50"], 1),
            "icon": {k: {"edge": [v["edge"].get(vn) for vn in VARS]} for k, v in s["icon"].items()},
            "tagsMinText": s["tags"]["minText"]}


def sheets(evidence: Path, doc: dict) -> list[str]:
    """W5b-R r3 (left) against 5c-B2 (right): K1 joiner and K3 of the three boards, 960 px per frame."""
    from PIL import Image, ImageDraw
    out = []
    for tag, name in (("K1_joiner", "r3-vs-5cb2-k1_joiner.jpg"), ("K3", "r3-vs-5cb2-k3.jpg")):
        rows = []
        for key in BOARDS:
            a_ = REPO / load(R3 / "analysis" / key / "summary.json")["frames"][tag]
            b_ = REPO / doc["boards"][key]["frames"][tag]
            pair = Image.new("RGB", (1920, 540))
            for i, (p, lab) in enumerate(((a_, f"{key} {tag} W5b-R r3 (EV100 1.3, key pitch 0)"),
                                          (b_, f"{key} {tag} 5c-B2 (light rev 5: EV100 2.05, key pitch -55)"))):
                with Image.open(p) as im:
                    pair.paste(im.convert("RGB").resize((960, 540), Image.LANCZOS), (960 * i, 0))
                ImageDraw.Draw(pair).text((960 * i + 8, 70), lab, fill=(255, 255, 0))
            rows.append(pair)
        sheet = Image.new("RGB", (1920, 540 * len(rows)))
        for i, r in enumerate(rows):
            sheet.paste(r, (0, 540 * i))
        p = evidence / "analysis" / name
        sheet.save(p, quality=85)
        out.append(p.relative_to(REPO).as_posix())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sim", help="packaged-vs-forecast.json of t5cb1_exposure_sim packaged")
    a = ap.parse_args(argv)
    import t53_readability as T53
    evidence = Path(a.evidence).resolve()
    th = T53.analysis_thresholds(evidence)
    doc = {"schema": "unmatched.t5cb2-b18/1", "status": "измерено (не приёмка)",
           "thresholds": th.get("_sources"), "acceptancePlan": th["acceptance"], "boards": {}, "r3": {}}
    for key in BOARDS:
        doc["boards"][key] = board_entry(evidence, key, th)
        doc["r3"][key] = r3_entry(key)
        b = doc["boards"][key]
        print(key, "rings", b["rings"]["shapeRev3AllVariants"], b["rings"]["edgeRev3Pass"], b["rings"]["edgeRev3Min"],
              "chips", b["chips"]["colourPass"], b["chips"]["shapePass"], b["chips"]["n"],
              "gray", (b["grayVsTile"].get("min"), b["grayVsTile"].get("slots")), "p50", b["k1PassableLuma"]["p50"], flush=True)
    if a.sim:
        doc["forecastVsPackaged"] = load(Path(a.sim))
    doc["sheets"] = sheets(evidence, doc)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("written", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
