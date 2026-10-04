"""Prepare a long gameplay video for multi-agent review.

usage:
  python tools/de-footage/prep.py VIDEO sheets      # 4x4 contact sheets, one frame per 2 s, per chapter
  python tools/de-footage/prep.py VIDEO motion      # 30 fps frame-difference timeline (global + 4x4 grid)
  python tools/de-footage/prep.py VIDEO segments    # motion segments per chapter from motion.npy
  python tools/de-footage/prep.py VIDEO all

Outputs go to C:/tmp/de-footage/work/.
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

ROOT = "C:/tmp/de-footage"
WORK = ROOT + "/work"
CHAPTERS = json.load(open(os.path.join(os.path.dirname(__file__), "chapters.json"), encoding="utf-8"))
FONT = "C\\:/Windows/Fonts/arialbd.ttf"
SHEET_STEP = 2  # seconds between tiles
TILES = 16  # 4x4
MW, MH, MFPS = 160, 96, 30  # motion probe resolution and rate


def duration(video):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", video]
    )
    return float(out)


def chapter_ranges(video):
    total = duration(video)
    res = []
    for i, c in enumerate(CHAPTERS):
        end = CHAPTERS[i + 1]["start"] if i + 1 < len(CHAPTERS) else total
        res.append((c["id"], c["start"], end, c["title"]))
    return res


def sheets(video):
    index = []
    for cid, s, e, title in chapter_ranges(video):
        out = f"{WORK}/sheets/{cid}"
        os.makedirs(out, exist_ok=True)
        text = "%{pts\\:hms\\:" + str(s) + "}"
        vf = (
            f"fps=1/{SHEET_STEP},scale=480:270,"
            f"drawtext=fontfile='{FONT}':text='{text}':x=6:y=6:fontsize=24:fontcolor=yellow:box=1:boxcolor=black@0.65,"
            f"tile=4x4:padding=2:color=black"
        )
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(s), "-to", str(e), "-i", video, "-vf", vf,
             "-q:v", "3", f"{out}/sheet_%04d.jpg"],
            check=True,
        )
        n = len([f for f in os.listdir(out) if f.endswith(".jpg")])
        for k in range(n):
            t0 = s + k * SHEET_STEP * TILES
            index.append({"chapter": cid, "file": f"sheets/{cid}/sheet_{k + 1:04d}.jpg",
                          "t0": t0, "t1": min(e, t0 + SHEET_STEP * TILES)})
        print(cid, title, n, "sheets", flush=True)
    with open(f"{WORK}/sheets/index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["chapter", "file", "t0", "t1"])
        w.writeheader()
        w.writerows(index)


def motion(video):
    os.makedirs(WORK, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={MFPS},scale={MW}:{MH},format=gray",
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=MW * MH * 64)
    size = MW * MH
    prev = None
    rows = []
    n = 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        cur = np.frombuffer(buf, np.uint8).reshape(MH, MW).astype(np.int16)
        if prev is None:
            rows.append(np.zeros(17, np.float32))
        else:
            d = np.abs(cur - prev)
            grid = d.reshape(4, MH // 4, 4, MW // 4).mean(axis=(1, 3)).ravel()
            rows.append(np.concatenate([[d.mean()], grid]).astype(np.float32))
        prev = cur
        n += 1
        if n % (MFPS * 600) == 0:
            print("motion", n // MFPS, "s", flush=True)
    p.wait()
    arr = np.stack(rows).astype(np.float16)
    np.save(f"{WORK}/motion.npy", arr)
    print("motion frames", len(arr), flush=True)


def scan(video):
    """One decode pass (NVDEC): global contact sheets + 30 fps motion timeline."""
    out = f"{WORK}/sheets"
    os.makedirs(out, exist_ok=True)
    text = "%{pts\\:hms}"
    fc = (
        "[0:v]split=2[s][m];"
        f"[s]fps=1/{SHEET_STEP},scale=480:270,"
        f"drawtext=fontfile='{FONT}':text='{text}':x=6:y=6:fontsize=24:fontcolor=yellow:box=1:boxcolor=black@0.65,"
        "tile=4x4:padding=2:color=black[sheet];"
        f"[m]fps={MFPS},scale={MW}:{MH},format=gray[mo]"
    )
    cmd = ["ffmpeg", "-v", "error", "-y", "-hwaccel", "cuda", "-i", video, "-filter_complex", fc,
           "-map", "[sheet]", "-q:v", "3", f"{out}/sheet_%05d.jpg",
           "-map", "[mo]", "-f", "rawvideo", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=MW * MH * 64)
    size = MW * MH
    prev = None
    rows = []
    n = 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        cur = np.frombuffer(buf, np.uint8).reshape(MH, MW).astype(np.int16)
        if prev is None:
            rows.append(np.zeros(17, np.float32))
        else:
            d = np.abs(cur - prev)
            grid = d.reshape(4, MH // 4, 4, MW // 4).mean(axis=(1, 3)).ravel()
            rows.append(np.concatenate([[d.mean()], grid]).astype(np.float32))
        prev = cur
        n += 1
        if n % (MFPS * 600) == 0:
            print("scan", n // MFPS, "s", flush=True)
    p.wait()
    np.save(f"{WORK}/motion.npy", np.stack(rows).astype(np.float16))
    total = duration(video)
    ranges = chapter_ranges(video)
    files = sorted(f for f in os.listdir(out) if f.startswith("sheet_"))
    with open(f"{out}/index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "t0", "t1", "chapters"])
        for k, name in enumerate(files):
            t0 = k * SHEET_STEP * TILES
            t1 = min(total, t0 + SHEET_STEP * TILES)
            chs = [cid for cid, s, e, _ in ranges if s < t1 and t0 < e]
            w.writerow([f"sheets/{name}", t0, round(t1, 1), " ".join(chs)])
    print("scan done: motion frames", len(rows), "sheets", len(files), flush=True)


def segments(video):
    arr = np.load(f"{WORK}/motion.npy").astype(np.float32)
    grid = arr[:, 1:]
    # cells busy most of the time (webcam overlay, animated background) are masked out
    busy = (grid > 1.0).mean(axis=0)
    mask = busy < 0.35
    sig = grid[:, mask].mean(axis=1) if mask.any() else arr[:, 0]
    k = np.ones(3) / 3
    sig = np.convolve(sig, k, mode="same")
    base = np.median(sig)
    mad = np.median(np.abs(sig - base)) + 1e-6
    thr = max(base + 6 * mad, 0.25)
    on = sig > thr
    segs = []
    i = 0
    n = len(on)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j < n and (on[j] or (j + 4 < n and on[j:j + 5].any())):  # bridge gaps < 150 ms
            j += 1
        if j - i >= 3:
            seg = grid[i:j]
            cells = [int(c) for c in np.argsort(-seg.mean(axis=0))[:3]]
            segs.append((i / MFPS, j / MFPS, (j - i) * 1000 / MFPS, float(sig[i:j].max()),
                         float(arr[i:j, 0].max()), cells))
        i = j
    rows = []
    for cid, s, e, title in chapter_ranges(video):
        for a, b, ms, peak, glob, cells in segs:
            if s <= a < e:
                rows.append({"chapter": cid, "t0": f"{a:.3f}", "t1": f"{b:.3f}", "ms": int(ms),
                             "peak": f"{peak:.2f}", "global_peak": f"{glob:.2f}",
                             "cut": int(glob > 40), "top_cells": " ".join(map(str, cells))})
    with open(f"{WORK}/segments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json.dump({"mask": mask.tolist(), "busy": busy.round(3).tolist(), "thr": thr, "fps": MFPS,
               "grid": "4x4 row-major, cell = row*4+col, 0 = top-left"},
              open(f"{WORK}/segments-meta.json", "w"), indent=1)
    print("segments", len(rows), "thr", round(thr, 3), "masked cells", [i for i, m in enumerate(mask) if not m])


if __name__ == "__main__":
    video, step = sys.argv[1], sys.argv[2]
    for name in (["scan", "segments"] if step == "all" else [step]):
        globals()[name](video)
