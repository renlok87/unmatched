"""SFX of the sound registry built from CC0 Kenney packs and our own synthesis (cards AUC-X02..X08, 02 §4).

    python tools/audio/sfx_build.py --kenney C:/tmp/audio-src/kenney --out C:/tmp/audio-src/final/sfx [--only ID ...]

Every registry unit with a recipe below gets its variations as <ID>_NN.wav (48 kHz / 16 bit, mono) and one line in
sfx.json (recipe, sources, momentary-max loudness). Recipes layer Kenney files (pitch, filters, offsets, gains) and
deterministic synthesis (bells, ticks, whooshes, shimmer, plucks, grains, thuds); each variant is trimmed, faded and
normalised to the momentary-max target of its group (02 §5.3). Random parts use a seed from the unit id, so a rebuild
gives the same files. Sources: Kenney Interface Sounds, Impact Sounds, RPG Audio (CC0 1.0).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).parent))
from analyze import ffmpeg  # noqa: E402

SR = 48000
KENNEY: Path = Path("C:/tmp/audio-src/kenney")
_cache: dict[str, np.ndarray] = {}


# ------------------------------------------------------------------ io
def k(name: str) -> np.ndarray:
    """A Kenney file by stem, searched in the three SFX packs ('click_001', 'impactPunch_heavy_000', 'bookFlip1')."""
    if name not in _cache:
        hits = list(KENNEY.glob(f"kenney_*/Audio/{name}.ogg"))
        if not hits:
            raise FileNotFoundError(name)
        raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(hits[0]), "-ac", "1", "-ar", str(SR), "-f", "f32le",
                              "-"], capture_output=True, check=True).stdout
        _cache[name] = np.frombuffer(raw, np.float32).astype(np.float64)
    return _cache[name].copy()


def write_wav16(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).round().astype("<i2").tobytes()
    head = (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, SR, SR * 2,
                                                                                    2, 16) +
            b"data" + struct.pack("<I", len(pcm)))
    path.write_bytes(head + pcm)


def momentary_max(x: np.ndarray) -> float:
    """Max momentary loudness (400 ms, EBU R128) via ffmpeg, padded so short sounds get a full window."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "m.wav"
        write_wav16(p, np.concatenate([x, np.zeros(int(0.5 * SR))]))
        err = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-v", "verbose", "-i", str(p), "-af",
                              "ebur128=framelog=verbose",
                              "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stderr
    vals = [float(v) for v in re.findall(r"M:\s*(-?[\d.]+)", err)]
    return max(vals) if vals else -120.0


# ------------------------------------------------------------------ dsp
def rng_for(key: str) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(key.encode()))


def pitch(x: np.ndarray, semis: float) -> np.ndarray:
    """Speed change by resampling (pitch and length together, like tape)."""
    if not semis:
        return x
    ratio = 2 ** (semis / 12)
    n = int(len(x) / ratio)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def filt(x: np.ndarray, kind: str, f, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, f, btype=kind, fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def trim(x: np.ndarray, top_db: float = 50) -> np.ndarray:
    if not len(x):
        return x
    env = np.abs(x)
    thr = env.max() * 10 ** (-top_db / 20)
    idx = np.where(env > thr)[0]
    return x[idx[0]: idx[-1] + 1] if len(idx) else x


def fade(x: np.ndarray, fin: float = 0.003, fout: float = 0.02) -> np.ndarray:
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b and b < len(x):
        x[-b:] *= np.linspace(1, 0, b)
    return x


def cap(x: np.ndarray, seconds: float, fout: float = 0.05) -> np.ndarray:
    return fade(x[: int(seconds * SR)], 0.0, fout)


def mix(*layers: tuple) -> np.ndarray:
    """layers: (signal, gain_db, offset_s)."""
    n = max(int(o * SR) + len(s) for s, g, o in layers)
    out = np.zeros(n)
    for s, g, o in layers:
        i = int(o * SR)
        out[i: i + len(s)] += s * 10 ** (g / 20)
    return out


def reverb(x: np.ndarray, seconds: float = 0.8, wet: float = 0.25, seed: str = "rv") -> np.ndarray:
    n = int(seconds * SR)
    ir = rng_for(seed).standard_normal(n) * np.exp(-np.arange(n) / (seconds * SR / 6.9))
    ir = filt(ir, "lowpass", 6000)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    wetsig = np.pad(signal.fftconvolve(x, ir), (0, 1))[: len(x) + n]
    dry = np.concatenate([x, np.zeros(n)])
    return dry * (1 - wet) + wetsig * wet * 3


def t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def note(n: str) -> float:
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    return 440.0 * 2 ** ((names[n[:-1]] + 12 * (int(n[-1]) + 1) - 69) / 12)


# ------------------------------------------------------------------ synthesis
def bell(f: float, dur: float = 0.9, bright: float = 1.0) -> np.ndarray:
    """Small tuned bell: inharmonic partials with their own decays (warm, not a sine beep)."""
    tt = t(dur)
    parts = [(1.0, 1.0, 1.0), (2.0, 0.45, 1.6), (2.76, 0.30 * bright, 2.4), (5.40, 0.12 * bright, 4.0),
             (8.93, 0.05 * bright, 6.0)]
    y = sum(a * np.sin(2 * np.pi * f * r * tt) * np.exp(-tt * d * 4.0 / dur) for r, a, d in parts)
    att = int(0.004 * SR)
    y[:att] *= np.linspace(0, 1, att)
    return y


def tick(center: float = 2500, dur: float = 0.03, seed: str = "tick") -> np.ndarray:
    n = rng_for(seed).standard_normal(int(dur * SR)) * np.exp(-t(dur) * 160)
    return filt(n, "bandpass", [center * 0.6, center * 1.6])


def thud(f0: float = 110, f1: float = 45, dur: float = 0.35, noise: float = 0.2, seed: str = "thud") -> np.ndarray:
    tt = t(dur)
    f = f1 + (f0 - f1) * np.exp(-tt * 25)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)
    nz = filt(rng_for(seed).standard_normal(len(tt)), "lowpass", 900) * np.exp(-tt * 60) * noise
    return body + nz


def whoosh(dur: float = 0.35, f0: float = 600, f1: float = 2400, seed: str = "wh") -> np.ndarray:
    tt = t(dur)
    nz = rng_for(seed).standard_normal(len(tt))
    out = np.zeros_like(nz)
    seg = 512
    for i in range(0, len(nz), seg):
        fc = f0 + (f1 - f0) * (i / len(nz))
        out[i: i + seg] = filt(nz[max(0, i - 2048): i + seg], "bandpass", [fc * 0.7, fc * 1.4])[-len(nz[i: i + seg]):]
    env = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 2
    return out * env


def shimmer(freqs: list[float], dur: float = 0.6, trem: float = 7.0) -> np.ndarray:
    tt = t(dur)
    y = sum(np.sin(2 * np.pi * f * tt + i) / (i + 1) for i, f in enumerate(freqs))
    env = (1 - np.exp(-tt * 30)) * np.exp(-tt * 3.0 / dur) * (0.75 + 0.25 * np.sin(2 * np.pi * trem * tt))
    return y * env


def pluck(f: float, dur: float = 0.8, damp: float = 0.996, seed: str = "pl") -> np.ndarray:
    """Karplus-Strong string (harp / bowstring)."""
    n = int(dur * SR)
    p = max(2, int(SR / f))
    buf = rng_for(seed).uniform(-1, 1, p)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = damp * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return filt(out, "lowpass", min(8000, f * 12))


def grains(dur: float = 0.45, density: float = 160, seed: str = "gr") -> np.ndarray:
    r = rng_for(seed)
    out = np.zeros(int(dur * SR))
    for _ in range(int(density * dur)):
        pos = int(r.uniform(0, 1) ** 1.6 * (len(out) - 600))
        g = r.standard_normal(400) * np.hanning(400) * r.uniform(0.2, 1.0)
        out[pos: pos + 400] += g
    return filt(out, "highpass", 1500) * np.exp(-t(dur) * 3.5)


def glide(f0: float, f1: float, dur: float, vib: float = 0.0) -> np.ndarray:
    tt = t(dur)
    f = f0 * (f1 / f0) ** (tt / dur) * (1 + vib * np.sin(2 * np.pi * 5.5 * tt))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / dur) ** 0.5


def fizzle(dur: float = 0.4, seed: str = "fz") -> np.ndarray:
    return whoosh(dur, 3000, 500, seed) * np.exp(-t(dur) * 4)


def wind(dur: float = 1.5, seed: str = "wd") -> np.ndarray:
    tt = t(dur)
    base = whoosh(dur, 300, 900, seed) + 0.6 * whoosh(dur, 900, 400, seed + "b")
    return base * (0.6 + 0.4 * np.sin(2 * np.pi * 1.3 * tt) ** 2)


def rumble(dur: float = 1.0, seed: str = "rb") -> np.ndarray:
    tt = t(dur)
    n = filt(rng_for(seed).standard_normal(len(tt)), "lowpass", 160, 4)
    return n * (1 - np.exp(-tt * 12)) * np.exp(-tt * 2.5)


def chord_pad(freqs: list[float], dur: float = 1.2) -> np.ndarray:
    tt = t(dur)
    y = sum(sum(np.sin(2 * np.pi * f * h * tt * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * tt))) / h ** 1.4
                for h in range(1, 6)) for f in freqs)
    y = filt(y, "bandpass", [300, 3200])  # vowel-ish "ah" body
    env = np.minimum(1, tt / 0.25) * np.exp(-np.maximum(0, tt - dur * 0.5) * 4)
    return y * env


# ------------------------------------------------------------------ recipes
# target: momentary-max LUFS (02 §5.3). Each recipe returns a list of variants (np arrays).
GROUP_TARGET = {"ui": -18.0, "ui_loud": -16.0, "ui_soft": -24.0, "cards_quiet": -30.0, "cards": -20.0,
                "board": -24.0, "combat_hit": -12.0, "combat": -16.0, "death": -12.0, "fx": -16.0}

R: dict[str, tuple[str, callable]] = {}


def recipe(uid: str, group: str):
    def deco(fn):
        R[uid] = (group, fn)
        return fn
    return deco


# --- UI
@recipe("UI-SELECT", "ui")
def _():
    return [mix((trim(k(f"select_00{i}")), 0, 0), (filt(trim(k(f"impactWood_light_00{i - 1}")), "lowpass", 3500), -8, 0))
            for i in (1, 2, 3)]


@recipe("UI-CONFIRM", "ui")
def _():
    return [mix((trim(k(f"click_00{i}")), 0, 0), (filt(pitch(trim(k(f"impactWood_medium_00{j}")), -2), "lowpass", 2500),
                                                  -5, 0)) for i, j in ((4, 0), (5, 1))]


@recipe("UI-REJECT", "ui")
def _():
    return [mix((thud(170 + 15 * v, 110, 0.22, 0.1, f"rej{v}"), 0, 0),
                (filt(pitch(trim(k(f"impactWood_heavy_00{v}")), -5), "lowpass", 1800), -6, 0)) for v in (0, 1)]


@recipe("UI-BTN-HOVER", "ui_soft")
def _():
    return [filt(trim(k(f"tick_00{i}")), "highpass", 1500) for i in (1, 2)]


@recipe("UI-BTN-CLICK", "ui")
def _():
    return [trim(k(f"click_00{i}")) for i in (1, 2, 3)]


@recipe("UI-BTN-BACK", "ui")
def _():
    return [trim(k(f"back_00{i}")) for i in (1, 2)]


@recipe("UI-TOGGLE", "ui")
def _():
    return [trim(k("toggle_001")), trim(k("toggle_002"))]


@recipe("UI-SLIDER-TICK", "ui_soft")
def _():
    return [tick(3000, 0.025, "slider")]


@recipe("UI-PANEL-OPEN", "ui")
def _():
    return [cap(trim(k("bookFlip2")), 0.25)]


@recipe("UI-PANEL-CLOSE", "ui")
def _():
    return [cap(trim(k("bookClose")), 0.2)]


@recipe("UI-TOAST", "ui")
def _():
    return [mix((bell(note("E5"), 0.35), 0, 0), (bell(note("A5"), 0.4), -2, 0.09))]


@recipe("UI-TURN-CHIME", "ui_loud")
def _():
    return [reverb(mix((bell(note("A5"), 1.0), 0, 0), (bell(note("E6"), 1.0, 0.8), -3, 0.12)), 0.9, 0.2, "chime")]


@recipe("UI-TIMER-WARN", "ui")
def _():
    return [reverb(bell(note("A4"), 0.6), 0.6, 0.15, "warn")]


@recipe("UI-TIMER-TICK", "ui_soft")
def _():
    return [mix((tick(1800, 0.04, "tt"), 0, 0), (np.sin(2 * np.pi * 900 * t(0.03)) * np.exp(-t(0.03) * 120), -6, 0))]


@recipe("UI-NET-LOST", "ui_loud")
def _():
    s = lambda f: np.sin(2 * np.pi * f * t(0.18)) * np.sin(np.pi * t(0.18) / 0.18) ** 0.6
    return [mix((s(note("E5")), 0, 0), (s(note("A4")), 0, 0.2))]


@recipe("UI-NET-BACK", "ui_loud")
def _():
    s = lambda f: np.sin(2 * np.pi * f * t(0.16)) * np.sin(np.pi * t(0.16) / 0.16) ** 0.6
    return [mix((s(note("A4")), 0, 0), (s(note("E5")), 0, 0.18), (tick(2500, 0.03, "nb"), -8, 0.4))]


@recipe("UI-LOGIN-OK", "ui")
def _():
    return [mix((bell(note("C5"), 0.4), 0, 0), (bell(note("G5"), 0.5), -1, 0.1))]


@recipe("UI-LOGIN-ERR", "ui")
def _():
    return [mix((filt(bell(note("A4"), 0.35, 0.3), "lowpass", 2500), 0, 0),
                (filt(bell(note("F4"), 0.4, 0.3), "lowpass", 2500), 0, 0.14))]


@recipe("UI-ROOM-CREATE", "ui")
def _():
    return [reverb(mix((bell(note("A4"), 0.5), 0, 0), (bell(note("C#5"), 0.5), -1, 0.08),
                       (bell(note("E5"), 0.6), -1, 0.16)), 0.6, 0.15, "rc")]


@recipe("UI-ROOM-JOIN", "ui")
def _():
    return [mix((bell(note("E5"), 0.35), 0, 0), (bell(note("A5"), 0.45), 0, 0.1))]


@recipe("UI-ROOM-LEAVE", "ui")
def _():
    return [mix((bell(note("A5"), 0.35), 0, 0), (bell(note("E5"), 0.45), 0, 0.1))]


@recipe("UI-ROOM-READY", "ui")
def _():
    w = trim(k("impactWood_light_002"))
    return [mix((w, 0, 0), (w, -3, 0.09))]


@recipe("UI-ROOM-COUNT", "ui_loud")
def _():
    return [bell(note(n), 0.35) for n in ("A4", "C#5", "E5")]


@recipe("UI-ROOM-COUNT-GO", "ui_loud")
def _():
    return [reverb(mix((bell(note("A5"), 0.8), 0, 0), (thud(90, 45, 0.4, 0.1, "go"), -2, 0),
                       (shimmer([note("E6"), note("A6")], 0.6), -12, 0.02)), 0.8, 0.2, "go")]


@recipe("UI-PAUSE-EXIT", "ui")
def _():
    return [reverb(mix((bell(note("A3"), 0.7, 0.5), 0, 0), (thud(80, 40, 0.3, 0.05, "px"), -4, 0)), 0.7, 0.15, "px")]


@recipe("STG-HAND-LIMIT", "ui")
def _():
    scale = ["A5", "G5", "E5", "D5", "C5", "B4", "A4", "E4"]
    out = []
    for v in range(3):
        notes = [(pluck(note(n) * (1 + 0.002 * v), 0.9, 0.997, f"harp{v}{i}"), -i * 0.6, i * 0.1) for i, n in
                 enumerate(scale)]
        out.append(reverb(mix(*notes), 0.9, 0.25, f"hl{v}"))
    return out


# --- cards
@recipe("CRD-DRAW", "cards_quiet")
def _():
    src = [("bookFlip1", 2), ("bookFlip2", 2), ("bookFlip3", 2), ("bookFlip1", 4)]
    return [cap(filt(pitch(trim(k(n)), p), "highpass", 400), 0.3) for n, p in src]


@recipe("CRD-PLAY", "cards")
def _():
    return [cap(trim(k(f"bookPlace{i}")), 0.3) for i in (1, 2, 3)]


@recipe("CRD-FLIP", "cards_quiet")
def _():
    return [mix((cap(filt(pitch(trim(k(n)), 4), "highpass", 500), 0.18), 0, 0)) for n in ("bookFlip2", "bookFlip3",
                                                                                          "bookFlip1")]


@recipe("CRD-DISCARD", "cards")
def _():
    return [mix((cap(pitch(trim(k(f"bookPlace{i}")), -2), 0.25), 0, 0), (cap(trim(k(f"cloth{i}")), 0.2), -10, 0.02))
            for i in (1, 2, 3)]


@recipe("CRD-SHUFFLE", "cards")
def _():
    out = []
    for v in (0, 1):
        r = rng_for(f"shuffle{v}")
        layers = []
        tpos = 0.0
        for j in range(14):
            n = ("bookFlip1", "bookFlip2", "bookFlip3")[j % 3]
            layers.append((cap(filt(pitch(trim(k(n)), 5 + r.uniform(-1, 1)), "highpass", 600), 0.12), -2 - j * 0.3,
                           tpos))
            tpos += 0.075 - j * 0.0025
        out.append(mix(*layers))
    return out


@recipe("CRD-BOOST-PLACE", "cards_quiet")
def _():
    return [cap(filt(trim(k(f"cloth{i}")), "lowpass", 3000), 0.28) for i in (1, 2)]


@recipe("CRD-BOOST-REVEAL", "cards")
def _():
    return [mix((cap(filt(pitch(trim(k("bookFlip2")), 4), "highpass", 500), 0.18), 0, 0),
                (shimmer([note("A6"), note("E7")], 0.35), -10, 0.06), (trim(k("glass_002")), -12, 0.05))]


@recipe("CRD-SCHEME", "cards")
def _():
    return [reverb(mix((cap(trim(k("bookOpen")), 0.5), 0, 0), (thud(120, 60, 0.3, 0.1, f"seal{v}"), -4, 0.18),
                       (shimmer([note("A5"), note("E6"), note("A6")], 0.5), -16, 0.2)), 0.7, 0.15, f"sch{v}")
            for v in (0, 1)]


@recipe("CRD-CANCEL", "cards")
def _():
    return [mix((trim(k("impactPlank_medium_000")), 0, 0), (fizzle(0.45, "cancel"), -6, 0.08))]


@recipe("CRD-VALUE-CHANGE", "cards")
def _():
    return [cap(trim(k("switch_002")), 0.15)]


@recipe("CRD-FORCED-DISCARD", "cards")
def _():
    return [mix((cap(trim(k("bookFlip3"))[::-1], 0.2), 0, 0), (cap(trim(k(f"scratch_00{i}")), 0.25), -4, 0.08))
            for i in (1, 2)]


@recipe("CRD-INSPECT-OPEN", "cards")
def _():
    return [cap(trim(k("bookOpen")), 0.35)]


@recipe("CRD-INSPECT-PAGE", "cards_quiet")
def _():
    return [cap(filt(trim(k(f"bookFlip{i}")), "highpass", 500), 0.12) for i in (1, 2, 3)]


# --- board
@recipe("BRD-STEP", "board")
def _():
    return [mix((cap(filt(trim(k(f"footstep_carpet_00{i}")), "lowpass", 2500), 0.22), 0, 0),
                (filt(pitch(trim(k(f"impactWood_light_00{i}")), -3), "lowpass", 3000), -10, 0)) for i in range(5)]


@recipe("BRD-PLACE", "board")
def _():
    return [mix((whoosh(0.2, 2500, 700, f"pl{v}")[::-1], -4, 0), (trim(k(f"impactWood_light_00{v}")), 0, 0.2))
            for v in (0, 1)]


@recipe("BRD-SETUP", "board")
def _():
    return [filt(trim(k(f"impactWood_medium_00{i}")), "lowpass", 3000) for i in (0, 1, 2)]


@recipe("BRD-CANDIDATES", "ui_soft")
def _():
    return [shimmer([note("E6"), note("A6"), note("C#7")], 0.28)]


@recipe("BRD-PUSH", "board")
def _():
    return [whoosh(0.4, 1800, 500, f"push{v}") for v in (0, 1)]


# --- combat
@recipe("CMB-ATTACK-DECLARE", "combat")
def _():
    return [mix((thud(95, 55, 0.4, 0.25, f"decl{v}"), 0, 0), (cap(trim(k(f"drawKnife{v + 1}")), 0.4), -6, 0.02))
            for v in (0, 1)]


@recipe("CMB-DEFENSE-PLAYED", "combat")
def _():
    return [mix((cap(filt(pitch(trim(k(f"bookPlace{i}")), -3), "lowpass", 2500), 0.3), 0, 0),
                (trim(k(f"impactSoft_medium_00{i}")), -6, 0)) for i in (1, 2)]


@recipe("CMB-NO-DEFENSE", "combat")
def _():
    return [trim(k("impactPlank_medium_001"))]


@recipe("CMB-SLAM", "combat_hit")
def _():
    return [mix((trim(k(f"impactPunch_heavy_00{i}")), 0, 0), (trim(k(f"impactMetal_light_00{i}")), -8, 0.01),
                (thud(70, 35, 0.45, 0.1, f"slam{i}"), -4, 0)) for i in (0, 1)]


@recipe("CMB-EFFECT-LINE", "combat")
def _():
    return [bell(note(n), 0.4) for n in ("A5", "C#6", "E6")]


@recipe("CMB-LUNGE-BLADE", "combat")
def _():
    return [mix((whoosh(0.3, 700, 3200, f"lb{v}"), 0, 0), (cap(trim(k("knifeSlice")), 0.3), -10, 0.12)) for v in (0, 1)]


@recipe("CMB-LUNGE-CLAW", "combat")
def _():
    return [mix((whoosh(0.22, 1200, 3800, f"lc{v}"), 0, 0), (cap(trim(k(f"cloth{v + 3}")), 0.25), -4, 0))
            for v in (0, 1)]


@recipe("CMB-LUNGE-ARROW", "combat")
def _():
    return [mix((cap(filt(trim(k(f"creak{v + 1}")), "highpass", 300), 0.25), -6, 0),
                (pluck(98 + 10 * v, 0.35, 0.985, f"bow{v}"), 0, 0.22), (whoosh(0.15, 2500, 4500, f"ar{v}"), -6, 0.24))
            for v in (0, 1)]


@recipe("CMB-LUNGE-MAGIC", "combat")
def _():
    return [mix((glide(300, 900, 0.3), -6, 0), (shimmer([note("E6"), note("B6")], 0.3, 12), -2, 0)) for _ in (0, 1)]


def _hit(core: list[str], extra: list[tuple[str, float]], semis: float = 0.0) -> list[np.ndarray]:
    return [mix((pitch(trim(k(c)), semis), 0, 0), *[(pitch(trim(k(e.format(i=i))), semis), g, 0) for e, g in extra])
            for i, c in enumerate(core)]


@recipe("CMB-HIT-BLADE", "combat_hit")
def _():
    return [mix((cap(trim(k(s)), 0.4), -2, 0), (trim(k(f"impactPunch_medium_00{i}")), 0, 0),
                (trim(k(f"impactMetal_light_00{i}")), -9, 0)) for i, s in enumerate(("chop", "knifeSlice", "knifeSlice2"))]


@recipe("CMB-HIT-CLAW", "combat_hit")
def _():
    return [mix((pitch(cap(trim(k("knifeSlice2")), 0.3), 3), -2, 0), (trim(k(f"impactSoft_heavy_00{i}")), 0, 0),
                (cap(trim(k(f"cloth{i + 1}")), 0.2), -8, 0)) for i in range(3)]


@recipe("CMB-HIT-ARROW", "combat_hit")
def _():
    return [mix((trim(k(f"impactPlank_medium_00{i + 2}")), 0, 0), (trim(k(f"impactPunch_medium_00{i + 1}")), -3, 0))
            for i in range(3)]


@recipe("CMB-HIT-MAGIC", "combat_hit")
def _():
    return [mix((trim(k(f"impactSoft_heavy_00{i + 1}")), 0, 0), (shimmer([note("A5"), note("E6"), note("A6")], 0.5, 9),
                                                                  -6, 0),
                (whoosh(0.25, 3000, 800, f"hm{i}"), -6, 0)) for i in range(3)]


@recipe("CMB-HIT-BLUNT", "combat_hit")
def _():
    return [mix((trim(k(f"impactPunch_heavy_00{i + 2}")), 0, 0), (thud(80, 40, 0.3, 0.1, f"bl{i}"), -6, 0))
            for i in range(3)]


@recipe("CMB-HIT-BEAST", "combat_hit")
def _():
    return [mix((trim(k(f"impactSoft_heavy_00{i + 2}")), 0, 0), (pitch(cap(trim(k("knifeSlice")), 0.3), -4), -6, 0))
            for i in range(3)]


@recipe("CMB-HIT-HEAVY", "combat_hit")
def _():
    return [mix((pitch(trim(k(f"impactPlate_heavy_00{i}")), -4), 0, 0), (pitch(trim(k(f"impactPunch_heavy_00{i + 3}")), -3),
                                                                          -2, 0),
                (thud(60, 30, 0.7, 0.15, f"hv{i}"), -2, 0)) for i in (0, 1)]


@recipe("CMB-HIT-LETHAL", "combat_hit")
def _():
    return [reverb(mix((thud(55, 28, 1.2, 0.2, "leth"), 0, 0), (rumble(1.3, "leth"), -4, 0)), 1.2, 0.3, "leth")]


@recipe("CMB-HIT-MULTI", "combat_hit")
def _():
    return [mix((trim(k("impactPunch_medium_000")), 0, 0), (trim(k("impactPlank_medium_003")), -2, 0.045),
                (trim(k("impactSoft_heavy_004")), -2, 0.09), (trim(k(f"impactPunch_medium_00{v + 3}")), -4, 0.14))
            for v in (0, 1)]


@recipe("CMB-EXHAUST", "combat_hit")
def _():
    return [mix((glide(220, 50, 0.6), 0, 0), (whoosh(0.4, 1500, 300, "ex")[::-1], -6, 0), (thud(70, 35, 0.4, 0.2, "ex"),
                                                                                             -2, 0.35))]


@recipe("CMB-BLOCK-SHIELD", "combat_hit")
def _():
    return [mix((trim(k(f"impactMetal_heavy_00{i}")), 0, 0), (trim(k(f"impactPlate_medium_00{i}")), -6, 0)) for i in (0, 1)]


@recipe("CMB-BLOCK-ILLUSION", "combat")
def _():
    return [mix((filt(rng_for("ill").standard_normal(int(0.08 * SR)) * np.exp(-t(0.08) * 60), "bandpass", [800, 3000]),
                 0, 0), (shimmer([note("E6"), note("G#6"), note("B6")], 0.45, 14), -4, 0.02))]


@recipe("CMB-HEAL", "combat")
def _():
    return [reverb(mix((bell(note(a), 0.5, 0.6), 0, 0), (bell(note(b), 0.5, 0.6), -1, 0.1), (bell(note(c), 0.6, 0.6), -2, 0.2)),
                   0.7, 0.2, f"heal{a}") for a, b, c in (("A4", "E5", "A5"), ("E4", "B4", "E5"))]


@recipe("CMB-HEAL-GRAIL", "combat")
def _():
    return [reverb(mix((chord_pad([note("A3"), note("C#4"), note("E4"), note("A4")], 1.3), 0, 0),
                       (bell(note("A5"), 1.0), -6, 0.15), (bell(note("E6"), 1.0), -9, 0.3)), 1.2, 0.3, "grail")]


# --- death
@recipe("DTH-ARTHUR", "death")
def _():
    return [reverb(mix((trim(k("impactMetal_heavy_002")), 0, 0), (trim(k("impactSoft_heavy_000")), -2, 0.06),
                       (thud(55, 27, 0.9, 0.1, "da"), -4, 0.05)), 0.9, 0.2, "da")]


@recipe("DTH-MEDUSA", "death")
def _():
    return [reverb(mix((trim(k("impactMining_000")), 0, 0), (pitch(trim(k("impactPlate_heavy_002")), -5), -3, 0.05),
                       (trim(k("impactMining_002")), -4, 0.12), (thud(50, 25, 0.9, 0.1, "dm"), -4, 0.05)), 0.9, 0.2, "dm")]


@recipe("DTH-MERLIN", "death")
def _():
    return [mix((trim(k("impactWood_medium_003")), 0, 0), (trim(k("impactWood_light_003")), -4, 0.12),
                (shimmer([note("E6"), note("C6"), note("A5")], 0.8, 5), -8, 0.05), (glide(1200, 300, 0.7), -14, 0.05))]


@recipe("DTH-HARPY", "death")
def _():
    out = []
    for v in (0, 1):
        r = rng_for(f"dh{v}")
        flaps = [(cap(trim(k(f"cloth{j % 4 + 1}")), 0.15), -4 - j, j * 0.07 + r.uniform(0, 0.02)) for j in range(5)]
        out.append(mix(*flaps, (trim(k(f"impactSoft_medium_00{v + 2}")), 0, 0.35)))
    return out


@recipe("DTH-DISSOLVE", "death")
def _():
    return [grains(0.45, 180, f"dis{v}") for v in (0, 1)]


@recipe("DTH-TEMPLATE", "death")
def _():
    return [mix((trim(k("impactSoft_heavy_000")), 0, 0), (thud(55, 27, 0.8, 0.1, "t1"), -4, 0)),
            mix((trim(k("impactMining_001")), 0, 0), (thud(50, 25, 0.8, 0.1, "t2"), -4, 0)),
            mix((shimmer([note("E6"), note("A5")], 0.8, 5), 0, 0), (glide(1000, 250, 0.7), -6, 0)),
            mix((pitch(trim(k("impactSoft_heavy_001")), -5), 0, 0), (rumble(0.8, "t4"), -4, 0))]


# --- abilities and card effects
@recipe("FX-ARTHUR-BOOST", "fx")
def _():
    return [reverb(mix((shimmer([1760, 2640, 3960, 5280], 0.6, 0), 0, 0), (cap(trim(k(f"drawKnife{v + 2}")), 0.4), -8, 0)),
                   0.6, 0.2, f"ab{v}") for v in (0, 1)]


@recipe("FX-ARTHUR-BOOST-FIZZLE", "fx")
def _():
    return [mix((fizzle(0.45, "abf"), 0, 0), (shimmer([1760, 2640], 0.3, 0), -10, 0))]


@recipe("FX-GAZE-REQUEST", "fx")
def _():
    tt = t(0.6)
    n = rng_for("gr").standard_normal(len(tt))
    hiss = filt(n, "bandpass", [3500, 9000]) * (tt / 0.6) ** 1.5
    return [mix((hiss, 0, 0), (shimmer([note("D#5"), note("A5")], 0.6, 4), -14, 0))]


@recipe("FX-GAZE-BEAM", "fx")
def _():
    return [mix((shimmer([880, 1318.5, 1760 * 1.02], 0.8, 6), 0, 0), (trim(k(f"impactMining_00{v + 3}")), -2, 0.6))
            for v in (0, 1)]


@recipe("FX-GAZE-DECLINE", "fx")
def _():
    tt = t(0.4)
    n = filt(rng_for("gd").standard_normal(len(tt)), "bandpass", [3500, 9000]) * np.exp(-tt * 8)
    return [n]


@recipe("FX-PETRIFY", "fx")
def _():
    tt = t(0.9)
    grind = filt(rng_for("grind").standard_normal(len(tt)), "lowpass", 900) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * tt))
    return [mix((trim(k("impactMining_000")), 0, 0), (trim(k("impactMining_004")), -2, 0.1),
                (pitch(trim(k("impactPlate_heavy_004")), -5), -2, 0), (grind * np.exp(-tt * 3), -8, 0.1))]


@recipe("FX-HISS", "fx")
def _():
    tt = t(0.7)
    n = filt(rng_for("hiss").standard_normal(len(tt)), "highpass", 4000) * np.sin(np.pi * tt / 0.7) ** 0.7
    return [n]


@recipe("FX-CLAWS", "fx")
def _():
    return [mix((pitch(cap(trim(k("knifeSlice2")), 0.25), 4), 0, 0), (pitch(cap(trim(k("knifeSlice")), 0.25), 5), -2, 0.09),
                (cap(trim(k(f"scratch_00{v + 3}")), 0.2), -6, 0.05)) for v in (0, 1)]


@recipe("FX-LADY-LAKE", "fx")
def _():
    r = rng_for("lake")
    drops = [(glide(f, f * 1.8, 0.12), -6 - j * 0.5, j * 0.07) for j, f in enumerate(r.uniform(700, 1600, 12))]
    return [reverb(mix(*drops, (shimmer([note("A5"), note("C#6"), note("E6")], 1.0, 3), -8, 0)), 1.0, 0.3, "lake")]


@recipe("FX-PROPHECY", "fx")
def _():
    return [reverb(mix((shimmer([note("A5"), note("D6"), note("F6")], 1.0, 4), 0, 0),
                       *[(cap(filt(pitch(trim(k(f"bookFlip{j % 3 + 1}")), 3), "highpass", 500), 0.12), -6, 0.15 + j * 0.12)
                         for j in range(4)]), 0.9, 0.25, "proph")]


@recipe("FX-STORM", "fx")
def _():
    return [mix((wind(1.6, "storm"), 0, 0), (rumble(1.2, "thunder"), 2, 0.35))]


@recipe("FX-SPIRITS", "fx")
def _():
    return [reverb(mix((glide(700, 420, 1.0, 0.02), 0, 0), (glide(950, 600, 1.0, 0.03), -4, 0.08),
                       (whoosh(1.0, 400, 1400, "spirit"), -8, 0)), 1.0, 0.35, "spirit")]


@recipe("FX-FRENZY", "fx")
def _():
    r = rng_for("frenzy")
    flaps = [(cap(trim(k(f"cloth{j % 4 + 1}")), 0.15), -2 - r.uniform(0, 4), j * 0.06) for j in range(14)]
    return [mix(*flaps, (whoosh(1.0, 500, 2200, "frw"), -4, 0))]


@recipe("FX-HARPY-RETURN", "fx")
def _():
    return [mix((whoosh(0.5, 2200, 600, "hr"), 0, 0), (cap(trim(k("cloth2")), 0.15), -4, 0.3),
                (cap(trim(k("cloth4")), 0.15), -5, 0.38), (trim(k("impactSoft_medium_004")), -2, 0.55))]


@recipe("FX-NO-TARGET", "fx")
def _():
    return [mix((glide(660, 330, 0.35), -4, 0), (fizzle(0.35, "nt"), -6, 0))]


# ------------------------------------------------------------------ build
def limit(x: np.ndarray, ceiling: float = 0.89, max_gr_db: float = 6.0) -> np.ndarray:
    """Look-ahead peak limiter (2 ms attack, 60 ms release) - lets short hits reach their loudness target with at
    most max_gr_db of gain reduction, peaks kept under the ceiling (~ -1 dBTP)."""
    look = int(0.002 * SR)
    need = np.maximum(1.0, np.abs(x) / ceiling)
    need = np.minimum(need, 10 ** (max_gr_db / 20))
    # hold the max over the look-ahead window, then smooth the release
    held = np.array([need[max(0, i - look): i + look + 1].max() for i in range(len(need))]) if len(need) < 400000         else need
    rel = np.exp(-1.0 / (0.06 * SR))
    g = np.empty_like(held)
    cur = 1.0
    for i, h in enumerate(held):
        cur = h if h > cur else h + (cur - h) * rel
        g[i] = cur
    y = x / g
    peak = np.max(np.abs(y))
    return y * (ceiling / peak) if peak > ceiling else y


def build(uid: str, out: Path) -> dict:
    group, fn = R[uid]
    target = GROUP_TARGET[group]
    variants = fn()
    files = []
    for i, v in enumerate(variants, start=1):
        v = fade(trim(np.asarray(v, dtype=np.float64), 60), 0.002, 0.02)
        v = v / (np.max(np.abs(v)) + 1e-9) * 0.5
        m = momentary_max(v)
        v = limit(v * 10 ** ((target - m) / 20))
        name = f"{uid}_{i:02d}.wav"
        write_wav16(out / name, v)
        files.append({"file": name, "seconds": round(len(v) / SR, 3), "m_max": round(momentary_max(v), 1),
                      "sha256": hashlib.sha256((out / name).read_bytes()).hexdigest()[:16]})
    return {"id": uid, "group": group, "target_m_max": target, "variants": files}


def main(argv: list[str]) -> int:
    global KENNEY
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kenney", default=str(KENNEY))
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args(argv)
    KENNEY = Path(args.kenney)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for uid in R:
        if args.only and uid not in args.only:
            continue
        rep = build(uid, out)
        report.append(rep)
        print(f"{uid}: {len(rep['variants'])} x " + ", ".join(f"{v['seconds']}s/{v['m_max']}" for v in rep["variants"]))
    old = json.loads((out / "sfx.json").read_text(encoding="utf-8")) if (out / "sfx.json").exists() and args.only else []
    keep = [r for r in old if r["id"] not in {x["id"] for x in report}]
    (out / "sfx.json").write_text(json.dumps(keep + report, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
