"""Motifs and theme sketches as MIDI + a plain render to WAV (audio cards AUC-M01, AUC-M02).

The sketches are our own compositions. They are the uploaded melody for Suno V6 "cover" (05-production-plan §2.1):
the sketch fixes key, tempo, form and the loop length, Suno orchestrates it. The render only has to make melody,
harmony, bass and pulse clear - it is not a final sound.

    python tools/audio/sketch.py --out C:/tmp/audio-src/sketches [--only MOT-DUEL ...]

Each piece gives <ID>.mid and <ID>.wav (48 kHz / 16 bit) plus sketches.json (id, bpm, bars, key, seconds, sha256).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 48000
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
        "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
CHORD = {"m": (0, 3, 7), "": (0, 4, 7), "dim": (0, 3, 6), "sus4": (0, 5, 7), "7": (0, 4, 7, 10)}


def midi(name: str) -> int:
    """'A4' -> 69, 'F#5' -> 78."""
    pitch, octave = name[:-1], int(name[-1])
    return 12 * (octave + 1) + NOTE[pitch]


def chord_notes(sym: str, octave: int = 3) -> list[int]:
    root = sym[:2] if len(sym) > 1 and sym[1] in "#b" else sym[:1]
    kind = sym[len(root):]
    base = 12 * (octave + 1) + NOTE[root]
    return [base + i for i in CHORD[kind]]


def chord_root(sym: str) -> str:
    return sym[:2] if len(sym) > 1 and sym[1] in "#b" else sym[:1]


@dataclass
class Piece:
    id: str
    bpm: float
    bars: int
    key: str
    melody: list[tuple[float, float, str]]          # (start beat, length in beats, note)
    chords: list[tuple[float, float, str]]          # (start beat, length, chord symbol)
    style: str = "arp"                              # accompaniment: arp (harp), strum (guitar), pad
    drums: str = "frame"                            # frame | hand | none
    tail_beats: float = 0.0                         # extra render time after the last bar (stings)
    meta: dict = field(default_factory=dict)


def bars(spec: list[str], beats_per_bar: int = 4) -> list[tuple[float, float, str]]:
    """Melody written bar by bar: 'A4:1 E5:1.5 D5:.5 C5:1' (note:length, 'r' = rest)."""
    out, t = [], 0.0
    for bar in spec:
        start = t
        for tok in bar.split():
            n, d = tok.split(":")
            d = float(d)
            if n != "r":
                out.append((t, d, n))
            t += d
        if abs(t - start - beats_per_bar) > 1e-6:
            raise ValueError(f"bar '{bar}' has {t - start} beats")
    return out


def chords_by_bar(spec: list[str], beats_per_bar: int = 4) -> list[tuple[float, float, str]]:
    out = []
    for i, bar in enumerate(spec):
        parts = bar.split()
        each = beats_per_bar / len(parts)
        for j, sym in enumerate(parts):
            out.append((i * beats_per_bar + j * each, each, sym))
    return out


# ------------------------------------------------------------------ pieces (original compositions, 2026-10-05)
DUEL_Q = ["A4:1 E5:1.5 D5:.5 C5:1", "B4:1 C5:1 D5:2"]
DUEL_A = ["E5:1 C5:1.5 B4:.5 A4:1", "G#4:1 B4:1 A4:2"]


def pieces() -> list[Piece]:
    ps = []
    # Motifs (AUC-M01)
    ps.append(Piece("MOT-DUEL", 100, 4, "A minor", bars(DUEL_Q + DUEL_A), chords_by_bar(["Am", "G", "C", "E Am"]),
                    style="pad", drums="none", tail_beats=2))
    ps.append(Piece("MOT-ARTHUR", 100, 2, "A (mixolydian colour)",
                    bars(["A3:.5 D4:1.5 E4:.5 A4:1.5", "A4:4"]), chords_by_bar(["D A", "A"]), style="pad",
                    drums="none", tail_beats=2))
    ps.append(Piece("MOT-MEDUSA", 100, 2, "A minor, tritone",
                    bars(["A4:1 G#4:.5 G4:.5 D#4:2", "D#4:4"]), chords_by_bar(["Am D#dim", "D#dim"]), style="pad",
                    drums="none", tail_beats=2))
    # Menu theme (AUC-M02): A (motif) - A' to C major - B (C major) - A - C (back to E)
    menu_mel = (DUEL_Q + DUEL_A
                + ["A4:1 E5:1.5 D5:.5 C5:1", "B4:1 C5:1 D5:1 E5:1", "F5:1.5 E5:.5 D5:2", "C5:4"]
                + ["G4:1 C5:1 E5:1 G5:1", "F5:2 E5:1 D5:1", "E5:1 D5:1 C5:1 A4:1", "B4:3 G4:1",
                   "A4:1 C5:1 F5:1 A5:1", "G5:2 F5:1 E5:1", "D5:1 E5:1 F5:1 D5:1", "E5:4"]
                + DUEL_Q + DUEL_A
                + ["A4:1 E5:1.5 D5:.5 C5:1", "B4:1 C5:1 D5:1 E5:1", "F5:1.5 E5:.5 D5:2", "C5:4"]
                + ["C5:2 B4:2", "A4:2 G4:2", "F4:1 A4:1 C5:1 F5:1", "E5:4", "D5:2 C5:2", "B4:2 A4:2",
                   "G#4:2 B4:2", "E5:4"])
    menu_ch = (["Am", "G", "C", "E Am", "Am", "G", "Dm", "C"]
               + ["C", "F", "Am", "G", "F", "C", "Dm", "E"]
               + ["Am", "G", "C", "E Am", "Am", "G", "Dm", "C"]
               + ["Am", "Em", "F", "C", "Dm", "Am", "E", "E"])
    ps.append(Piece("SKETCH-MENU", 100, 32, "A minor / C major", bars(menu_mel), chords_by_bar(menu_ch),
                    style="arp", drums="frame"))
    # Marmoreal (D dorian, 90)
    marm_a = ["A4:2 D5:1 E5:1", "D5:2 B4:2", "A4:3 F4:1", "E4:2 G4:2",
              "A4:1 D5:1 F5:1 E5:1", "D5:2 B4:1 G4:1", "A4:4", "G4:2 E4:2"]
    marm_mel = (marm_a
                + ["C5:2 A4:2", "G4:2 E5:2", "D5:3 B4:1", "C5:2 A4:2",
                   "F5:2 E5:1 C5:1", "D5:2 B4:2", "C5:1 B4:1 A4:2", "E4:4"]
                + marm_a
                + ["A4:1 C5:1 F5:2", "G5:1 F5:1 D5:2", "E5:2 B4:2", "C5:2 A4:2",
                   "A4:2 C5:2", "B4:2 D5:2", "E5:2 C5:2", "A4:4"])
    marm_ch = (["Dm", "G", "Dm", "C", "Dm", "G", "Dm", "C"] + ["F", "C", "G", "Am", "F", "G", "Am", "Am"]
               + ["Dm", "G", "Dm", "C", "Dm", "G", "Am", "Am"] + ["F", "G", "Em", "Am", "F", "G", "C", "Am"])
    ps.append(Piece("SKETCH-MARMOREAL", 90, 32, "D dorian", bars(marm_mel), chords_by_bar(marm_ch), style="arp",
                    drums="frame"))
    # Sarpedon (A dorian, 96)
    sarp_a = ["A4:.5 B4:.5 C5:1 E5:1 D5:.5 C5:.5", "B4:1 A4:.5 F#4:.5 A4:2", "E5:1 D5:.5 C5:.5 B4:1 A4:1",
              "G4:2 B4:1 D5:1", "E5:1.5 D5:.5 C5:1 E5:1", "F#5:1 E5:.5 D5:.5 A4:2", "G4:1 B4:1 E5:1 D5:1", "A4:4"]
    sarp_mel = (sarp_a
                + ["G4:1 C5:1 E5:2", "D5:1 B4:1 G4:2", "A4:1 D5:1 F#5:1 E5:1", "C5:2 A4:2",
                   "E5:1 G5:1 E5:1 C5:1", "D5:1 F#5:1 A5:2", "G5:1 F#5:1 E5:1 B4:1", "E5:4"]
                + sarp_a
                + ["A5:2 G5:1 E5:1", "D5:2 B4:2", "F#5:1 E5:1 D5:1 A4:1", "A4:4",
                   "G4:1 A4:1 C5:1 E5:1", "D5:2 G4:2", "B4:1 D5:1 E5:2", "E4:2 G4:1 B4:1"])
    sarp_ch = (["Am", "D", "Am", "G", "Am", "D", "Em", "Am"] + ["C", "G", "D", "Am", "C", "D", "Em", "Em"]
               + ["Am", "D", "Am", "G", "Am", "D", "Em", "Am"] + ["Am", "G", "D", "D", "C", "G", "Em", "Em"])
    ps.append(Piece("SKETCH-SARPEDON", 96, 32, "A dorian", bars(sarp_mel), chords_by_bar(sarp_ch), style="strum",
                    drums="hand"))
    return ps


# ------------------------------------------------------------------ MIDI writer (SMF type 1, 480 ppq)
PPQ = 480


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, bytes]]) -> bytes:
    events.sort(key=lambda e: (e[0], e[1][0] & 0xF0 != 0x80))  # note-offs before note-ons at the same tick
    data, last = bytearray(), 0
    for tick, msg in events:
        data += _vlq(tick - last) + msg
        last = tick
    data += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + data


def write_midi(p: Piece, path: Path) -> None:
    tempo = int(60_000_000 / p.bpm)
    meta = [(0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")), (0, b"\xff\x58\x04\x04\x02\x18\x08")]
    tracks = [_track(meta)]

    def notes(ch: int, program: int, items: list[tuple[float, float, int, int]]) -> bytes:
        ev = [(0, bytes([0xC0 | ch, program]))]
        for start, length, note, vel in items:
            a, b = int(start * PPQ), int((start + length) * PPQ) - 1
            ev.append((a, bytes([0x90 | ch, note, vel])))
            ev.append((b, bytes([0x80 | ch, note, 0])))
        return _track(ev)

    tracks.append(notes(0, 60, [(s, d, midi(n), 96) for s, d, n in p.melody]))          # french horn
    tracks.append(notes(1, 48, [(s, d, n, 64) for s, d, c in p.chords for n in chord_notes(c)]))  # strings
    tracks.append(notes(2, 43, [(s, d, 12 * 3 + NOTE[chord_root(c)], 80) for s, d, c in p.chords]))  # contrabass
    if p.drums != "none":
        tracks.append(notes(9, 0, [(s, 0.25, n, v) for s, n, v in drum_hits(p)]))
    head = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQ)
    path.write_bytes(head + b"".join(tracks))


def drum_hits(p: Piece) -> list[tuple[float, int, int]]:
    """(beat, GM drum note, velocity): frame - low drum on 1 and 3, light tap on 4&; hand - doumbek-like."""
    hits = []
    for bar in range(p.bars):
        b = bar * 4
        if p.drums == "frame":
            hits += [(b, 41, 100), (b + 2, 41, 80), (b + 3.5, 45, 50)]
            if bar % 4 == 0:
                hits.append((b, 47, 90))  # timpani-like accent at each 4-bar group
        elif p.drums == "hand":
            hits += [(b, 41, 100), (b + 1.5, 60, 60), (b + 2, 41, 80), (b + 3, 60, 70), (b + 3.5, 60, 50)]
    return hits


# ------------------------------------------------------------------ plain synth render
def freq(n: int) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n: int, a: float, d: float, s: float, r: float, hold: int) -> np.ndarray:
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    e = np.zeros(hold + r_n)
    e[:a_n] = np.linspace(0, 1, a_n, endpoint=False)
    e[a_n:a_n + d_n] = np.linspace(1, s, d_n, endpoint=False)
    e[a_n + d_n:hold] = s
    e[hold:] = np.linspace(e[hold - 1] if hold > 0 else s, 0, r_n)
    return e[: n] if n < len(e) else e


def tone(f: float, seconds: float, harmonics: list[float], adsr=(0.02, 0.1, 0.7, 0.15), vib: float = 0.0,
         decay: float = 0.0) -> np.ndarray:
    hold = int(seconds * SR)
    total = hold + int(adsr[3] * SR)
    t = np.arange(total) / SR
    phase = 2 * np.pi * f * t + (vib * np.sin(2 * np.pi * 5.2 * t) if vib else 0)
    w = sum(a * np.sin(k * phase) for k, a in enumerate(harmonics, start=1))
    w = w * env(total, *adsr[:3], adsr[3], hold)
    if decay:
        w *= np.exp(-decay * t)
    return w


def drum(kind: int, vel: int) -> np.ndarray:
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(kind)
    if kind in (41, 47):  # low frame drum / timpani accent
        f = (60 if kind == 41 else 90) + 40 * np.exp(-t * 30)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (7 if kind == 41 else 3.5))
        noise = rng.standard_normal(n) * np.exp(-t * 60) * 0.15
        w = body + noise
    else:  # hand drum / tap
        body = np.sin(2 * np.pi * 220 * t) * np.exp(-t * 25)
        noise = rng.standard_normal(n) * np.exp(-t * 45) * 0.3
        w = body * 0.6 + noise
    return w * (vel / 127)


def render(p: Piece) -> np.ndarray:
    spb = 60.0 / p.bpm
    total = int((p.bars * 4 + p.tail_beats) * spb * SR) + SR
    out = np.zeros(total)

    def add(start_beat: float, w: np.ndarray, gain: float) -> None:
        i = int(start_beat * spb * SR)
        j = min(total, i + len(w))
        out[i:j] += w[: j - i] * gain

    for s, d, n in p.melody:
        add(s, tone(freq(midi(n)), d * spb * 0.95, [1, 0.5, 0.33, 0.2, 0.12, 0.08], vib=0.003), 0.30)
    for s, d, c in p.chords:
        notes = chord_notes(c, 3)
        if p.style == "pad":
            for n in notes:
                add(s, tone(freq(n), d * spb, [1, 0.25, 0.1], adsr=(0.15, 0.2, 0.8, 0.4)), 0.09)
        elif p.style == "arp":  # harp: chord tones as eighths, up and down
            seq = notes + [notes[0] + 12] + notes[1:][::-1]
            steps = int(d * 2)
            for k in range(steps):
                n = seq[k % len(seq)] + 12
                add(s + k * 0.5, tone(freq(n), 0.6, [1, 0.35, 0.15, 0.08], adsr=(0.003, 0.05, 0.6, 0.3),
                                      decay=4.0), 0.10)
            for n in notes:  # soft string bed under the harp
                add(s, tone(freq(n), d * spb, [1, 0.2, 0.08], adsr=(0.3, 0.2, 0.7, 0.4)), 0.035)
        else:  # strum: guitar-like hits on 1, 2&, 3, 4&
            for off in (0, 1.5, 2, 3.5):
                if off < d:
                    for k, n in enumerate(notes + [notes[0] + 12]):
                        add(s + off + k * 0.012 / spb, tone(freq(n + 12), 0.5, [1, 0.5, 0.3, 0.2, 0.1],
                                                             adsr=(0.002, 0.05, 0.5, 0.2), decay=6.0), 0.05)
        root = 12 * 2 + NOTE[chord_root(c)]
        add(s, tone(freq(root), d * spb * 0.9, [1, 0.3], adsr=(0.01, 0.1, 0.8, 0.1)), 0.22)
    if p.drums != "none":
        for s, n, v in drum_hits(p):
            add(s, drum(n, v), 0.5)
    peak = np.max(np.abs(out)) or 1.0
    return out / peak * 10 ** (-1 / 20)


def write_wav(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    stereo = np.repeat(pcm[:, None], 2, axis=1).tobytes()
    head = b"RIFF" + struct.pack("<I", 36 + len(stereo)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, SR,
                                                                                      SR * 4, 4, 16)
    path.write_bytes(head + b"data" + struct.pack("<I", len(stereo)) + stereo)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for p in pieces():
        if args.only and p.id not in args.only:
            continue
        write_midi(p, out / f"{p.id}.mid")
        x = render(p)
        write_wav(out / f"{p.id}.wav", x)
        sha = hashlib.sha256((out / f"{p.id}.wav").read_bytes()).hexdigest()
        index.append({"id": p.id, "bpm": p.bpm, "bars": p.bars, "key": p.key, "seconds": round(len(x) / SR, 2),
                      "loop_seconds": round(p.bars * 4 * 60 / p.bpm, 3), "sha256": sha})
        print(f"{p.id}: {p.bars} bars @ {p.bpm} = {p.bars * 4 * 60 / p.bpm:.1f} s")
    (out / "sketches.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
