#!/usr/bin/env python3
"""W4-A (c): Medusa face luma at K2 5x, with the face ROI placed on the projected face.

The first W4-A rule centred the ROI on the Head socket's screen X. On the v2 candidate
that box covered the right third of the face, the robe and the black gap by the neck.
It was withdrawn. This tool applies render_bench.FACE_ROI_CALIBRATION (per-mesh screen
offset from the traced Head socket) to every K2 5x frame of the W4-A run set. For each
set it records:
  * faceRoi      the face, from below the diadem tip down to the chin;
  * faceNeckRoi  the face plus the throat below the chin (the verifier's box);
  * the withdrawn first-rule box, for the record only;
  * K1 board luma: p50 of the fixed board rectangle x 600-1360, y 700-940 (the number the
    report quotes as "доска K1").
Then it draws the boxes on every frame (face-roi-contact-sheet.jpg), so the placement can
be checked by eye, and on the three-panel comparison P17 / old live / new live
(face-k2-5x-compare.jpg).

The P17 editor frame has no traced socket. It uses the same board camera as the live host
(cam (0,171,344), rot (-55,-90,0), focus (0,-50,28), 386 uu - SHOT ctx of the host trace and
the P17 evidence json), and the face of its mesh (T4, not v2) falls on the same pixels, so
the same pixel boxes are applied. The contact sheet shows the check. The
mesh differs (T4 has deeper eye sockets), so P17 is a reference point, not a like-for-like
comparison.

  python tools/art/render/face_roi.py [--evidence <evidence dir>] [--out <dir>] [--bench-raw C:/tmp/w4a/bench]
      [--calib-raw C:/tmp/w4a/calib] [--p17-dir C:/tmp/t31fix/cs/r1]

Differences count only when |delta| > 2 x the larger repeat noise (max - min over the runs) and
> 0.5 luma (half an 8-bit code value; the K1 board p50 has zero repeat noise).
Status: "измерено" on this PC (RTX 4090). This is a diagnostic, not a threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import render_bench as B  # noqa: E402
import render_fingerprint as RF  # noqa: E402

REPO = B.REPO
EVIDENCE = REPO / "docs" / "game-design" / "evidence" / "ART-004" / "render-dx12-lumen-2026-09-29"
P17_EVIDENCE = REPO / "docs" / "art-pipeline" / "evidence" / "p17-control-scene-2026-09-28" / "frames"
WITHDRAWN_BOX = (946, 461, 974, 490)  # first rule: 6x6 uu square centred on the socket X, Head + 9 uu
BOARD_K1_BOX = (600, 700, 1360, 940)  # x0, y0, x1, y1
BENCH_VARIANTS = ["dx12sm5-legacy", "dx11-legacy", "dx12-lumen-high", "dx12-lumen-high-vsm",
                  "dx12-lumen-high-csmdefault", "dx12-medium", "dx12-low", "dx12-sm5-fallback", "dx11-fallback"]
COMPARISONS = [("live-dx11-old", "live-dx12-lumen-high"), ("bench:dx12sm5-legacy", "bench:dx12-lumen-high"),
               ("bench:dx11-legacy", "bench:dx12sm5-legacy"), ("live-dx11-old", "bench:dx12sm5-legacy"),
               ("live-dx12-lumen-high", "bench:dx12-lumen-high"), ("bench:dx12-lumen-high", "bench:dx12-lumen-high-vsm"),
               ("bench:dx12-lumen-high", "bench:dx12-medium"), ("bench:dx12-lumen-high", "bench:dx12-low"),
               ("bench:dx12-lumen-high", "bench:dx12-sm5-fallback"), ("bench:dx12-lumen-high", "calib:sky-1.5"),
               ("bench:dx12-lumen-high", "calib:sky-2"), ("p17-editor", "live-dx11-old"), ("p17-editor", "live-dx12-lumen-high")]
LUMA_FLOOR = 0.5  # 8-bit luma: a difference below half a code value is not claimed, whatever the noise
METRICS = ["faceMean", "faceP5", "faceP50", "faceP95", "faceSpread", "faceNeckMean", "withdrawnMean", "boardK1P50"]


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def luma(png: Path):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert("RGB")).astype(np.float64)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def board_p50(png: Path | None) -> float | None:
    import numpy as np
    if not png or not Path(png).is_file():
        return None
    x0, y0, x1, y1 = BOARD_K1_BOX
    return round(float(np.percentile(luma(png)[y0:y1, x0:x1], 50)), 2)


def head_from_trace(trace: Path, view: str | None = None) -> dict | None:
    """Last 'SHOT head' line of a live trace, or the one of <view> in a bench trace."""
    if view:
        return (B.parse_trace(trace).get("heads") or {}).get(view)
    head = None
    for ln in RF.read_lines(trace):
        body = RF.payload(ln)
        if body.startswith("SHOT head fighter="):
            head = dict(re.findall(r"(\w+)=(\([^)]*\)|\S+)", body[len("SHOT head "):]))
    return head


def frame_row(set_name: str, k2_png: Path, head: dict | None, k1_png: Path | None,
              fixed_boxes: dict | None = None, note: str | None = None) -> dict:
    L = luma(k2_png)
    if fixed_boxes:
        boxes, why = {k: (tuple(v), "fixed pixel box (no traced socket)") for k, v in fixed_boxes.items()}, None
    else:
        boxes, why = B.face_boxes(head)
    if why:
        raise SystemExit(f"{set_name}: {k2_png}: {why}")
    face = B.roi_stats(L, boxes["faceRoi"][0])
    neck = B.roi_stats(L, boxes["faceNeckRoi"][0])
    old = B.roi_stats(L, WITHDRAWN_BOX)
    row = {"set": set_name, "k2": B.rel(k2_png), "k2Sha256": sha256(k2_png),
           "head": {k: head.get(k) for k in ("mesh", "screen", "headPx")} if head else None,
           "faceRoi": face, "faceNeckRoi": neck, "withdrawnFirstRule": old,
           "faceSpread": round(face["p95"] - face["p5"], 2),
           "k1": B.rel(k1_png) if k1_png else None, "k1Sha256": sha256(k1_png) if k1_png else None,
           "boardK1P50": board_p50(k1_png)}
    if note:
        row["note"] = note
    return row


def metric(row: dict, m: str):
    return {"faceMean": row["faceRoi"]["mean"], "faceP5": row["faceRoi"]["p5"], "faceP50": row["faceRoi"]["p50"],
            "faceP95": row["faceRoi"]["p95"], "faceSpread": row["faceSpread"], "faceNeckMean": row["faceNeckRoi"]["mean"],
            "withdrawnMean": row["withdrawnFirstRule"]["mean"], "boardK1P50": row["boardK1P50"]}[m]


def collect(a) -> dict[str, list[dict]]:
    sets: dict[str, list[dict]] = {}
    p17 = Path(a.p17_dir)
    p17_k2, p17_k1 = p17 / "p17-k2-5x-medusa-ue-editor.png", p17 / "p17-k1-overview-ue-editor.png"
    for png, ev in ((p17_k2, "p17-k2-5x-medusa-ue-editor.evidence.json"), (p17_k1, "p17-k1-overview-ue-editor.evidence.json")):
        want = json.loads((P17_EVIDENCE / ev).read_text(encoding="utf-8"))["png_before_jpeg"]["sha256"]
        if sha256(png) != want:
            raise SystemExit(f"P17 PNG {png} does not match {ev} png_before_jpeg.sha256")
    live_boxes, _ = B.face_boxes({"projected": "1", "mesh": "SK_Medusa_FaceNeck_v2Candidate",
                                  "screen": "(960.0,517.7)", "headPx": "56.4"})
    sets["p17-editor"] = [frame_row("p17-editor", p17_k2, None, p17_k1,
                                    fixed_boxes={k: v[0] for k, v in live_boxes.items()},
                                    note="editor frame, mesh T4 (not v2), DX11, candelas, EV100 1.3, point fill; "
                                         "no traced socket: the live K2 5x pixel boxes (same board camera)")]
    for name, sub in (("live-dx11-old", "live-pair-dx11-old"), ("live-dx12-lumen-high", "live-pair-dx12-lumen")):
        rows = []
        for rd in sorted((Path(a.evidence) / sub).glob("run-*")):
            rows.append(frame_row(name, rd / "phase2-board-host-1920x1080.png",
                                  head_from_trace(rd / "phase2-client-host.trace.log"),
                                  rd / "phase2-board-joiner-1920x1080.png"))
        sets[name] = rows
    for v in BENCH_VARIANTS:
        rows = []
        for rd in sorted((Path(a.bench_raw) / v).glob("r*")):
            if (rd / "bench-K2x5-1920x1080.png").is_file():
                rows.append(frame_row(f"bench:{v}", rd / "bench-K2x5-1920x1080.png",
                                      head_from_trace(rd / "bench.trace.log", "K2x5"), rd / "bench-K1-1920x1080.png"))
        sets[f"bench:{v}"] = rows
    for rd in sorted(Path(a.calib_raw).glob("*/r1")):
        name = f"calib:{rd.parent.name}"
        sets[name] = [frame_row(name, rd / "bench-K2x5-1920x1080.png", head_from_trace(rd / "bench.trace.log", "K2x5"),
                                rd / "bench-K1-1920x1080.png")]
    return sets


def aggregate(rows: list[dict]) -> dict:
    return {m: B._stats([metric(r, m) for r in rows]) for m in METRICS}


def compare(sa: dict, sb: dict) -> dict:
    out = {}
    for m in METRICS:
        a, b = sa[m], sb[m]
        if not a.get("n") or not b.get("n"):
            continue
        delta = b["mean"] - a["mean"]
        thr = max(2 * max(a["noise"], b["noise"]), LUMA_FLOOR)
        out[m] = {"a": a["mean"], "b": b["mean"], "delta": round(delta, 2), "threshold2xNoise": round(thr, 3),
                  "significant": abs(delta) > thr if min(a["n"], b["n"]) > 1 else None}
    return out


# ------------------------------------------------------------------ images
def _font(size: int):
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _dotted_rect(d, box, fill, step=4):
    x0, y0, x1, y1 = box
    for x in range(int(x0), int(x1), step * 2):
        d.line([(x, y0), (min(x + step, x1), y0)], fill=fill)
        d.line([(x, y1), (min(x + step, x1), y1)], fill=fill)
    for y in range(int(y0), int(y1), step * 2):
        d.line([(x0, y), (x0, min(y + step, y1))], fill=fill)
        d.line([(x1, y), (x1, min(y + step, y1))], fill=fill)


def tile(row: dict, crop: tuple, scale: int, title: list[str], font, withdrawn: bool = True):
    from PIL import Image, ImageDraw
    cx0, cy0, cx1, cy1 = crop
    png = REPO / row["k2"] if not Path(row["k2"]).is_absolute() else Path(row["k2"])
    im = Image.open(png).convert("RGB").crop(crop).resize(((cx1 - cx0) * scale, (cy1 - cy0) * scale), Image.LANCZOS)
    d = ImageDraw.Draw(im)

    def sbox(b):
        return [(b[0] - cx0) * scale, (b[1] - cy0) * scale, (b[2] - cx0) * scale - 1, (b[3] - cy0) * scale - 1]
    if withdrawn:
        _dotted_rect(d, sbox(row["withdrawnFirstRule"]["box"]), (170, 170, 170))
    d.rectangle(sbox(row["faceNeckRoi"]["box"]), outline=(255, 210, 0), width=1)
    d.rectangle(sbox(row["faceRoi"]["box"]), outline=(255, 30, 30), width=2)
    line_h = font.size + 3
    head = Image.new("RGB", (im.width, line_h * len(title) + 4), (0, 0, 0))
    hd = ImageDraw.Draw(head)
    for i, t in enumerate(title):
        hd.text((4, 2 + i * line_h), t, fill=(255, 255, 255) if i == 0 else (255, 230, 90), font=font)
    out = Image.new("RGB", (im.width, im.height + head.height), (0, 0, 0))
    out.paste(head, (0, 0))
    out.paste(im, (0, head.height))
    return out


def compare_image(sets: dict, path: Path) -> None:
    from PIL import Image
    font = _font(14)
    panels = [("p17-editor", "P17 editor (DX11, candelas, EV100 1.3; mesh T4)"),
              ("live-dx11-old", "old live DX11 (Unitless points, no sky)"),
              ("live-dx12-lumen-high", "new live DX12 + Lumen High")]
    tiles = []
    for name, label in panels:
        rows = sets[name]
        agg = aggregate(rows)
        r = rows[0]
        tiles.append(tile(r, (850, 400, 1060, 580), 2, [
            label + (f" (image: run 1; values: mean of {len(rows)})" if len(rows) > 1 else ""),
            f"face ROI (red) mean {agg['faceMean']['mean']:.1f}, p5-p95 {agg['faceP5']['mean']:.0f}-{agg['faceP95']['mean']:.0f}",
            f"face + throat (yellow) {agg['faceNeckMean']['mean']:.1f}; withdrawn box (grey) {agg['withdrawnMean']['mean']:.1f}"],
            font))
    W = sum(t.width for t in tiles) + 4 * (len(tiles) - 1)
    out = Image.new("RGB", (W, max(t.height for t in tiles)), (40, 40, 40))
    x = 0
    for t in tiles:
        out.paste(t, (x, 0))
        x += t.width + 4
    out.save(path, quality=90)


def contact_sheet(sets: dict, path: Path) -> None:
    from PIL import Image
    font = _font(12)
    tiles = []
    for name, rows in sets.items():
        for i, r in enumerate(rows):
            tiles.append(tile(r, (894, 440, 1000, 510), 3, [f"{name} #{i + 1}",
                                                              f"face {r['faceRoi']['mean']:.1f}  +throat {r['faceNeckRoi']['mean']:.1f}"],
                              font))
    cols = 6
    tw, th = tiles[0].width, tiles[0].height
    rows_n = (len(tiles) + cols - 1) // cols
    legend_h = 22
    out = Image.new("RGB", (cols * (tw + 4), rows_n * (th + 4) + legend_h), (40, 40, 40))
    from PIL import ImageDraw
    ImageDraw.Draw(out).text((6, 4), "red: face ROI (diadem tip to chin)   yellow: face + throat   grey dotted: withdrawn first rule "
                                     "(socket X)   crop x 894-1000, y 440-510, x3", fill=(255, 255, 255), font=_font(13))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * (tw + 4), legend_h + (i // cols) * (th + 4)))
    out.save(path, quality=88)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", default=str(EVIDENCE), help="evidence dir with live-pair-dx11-old/ and live-pair-dx12-lumen/")
    ap.add_argument("--out", default=str(EVIDENCE), help="where to write the summary and the two images")
    ap.add_argument("--bench-raw", default="C:/tmp/w4a/bench", help="bench variant dirs with the full PNGs of every repeat")
    ap.add_argument("--calib-raw", default="C:/tmp/w4a/calib")
    ap.add_argument("--p17-dir", default="C:/tmp/t31fix/cs/r1", help="P17 PNGs (kept outside git, sha256 in the P17 evidence)")
    a = ap.parse_args(argv)
    sets = collect(a)
    out = Path(a.out)
    cal = B.FACE_ROI_CALIBRATION["SK_Medusa_FaceNeck_v2Candidate"]
    doc = {"schema": "unmatched.w4a-face-roi/1", "status": "измерено (RTX 4090, не D-07); диагностика, не порог",
           "rule": {
               "faceRoi": cal["faceRoi"], "faceNeckRoi": cal["faceNeckRoi"],
               "units": "u = headPx / 12 px (screen length of 1 uu along world Z at the traced Head socket); "
                        "centre = Head projection + (dx right, dz up) u; screen offsets for the board camera only",
               "minHeadPx": B.FACE_ROI_MIN_HEAD_PX, "withdrawnFirstRuleBox": list(WITHDRAWN_BOX),
               "withdrawnWhy": "centred on the socket's screen X: covered the right third of the face, the robe and "
                               "the black gap by the neck (bimodal)",
               "boardK1": f"p50 of Rec.709 luma in x {BOARD_K1_BOX[0]}-{BOARD_K1_BOX[2]}, y {BOARD_K1_BOX[1]}-{BOARD_K1_BOX[3]}",
               "luma": "Rec.709 of the sRGB 8-bit frame, 0-255",
               "significance": f"noise = max - min over repeats; significant if |delta| > max(2 x max(noise), "
                               f"{LUMA_FLOOR} luma); a set with n = 1 -> null"},
           "placementCheck": "face-roi-contact-sheet.jpg (every K2 5x frame below with the boxes)",
           "sets": {}, "comparisons": {}}
    for name, rows in sets.items():
        doc["sets"][name] = {"n": len(rows), "aggregate": aggregate(rows), "frames": rows}
    for a_name, b_name in COMPARISONS:
        if a_name in doc["sets"] and b_name in doc["sets"]:
            doc["comparisons"][f"{a_name} -> {b_name}"] = compare(doc["sets"][a_name]["aggregate"],
                                                                  doc["sets"][b_name]["aggregate"])
    B.write_json(out / "face-roi-summary.json", doc)
    compare_image(sets, out / "face-k2-5x-compare.jpg")
    contact_sheet(sets, out / "face-roi-contact-sheet.jpg")
    for name, s in doc["sets"].items():
        g = s["aggregate"]
        print(f"{name:30s} n={s['n']} face {g['faceMean'].get('mean')} (noise {g['faceMean'].get('noise')}) "
              f"p5-p95 {g['faceP5'].get('mean')}-{g['faceP95'].get('mean')} +throat {g['faceNeckMean'].get('mean')} "
              f"withdrawn {g['withdrawnMean'].get('mean')} boardK1 {g['boardK1P50'].get('mean')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
