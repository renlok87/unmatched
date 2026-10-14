"""Тесты clip_closeups.py без Blender (W2-d: F146 камера крупных планов в отчёте, F154 пара шва Idle).

    python -m pytest tools/tripo-pipeline/tests/test_clip_closeups.py -q
"""
import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "anim"))

import clip_closeups as cc  # noqa: E402


def test_parse_shots_forms_and_errors():
    s = cc.parse_shots("7:q34:7.16,-9.52,33.7:18; 4:front:@hand.R:12;21:back:fig:auto;")
    assert [x["frame"] for x in s] == [7, 4, 21]
    assert s[0]["centre"] == {"kind": "arm_cm", "value": [7.16, -9.52, 33.7]} and s[0]["size_cm"] == 18.0
    assert s[1]["centre"] == {"kind": "bone", "bone": "hand.R"}
    assert s[2]["centre"] == {"kind": "fig"} and s[2]["size_cm"] is None
    for bad in ("7:q34:1,2:18", "7:side:fig:10", "7:q34:@hand.R:auto", "7:q34:fig", "7:q34:fig:-1"):
        with pytest.raises(ValueError):
            cc.parse_shots(bad)
    assert cc.parse_shots(None) == [] and cc.parse_shots(" ; ") == []


def test_name_shots_suffix_on_repeat():
    s = cc.name_shots("Achilles-LungeAttack", cc.parse_shots("7:q34:fig:auto;7:q34:0,0,30:10;4:front:fig:auto"))
    assert [x["name"] for x in s] == ["Achilles-LungeAttack-f07-q34", "Achilles-LungeAttack-f07-q34-b",
                                      "Achilles-LungeAttack-f04-front"]


def test_shots_from_report_repeats_numbers_not_bones():
    rep = {"schema": cc.SCHEMA, "res_px": 1100,
           "shots": [{"name": "A-Idle-f15-front", "frame": 15, "view": "front", "centre_arm_cm": [1.0, 2.0, 30.0],
                      "size_cm": 20.0, "centre_source": "@hand.R"}],
           "seam": {"frames": [60, 0], "views": {"front": {"centre_arm_cm": [0.5, 0.0, 27.0], "size_cm": 61.2}}}}
    shots, cams, res = cc.shots_from_report(rep)
    assert shots == [{"frame": 15, "view": "front", "centre": {"kind": "arm_cm", "value": [1.0, 2.0, 30.0]},
                      "size_cm": 20.0, "from": "A-Idle-f15-front"}]
    assert cams == {"front": {"centre_arm_cm": [0.5, 0.0, 27.0], "size_cm": 61.2}} and res == 1100


def test_label_files_only_this_label(tmp_path):
    for n in ("Achilles-Idle-f15-front.jpg", "Achilles-Idle-f30-q34r.jpg", "Achilles-Idle-f07-q34-b.jpg",
              "Achilles-Idle-seam-f60-f00-front.jpg", "Achilles-Idle-closeups.json", "Achilles-Idle-closeup.json",
              "Achilles-LungeAttack-f07-front.jpg", "Achilles-Idle-blender-sheet.jpg"):
        (tmp_path / n).write_bytes(b"")
    got = sorted(p.name for p in cc.label_files(tmp_path, "Achilles-Idle"))
    assert got == ["Achilles-Idle-closeups.json", "Achilles-Idle-f07-q34-b.jpg", "Achilles-Idle-f15-front.jpg",
                   "Achilles-Idle-f30-q34r.jpg", "Achilles-Idle-seam-f60-f00-front.jpg"]


def _png(p, patch=None):
    a = np.full((240, 120, 3), 61, dtype=np.uint8)
    a[40:200, 40:80] = 190
    if patch:
        a[patch[1]:patch[3], patch[0]:patch[2]] = 120
    Image.fromarray(a).save(p)


def test_seam_pair_same_and_different(tmp_path):
    _png(tmp_path / "n.png")
    _png(tmp_path / "z.png")
    m = cc.seam_pair(tmp_path / "n.png", tmp_path / "z.png", tmp_path / "pair.jpg", ("f60", "f00"))
    assert m["size_px"] == [240, 240] and m["max"] == 0 and m["diff_px"] == 0 and m["diff_bbox_px"] is None
    assert Image.open(tmp_path / "pair.jpg").size == (240, 240)
    _png(tmp_path / "z2.png", patch=(40, 100, 50, 110))
    m2 = cc.seam_pair(tmp_path / "n.png", tmp_path / "z2.png", tmp_path / "pair2.jpg", ("f60", "f00"))
    assert m2["diff_px"] == 100 and m2["diff_bbox_px"] == [40, 100, 49, 109]


def _args(**kw):
    d = dict(spec=None, clip=None, fbx=None, base=None, no_base=False, out=None, label=None)
    d.update(kw)
    return Namespace(**d)


def test_resolve_inputs_from_spec_seam_only_for_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "REPO", tmp_path)
    spec = {"ue_hero": "X", "run_dir": "a/run", "target": {"base_fbx": "a/bake/SM_X_H2_Base.fbx"},
            "clips": {"Idle": {"role": "idle", "frames": 60}, "LungeAttack": {"role": "oneshot", "frames": 14}}}
    sp = tmp_path / "x-h2anim.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    idle = cc.resolve_inputs(_args(spec=str(sp), clip="Idle"))
    assert idle["fbx"] == tmp_path / "a/run/export/AM_X_Idle.fbx" and idle["label"] == "X-Idle"
    assert idle["out"] == tmp_path / "a/run/preview/closeups-blender" and idle["seam_default"] == ("front", "q34")
    lunge = cc.resolve_inputs(_args(spec=str(sp), clip="LungeAttack", no_base=True))
    assert lunge["seam_default"] == () and lunge["base"] is None
    with pytest.raises(ValueError):
        cc.resolve_inputs(_args(spec=str(sp), clip="Walk"))
    f = cc.resolve_inputs(_args(fbx=str(tmp_path / "AM_King_Arthur_Idle.fbx"), out=str(tmp_path / "o")))
    assert f["label"] == "King-Arthur-Idle" and f["seam_default"] == ()


def test_main_refuses_without_shots_and_missing_files(tmp_path, capsys):
    assert cc.main(["--fbx", str(tmp_path / "AM_X_Idle.fbx"), "--out", str(tmp_path)]) == 1
    (tmp_path / "AM_X_Idle.fbx").write_bytes(b"x")
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"")
    assert cc.main(["--fbx", str(tmp_path / "AM_X_Idle.fbx"), "--out", str(tmp_path), "--blender", str(blender)]) == 1
    assert "нет кадров" in capsys.readouterr().err
