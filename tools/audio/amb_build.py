"""Map ambience: beds (seamless stereo loops) and spot one-shots (cards AUC-A01, AUC-A02; 02 §4.8).

    python tools/audio/amb_build.py --kenney C:/tmp/audio-src/kenney --out C:/tmp/audio-src/final/amb [--only ID ...]

Beds are synthesised (sea, surf, waterfall, fire, night insects, wind in leaves): rights-clean and loopable by
construction - each bed is rendered longer than its loop and the overhang is folded into the start (wrapped tail).
Spots mix synthesis with CC0 Kenney foley (creaks, cloth, metal). Targets (02 §5.3): beds -38 LUFS-I, spots momentary
max -30 LUFS. Output 48 kHz / 16 bit: beds stereo, spots mono; amb.json lists files and loudness.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).parent))
import sfx_build as sb  # noqa: E402
from loop import lufs, write_wav  # noqa: E402

SR = sb.SR


def noise(n: int, seed: str) -> np.ndarray:
    return sb.rng_for(seed).standard_normal(n)


def pink(n: int, seed: str) -> np.ndarray:
    w = np.fft.rfft(noise(n, seed))
    f = np.maximum(np.fft.rfftfreq(n, 1 / SR), 20)
    return np.fft.irfft(w / np.sqrt(f), n)


def slow_lfo(n: int, period_s: float, seed: str, depth: float = 1.0) -> np.ndarray:
    """Smooth random modulation 0..1 with a typical period (cubic interpolation of random points)."""
    pts = max(4, int(n / SR / period_s) + 3)
    r = sb.rng_for(seed).uniform(0, 1, pts)
    x = np.linspace(0, pts - 3, n)
    i = np.floor(x).astype(int)
    f = x - i
    y = r[i] * (1 - f) ** 2 * 0.5 + r[i + 1] * (0.5 + f - f * f) + r[i + 2] * f * f * 0.5
    return 1 - depth + depth * y


def wrap_loop(x: np.ndarray, loop_n: int, fade_n: int) -> np.ndarray:
    """x has loop_n + fade_n samples (per channel); fold the overhang into the start."""
    w = np.sin(np.linspace(0, np.pi / 2, fade_n)) ** 2
    y = x[..., :loop_n].copy()
    y[..., :fade_n] = x[..., loop_n: loop_n + fade_n] * (1 - w) + y[..., :fade_n] * w
    return y


def stereo(l: np.ndarray, r: np.ndarray) -> np.ndarray:
    return np.stack([l, r])


# ------------------------------------------------------------------ beds
def bed_sea(seconds: float) -> np.ndarray:
    n = int((seconds + 4) * SR)
    chans = []
    for ch in ("L", "R"):
        base = pink(n, f"sea{ch}")
        swell = np.zeros(n)
        r = sb.rng_for(f"waves{ch}")
        t0 = 0.0
        while t0 < seconds + 4:  # waves every 5-9 s: slow rise, crash, long wash
            a, dur = int(t0 * SR), r.uniform(4.5, 7.5)
            tt = np.arange(int(dur * SR)) / SR
            env = (np.minimum(1, tt / (dur * 0.35)) ** 2) * np.exp(-np.maximum(0, tt - dur * 0.35) * 1.1)
            swell[a: a + len(env)] += env[: max(0, n - a)] * r.uniform(0.6, 1.0)
            t0 += r.uniform(5.0, 9.0)
        cutoff = 300 + 2500 * np.clip(swell, 0, 1)
        # time-varying low-pass: filter in blocks with the block's cutoff
        out = np.zeros(n)
        blk = 2048
        zi = None
        for i in range(0, n, blk):
            sos = signal.butter(2, float(np.mean(cutoff[i: i + blk])), "lowpass", fs=SR, output="sos")
            if zi is None:
                zi = signal.sosfilt_zi(sos) * 0
            out[i: i + blk], zi = signal.sosfilt(sos, base[i: i + blk], zi=zi)
        chans.append(out * (0.25 + swell))
    x = stereo(*chans)
    return wrap_loop(x, int(seconds * SR), int(4 * SR))


def bed_waterfall(seconds: float) -> np.ndarray:
    n = int((seconds + 2) * SR)
    chans = []
    for ch in ("L", "R"):
        x = sb.filt(pink(n, f"falls{ch}"), "bandpass", [180, 7000]) * slow_lfo(n, 1.5, f"fl{ch}", 0.25)
        x += sb.filt(noise(n, f"fallsh{ch}"), "highpass", 2500) * 0.08 * slow_lfo(n, 0.4, f"fh{ch}", 0.5)
        chans.append(x)
    return wrap_loop(stereo(*chans), int(seconds * SR), int(2 * SR))


def bed_fire(seconds: float, size: float, seed: str) -> np.ndarray:
    n = int((seconds + 2) * SR)
    chans = []
    for ch in ("L", "R"):
        roar = sb.filt(pink(n, f"{seed}roar{ch}"), "lowpass", 350 * size + 150) * slow_lfo(n, 0.7, f"{seed}r{ch}", 0.5)
        cr = np.zeros(n)
        r = sb.rng_for(f"{seed}cr{ch}")
        for _ in range(int((seconds + 2) * 9 * size)):
            a = r.integers(0, n - 2000)
            m = int(r.uniform(80, 900))
            c = r.standard_normal(m) * np.exp(-np.arange(m) / (m / 5)) * r.uniform(0.2, 1.0) ** 2
            cr[a: a + m] += sb.filt(c, "highpass", r.uniform(1200, 4000)) if m > 30 else c
        chans.append(roar * 0.6 + cr * 0.9)
    return wrap_loop(stereo(*chans), int(seconds * SR), int(2 * SR))


def bed_night(seconds: float) -> np.ndarray:
    n = int((seconds + 3) * SR)
    t = np.arange(n) / SR
    chans = []
    for ch in ("L", "R"):
        leaves = sb.filt(pink(n, f"leaves{ch}"), "bandpass", [600, 6000]) * slow_lfo(n, 6.0, f"lv{ch}", 0.7) * 0.5
        cliff = sb.filt(pink(n, f"cliff{ch}"), "lowpass", 220) * slow_lfo(n, 9.0, f"cl{ch}", 0.4) * 0.8
        crick = np.zeros(n)
        r = sb.rng_for(f"crick{ch}")
        for v in range(3):  # three distant crickets, each its own pitch and rhythm
            f = r.uniform(3900, 4800)
            rate = r.uniform(2.2, 3.2)
            gate = (np.sin(2 * np.pi * rate * t + r.uniform(0, 6)) > 0.55).astype(float)
            chirp = np.sin(2 * np.pi * f * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 45 * t)) * gate
            crick += chirp * slow_lfo(n, 12.0, f"cg{ch}{v}", 0.8) * 0.05
        chans.append(leaves + cliff + sb.filt(crick, "bandpass", [3000, 6000]))
    return wrap_loop(stereo(*chans), int(seconds * SR), int(3 * SR))


def bed_banner(cycles: int = 10) -> np.ndarray:
    period = 1 / 0.35
    seconds = cycles * period
    n = int((seconds + 1) * SR)
    t = np.arange(n) / SR
    flap_env = np.clip(np.sin(2 * np.pi * 0.35 * t), 0, 1) ** 1.5
    chans = []
    for ch in ("L", "R"):
        x = np.zeros(n)
        r = sb.rng_for(f"flag{ch}")
        tt = 0.0
        while tt < seconds + 1:
            a = int(tt * SR)
            c = sb.k(f"cloth{r.integers(1, 5)}")
            c = sb.pitch(sb.trim(c), r.uniform(-3, 1))[: int(0.18 * SR)]
            g = flap_env[min(a, n - 1)]
            x[a: a + len(c)] += c[: max(0, n - a)] * g
            tt += r.uniform(0.07, 0.16) if g > 0.3 else 0.3
        x += sb.filt(noise(n, f"flagw{ch}"), "bandpass", [300, 2500]) * flap_env * 0.05
        chans.append(x)
    return wrap_loop(stereo(*chans), int(seconds * SR), int(1 * SR))


# ------------------------------------------------------------------ spots
def gull(seed: str) -> np.ndarray:
    r = sb.rng_for(seed)
    calls = []
    for j in range(int(r.integers(2, 4))):
        dur = r.uniform(0.25, 0.45)
        tt = np.arange(int(dur * SR)) / SR
        f = r.uniform(1100, 1400) * (1 - 0.35 * (tt / dur) ** 0.7) * (1 + 0.02 * np.sin(2 * np.pi * 28 * tt))
        ph = 2 * np.pi * np.cumsum(f) / SR
        saw = sum(np.sin(h * ph) / h for h in range(1, 9))
        x = sb.filt(saw, "bandpass", [900, 3500]) * np.sin(np.pi * tt / dur) ** 0.7
        calls.append((x, -j * 2.0, j * r.uniform(0.35, 0.55)))
    return sb.reverb(sb.mix(*calls), 1.0, 0.35, seed)


def owl(seed: str) -> np.ndarray:
    r = sb.rng_for(seed)
    hoots = []
    for j in range(2):
        dur = 0.35 if j == 0 else 0.6
        tt = np.arange(int(dur * SR)) / SR
        f = r.uniform(360, 420) * (1 - 0.06 * tt / dur)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / dur) ** 1.5
        x = sb.filt(x + 0.05 * noise(len(x), seed + str(j)), "lowpass", 1500)
        hoots.append((x, 0, j * 0.55))
    return sb.reverb(sb.mix(*hoots), 1.5, 0.45, seed)


def gust(seed: str) -> np.ndarray:
    r = sb.rng_for(seed)
    dur = r.uniform(2.0, 3.6)
    n = int(dur * SR)
    tt = np.arange(n) / SR
    env = np.sin(np.pi * tt / dur) ** 2
    body = sb.filt(pink(n, seed), "bandpass", [250, 1800]) * env
    rustle = sb.filt(noise(n, seed + "r"), "bandpass", [2500, 9000]) * env ** 1.5 * slow_lfo(n, 0.15, seed, 0.8)
    return body * 0.7 + rustle * 0.6


def petals(seed: str) -> np.ndarray:
    dur = sb.rng_for(seed).uniform(1.5, 2.8)
    g = sb.grains(dur, 70, seed)
    return sb.filt(g, "bandpass", [3000, 10000]) * np.sin(np.pi * np.arange(len(g)) / len(g)) ** 0.8


def lantern(seed: str) -> np.ndarray:
    r = sb.rng_for(seed)
    x = np.zeros(int(0.8 * SR))
    for _ in range(int(r.integers(3, 8))):
        a = int(r.uniform(0, 0.7) * SR)
        m = int(r.uniform(60, 500))
        c = r.standard_normal(m) * np.exp(-np.arange(m) / (m / 5))
        x[a: a + m] += c * r.uniform(0.3, 1.0)
    return sb.filt(x, "highpass", 1500)


def creak(i: int, semis: float) -> np.ndarray:
    return sb.pitch(sb.trim(sb.k(f"creak{i}")), semis)


def chain(seed: str) -> np.ndarray:
    r = sb.rng_for(seed)
    parts = [(sb.pitch(sb.trim(sb.k(n)), r.uniform(-2, 3)), r.uniform(-6, 0), j * r.uniform(0.06, 0.14))
             for j, n in enumerate(("metalLatch", "metalClick", "handleCoins", "metalClick"))]
    return sb.mix(*parts)


BEDS = {
    "AMB-MARMOREAL-BED": lambda: bed_night(96.0),
    "AMB-SARPEDON-BED": lambda: bed_sea(96.0),
    "AMB-SARPEDON-FALLS": lambda: bed_waterfall(45.0),
    "AMB-SARPEDON-FIRE-FORT": lambda: bed_fire(30.0, 1.0, "fort"),
    "AMB-SARPEDON-FIRE-BRAZIER": lambda: bed_fire(30.0, 0.5, "brazier"),
    "AMB-SARPEDON-BANNER": lambda: bed_banner(10),
}
SPOTS = {
    "AMB-MARMOREAL-GUST": lambda: [gust(f"gust{i}") for i in range(4)],
    "AMB-MARMOREAL-PETALS": lambda: [petals(f"pet{i}") for i in range(3)],
    "AMB-MARMOREAL-LANTERN": lambda: [lantern(f"lan{i}") for i in range(4)],
    "AMB-MARMOREAL-BIRD": lambda: [owl(f"owl{i}") for i in range(3)],
    "AMB-SARPEDON-RIGGING": lambda: [creak(1, 0), creak(2, -2), creak(3, 0), creak(1, -4)],
    "AMB-SARPEDON-GULLS": lambda: [gull(f"gull{i}") for i in range(3)],
    "AMB-SARPEDON-CHAIN": lambda: [chain(f"chain{i}") for i in range(2)],
}
BED_TARGET = {"AMB-SARPEDON-FIRE-BRAZIER": -42.0, "AMB-SARPEDON-BANNER": -42.0, "AMB-SARPEDON-FIRE-FORT": -40.0,
              "AMB-SARPEDON-FALLS": -40.0}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kenney", default=str(sb.KENNEY))
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args(argv)
    sb.KENNEY = Path(args.kenney)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for uid, fn in BEDS.items():
        if args.only and uid not in args.only:
            continue
        x = fn()
        target = BED_TARGET.get(uid, -38.0)
        loud = lufs(x, SR)
        x = x * 10 ** ((target - loud["I"]) / 20)
        write_wav(out / f"{uid}.wav", x, SR, 16)
        rep = {"id": uid, "kind": "bed", "seconds": round(x.shape[1] / SR, 3), "target_I": target, **lufs(x, SR)}
        report.append(rep)
        print(json.dumps(rep))
    for uid, fn in SPOTS.items():
        if args.only and uid not in args.only:
            continue
        files = []
        for i, v in enumerate(fn(), start=1):
            v = sb.fade(sb.trim(np.asarray(v, float), 60), 0.005, 0.05)
            v = v / (np.max(np.abs(v)) + 1e-9) * 0.5
            v = sb.limit(v * 10 ** ((-30.0 - sb.momentary_max(v)) / 20))
            name = f"{uid}_{i:02d}.wav"
            sb.write_wav16(out / name, v)
            files.append({"file": name, "seconds": round(len(v) / SR, 2), "m_max": round(sb.momentary_max(v), 1)})
        rep = {"id": uid, "kind": "spot", "target_m_max": -30.0, "variants": files}
        report.append(rep)
        print(json.dumps(rep))
    (out / "amb.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
