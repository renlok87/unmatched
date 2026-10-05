"""Pick and finish VO takes (cards AUC-V05..V08, 02 §3, 04 §0): one WAV per script line.

    python tools/audio/vo_process.py --takes C:/tmp/audio-src/vo/takes --out C:/tmp/audio-src/final/vo
           [--harpy C:/tmp/audio-src/vo/harpy] [--fx C:/tmp/audio-src/vo/fx]

For every line of 04-vo-script.md the takes (VO_<ID>_t<k>.mp3) are scored: speech within its limit (2 s; 3 s for
select / match start / matchup / low HP / ally down / victory / defeat), no inner pause over 0.6 s, no clipping;
the best one is trimmed (-45 dB), inner pauses longer than 350 ms are shortened to 350 ms, a high-pass at 80 Hz and a
gentle compressor are applied, a line still over its limit is sped up (pitch kept,
at most x1.2), and it is normalised to -19 LUFS-I with true peak <= -3 dBTP. Harpy cries get three
pitch versions (-2, 0, +2 semitones: harpy 1, 2, 3). FX voice layers are finished the same way at -24 LUFS.
Output: <out>/<ID>.wav (48 kHz / 16 bit mono) + vo.json (chosen take, scores, loudness).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import sfx_build as sb  # noqa: E402
from loop import lufs  # noqa: E402
from vo_batch import lines as script_lines  # noqa: E402

SR = sb.SR
LONG_EVENTS = ("SELECT", "MATCH-START", "MATCHUP", "LOW-HP", "ALLY-DOWN", "ALLY-LOW", "VICTORY", "DEFEAT")


def decode(path: Path) -> np.ndarray:
    import subprocess
    raw = subprocess.run([sb.ffmpeg(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le",
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def envelope_db(x: np.ndarray, win: int) -> np.ndarray:
    n = len(x) // win
    return 20 * np.log10(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-9)


def shorten_pauses(x: np.ndarray, max_pause: float = 0.35, top_db: float = 45) -> np.ndarray:
    win = SR // 100
    env = envelope_db(x, win)
    quiet = env < env.max() - top_db
    out, i, n = [], 0, len(env)
    keep = int(max_pause * 100)
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            run = j - i
            if 0 < i and j < n and run > keep:  # inner pause: keep its start and end, drop the middle
                half = keep // 2
                out.append(x[i * win:(i + half) * win])
                out.append(x[(j - half) * win: j * win])
            else:
                out.append(x[i * win: j * win])
            i = j
        else:
            out.append(x[i * win:(i + 1) * win])
            i += 1
    out.append(x[n * win:])
    return np.concatenate(out)


def compress(x: np.ndarray, thresh_db: float = -18, ratio: float = 2.5) -> np.ndarray:
    env = np.abs(x)
    a = np.exp(-1 / (0.005 * SR))
    r = np.exp(-1 / (0.12 * SR))
    lvl = np.empty_like(env)
    cur = 0.0
    for i, e in enumerate(env):
        cur = e + (cur - e) * (a if e > cur else r)
        lvl[i] = cur
    db = 20 * np.log10(lvl / (np.max(lvl) + 1e-12) + 1e-9)
    gr = np.where(db > thresh_db, (db - thresh_db) * (1 - 1 / ratio), 0.0)
    return x * 10 ** (-gr / 20)


def tempo(x: np.ndarray, factor: float) -> np.ndarray:
    """Pitch-preserving speed-up (ffmpeg atempo), for lines over their length limit."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "i.wav", Path(d) / "o.raw"
        sb.write_wav16(src, x / (np.max(np.abs(x)) + 1e-9) * 0.9)
        subprocess.run([sb.ffmpeg(), "-v", "error", "-y", "-i", str(src), "-af", f"atempo={factor:.3f}", "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), str(dst)], check=True)
        return np.frombuffer(dst.read_bytes(), np.float32).astype(np.float64)


def finish(x: np.ndarray, target: float, limit: float = 0.0) -> tuple[np.ndarray, dict]:
    x = sb.trim(x, 45)
    x = shorten_pauses(x)
    if limit and len(x) / SR > limit:
        x = tempo(x, min(1.2, len(x) / SR / limit))
    x = sb.filt(x, "highpass", 80)
    x = compress(x)
    x = sb.fade(x, 0.005, 0.03)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.5
    st = np.stack([x, x])
    loud = lufs(st, SR)
    x = x * 10 ** ((target - loud["I"]) / 20)
    peak = np.max(np.abs(x))
    if peak > 0.708:  # -3 dBFS sample peak as the true-peak guard
        x = x * 0.708 / peak
    return x, lufs(np.stack([x, x]), SR)


def score(x: np.ndarray, limit: float) -> tuple[float, dict]:
    win = SR // 100
    env = envelope_db(x, win)
    on = env > env.max() - 40
    idx = np.where(on)[0]
    span = (idx[-1] - idx[0] + 1) / 100 if len(idx) else 0.0
    gaps, run = [0], 0
    for v in on[idx[0]: idx[-1] + 1] if len(idx) else []:
        run = 0 if v else run + 1
        gaps.append(run)
    pause = max(gaps) / 100
    clipped = float(np.max(np.abs(x))) > 0.999
    s = 0.0
    s -= max(0.0, span - limit) * 4
    s -= max(0.0, pause - 0.6) * 2
    s -= 5 if clipped else 0
    s -= 10 if span < 0.15 else 0
    return s, {"speech_s": round(span, 2), "max_pause_s": round(pause, 2), "clipped": clipped}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--takes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--harpy")
    ap.add_argument("--fx")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report, missing = [], []
    for ln in script_lines():
        stem = "VO_" + ln["id"].replace("-", "_")
        takes = sorted(Path(args.takes).glob(f"{ln['fighter']}/{stem}_t*/{stem}_t*.mp3"))
        if not takes:
            missing.append(ln["id"])
            continue
        limit = 3.0 if any(e in ln["id"] for e in LONG_EVENTS) else 2.0
        scored = []
        for tk in takes:
            x = decode(tk)
            s, info = score(x, limit)
            scored.append((s, tk, x, info))
        s, tk, x, info = max(scored, key=lambda t: t[0])
        y, loud = finish(x, -19.0, limit)
        sb.write_wav16(out / f"{ln['id']}.wav", y)
        report.append({"id": ln["id"], "take": tk.name, "score": round(s, 2), **info, "seconds": round(len(y) / SR, 2),
                       "I": loud["I"], "TP": loud["TP"], "takes": len(takes)})
    if args.harpy:
        for f in sorted(Path(args.harpy).glob("HARPY_*/HARPY_*.mp3")):
            uid = f.stem.replace("_", "-")
            base = decode(f)
            for k, semis in enumerate((-2, 0, 2), start=1):
                y, loud = finish(sb.pitch(base, semis), -19.0)
                sb.write_wav16(out / f"{uid}-H{k}.wav", y)
                report.append({"id": f"{uid}-H{k}", "take": f.name, "pitch": semis, "seconds": round(len(y) / SR, 2),
                               "I": loud["I"]})
    if args.fx:
        for f in sorted(Path(args.fx).glob("FX_*/FX_*.mp3")):
            uid = re.sub(r"_01$", "", f.stem).replace("_", "-") + "-VOICE"
            y, loud = finish(decode(f), -24.0)
            sb.write_wav16(out / f"{uid}.wav", y)
            report.append({"id": uid, "take": f.name, "seconds": round(len(y) / SR, 2), "I": loud["I"]})
    (out / "vo.json").write_text(json.dumps({"lines": report, "missing": missing}, indent=1), encoding="utf-8")
    print(json.dumps({"finished": len(report), "missing": missing}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
