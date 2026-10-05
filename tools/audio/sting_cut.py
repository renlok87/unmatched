"""Cut 2-4 s stings out of Suno covers of our motifs (cards AUC-S01..S12, 02 §2.6).

    python tools/audio/sting_cut.py --src <dir with <ID>_v*.mp3> --motif MOT-ARTHUR.wav --beats 4 --tail 1.2
           --bpm 100 --id STG-WIN-ARTHUR --out <dir> [--target-lufs -18]
    python tools/audio/sting_cut.py ... --no-motif --start 0 --seconds 2.0     (generated stings without a motif)

A cover of a 5-10 s motif comes back as a 1-2 minute piece; the motif is stated near the start. For each take the
script finds where the motif sits (chroma of the motif against the take, 50 ms steps, first 20 s), keeps `beats`
beats from there plus an exponential tail, normalises to the target (integrated LUFS, true peak <= -1 dBTP) and keeps
the take whose motif match is best. Output: <out>/<ID>.wav (48 kHz / 24 bit), <ID>_16.wav (import), <ID>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze import decode as decode_mono, ffmpeg  # noqa: E402
from loop import lufs, write_wav  # noqa: E402

import subprocess

SR = 48000
ASR = 22050  # analysis rate


def decode_stereo(path: str) -> np.ndarray:
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.astype(np.float64)


def chroma_frames(x: np.ndarray, hop: int) -> np.ndarray:
    n = 4096
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    mag = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(n, 1 / ASR)
    sel = (freqs > 80) & (freqs < 3000)
    pc = (np.round(12 * np.log2(freqs[sel] / 440.0)) % 12).astype(int)
    c = np.stack([mag[:, sel][:, pc == k].sum(axis=1) for k in range(12)], axis=1)
    return c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-9)


def locate(take: np.ndarray, motif: np.ndarray, motif_s: float) -> tuple[float, float]:
    hop = int(0.05 * ASR)
    cm = chroma_frames(motif[: int(motif_s * ASR)], hop)
    ct = chroma_frames(take[: int(20 * ASR)], hop)
    best, at = -1.0, 0
    for i in range(0, max(1, len(ct) - len(cm))):
        s = float(np.mean(np.sum(ct[i: i + len(cm)] * cm, axis=1)))
        if s > best:
            best, at = s, i
    return at * 0.05, best


def first_sound(x: np.ndarray) -> float:
    win = ASR // 100
    n = len(x) // win
    env = 20 * np.log10(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-9)
    idx = np.where(env > env.max() - 35)[0]
    return idx[0] / 100 if len(idx) else 0.0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--motif")
    ap.add_argument("--no-motif", action="store_true")
    ap.add_argument("--beats", type=float, default=4)
    ap.add_argument("--bpm", type=float, default=100)
    ap.add_argument("--tail", type=float, default=1.2)
    ap.add_argument("--start", type=float)
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--target-lufs", type=float, default=-18.0)
    args = ap.parse_args(argv)

    takes = sorted(Path(args.src).glob(f"{args.id}_v*.mp3"))
    if not takes:
        raise SystemExit(f"no takes for {args.id} in {args.src}")
    motif = decode_mono(args.motif, ASR) if args.motif and not args.no_motif else None
    keep = args.seconds if args.seconds else args.beats * 60.0 / args.bpm
    cands = []
    for tk in takes:
        mono = decode_mono(str(tk), ASR)
        if motif is not None:
            start, sim = locate(mono, motif, keep)
        else:
            start, sim = (args.start if args.start is not None else first_sound(mono)), 0.0
        cands.append((sim, tk, start))
    sim, tk, start = max(cands, key=lambda c: c[0])
    x = decode_stereo(str(tk))
    a, b = int(start * SR), int((start + keep) * SR)
    tail_n = int(args.tail * SR)
    body = x[:, a:b].copy()
    tail = x[:, b: b + tail_n] * np.exp(-np.arange(tail_n) / (args.tail * SR / 4.6))
    y = np.concatenate([body, tail], axis=1)
    fi = int(0.004 * SR)
    y[:, :fi] *= np.linspace(0, 1, fi)
    fo = int(0.05 * SR)
    y[:, -fo:] *= np.linspace(1, 0, fo)
    loud = lufs(y, SR)
    y *= 10 ** ((args.target_lufs - loud["I"]) / 20)
    peak = np.max(np.abs(y))
    if peak > 0.89:
        y *= 0.89 / peak
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_wav(out / f"{args.id}.wav", y, SR, 24)
    write_wav(out / f"{args.id}_16.wav", y, SR, 16)
    rep = {"id": args.id, "take": tk.name, "motif_sim": round(sim, 3), "start_s": round(start, 2),
           "seconds": round(y.shape[1] / SR, 2), "candidates": [{"take": c[1].name, "motif_sim": round(c[0], 3),
                                                                  "start_s": round(c[2], 2)} for c in cands],
           **{f"final_{k}": v for k, v in lufs(y, SR).items()}}
    (out / f"{args.id}.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
