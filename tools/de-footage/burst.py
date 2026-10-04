"""Frame tools for reviewers.

  python tools/de-footage/burst.py strip T0 T1 FPS COLS WIDTH OUT.jpg [CROP]
      Grid of consecutive frames between T0 and T1 (seconds, absolute video time),
      each labelled with its timestamp in ms (e.g. 30 6 400). Count frames between
      labels to time an animation (1 tile = 1000/FPS ms; source is 30 fps, so 30 is
      the finest step). CROP = w:h:x:y in 1920x1080 source pixels zooms one region.
  python tools/de-footage/burst.py frame T OUT.png [CROP]
      One full-resolution frame. CROP = w:h:x:y in source pixels (optional).
  python tools/de-footage/burst.py motion T0 T1
      Print the 30 fps motion timeline (global + busiest cell) for a range.
  python tools/de-footage/burst.py segs T0 T1 [MIN_MS]
      Motion segments (start-end, duration, 4x4 cells that moved; cell = row*4+col).
"""
import math
import subprocess
import sys

import numpy as np

VIDEO_FILE = "C:/tmp/de-footage/work/video.txt"
FONT = "C\\:/Windows/Fonts/arialbd.ttf"


def video():
    return open(VIDEO_FILE, encoding="utf-8").read().strip()


def strip(t0, t1, fps=30, cols=6, width=400, out="strip.jpg", crop=None):
    t0, t1, fps, cols, width = float(t0), float(t1), float(fps), int(cols), int(width)
    n = max(1, int(round((t1 - t0) * fps)))
    if n > 96:
        raise SystemExit(f"{n} frames: keep a strip under 96 frames (shorter range or lower fps)")
    rows = math.ceil(n / cols)
    text = "%{pts\\:hms\\:" + f"{t0:.3f}" + "}"
    pre = f"crop={crop}," if crop else ""
    vf = (f"fps={fps},{pre}scale={width}:-2,"
          f"drawtext=fontfile='{FONT}':text='{text}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.7,"
          f"tile={cols}x{rows}:padding=2:color=black")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-i", video(), "-frames:v", "1",
                    "-vf", f"trim=duration={t1 - t0:.3f},{vf}", "-q:v", "3", out], check=True)
    print(out, n, "frames", f"{1000 / fps:.1f} ms/tile")


def frame(t, out="frame.png", crop=None):
    vf = ["-vf", f"crop={crop}"] if crop else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{float(t):.3f}", "-i", video(), "-frames:v", "1",
                    *vf, out], check=True)
    print(out)


def motion(t0, t1):
    arr = np.load("C:/tmp/de-footage/work/motion.npy").astype(np.float32)
    a, b = int(float(t0) * 30), int(float(t1) * 30)
    for i in range(a, min(b, len(arr))):
        g = arr[i, 1:]
        c = int(g.argmax())
        print(f"{i / 30:9.3f}s global={arr[i, 0]:6.2f} top_cell={c:2d} ({g[c]:6.2f})")


def segs(t0, t1, min_ms=0):
    import csv
    rows = list(csv.DictReader(open("C:/tmp/de-footage/work/segments.csv", encoding="utf-8")))
    for r in rows:
        if float(t0) <= float(r["t0"]) < float(t1) and int(r["ms"]) >= int(min_ms):
            print(f'{float(r["t0"]):9.3f}-{float(r["t1"]):9.3f}s {int(r["ms"]):6d} ms peak={r["peak"]:>6} '
                  f'cut={r["cut"]} cells={r["top_cells"]}')


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:]
    {"strip": strip, "frame": frame, "motion": motion, "segs": segs}[cmd](*rest)
