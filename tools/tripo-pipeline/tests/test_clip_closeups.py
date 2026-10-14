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


# ------------------------------------------------- C43/C45 (2026-10-14): стандартный список кадров по роли клипа
def test_parse_shots_frame_rules_height_sizes_and_lists():
    s = cc.parse_shots("armR:q34b:@arm_upper.R:h0.33;last:topb:@head:h0.33;mid:q34:fig:auto")
    assert [x["frame"] for x in s] == ["armR", "last", "mid"]
    assert s[0]["size_cm"] is None and s[0]["size_h"] == 0.33 and "size_h" not in s[2]
    assert s[1]["view"] == "topb"
    assert cc.parse_shots(["7:q34:fig:auto", " gripL:q34l:@hand.L:h0.22 "])[1]["frame"] == "gripL"
    for bad in ("armX:q34:fig:auto", "x7:q34:fig:auto", "7:q34:@head:h0", "7:q34:@head:h3", "7:q34:@head:hx"):
        with pytest.raises(ValueError):
            cc.parse_shots(bad)
    # прежние формы — прежний результат (числа, без size_h)
    assert cc.parse_shots("7:q34:7.16,-9.52,33.7:18") == [
        {"frame": 7, "view": "q34", "centre": {"kind": "arm_cm", "value": [7.16, -9.52, 33.7]}, "size_cm": 18.0}]


def test_default_shots_by_role_and_side():
    for role in cc.ROLES:
        lst = cc.default_shots(role, "R", True)
        shots = cc.parse_shots(lst)  # каждая строка разбирается
        views = {(s["frame"], s["view"], s["centre"].get("bone")) for s in shots}
        # со спины 3/4 на кадре наибольшего поворота плеча каждой руки (срез рукава, C43; F129)
        assert ("armR", "q34b", "arm_upper.R") in views and ("armL", "q34bl", "arm_upper.L") in views
        # ворот и затылок сзади и сзади сверху (провал ворота, C61) и кулак при повороте оружия
        assert ("armR", "back", "head") in views and ("armR", "topb", "head") in views
        assert ("gripR", "q34r", "hand.R") in views
    term = {(s["frame"], s["view"]) for s in cc.parse_shots(cc.default_shots("terminal"))}
    assert {("last", "back"), ("last", "topb"), ("last", "q34"), ("mid", "q34b")} <= term
    assert ("mid", "q34") in {(s["frame"], s["view"]) for s in cc.parse_shots(cc.default_shots("idle"))}
    left = cc.default_shots("oneshot", "L", False)
    assert "armL:q34bl:@arm_upper.L:h0.33" in left and not any(x.startswith("grip") for x in left)
    with pytest.raises(ValueError):
        cc.default_shots("walk")
    with pytest.raises(ValueError):
        cc.default_shots("idle", "X")


class _FakeBlender:
    """Подмена subprocess.run обёртки: читает cfg, переводит правила кадра в числа (mid = 5, last = 10, arm/grip = 3),
    называет кадры name_shots и пишет PNG и render.json, как _clip_closeups_blender.py."""

    def __init__(self):
        self.cfg = None

    def __call__(self, cmd, **kw):
        from types import SimpleNamespace

        cfg = json.loads(Path(cmd[-1]).read_text(encoding="utf-8"))
        self.cfg = cfg
        work = Path(cfg["work_dir"])
        (work / "raw").mkdir(parents=True, exist_ok=True)
        shots, tokens = [dict(s) for s in cfg["shots"]], {}
        for s in shots:
            if isinstance(s["frame"], str):
                f = {"mid": 5, "last": 10}.get(s["frame"], 3)
                tokens[s["frame"]] = {"frame": f, "rule": s["frame"]}
                s["frame_rule"], s["frame"] = s["frame"], f
        cc.name_shots(cfg["label"], shots)
        meta = []
        for s in shots:
            Image.new("RGB", (8, 8), (90, 90, 90)).save(work / "raw" / (s["name"] + ".png"))
            m = {"name": s["name"], "frame": s["frame"], "view": s["view"], "centre_arm_cm": [0.0, 0.0, 30.0],
                 "size_cm": 16.0}
            if s.get("frame_rule"):
                m["frame_rule"] = s["frame_rule"]
            meta.append(m)
        look = {"engine": "BLENDER_WORKBENCH"}
        if cfg["look"]["backface_culling"]:
            look["backface_culling"] = True
        info = {"blender": "5.2", "frame_start": 1, "frame_end": 11, "last_frame": 10, "fps": 24, "shots": meta,
                "seam": None, "look": look, "frame_tokens": tokens}
        (work / "render.json").write_text(json.dumps(info), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="CLOSEUPS_OK", stderr="")


def _fake_env(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "REPO", tmp_path)
    spec = {"ue_hero": "X", "run_dir": "a/run", "target": {"base_fbx": "a/bake/SM_X_H2_Base.fbx"},
            "weapon": {"bone": "weapon.R", "side": "R"},
            "clips": {"DeathSettle": {"role": "terminal", "frames": 10}, "Idle": {"role": "idle", "frames": 60}}}
    sp = tmp_path / "x-h2anim.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    for p in ("a/run/export/AM_X_DeathSettle.fbx", "a/run/export/AM_X_Idle.fbx", "a/bake/SM_X_H2_Base.fbx"):
        (tmp_path / p).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / p).write_bytes(b"fbx")
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"")
    fake = _FakeBlender()
    monkeypatch.setattr(cc.subprocess, "run", fake)
    return sp, blender, fake


def test_main_default_shots_culling_and_repeat(tmp_path, monkeypatch):
    sp, blender, fake = _fake_env(tmp_path, monkeypatch)
    out = tmp_path / "o"
    assert cc.main(["--spec", str(sp), "--clip", "DeathSettle", "--default-shots", "--out", str(out),
                    "--blender", str(blender)]) == 0
    assert fake.cfg["look"] == {"backface_culling": True} and fake.cfg["label"] == "X-DeathSettle"
    assert [s["frame"] for s in fake.cfg["shots"]][:5] == ["armR", "armL", "armR", "armR", "gripR"]
    rep = json.loads((out / "X-DeathSettle-closeups.json").read_text(encoding="utf-8"))
    assert rep["default_shots"]["role"] == "terminal" and rep["default_shots"]["side"] == "R"
    assert rep["default_shots"]["list"] == cc.default_shots("terminal", "R", True)
    assert rep["look"]["backface_culling"] is True and rep["frame_tokens"]["last"]["frame"] == 10
    names = [s["name"] for s in rep["shots"]]
    assert "X-DeathSettle-f03-q34b" in names and "X-DeathSettle-f10-topb" in names
    assert "X-DeathSettle-f03-back" in names and len(names) == len(set(names))
    assert all((out / (n + ".jpg")).is_file() for n in names)
    # повтор --shots-from: те же числа, то же отсечение, без списка по умолчанию
    assert cc.main(["--spec", str(sp), "--clip", "DeathSettle", "--shots-from", str(out / "X-DeathSettle-closeups.json"),
                    "--out", str(out), "--blender", str(blender)]) == 0
    assert fake.cfg["look"] == {"backface_culling": True}
    assert all(isinstance(s["frame"], int) for s in fake.cfg["shots"])
    rep2 = json.loads((out / "X-DeathSettle-closeups.json").read_text(encoding="utf-8"))
    assert "default_shots" not in rep2 and [s["name"] for s in rep2["shots"]] == names


def test_main_without_new_flags_keeps_the_old_look(tmp_path, monkeypatch):
    sp, blender, fake = _fake_env(tmp_path, monkeypatch)
    out = tmp_path / "o"
    assert cc.main(["--spec", str(sp), "--clip", "Idle", "--shots", "15:q34:fig:auto", "--no-seam", "--out", str(out),
                    "--blender", str(blender)]) == 0
    assert fake.cfg["look"] == {"backface_culling": False}
    rep = json.loads((out / "X-Idle-closeups.json").read_text(encoding="utf-8"))
    assert "backface_culling" not in rep["look"] and "default_shots" not in rep and "frame_tokens" not in rep
    assert [s["name"] for s in rep["shots"]] == ["X-Idle-f15-q34"]
    assert cc.main(["--spec", str(sp), "--clip", "Idle", "--default-shots", "--backface-culling", "off", "--no-seam",
                    "--out", str(out), "--blender", str(blender)]) == 0
    assert fake.cfg["look"] == {"backface_culling": False}


def test_main_default_shots_needs_a_role(tmp_path, capsys):
    (tmp_path / "AM_X_Hit.fbx").write_bytes(b"x")
    assert cc.main(["--fbx", str(tmp_path / "AM_X_Hit.fbx"), "--out", str(tmp_path), "--default-shots"]) == 1
    assert "--role" in capsys.readouterr().err
