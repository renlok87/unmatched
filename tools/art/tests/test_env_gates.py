"""EN-05: tools/art/render/env_gates.py - the environment gates moved into git.

  python -m pytest tools/art/tests/test_env_gates.py -q
The P10 numbers are re-measured on the packaged P10 frames in git (docs/game-design/evidence/ENV-MAPS/
p10-sarpedon-rework-2026-10-03/sarpedon-packaged/). The concept-based numbers need the registered concept, which is
never in git (ENV-U3): C:/tmp/envmaps-research/p7/proto/sarpedon/concept-registered-H.png or env UM_ENV_CONCEPT;
skipped without it. The zone dE needs the derived map textures (out of git; zone_separation falls back to the main
checkout); skipped without them.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "render"))
import env_gates as G  # noqa: E402

P10 = REPO / "docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged"
CONCEPT = Path(os.environ.get("UM_ENV_CONCEPT", "C:/tmp/envmaps-research/p7/proto/sarpedon/concept-registered-H.png"))
need_concept = pytest.mark.skipif(not CONCEPT.is_file(), reason=f"registered concept not here ({CONCEPT}; ENV-U3)")


def test_check_synthetic_is_green_and_fast():
    t0 = time.time()
    assert G.self_check() == []
    assert time.time() - t0 < 10


def test_p10_k1_straight_edge():
    n, row = G.edge(P10 / "bench-K1-1920x1080.png", (560, 900, 1360, 1080), 1)
    assert (n, row) == (20, 1059)


def test_p10_g5_measure():
    k1 = G.g5(P10)["K1"]
    assert abs(k1["mapY"] - 104.9) <= 0.05
    assert abs(k1["warm"] - 0.126) <= 0.0005
    assert abs(k1["ringDL50"] - 33.6) <= 0.05
    assert G.map_key_of(P10) == "sarpedon"


def test_p10_g5_zone_min_de():
    try:
        z = G.zone_min_de(P10)
    except (FileNotFoundError, OSError) as exc:
        pytest.skip(f"derived map textures missing: {exc}")
    assert z["pair"] == "blue-purple" and abs(z["dE76"] - 25.33) <= 0.05


@need_concept
def test_p10_concept_numbers():
    c = G.crit(P10, CONCEPT)
    assert abs(c["V3_F1_ssimShipPoly"]["value"] - 0.442) <= 0.01
    assert abs(c["V1_C0_fallsBody"]["dE76"] - 3.84) <= 0.01
    assert abs(c["V2_C0_fort"]["dE76"] - 5.93) <= 0.01
    assert c["V1_K1_edgeRunPx"]["value"] == 20
    assert abs(c["V4_hullRed"]["dE76"] - 5.52) <= 0.01 and c["V4_hullWallMax"]["px>=245"] == 0


@need_concept
def test_p10_g4_g6_and_streams_on_the_concept():
    g4 = G.g4(P10, CONCEPT)
    assert abs(g4["ssimQuarter"] - 0.490) <= 0.001 and g4["patchDeltaE76Median"] == 5.52
    g6 = G.g6(P10, CONCEPT)
    assert g6["lanternsAt80pct"] == 4
    assert abs(g6["lanterns"]["lantern-deck-se"]["ratio"] - 0.69) <= 0.01
    # N_concept of EN-19 (recorded in tools/art/render/LIVE-TUNE.md, section env_gates)
    assert G.streams(CONCEPT)["N"] == 3
    assert G.streams(P10 / "bench-Fitx1p45-1920x1080.png")["N"] == 2


def test_g6_exclusion_polygon_is_optional_and_parsed():
    assert G.parse_exclude(None) is None
    ex = G.parse_exclude(["lantern-deck-se=1700,700;1740,700;1740,745;1700,745"])
    assert list(ex) == ["lantern-deck-se"] and len(ex["lantern-deck-se"][0]) == 4
    with pytest.raises(Exception):
        G.parse_exclude(["no-such-lantern=1,2;3,4;5,6"])
    with pytest.raises(Exception):
        G.parse_exclude(["lantern-left=1,2;3,4"])


def test_cli_edge_and_cannons_json(tmp_path, capsys):
    out = tmp_path / "edge.json"
    assert G.main(["--json", str(out), "edge", str(P10 / "bench-K1-1920x1080.png")]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["edgeRunPx"] == 20
    capsys.readouterr()
    assert G.main(["cannons", str(P10 / "bench-Fitx1p45-1920x1080.png")]) == 0
    res = json.loads(capsys.readouterr().out)
    per = next(iter(res.values()))
    assert set(per) == {"cannon-1", "cannon-2", "cannon-3"} and all("dL" in v for v in per.values())


def test_fire_rois_from_the_trace():
    rois = G.fire_rois(P10 / "bench-K1-1920x1080.png")
    assert set(rois) == {"fire-fort", "fire-brazier"}
    f = G.fire(P10 / "bench-K1-1920x1080.png", rois["fire-brazier"])
    assert f["height"] > 0 and f["tongues"] >= 1 and 0 <= f["redShare"] <= 1


def test_sheet_three_panels(tmp_path):
    res = G.sheet([P10 / "bench-K1-1920x1080.png"], tmp_path / "s.png", crop=(560, 900, 1360, 1080), label="K1 band")
    assert res["size"][0] == 3 * 800 and (tmp_path / "s.png").is_file()


def test_trace_txt_or_log(tmp_path):
    with pytest.raises(FileNotFoundError):
        G.trace_path(tmp_path)
    (tmp_path / "bench.trace.txt").write_text("", encoding="utf-8")
    assert G.trace_path(tmp_path).name == "bench.trace.txt"
    (tmp_path / "bench.trace.log").write_text("", encoding="utf-8")
    assert G.trace_path(tmp_path).name == "bench.trace.log"
