"""Seamless music loops from Demucs stems (card AUC-M06, 02 §2.3-2.4, §5.5).

    python tools/audio/loop.py --stems <dir> --bars 32 --bpm 90 --out <dir> --id MUS-MAP-MARMOREAL
           [--fade-beats 1] [--target-lufs -23]

The cover follows our sketch, so bar 1 starts at the first onset and the form repeats after 32 bars. The script
1. finds the first onset s0 and the beat period (comb autocorrelation of the onset envelope), L = 4 x bars beats;
   compares the chroma of the 2 bars after L with the opening (cont_sim): >= 0.85 -> "wrap" mode, else "cut";
2. wrap: cuts every stem at [s0, s0 + L) and folds the continuation x[s0 + L ...] into the first beat with an
   equal-power crossfade ("wrapped tail"); cut: cuts on the downbeat (30 ms fade-in) and adds only the decaying ring
   of bar 32 (tau 120 ms, -6 dB) - the sketches resolve bar 32 into bar 1, so the harmony closes;
3. builds L1 = other + vocals (maneuver) and L2 = drums + bass (combat); full = L1 + L2;
4. checks the seam (RMS and spectrum just before and after the wrap), normalises full to the target LUFS (02 §5.3)
   with one gain for both layers, resamples to 48 kHz through a 3x tiled copy (no filter ringing at the seam);
5. writes <id>-L1.wav, <id>-L2.wav, <id>-full.wav (48 kHz / 24 bit sources) + <id>-*_16.wav (import) + loop.json.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    hits = list((Path.home() / "AppData/Local/Microsoft/WinGet/Packages").glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"))
    if not hits:
        raise SystemExit("ffmpeg not found")
    return str(hits[0])


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Reads the float32 / int16 / int24 PCM WAVs these tools write (fmt chunk then data chunk)."""
    b = path.read_bytes()
    pos, fmt, data = 12, None, None
    while pos < len(b):
        cid, size = b[pos:pos + 4], struct.unpack("<I", b[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", b[pos + 8:pos + 24])
        elif cid == b"data":
            data = b[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)
    tag, ch, sr, _, _, bits = fmt
    if tag == 3:
        x = np.frombuffer(data, "<f4")
    elif bits == 16:
        x = np.frombuffer(data, "<i2") / 32768.0
    else:
        raw = np.frombuffer(data, np.uint8).reshape(-1, 3)
        x = (raw[:, 0].astype(np.int32) | raw[:, 1].astype(np.int32) << 8 | raw[:, 2].astype(np.int32) << 16)
        x = np.where(x >= 1 << 23, x - (1 << 24), x) / float(1 << 23)
    return x.reshape(-1, ch).T.astype(np.float64), sr


def write_wav(path: Path, x: np.ndarray, sr: int, bits: int) -> None:
    ch = x.shape[0]
    y = np.clip(x.T, -1.0, 1.0)
    if bits == 16:
        data = (np.round(y * 32767)).astype("<i2").tobytes()
    else:
        v = np.round(y * 8388607).astype(np.int32).reshape(-1)
        data = np.stack([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF], axis=1).astype(np.uint8).tobytes()
    bps = bits // 8
    head = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, ch, sr, sr * ch * bps, ch * bps, bits) + b"data" +
            struct.pack("<I", len(data)))
    path.write_bytes(head + data)


def flux_env(mono: np.ndarray, sr: int, hop: int = 256, n: int = 1024) -> np.ndarray:
    frames = np.lib.stride_tricks.sliding_window_view(mono, n)[::hop] * np.hanning(n)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    f = np.maximum(np.diff(mag, axis=0), 0).sum(axis=1)
    return np.concatenate([[0.0], f])


def first_onset(mono: np.ndarray, sr: int) -> int:
    win = sr // 100
    n = len(mono) // win
    env = 20 * np.log10(np.sqrt(np.mean(mono[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-9)
    above = np.where(env > env.max() - 30)[0]
    return int(above[0] * win) if len(above) else 0


def beat_period(mono: np.ndarray, sr: int, s0: int, bpm: float, span_s: float) -> tuple[float, float]:
    """Beat period in samples from the onset envelope of [s0, s0 + span]: comb autocorrelation over 16 multiples of
    the lag, searched within +-6 % of the sketch tempo, refined parabolically."""
    hop = 128
    env = flux_env(mono[s0: s0 + int(span_s * sr)], sr, hop)
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    ac /= ac[0] + 1e-9
    nominal = 60.0 / bpm * sr / hop
    lags = np.arange(int(nominal * 0.94), int(nominal * 1.06) + 1)
    score = np.array([sum(ac[int(round(k * l))] for k in range(1, 17) if int(round(k * l)) < len(ac)) for l in lags])
    i = int(np.argmax(score))
    if 0 < i < len(score) - 1:
        a, b, c = score[i - 1], score[i], score[i + 1]
        frac = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    else:
        frac = 0.0
    return (lags[i] + frac) * hop, float(score[i] / 16)


def chroma_blocks(mono: np.ndarray, sr: int, start: int, seconds: float) -> np.ndarray:
    seg = mono[start: start + int(seconds * sr)]
    n = 4096
    frames = np.lib.stride_tricks.sliding_window_view(seg, n)[::2048] * np.hanning(n)
    mag = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    sel = (freqs > 55) & (freqs < 4000)
    pc = (np.round(12 * np.log2(freqs[sel] / 440.0)) % 12).astype(int)
    c = np.stack([mag[:, sel][:, pc == k].sum(axis=1) for k in range(12)], axis=1).mean(axis=0)
    return c / (np.linalg.norm(c) + 1e-9)


def lufs(x: np.ndarray, sr: int) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "m.wav"
        write_wav(p, np.tile(x, 2), sr, 24)  # two passes: the meter's gating settles over the loop
        err = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f",
                              "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    summ = err[err.rfind("Summary:"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+|-inf)", summ).group(1).replace("-inf", "-120"))
    return {"I": g("I"), "LRA": g("LRA"), "TP": g("Peak")}


def resample_loop(x: np.ndarray, sr: int, out_sr: int) -> np.ndarray:
    n_out = int(round(x.shape[1] * out_sr / sr))
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.wav", Path(d) / "out.wav"
        write_wav(src, np.tile(x, 3), sr, 24)
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(src), "-af", "aresample=resampler=soxr:precision=28",
                        "-ar", str(out_sr), "-c:a", "pcm_f32le", str(dst)], check=True)
        y, _ = read_wav(dst)
    return y[:, n_out: 2 * n_out]


def seam_metrics(x: np.ndarray, sr: int) -> dict:
    mono = x.mean(0)
    n = int(0.1 * sr)
    tail, head = mono[-n:], mono[:n]
    rms = lambda v: 20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-9)

    def spec(v):
        s = np.abs(np.fft.rfft(v * np.hanning(len(v))))
        return s / (np.linalg.norm(s) + 1e-9)

    m = int(0.2 * sr)
    return {"rms_jump_db": round(abs(rms(tail) - rms(head)), 2),
            "spectral_cos": round(float(np.dot(spec(mono[-m:]), spec(mono[:m]))), 3),
            "sample_jump": round(float(np.max(np.abs(x[:, 0] - x[:, -1]))), 4)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stems", required=True)
    ap.add_argument("--bars", type=int, default=32)
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--fade-beats", type=float, default=1.0)
    ap.add_argument("--target-lufs", type=float, default=-23.0)
    ap.add_argument("--out-sr", type=int, default=48000)
    args = ap.parse_args(argv)

    stems = {}
    for name in ("drums", "bass", "other", "vocals"):
        stems[name], sr = read_wav(Path(args.stems) / f"{name}.wav")
    full = sum(stems.values())
    mono = full.mean(0)
    s0 = first_onset(mono, sr)
    nominal = args.bars * 4 * 60.0 / args.bpm
    period, comb = beat_period(mono, sr, s0, args.bpm, min(nominal, (len(mono) - s0) / sr - 1))
    L = int(round(period * args.bars * 4))
    beat = int(round(period))
    bar = 4 * beat
    cont_sim = float(np.dot(chroma_blocks(mono, sr, s0, 2 * bar / sr), chroma_blocks(mono, sr, s0 + L, 2 * bar / sr)))
    mode = "wrap" if cont_sim >= 0.85 else "cut"
    if mode == "wrap":  # the form repeats: fold one beat of the continuation into the opening
        T = int(args.fade_beats * beat)
        w = np.sin(np.linspace(0, np.pi / 2, T)) ** 2

        def cut(x):
            y = x[:, s0: s0 + L].copy()
            y[:, :T] = x[:, s0 + L: s0 + L + T] * (1 - w) + y[:, :T] * w
            return y
    else:  # the cover goes elsewhere after bar 32: cut on the downbeat, keep only the decaying ring of bar 32
        T = int(0.03 * sr)
        tail_n = beat
        decay = np.exp(-np.arange(tail_n) / (0.12 * sr))
        w = np.sin(np.linspace(0, np.pi / 2, T)) ** 2

        def cut(x):
            y = x[:, s0: s0 + L].copy()
            pre = x[:, s0 - T: s0] if s0 >= T else np.zeros((x.shape[0], T))
            y[:, :T] = pre * (1 - w) + y[:, :T] * w  # no click at the opening downbeat
            ring = x[:, s0 + L: s0 + L + tail_n] * decay * 0.5
            y[:, :tail_n] += ring
            return y

    layers = {"L1": cut(stems["other"] + stems["vocals"]), "L2": cut(stems["drums"] + stems["bass"])}
    layers["full"] = layers["L1"] + layers["L2"]
    loud = lufs(layers["full"], sr)
    gain = 10 ** ((args.target_lufs - loud["I"]) / 20)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"id": args.id, "src_stems": str(args.stems), "sr_in": sr, "start_s": round(s0 / sr, 4),
              "loop_s": round(L / sr, 4), "bpm_true": round(60.0 * sr / period, 3), "bars": args.bars,
              "comb": round(comb, 3), "cont_sim": round(cont_sim, 3), "mode": mode, "fade_ms": round(T / sr * 1000),
              "gain_db": round(20 * np.log10(gain), 2),
              "layers": {}}
    for name, y in layers.items():
        z = resample_loop(y * gain, sr, args.out_sr)
        write_wav(out / f"{args.id}-{name}.wav", z, args.out_sr, 24)
        write_wav(out / f"{args.id}-{name}_16.wav", z, args.out_sr, 16)
        report["layers"][name] = {"samples": z.shape[1], **lufs(z, args.out_sr), **seam_metrics(z, args.out_sr)}
    (out / f"{args.id}-loop.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
