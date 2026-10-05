"""Objective pre-check of generated music (no listening judgement): 05-production-plan §2.1, 01-inventory §3.1.

    python tools/audio/analyze.py <file> [<file> ...] [--ref sketch.wav] [--bpm 90] [--json out.json]

Per file: EBU R128 (ffmpeg ebur128: I, LRA, true peak), duration, leading/trailing silence, start/end level against
the body (intro / fade-out), tempo by onset autocorrelation, and - with --ref - harmonic agreement with our sketch:
chroma of the sketch against the best-matching window of the file (cosine, 0..1) and the key offset in semitones
(0 = same key). With --bpm the loop window search uses that tempo instead of the estimate.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050  # analysis rate (decoded mono); enough for chroma and tempo
FFMPEG_DIR = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    hits = list(FFMPEG_DIR.glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"))
    if not hits:
        raise SystemExit("ffmpeg not found")
    return str(hits[0])


def decode(path: str, sr: int = SR) -> np.ndarray:
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def ebur128(path: str) -> dict:
    err = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null",
                          "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    summ = err[err.rfind("Summary:"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+|-inf)", summ).group(1).replace("-inf", "-120"))
    return {"I": g("I"), "LRA": g("LRA"), "TP": g("Peak")}


def stft_mag(x: np.ndarray, n: int = 4096, hop: int = 1024) -> np.ndarray:
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    return np.abs(np.fft.rfft(frames, axis=1))


def chroma(x: np.ndarray, hop: int = 1024) -> tuple[np.ndarray, float]:
    mag = stft_mag(x, 4096, hop)
    freqs = np.fft.rfftfreq(4096, 1 / SR)
    sel = (freqs > 55) & (freqs < 4000)
    pc = (np.round(12 * np.log2(freqs[sel] / 440.0)) % 12).astype(int)  # 0 = A
    c = np.zeros((mag.shape[0], 12))
    for k in range(12):
        c[:, k] = mag[:, sel][:, pc == k].sum(axis=1)
    c /= np.linalg.norm(c, axis=1, keepdims=True) + 1e-9
    return c, hop / SR


def tempo(x: np.ndarray) -> float:
    mag = stft_mag(x, 2048, 512)
    flux = np.maximum(np.diff(np.log1p(mag), axis=0), 0).sum(axis=1)
    flux -= flux.mean()
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    dt = 512 / SR
    lags = np.arange(len(ac)) * dt
    sel = (lags > 60 / 180) & (lags < 60 / 60)
    return round(60 / lags[sel][np.argmax(ac[sel])], 1)


def ref_match(x: np.ndarray, ref: np.ndarray) -> dict:
    """Best window of x against the sketch: mean cosine of per-second chroma, over shifts and transpositions."""
    cx, dt = chroma(x)
    cr, _ = chroma(ref)
    per = int(round(1.0 / dt))  # average chroma per ~1 s block to tolerate small tempo drift

    def blocks(c):
        n = len(c) // per
        b = c[: n * per].reshape(n, per, 12).mean(axis=1)
        return b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)

    bx, br = blocks(cx), blocks(cr)
    if len(bx) < len(br):
        br = br[: len(bx)]
    best = (-1.0, 0, 0)
    for shift in range(0, len(bx) - len(br) + 1):
        win = bx[shift: shift + len(br)]
        for t in range(12):
            sim = float(np.mean(np.sum(win * np.roll(br, t, axis=1), axis=1)))
            if sim > best[0]:
                best = (sim, shift, t)
    return {"chroma_sim": round(best[0], 3), "best_offset_s": best[1], "key_offset_semitones": (best[2] + 6) % 12 - 6}


def level_profile(x: np.ndarray) -> dict:
    win = SR // 20
    n = len(x) // win
    env = 20 * np.log10(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-9)
    peak = env.max()
    above = np.where(env > peak - 50)[0]
    body = np.median(env[int(n * 0.2): int(n * 0.8)])
    return {"lead_sil_s": round(above[0] * 0.05, 2) if len(above) else 0.0,
            "trail_sil_s": round((n - above[-1] - 1) * 0.05, 2) if len(above) else 0.0,
            "first3_vs_body_db": round(float(np.mean(env[:60]) - body), 1),
            "last3_vs_body_db": round(float(np.mean(env[-60:]) - body), 1)}


def analyze(path: str, ref: np.ndarray | None) -> dict:
    x = decode(path)
    out = {"file": Path(path).name, "seconds": round(len(x) / SR, 2), **ebur128(path), **level_profile(x),
           "bpm_est": tempo(x)}
    if ref is not None:
        out.update(ref_match(x, ref))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--ref")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    ref = decode(args.ref) if args.ref else None
    rows = [analyze(f, ref) for f in args.files]
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
