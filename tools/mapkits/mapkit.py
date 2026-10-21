"""Map kits: prop prompts for Gemini, turnaround split, status of every prop (docs/art-pipeline/map-kits/<map>/).

    python tools/mapkits/mapkit.py prompt <map> <key>                 # Gemini prompt of one prop (stdout)
    python tools/mapkits/mapkit.py split <map> <key> <sheet.png>      # turnaround -> props/<key>/{sheet,front,side}.png
    python tools/mapkits/mapkit.py set <map> <key> stage=tripo tripo.taskId=... tripo.credits=115
    python tools/mapkits/mapkit.py summary [<map>]                    # stages and credits per map
    python tools/mapkits/mapkit.py next <map> [--stage listed] [--n 5] # next props by priority at a stage

Data: map.json and props.json are authored; status.json is written only by this tool. Images go to
art/imagegen/mapkit-<map>/props/<key>/. The side view is the object's LEFT side for an axial prop (Tripo slot LEFT)
and its BACK for an asymmetric one (slot BACK), skill 3d-model-pipeline references/tripo3d-stages.md §5.3.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KITS = ROOT / "docs" / "art-pipeline" / "map-kits"
STAGES = ["listed", "views", "tripo", "built", "accepted", "rework", "rejected", "ue"]


def kit_dir(m: str) -> Path:
    d = KITS / m
    if not (d / "props.json").is_file():
        sys.exit(f"ERROR unknown map kit {m!r} (no {d / 'props.json'})")
    return d


def load_props(m: str) -> dict:
    return json.loads((kit_dir(m) / "props.json").read_text(encoding="utf-8"))


def prop(m: str, key: str) -> dict:
    for p in load_props(m)["props"]:
        if p["key"] == key:
            return p
    sys.exit(f"ERROR prop {key!r} not in {m}")


def load_status(m: str) -> dict:
    f = kit_dir(m) / "status.json"
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"schema": "unmatched.map-kit.status/1", "map": m, "updatedAt": None, "props": {}}


def save_status(m: str, st: dict) -> None:
    st["updatedAt"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    st["totals"] = {"credits": sum(((v.get("tripo") or {}).get("credits") or 0) for v in st["props"].values()),
                    "byStage": {s: sum(1 for v in st["props"].values() if v.get("stage") == s) for s in STAGES}}
    f = kit_dir(m) / "status.json"
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, f)


def side_slot(p: dict) -> str:
    return "left" if p["symmetry"] == "axial" else "back"


def prompt_text(m: str, key: str) -> str:
    kit = load_props(m)
    p = prop(m, key)
    w, d, h = p["sizeM"]
    side = ("RIGHT half: the exact LEFT side view of the same object (camera turned 90 degrees, the object's own left "
            "side faces the camera, so the object's FRONT points to the LEFT edge of the image)") if side_slot(p) == "left" else \
           ("RIGHT half: the exact BACK view of the same object (camera turned 180 degrees, we see its back)")
    return (
        "Production reference image for image-to-3D modelling. One wide 2:1 landscape image showing ONE object twice, "
        "side by side, with empty space between them: LEFT half: the exact FRONT view. " + side + ". "
        "Near-orthographic camera at the object's mid-height, no perspective distortion, no tilt. Both views at the same "
        "scale, same height and same vertical position, each fully inside its half with about 10% margin. "
        "Plain flat seamless neutral mid-grey background (#808080) everywhere. Soft even light from the front and above, "
        "no cast shadows, no floor, no ground plane, no reflections - only the object's own base. Neutral daylight "
        "material colours, not night lighting, no glow. No text, no labels, no watermark, no border, no divider line. "
        f"Art style (shapes and materials only; the lighting stays neutral daylight as above): {kit['styleEn']}. "
        f"Object: {p['nameEn']} - {p['descEn']}. Materials: {p['material']}. "
        f"Real-world size about {w:g} m wide, {d:g} m deep, {h:g} m tall; keep these proportions."
    )


def _bbox_of_object(arr, x0: int, x1: int, bg_tol: float):
    import numpy as np
    sub = arr[:, x0:x1].astype(np.float32)
    bg = np.median(np.concatenate([sub[:8].reshape(-1, 3), sub[-8:].reshape(-1, 3)]), axis=0)
    diff = np.abs(sub - bg).max(axis=2) > bg_tol
    ys, xs = np.nonzero(diff)
    if len(xs) < 50:
        return None, bg
    return (int(xs.min()) + x0, int(ys.min()), int(xs.max()) + x0 + 1, int(ys.max()) + 1), bg


def split(m: str, key: str, sheet: Path, bg_tol: float = 18.0) -> dict:
    """Cut a 2-view turnaround into square front/side PNGs on #808080 (object centred, ~10% margin)."""
    import numpy as np
    from PIL import Image
    p = prop(m, key)
    img = Image.open(sheet).convert("RGB")
    arr = np.asarray(img)
    hgt, wid = arr.shape[:2]
    # split at the widest background column gap near the middle
    col_bg = np.abs(arr.astype(np.float32) - np.median(arr[:8].reshape(-1, 3), axis=0)).max(axis=2) > bg_tol
    occupied = col_bg.any(axis=0)
    lo, hi = int(wid * 0.3), int(wid * 0.7)
    gaps = [x for x in range(lo, hi) if not occupied[x]]
    cut = int(np.median(gaps)) if gaps else wid // 2
    out_dir = ROOT / "art" / "imagegen" / f"mapkit-{m}" / "props" / key
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"sheet": None, "cut_x": cut, "gap_found": bool(gaps), "views": {}}
    img.save(out_dir / "sheet.png")
    res["sheet"] = str((out_dir / "sheet.png").relative_to(ROOT)).replace("\\", "/")
    prev = img.copy()
    prev.thumbnail((1200, 1200))
    prev.save(out_dir / "sheet.jpg", quality=85)  # in git; the PNG views stay local (NOTES MK-07)
    boxes = {}
    for name, (x0, x1) in (("front", (0, cut)), ("side", (cut, wid))):
        box, bg = _bbox_of_object(arr, x0, x1, bg_tol)
        if box is None:
            sys.exit(f"ERROR no object found in the {name} half of {sheet}")
        boxes[name] = box
    # one canvas size for both views: same pixel scale, so Tripo sees the same object size in every slot
    side_len = int(max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()) / 0.8)
    for name, box in boxes.items():
        crop = img.crop(box)
        canvas = Image.new("RGB", (side_len, side_len), (128, 128, 128))
        canvas.paste(crop, ((side_len - crop.width) // 2, (side_len - crop.height) // 2))
        if side_len < 1024:
            canvas = canvas.resize((1024, 1024), Image.LANCZOS)
        f = out_dir / f"{name}.png"
        canvas.save(f)
        res["views"][name] = {"path": str(f.relative_to(ROOT)).replace("\\", "/"), "bbox": box,
                              "px": [crop.width, crop.height]}
    hf, hs = (boxes["front"][3] - boxes["front"][1]), (boxes["side"][3] - boxes["side"][1])
    res["height_mismatch_pct"] = round(abs(hf - hs) / max(hf, hs) * 100, 1)
    st = load_status(m)
    e = st["props"].setdefault(key, {})
    e["stage"] = "views" if e.get("stage") in (None, "listed") else e["stage"]
    e["views"] = {"sheet": res["sheet"], "sheetJpg": res["sheet"][:-4] + ".jpg",
                  "front": res["views"]["front"]["path"], "side": res["views"]["side"]["path"],
                  "slot": side_slot(p), "heightMismatchPct": res["height_mismatch_pct"]}
    save_status(m, st)
    return res


def set_fields(m: str, key: str, pairs: list[str]) -> dict:
    prop(m, key)
    st = load_status(m)
    e = st["props"].setdefault(key, {"stage": "listed"})
    for pair in pairs:
        k, _, v = pair.partition("=")
        try:
            val = json.loads(v)
        except json.JSONDecodeError:
            val = v
        cur = e
        parts = k.split(".")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = val
    if e.get("stage") not in STAGES:
        sys.exit(f"ERROR stage {e.get('stage')!r} not in {STAGES}")
    save_status(m, st)
    return e


def summary(maps: list[str]) -> None:
    grand = 0
    for m in maps:
        props = load_props(m)["props"]
        st = load_status(m)["props"]
        counts = {s: 0 for s in STAGES}
        cr = 0
        for p in props:
            e = st.get(p["key"], {})
            counts[e.get("stage", "listed")] += 1
            cr += ((e.get("tripo") or {}).get("credits") or 0)
        grand += cr
        print(f"{m:18} props {len(props):3}  " + "  ".join(f"{s} {n}" for s, n in counts.items() if n) + f"  credits {cr}")
    print(f"total credits {grand}")


def next_props(m: str, stage: str, n: int) -> None:
    st = load_status(m)["props"]
    order = {"P0": 0, "P1": 1, "P2": 2}
    rows = [p for p in load_props(m)["props"] if st.get(p["key"], {}).get("stage", "listed") == stage]
    rows.sort(key=lambda p: (order[p["priority"]], p["key"]))
    for p in rows[:n]:
        print(p["key"], p["priority"], p["symmetry"], side_slot(p))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prompt"); a.add_argument("map"); a.add_argument("key")
    a = sub.add_parser("split"); a.add_argument("map"); a.add_argument("key"); a.add_argument("sheet", type=Path)
    a.add_argument("--bg-tol", type=float, default=18.0)
    a = sub.add_parser("set"); a.add_argument("map"); a.add_argument("key"); a.add_argument("pairs", nargs="+")
    a = sub.add_parser("summary"); a.add_argument("map", nargs="?")
    a = sub.add_parser("next"); a.add_argument("map"); a.add_argument("--stage", default="listed")
    a.add_argument("--n", type=int, default=5)
    args = ap.parse_args()
    if args.cmd == "prompt":
        print(prompt_text(args.map, args.key))
    elif args.cmd == "split":
        sheet = args.sheet
        if str(sheet) == "latest":  # newest Gemini download; the raw file is moved out of Downloads after the split
            import time
            dl = Path.home().joinpath("Downloads")
            for _ in range(40):  # Gemini prepares the full-size file for a few seconds, then *.crdownload lands
                ready = [c for c in dl.glob("Gemini_Generated_Image_*") if c.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
                if ready and not list(dl.glob("*.crdownload")):
                    break
                time.sleep(1)
            cands = sorted((c for c in dl.glob("Gemini_Generated_Image_*") if c.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")),
                           key=lambda p: p.stat().st_mtime)
            if not cands:
                sys.exit("ERROR no Gemini_Generated_Image_* in Downloads")
            sheet = cands[-1]
        res = split(args.map, args.key, sheet, args.bg_tol)
        if str(args.sheet) == "latest":
            raw = Path("C:/tmp/mapkits/gemini-raw")
            raw.mkdir(parents=True, exist_ok=True)
            res["raw"] = str(raw / f"{args.map}--{args.key}--{sheet.name}")
            shutil.move(str(sheet), res["raw"])
        print(json.dumps(res, ensure_ascii=False))
    elif args.cmd == "set":
        print(json.dumps(set_fields(args.map, args.key, args.pairs), ensure_ascii=False))
    elif args.cmd == "summary":
        summary([args.map] if args.map else sorted(d.name for d in KITS.iterdir() if (d / "props.json").is_file()))
    elif args.cmd == "next":
        next_props(args.map, args.stage, args.n)


if __name__ == "__main__":
    main()
