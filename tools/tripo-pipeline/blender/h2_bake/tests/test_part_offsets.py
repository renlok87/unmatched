"""Opt-in `prepare.part_offsets_m` (Ancient Leshen stage 5 r3, 2026-10-14): the prepare stage translates the listed source
parts in the final frame right after the frame map (st_prepare.py, profile.part_offsets). A profile without the key takes
the old code path.

Plain Python: accessor and validation. Blender headless (skipped without Blender 5.2 or the local Tripo source GLBs,
which are not in git): the Medusa prepare stage re-run gives the committed prepare-report.json byte for byte, and the
Ancient Leshen r2 profile with an offset of the crow tripo_part_8 moves only that part (the frame map and every other
part's final bounds equal the committed r2 report).
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[4]
sys.path.insert(0, str(PKG.parent))

from h2_bake import profile as PR  # noqa: E402

MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
MEDUSA_RUN = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake"
LESHEN = REPO / "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2-bake-h2-r2.json"
LESHEN_RUN = REPO / "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2-bake-r2"
BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@pytest.fixture()
def medusa():
    return json.loads(MEDUSA.read_text(encoding="utf-8"))


def body_part(p):
    return next(n for n, c in sorted(p["parts"].items()) if c["mesh"] == "body")


def sources_present(profile_path):
    p = json.loads(profile_path.read_text(encoding="utf-8"))
    return all((REPO / p["sources"][k]["path"]).is_file() for k in ("parts_glb", "tex_glb"))


# ------------------------------------------------------------------ plain Python
def test_profiles_without_the_key_are_unchanged(medusa):
    assert "prepare" not in medusa
    assert PR.part_offsets(medusa) is None
    assert PR.part_offsets_problems(medusa) == []
    assert PR.validate(medusa) == []


def test_valid_part_offsets(medusa):
    p = copy.deepcopy(medusa)
    p["prepare"] = {"part_offsets_m": {body_part(p): [0.01, 0.0325, -0.01]}}
    assert PR.validate(p) == []
    assert PR.part_offsets(p) == {body_part(p): [0.01, 0.0325, -0.01]}
    p["prepare"] = {"note": "no offsets"}  # a prepare block without the key: the old path
    assert PR.part_offsets(p) is None and PR.validate(p) == []


@pytest.mark.parametrize("prep, message", [
    ("x", "must be an object"),
    ({"part_offsets_m": {}}, "non-empty object"),
    ({"part_offsets_m": [0.01, 0.0, 0.0]}, "non-empty object"),
    ({"part_offsets_m": {"tripo_part_99": [0.01, 0.0, 0.0]}}, "unknown part"),
    ({"part_offsets_m": {"BASE": [0.01, 0.0, 0.0]}}, "is the base"),
    ({"part_offsets_m": {"BODY": [0.01, 0.0]}}, "[dx, dy, dz]"),
    ({"part_offsets_m": {"BODY": [0.01, "0", 0.0]}}, "[dx, dy, dz]"),
    ({"part_offsets_m": {"BODY": [True, 0.0, 0.0]}}, "[dx, dy, dz]"),
    ({"part_offsets_m": {"BODY": [float("nan"), 0.0, 0.0]}}, "[dx, dy, dz]"),
    ({"part_offsets_m": {"BODY": [0.0, 0.0, 0.0]}}, "is zero"),
    ({"part_offsets_m": {"BODY": [0.04, 0.04, 0.0]}}, "> 0.05 m"),
])
def test_invalid_part_offsets(medusa, prep, message):
    p = copy.deepcopy(medusa)
    base = next(n for n, c in p["parts"].items() if c["mesh"] == "base")
    if isinstance(prep, dict) and isinstance(prep.get("part_offsets_m"), dict):
        prep = {"part_offsets_m": {(base if k == "BASE" else body_part(p) if k == "BODY" else k): v
                                   for k, v in prep["part_offsets_m"].items()}}
    p["prepare"] = prep
    problems = PR.validate(p)
    assert any(message in s for s in problems), problems


# ------------------------------------------------------------------ Blender: the prepare stage
def run_prepare(run, profile_path, timeout=900):
    r = subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--profile", str(profile_path), "--run-dir", str(run),
                        "--stages", "prepare", "--blender", BLENDER], capture_output=True, text=True, timeout=timeout,
                       creationflags=FLAGS)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    return json.loads((run / "reports" / "prepare-report.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(not Path(BLENDER).is_file() or not sources_present(MEDUSA),
                    reason="Blender 5.2 or the local Medusa Tripo source GLBs (not in git) are missing")
def test_medusa_prepare_report_is_byte_identical(tmp_path):
    run = tmp_path / "run"
    rep = run_prepare(run, MEDUSA)
    assert "part_offsets_m" not in rep
    assert (run / "reports" / "prepare-report.json").read_bytes() == \
        (MEDUSA_RUN / "reports" / "prepare-report.json").read_bytes()


@pytest.mark.skipif(not Path(BLENDER).is_file() or not sources_present(LESHEN)
                    or not (LESHEN_RUN / "reports" / "prepare-report.json").is_file(),
                    reason="Blender 5.2 or the local Ancient Leshen Tripo source GLBs (not in git) are missing")
def test_offset_moves_only_the_listed_part(tmp_path):
    prof = json.loads(LESHEN.read_text(encoding="utf-8"))
    off = [0.01, 0.0325, 0.01]
    prof["prepare"] = {"part_offsets_m": {"tripo_part_8": off}}
    pfile = tmp_path / "leshen-offset.json"
    pfile.write_text(json.dumps(prof, ensure_ascii=False), encoding="utf-8")
    rep = run_prepare(tmp_path / "run", pfile)
    old = json.loads((LESHEN_RUN / "reports" / "prepare-report.json").read_text(encoding="utf-8"))
    assert rep["passed"] and rep["frame_map"] == old["frame_map"]
    assert rep["part_offsets_m"]["parts"] == {"tripo_part_8": off}
    for name, part in old["parts"].items():
        got = rep["parts"][name]
        assert got["source_bounds_m"] == part["source_bounds_m"]
        if name == "tripo_part_8":
            for lo_hi in (0, 1):
                for a in range(3):
                    assert got["final_bounds_m"][lo_hi][a] == pytest.approx(part["final_bounds_m"][lo_hi][a] + off[a],
                                                                             abs=2e-5)
            assert got["final_area_cm2"] == pytest.approx(part["final_area_cm2"], rel=1e-5)
        else:
            assert got["final_bounds_m"] == part["final_bounds_m"] and got["final_area_cm2"] == part["final_area_cm2"]
