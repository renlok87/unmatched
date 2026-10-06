"""Objective metrics of VO takes (cards AUC-V01..V09): no listening judgement, only checks a listener would also make.

    python tools/audio/voice_metrics.py <file|dir> [...] [--json out.json]

Per file: duration, speech span (first to last frame above -40 dB of the peak), longest inner pause, median F0 of
voiced frames (autocorrelation, 60-500 Hz) and its spread, the median harmonics-to-noise ratio of voiced frames
(hnr_db; lower = rougher, raspier voice), integrated loudness, true peak, and flags:
too_long (> 2.0 s speech; victory/defeat lines get 3.0 s), long_pause (> 0.6 s inside the line), clipped.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze import decode, ebur128  # noqa: E402

SR = 22050


def f0_track(x: np.ndarray, sr: int = SR, peaks: list | None = None) -> np.ndarray:
    """F0 per frame (nan when unvoiced); voiced frames append their normalized autocorrelation peak to peaks."""
    n, hop = 1024, 256
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
    out = []
    lo, hi = int(sr / 500), int(sr / 60)
    for f in frames:
        f = f - f.mean()
        e = np.dot(f, f)
        if e < 1e-6:
            out.append(np.nan)
            continue
        ac = np.correlate(f, f, mode="full")[n - 1:]
        ac /= ac[0]
        lag = lo + int(np.argmax(ac[lo:hi]))
        out.append(sr / lag if ac[lag] > 0.45 else np.nan)
        if ac[lag] > 0.45 and peaks is not None:
            peaks.append(min(float(ac[lag]), 0.999))
    return np.array(out)


def metrics(path: Path) -> dict:
    x = decode(str(path), SR)
    win = SR // 100
    n = len(x) // win
    env = 20 * np.log10(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-9)
    on = env > env.max() - 40
    idx = np.where(on)[0]
    span = (idx[-1] - idx[0] + 1) / 100 if len(idx) else 0.0
    gaps, run = [], 0
    for v in on[idx[0]: idx[-1] + 1] if len(idx) else []:
        run = 0 if v else run + 1
        gaps.append(run)
    peaks: list = []
    f0 = f0_track(x, peaks=peaks)
    f0 = f0[~np.isnan(f0)]
    r = np.array(peaks)
    loud = ebur128(str(path))
    limit = 3.0 if re.search(r"VICTORY|DEFEAT", path.name) else 2.0
    return {"file": path.name, "dir": path.parent.name, "seconds": round(len(x) / SR, 2), "speech_s": round(float(span), 2),
            "max_pause_s": round(float(max(gaps or [0])) / 100, 2),
            "f0_median": round(float(np.median(f0)), 1) if len(f0) else None,
            "f0_iqr": round(float(np.subtract(*np.percentile(f0, [75, 25]))), 1) if len(f0) > 4 else None,
            "hnr_db": round(float(np.median(10 * np.log10(r / (1 - r)))), 1) if len(r) else None,
            "I": loud["I"], "TP": loud["TP"],
            "too_long": bool(span > limit), "long_pause": bool(max(gaps or [0]) / 100 > 0.6),
            "clipped": bool(loud["TP"] > -0.1)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    files = []
    for p in map(Path, args.paths):
        files += sorted(p.rglob("*.mp3")) + sorted(p.rglob("*.wav")) if p.is_dir() else [p]
    rows = [metrics(f) for f in files]
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
