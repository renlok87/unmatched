#!/usr/bin/env python3
"""ENV-MAPS P5a: UMG label plates (P4 readability HIGH, profile flag "labelPlates") in packaged-live frames. Read-only.

For every frame of the given run dirs: the 'SHOT widget id=board.tag ... bbox=(x0,y0,x1,y1) geom=painted visible=1'
lines of its late SHOT block ('SHOT late begin file=<frame>') give the painted tag rects. Per rect (frame pixels):
  plateL      median luminance (0-255, Rec.709 on sRGB bytes) of the darker 60 % of the interior (inset 3 px): the
              plate fill (#10131E at 84 % over the board, P4 style);
  textL       90th percentile luminance of the interior (name / HP text);
  contrast    WCAG ratio textL : plateL (sRGB -> linear);
  aroundL     median luminance of the 4-9 px ring OUTSIDE the rect (the board under / next to the tag);
  outline     mean sRGB of the 1 px rect border (team-colour outline);
and per frame the smallest gap (px) between two painted tag rects (P4: hard pad 3 px).
Usage: python plates.py --json OUT --crops DIR <run-dir> [<run-dir> ...]   (crops: x3 tiles, outside git)"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np
from PIL import Image

TAG = re.compile(r"SHOT widget id=board\.tag impl=\S+ state=(\S+) fighter=(\S+) bbox=\((\d+),(\d+),(\d+),(\d+)\) geom=(\S+) visible=(\d)")
LATE = re.compile(r"SHOT late begin file=(\S+)")
PLATE = re.compile(r"HUD tags boardPlate=(\d) hardPadPx=(\S+) profile=(\S+)")


def lum(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def lin(v):
    v = v / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def tags_by_frame(trace: Path):
    out, cur, plate = {}, None, None
    for ln in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        m = PLATE.search(ln)
        if m:
            plate = {"boardPlate": int(m.group(1)), "hardPadPx": float(m.group(2)), "profile": m.group(3)}
        m = LATE.search(ln)
        if m:
            cur = m.group(1)
            out[cur] = []  # a repeated late block of the same file (re-shot) replaces the earlier one
            continue
        if "SHOT request file=" in ln:
            cur = None
        m = TAG.search(ln)
        if m and cur:
            out[cur].append({"state": m.group(1), "fighter": m.group(2), "bbox": [int(m.group(i)) for i in range(3, 7)],
                             "painted": m.group(7) == "painted" and m.group(8) == "1"})
    return out, plate


def measure(img, bb):
    x0, y0, x1, y1 = bb
    h, w = img.shape[:2]
    inner = img[y0 + 3:y1 - 2, x0 + 3:x1 - 2].reshape(-1, 3)
    L = lum(inner)
    s = np.sort(L)
    plate = float(np.median(s[: max(1, int(len(s) * 0.6))]))
    text = float(np.percentile(L, 90))
    ring = np.zeros((h, w), bool)
    ring[max(0, y0 - 9):min(h, y1 + 9), max(0, x0 - 9):min(w, x1 + 9)] = True
    ring[max(0, y0 - 4):min(h, y1 + 4), max(0, x0 - 4):min(w, x1 + 4)] = False
    around = float(np.median(lum(img[ring])))
    border = np.concatenate([img[y0, x0:x1], img[y1 - 1, x0:x1], img[y0:y1, x0], img[y0:y1, x1 - 1]])
    lp, lt = float(lin(np.array(plate))), float(lin(np.array(text)))
    return {"plateL": round(plate, 1), "textL": round(text, 1), "contrast": round((lt + 0.05) / (lp + 0.05), 2),
            "aroundL": round(around, 1), "outlineMeanSrgb": [round(float(x)) for x in border.mean(0)]}


def gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return max(dx, dy) if (dx == 0 or dy == 0) else int(round((dx * dx + dy * dy) ** 0.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--crops")
    a = ap.parse_args()
    res = {"schema": "unmatched.env-maps.label-plates/1", "frames": []}
    for rd in map(Path, a.runs):
        for tr in sorted(rd.glob("*.trace.log")):
            side = "host" if "host" in tr.name else "joiner"
            frames, plate = tags_by_frame(tr)
            for name, tags in frames.items():
                pngs = [p for p in (rd / name, rd / side / name) if p.is_file()]
                if not pngs:
                    continue
                img = np.asarray(Image.open(pngs[0]).convert("RGB")).astype(np.float64)
                painted = [t for t in tags if t["painted"]]
                for t in painted:
                    t.update(measure(img, t["bbox"]))
                gaps = [gap(p["bbox"], q["bbox"]) for i, p in enumerate(painted) for q in painted[i + 1:]]
                rec = {"run": rd.name, "frame": pngs[0].relative_to(rd).as_posix(), "side": side, "hudTags": plate,
                       "tagsPainted": len(painted), "tags": painted, "minGapPx": min(gaps) if gaps else None}
                res["frames"].append(rec)
                if a.crops and painted:
                    tiles = []
                    for t in painted:
                        x0, y0, x1, y1 = t["bbox"]
                        c = Image.fromarray(img[max(0, y0 - 12):y1 + 12, max(0, x0 - 12):x1 + 12].astype(np.uint8))
                        tiles.append(c.resize((c.width * 3, c.height * 3), Image.NEAREST))
                    W = sum(t.width for t in tiles) + 8 * len(tiles); H = max(t.height for t in tiles)
                    sheet = Image.new("RGB", (W, H), (40, 40, 40)); x = 0
                    for t in tiles:
                        sheet.paste(t, (x, 0)); x += t.width + 8
                    Path(a.crops).mkdir(parents=True, exist_ok=True)
                    sheet.save(Path(a.crops) / f"{rd.parent.parent.name}-{rd.name}-{Path(name).stem}-{side}-tags.png")
                print(rec["run"], rec["frame"], "tags", len(painted), "plateL", [t["plateL"] for t in painted],
                      "contrast", [t["contrast"] for t in painted], "around", [t["aroundL"] for t in painted],
                      "minGap", rec["minGapPx"], plate and plate["boardPlate"])
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
