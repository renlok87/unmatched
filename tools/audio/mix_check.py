"""Loudness of a recorded match against the mix targets (02-audio-design.md §5.3, AU-S5 07-production-log §9).

    python tools/audio/mix_check.py <client.wav> [--trace <client.trace.log>] [--json out.json]

The client writes its whole output with -S08AudioRecord=<file.wav> (S08FlowGameModeAudio.cpp): from the match start
to the result + 8 s, after the master volume. The trace line `AUDIO-REC stop ... master=<g>` gives that volume; the
measure is brought back to master 100 % (+20·log10(1/g) dB), the other sliders stay at their defaults - the
"default volumes" of the target. Reported: integrated loudness, loudness range, true peak, the loudest short-term
(3 s) value and the share of time the short-term loudness is within 6 LU of it. Targets: -20 ±2 LUFS-I, true peak
<= -1 dBTP, combat peaks near -13.5 LUFS-S (the DE match, 01-inventory §4.3).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze import ffmpeg  # noqa: E402

TARGET_I, TOL_I, MAX_TP, PEAK_S = -20.0, 2.0, -1.0, -13.5


def master_gain(trace: Path) -> float | None:
    gain = None
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"AUDIO-REC (?:start|stop).*?master=([\d.]+)", line)
        if m:
            gain = float(m.group(1))
    return gain


def measure(wav: Path, gain_db: float) -> dict:
    af = f"volume={gain_db:.3f}dB,ebur128=peak=true:framelog=info"
    err = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(wav), "-af", af, "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    short = [float(v) for v in re.findall(r"\bS:\s*(-?[\d.]+)", err[: err.rfind("Summary:")])]
    summ = err[err.rfind("Summary:"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+|-inf)", summ).group(1).replace("-inf", "-120"))
    s_max = max(short) if short else None
    near = sum(1 for v in short if s_max is not None and v >= s_max - 6) / len(short) if short else 0.0
    return {"I": g("I"), "LRA": g("LRA"), "TP": g("Peak"), "S_max": s_max, "near_peak_share": round(near, 3),
            "seconds": round(len(short) / 10.0, 1)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("wav")
    ap.add_argument("--trace")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    gain = master_gain(Path(args.trace)) if args.trace else None
    gain_db = -20 * math.log10(gain) if gain and gain > 0 else 0.0
    m = measure(Path(args.wav), gain_db)
    m.update({"file": Path(args.wav).name, "master": gain, "correction_db": round(gain_db, 2),
              "ok_I": abs(m["I"] - TARGET_I) <= TOL_I, "ok_TP": m["TP"] <= MAX_TP,
              "targets": {"I": f"{TARGET_I} ±{TOL_I}", "TP_max": MAX_TP, "S_peak_ref": PEAK_S}})
    print(json.dumps(m, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if m["ok_I"] and m["ok_TP"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
