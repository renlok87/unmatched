"""Check the published ART-003 live combat evidence without modifying images."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


CUE = re.compile(r"CUE damage (\S+) -(\d+) seq=(\d+)")
NUMBER = re.compile(r"ARTPREVIEW damage-number fighter=(\S+) amount=(\d+) seq=(\d+)")
RESULT = re.compile(r"COMBAT-RESULT seq=(\d+) damage=(-?\d+)")
MAX_SEQ = re.compile(r"SNAPSHOT applied seq=(\d+)")


def check_trace(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    cues = Counter((fighter, int(amount), int(seq)) for fighter, amount, seq in CUE.findall(text))
    numbers = Counter((fighter, int(amount), int(seq)) for fighter, amount, seq in NUMBER.findall(text))
    assert cues, f"No live damage cues: {path}"
    assert cues == numbers, f"Damage number does not match exactly-once cues: {path}"
    assert max(numbers.values()) == 1, f"Duplicate damage number: {path}"
    assert "target=1 icon=1" in text, f"No target icon binding: {path}"
    assert "target=0 icon=0" in text, f"Target icon never cleared: {path}"
    results = [(int(seq), int(damage)) for seq, damage in RESULT.findall(text)]
    assert results, f"No combat result: {path}"
    first_seq, first_damage = results[0]
    assert first_damage > 0, f"First observed combat result has no known damage: {path}"
    assert any(seq == first_seq and amount == first_damage for _, amount, seq in cues), (
        f"First HUD result and server damage cue disagree: {path}"
    )
    seqs = [int(seq) for seq in MAX_SEQ.findall(text)]
    assert seqs, f"No authoritative snapshots: {path}"
    return {
        "max_seq": max(seqs),
        "damage_cues": sum(cues.values()),
        "unique_damage_numbers": sum(numbers.values()),
        "combat_results": len(results),
        "first_combat_result": {"seq": first_seq, "damage": first_damage},
        "target_icon_bound_and_cleared": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--git-staged", action="store_true")
    parser.add_argument("--write-report", action="store_true",
                        help="Save validation.json; default verification is read-only")
    args = parser.parse_args()
    root = args.run_dir.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    checked = []
    image_dimensions = {}
    for entry in manifest["files"]:
        name = entry["name"].replace("\\", "/")
        path = root / name
        data = path.read_bytes()
        assert len(data) == entry["bytes"], f"Size changed: {name}"
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], f"SHA-256 changed: {name}"
        if args.git_staged:
            relative = path.relative_to(Path.cwd()).as_posix()
            staged = subprocess.run(["git", "show", f":{relative}"],
                                    check=True, capture_output=True).stdout
            assert hashlib.sha256(staged).hexdigest() == entry["sha256"], (
                f"Git staged bytes differ from manifest: {name}"
            )
        checked.append(name)
        if path.suffix.lower() == ".png":
            assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR"
            dimensions = struct.unpack(">II", data[16:24])
            assert dimensions == (1920, 1080), f"Unexpected screenshot resolution: {name}"
            image_dimensions[name] = list(dimensions)
    assert len(checked) == 8, f"Expected 2 traces and 6 screenshots, got {len(checked)}"
    assert "joiner/s09-damage-number.png" in image_dimensions
    assert "joiner/s09-combat-resolve-revealed.png" in image_dimensions
    traces = {
        side: check_trace(root / f"combat-client-{side}.trace.log")
        for side in ("host", "joiner")
    }
    assert traces["host"]["max_seq"] == traces["joiner"]["max_seq"], "Clients diverged"
    assert traces["host"]["first_combat_result"] == traces["joiner"]["first_combat_result"], (
        "Clients disagree on the first combat result"
    )
    result = {
        "status": "pass_technical_evidence_only",
        "run": root.name,
        "manifest_files_verified": len(checked),
        "git_staged_bytes_verified": bool(args.git_staged),
        "screenshots_1920x1080": len(image_dimensions),
        "trace": traces,
        "visual_review": "manual; see acceptance report",
        "full_K3_or_GD058": "open",
    }
    if args.write_report:
        (root / "validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


main()
