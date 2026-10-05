"""Split a music file into stems with Demucs (card AUC-M06): drums, bass, other, vocals.

Run with the audio venv (Demucs + CPU torch, outside the system Python):

    C:/tmp/audio-tools/venv/Scripts/python tools/audio/stems.py <in.mp3|wav> <out dir> [--model htdemucs]

Writes <out dir>/{drums,bass,other,vocals}.wav (float32, model rate 44.1 kHz, stereo) and stems.json with the RMS of
each stem relative to the mix - a "vocals" stem louder than about -25 dB means the generator slipped in a voice
(02 §2.1 forbids vocals). L2 (combat) = drums + bass, L1 (maneuver) = other + vocals (loop.py builds them).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
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


def decode(path: str, sr: int) -> np.ndarray:
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.copy()


def write_wav_f32(path: Path, x: np.ndarray, sr: int) -> None:
    import struct
    data = np.ascontiguousarray(x.T.astype("<f4")).tobytes()
    ch = x.shape[0]
    head = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 3, ch, sr, sr * ch * 4, ch * 4, 32) + b"data" + struct.pack("<I", len(data)))
    path.write_bytes(head + data)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--model", default="htdemucs")
    args = ap.parse_args(argv)
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(args.model)
    model.eval()
    sr = model.samplerate
    mix = decode(args.src, sr)
    wav = torch.from_numpy(mix)
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    with torch.no_grad():
        sources = apply_model(model, ((wav - mean) / std)[None], device="cpu", split=True, overlap=0.25,
                              progress=False)[0]
    sources = sources * std + mean
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    mix_rms = float(np.sqrt(np.mean(mix ** 2)) + 1e-12)
    info = {"src": str(args.src), "model": args.model, "sr": sr, "seconds": round(mix.shape[1] / sr, 3), "stems": {}}
    for name, src in zip(model.sources, sources):
        x = src.numpy()
        write_wav_f32(out / f"{name}.wav", x, sr)
        info["stems"][name] = {"rel_db": round(20 * np.log10(float(np.sqrt(np.mean(x ** 2))) / mix_rms + 1e-12), 1)}
    (out / "stems.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
