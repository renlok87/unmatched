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
    """Second view: axial -> left; elongated (depth >= 1.5 x width: cab, boat, log) -> left, so Tripo sees the length;
    other asymmetric -> back (skill tripo3d-stages §5.3); props.json "sideSlot" overrides."""
    if p.get("sideSlot"):
        return p["sideSlot"]
    w, d, _ = p["sizeM"]
    return "left" if p["symmetry"] == "axial" or d >= 1.5 * w else "back"


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


def prompt_single(m: str, key: str) -> str:
    """One three-quarter view for Tripo Smart Mesh + Generate Multi-Views (NOTES MK-10): Tripo draws the other views
    itself, consistently, so the image only has to show the object clearly."""
    kit = load_props(m)
    p = prop(m, key)
    w, d, h = p["sizeM"]
    return (
        "Production reference image for image-to-3D modelling: ONE object, three-quarter front view from slightly above "
        "(camera 30 degrees to the left of the front, 15 degrees above), the whole object centred with 10% margin. "
        "Plain flat seamless neutral mid-grey background (#808080), no vignette. Soft even light, no cast shadows, no "
        "floor, no ground plane, no water, no reflections. Neutral daylight material colours, not night lighting, no "
        "glow. No text, no letters, no labels, no watermark. "
        f"Art style: {kit['styleEn']}. Object: {p['nameEn']} - {p['descEn']}. Materials: {p['material']}. "
        f"Real-world size about {w:g} m wide, {d:g} m deep, {h:g} m tall; keep these proportions."
    )


THEME = {"baskerville-manor": "Victorian gothic manor on Dartmoor", "soho": "Victorian London street and Thames wharf",
         "heorot": "Anglo-Saxon / Norse mead hall in snow", "sherwood-forest": "Robin Hood's Sherwood greenwood"}


def prompt_short(m: str, key: str) -> str:
    """Short single-view prompt for Tripo Image / Nano Banana Pro (MK-10): Tripo adds the other views itself.

    Low camera (NOTES F8): Tripo turns the camera elevation of the view into a tilt of the mesh, and "tabletop
    miniature" pulls in a base plate unless the prompt forbids it."""
    p = prop(m, key)
    w, d, h = p["sizeM"]
    text = f"{p['nameEn']} {p['descEn']}".lower()
    # NOTES F12: a wall or hanging prop gets a phantom stand or back plate unless the prompt rules it out
    tail = (" Wall-mounted: flat back, nothing behind it, no stand, no legs." if any(w_ in text for w_ in ("wall", "mounted"))
            else " Hanging item: shown alone with only a short chain or hook at the top, nothing below it, no stand."
            if any(w_ in text for w_ in ("hanging", "chandelier"))
            and not any(w_ in text for w_ in ("tripod", "pole", "stand", "rack", "spit", "beam")) else "")
    s = (f"3/4 front view of ONE object, camera low at the object's mid height, centred, 10% margin, plain flat "
         f"mid-grey (#808080) background, soft even daylight, no shadows, no floor, no base, no plinth, no text or "
         f"letters. Stylized hand-painted tabletop "
         f"miniature prop, {THEME[m]}. Object: {p['nameEn']} - {p['descEn']}. Materials: {p['material']}. "
         f"About {w:g} x {d:g} x {h:g} m (w x d x h).{tail}")
    # NOTES F13: Tripo Image silently drops prompts with "wrought-iron" / "cast-iron"
    for bad in ("Wrought-iron", "wrought-iron", "Wrought iron", "wrought iron", "Cast-iron", "cast-iron"):
        s = s.replace(bad, "black iron")
    return s


def _bbox_of_object(arr, x0: int, x1: int, bg_tol: float):
    """Object box in columns [x0, x1). The background is a plane fitted to the border pixels (the 4K Tripo Image
    upscaler and Gemini leave a light vertical gradient on the grey); rows and columns count as object only with at
    least 0.3 % of their pixels off the plane, so stray noise does not stretch the box."""
    import numpy as np
    sub = arr[:, x0:x1].astype(np.float32)
    h, w = sub.shape[:2]
    b = 6
    ys, xs = np.mgrid[0:h, 0:w]
    border = np.zeros((h, w), bool)
    border[:b], border[-b:], border[:, :b], border[:, -b:] = True, True, True, True
    A = np.stack([np.ones(border.sum()), xs[border] / w, ys[border] / h], axis=1)
    bg = np.empty_like(sub)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(A, sub[..., c][border], rcond=None)
        bg[..., c] = coef[0] + coef[1] * xs / w + coef[2] * ys / h
    diff = np.abs(sub - bg).max(axis=2) > bg_tol
    rows = np.nonzero(diff.sum(axis=1) > max(3, 0.003 * w))[0]
    cols = np.nonzero(diff.sum(axis=0) > max(3, 0.003 * h))[0]
    if len(rows) < 10 or len(cols) < 10:
        return None, bg
    return (int(cols.min()) + x0, int(rows.min()), int(cols.max()) + x0 + 1, int(rows.max()) + 1), bg


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


def pick_latest() -> Path:
    """Newest Gemini / Tripo Image download of the last 2 minutes only: Downloads also holds the user's own files (an
    older "image (1).png" was once taken by mistake and put back), so never pick anything older."""
    import time
    dl = Path.home().joinpath("Downloads")
    pats = ("Gemini_Generated_Image_*", "image*", "upscaled_*")

    def fresh():
        now = time.time()
        return sorted((c for pat in pats for c in dl.glob(pat)
                       if c.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and now - c.stat().st_mtime < 120),
                      key=lambda c: c.stat().st_mtime)
    for _ in range(40):  # Gemini prepares the full-size file for a few seconds, then *.crdownload lands
        if fresh() and not list(dl.glob("*.crdownload")):
            break
        time.sleep(1)
    cands = fresh()
    if not cands:
        sys.exit("ERROR no Gemini / Tripo Image download of the last 2 minutes in Downloads")
    return cands[-1]


def archive_raw(m: str, key: str, src: Path) -> str:
    raw = Path("C:/tmp/mapkits/gemini-raw")
    raw.mkdir(parents=True, exist_ok=True)
    dst = raw / f"{m}--{key}--{src.name}"
    shutil.move(str(src), dst)
    return str(dst)


def single(m: str, key: str, image: Path, note: str, bg_tol: float = 28.0) -> dict:
    """One view (3/4 or profile) -> props/<key>/front.png, centred square on #808080; Tripo adds views itself."""
    from PIL import Image
    import numpy as np
    prop(m, key)
    img = Image.open(image).convert("RGB")
    arr = np.asarray(img)
    box, _ = _bbox_of_object(arr, 0, arr.shape[1], bg_tol)
    if box is None:
        sys.exit(f"ERROR no object in {image}")
    crop = img.crop(box)
    side_len = int(max(crop.size) / 0.8)
    canvas = Image.new("RGB", (side_len, side_len), (128, 128, 128))
    canvas.paste(crop, ((side_len - crop.width) // 2, (side_len - crop.height) // 2))
    if side_len < 1024 or side_len > 2048:  # Tripo uploads of 5 MB stall the form; 2048 is plenty for Smart Mesh
        canvas = canvas.resize((2048, 2048) if side_len > 2048 else (1024, 1024), Image.LANCZOS)
    out_dir = ROOT / "art" / "imagegen" / f"mapkit-{m}" / "props" / key
    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(out_dir / "sheet.png")
    prev = img.copy(); prev.thumbnail((1200, 1200)); prev.save(out_dir / "sheet.jpg", quality=85)
    canvas.save(out_dir / "front.png")
    rel = lambda q: str(q.relative_to(ROOT)).replace("\\", "/")
    st = load_status(m)
    e = st["props"].setdefault(key, {})
    e["stage"] = "views" if e.get("stage") in (None, "listed") else e["stage"]
    e["views"] = {"sheet": rel(out_dir / "sheet.png"), "sheetJpg": rel(out_dir / "sheet.jpg"),
                  "front": rel(out_dir / "front.png"), "side": None, "slot": "single", "source": note}
    save_status(m, st)
    return {"front": rel(out_dir / "front.png"), "bbox": box, "px": list(crop.size)}


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


def todo(m: str) -> list[tuple[str, str, str]]:
    """Next step of every prop in flight: (key, next, task) from status.json (views/tripo ops/glb/build/acceptance)."""
    out = []
    order = {"P0": 0, "P1": 1, "P2": 2}
    pr = {p["key"]: p for p in load_props(m)["props"]}
    for key, e in sorted(load_status(m)["props"].items(), key=lambda kv: (order[pr[kv[0]]["priority"]], kv[0])):
        t = e.get("tripo") or {}
        ops = [o["op"] for o in t.get("ops", []) if o.get("status") == "ok"]
        task = t.get("taskId", "")
        st = e.get("stage")
        if st in ("accepted", "rejected"):
            continue
        if st == "rework":
            nxt = "rework (regenerate r2)"
        elif st == "built":
            nxt = "acceptance" if not (e.get("acceptance") or {}).get("card") else "second acceptor / finish"
        elif t.get("glb"):
            nxt = "env_kit build"
        elif "pbr" in ops:
            nxt = "export GLB"
        elif any(o.startswith("texture") for o in ops):
            nxt = "PBR"
        elif "generate" in ops or "multiview" in ops:
            nxt = "texture " + ("4K" if pr[key]["priority"] == "P0" else "2K")
        elif (e.get("views") or {}).get("front"):
            nxt = "Smart Mesh"
        else:
            nxt = "views"
        out.append((key, nxt, task))
    return out


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
    a.add_argument("--single", action="store_true", help="one 3/4 view for Generate Multi-Views (MK-10)")
    a.add_argument("--short", action="store_true", help="short single-view prompt (MK-10)")
    a = sub.add_parser("split"); a.add_argument("map"); a.add_argument("key"); a.add_argument("sheet", type=Path)
    a.add_argument("--bg-tol", type=float, default=18.0)
    a = sub.add_parser("single"); a.add_argument("map"); a.add_argument("key"); a.add_argument("image", type=Path)
    a.add_argument("--note", default="Tripo Image, Nano Banana Pro (Gemini 3 Pro Image), one 3/4 view")
    a = sub.add_parser("set"); a.add_argument("map"); a.add_argument("key"); a.add_argument("pairs", nargs="+")
    a = sub.add_parser("summary"); a.add_argument("map", nargs="?")
    a = sub.add_parser("todo"); a.add_argument("map")
    a = sub.add_parser("next"); a.add_argument("map"); a.add_argument("--stage", default="listed")
    a.add_argument("--n", type=int, default=5)
    args = ap.parse_args()
    if args.cmd == "prompt":
        print(prompt_short(args.map, args.key) if args.short else
              prompt_single(args.map, args.key) if args.single else prompt_text(args.map, args.key))
    elif args.cmd == "split":
        sheet = args.sheet
        sheet = pick_latest() if str(args.sheet) == "latest" else args.sheet
        res = split(args.map, args.key, sheet, args.bg_tol)
        if str(args.sheet) == "latest":
            res["raw"] = archive_raw(args.map, args.key, sheet)
        print(json.dumps(res, ensure_ascii=False))
    elif args.cmd == "single":
        src = pick_latest() if str(args.image) == "latest" else args.image
        res = single(args.map, args.key, src, args.note)
        if str(args.image) == "latest":
            res["raw"] = archive_raw(args.map, args.key, src)
        print(json.dumps(res, ensure_ascii=False))
    elif args.cmd == "set":
        print(json.dumps(set_fields(args.map, args.key, args.pairs), ensure_ascii=False))
    elif args.cmd == "todo":
        for key, nxt, task in todo(args.map):
            print(f"{key:22} {nxt:28} {task}")
    elif args.cmd == "summary":
        summary([args.map] if args.map else sorted(d.name for d in KITS.iterdir() if (d / "props.json").is_file()))
    elif args.cmd == "next":
        next_props(args.map, args.stage, args.n)


if __name__ == "__main__":
    main()
