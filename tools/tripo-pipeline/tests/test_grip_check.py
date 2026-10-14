"""grip_check.py без Blender: разбор аргументов (форма «-- …» Blender и python --help), математика суставов и
кватернионов, итог summarize на фикстуре кадров, отказ вне Blender (код 2).

    python -B -m pytest -q tools/tripo-pipeline/tests/test_grip_check.py
"""
import math
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
TOOL = TESTS.parent / "anim" / "grip_check.py"
sys.path.insert(0, str(TESTS.parent / "anim"))
import grip_check as g  # noqa: E402


def test_parse_args_blender_form_and_defaults():
    a = g.parse_args(["blender", "-b", "--python", "grip_check.py", "--", "clip.fbx", "out.json"])
    assert (a.clip, a.out, a.side, a.base, a.shield_bone, a.weapon_suffix) == ("clip.fbx", "out.json", "R", None, None, None)
    a = g.parse_args(["blender", "--", "c.fbx", "o.json", "--side", "L", "--base", "b.fbx", "--shield-bone",
                      "arm_lower.L", "--weapon-suffix", "_Spear", "_Shaft", "--rest-only"])
    assert a.side == "L" and a.base == "b.fbx" and a.shield_bone == "arm_lower.L"
    assert a.weapon_suffix == ["_Spear", "_Shaft"] and a.rest_only and a.shield_min_dist_cm == 2.5


def test_parse_args_rejects_bad_values():
    with pytest.raises(SystemExit):
        g.parse_args(["blender", "--", "c.fbx", "o.json", "--side", "X"])
    with pytest.raises(SystemExit):
        g.parse_args(["blender", "--", "c.fbx", "o.json", "--shield-bone", "spine"])
    with pytest.raises(SystemExit):
        g.parse_args(["blender", "--", "c.fbx"])


def test_help_and_refusal_outside_blender():
    h = subprocess.run([sys.executable, str(TOOL), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert h.returncode == 0 and "--shield-bone" in h.stdout and "weapon_in_hand_deg" in h.stdout
    r = subprocess.run([sys.executable, str(TOOL), "--", "c.fbx", "o.json"], capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 2 and "Blender" in r.stderr


def test_quaternion_and_joint_math():
    half = math.sqrt(0.5)
    assert g.quat_angle_deg((1.0, 0, 0, 0)) == pytest.approx(0.0)
    assert g.quat_angle_deg((half, 0, 0, half)) == pytest.approx(90.0)
    assert g.quat_angle_deg((-half, 0, 0, -half)) == pytest.approx(90.0)  # q и -q — один поворот
    tw, sw = g.twist_swing_deg((half, 0, half, 0))  # 90° вокруг оси кости Y — чистый twist
    assert (tw, sw) == (90.0, 0.0)
    tw, sw = g.twist_swing_deg((half, half, 0, 0))  # 90° вокруг X — чистый swing
    assert (tw, sw) == (0.0, 90.0)
    assert g.joint_angle_deg((0, 0, 2), (0, 0, 1), (0, 0, 0)) == pytest.approx(180.0)
    assert g.joint_angle_deg((0, 0, 1), (0, 0, 0), (1, 0, 0)) == pytest.approx(90.0)
    assert g.joint_angle_deg((0, 0, 0), (0, 0, 0), (1, 0, 0)) == 180.0  # вырожденный сустав


def row(f, hand, wr, wl, elr, ell, kl, kr, tl, tr, butt=None, wp=0, sh=None, shp=None):
    return {"f": f, "weapon_in_hand_deg": hand, "wrist_R_deg": wr, "wrist_L_deg": wl, "elbow_R_deg": elr,
            "elbow_L_deg": ell, "elbow_R_offhinge_deg": 3.0 * f, "knee_L_deg": kl, "knee_R_deg": kr,
            "thigh_flex_L_deg": tl, "thigh_flex_R_deg": tr, "butt_below_top_cm": butt, "weapon_body_pairs": wp,
            "shield_vs_forearm_cm": sh, "shield_body_pairs": shp}


def test_summarize_fixture_frames():
    rows = [row(0, 0.0, 1.0, 0.5, 120.0, 140.0, 177.0, 176.0, 0.5, 0.4, None, 2, 0.0, 1),
            row(1, 0.02, 14.5, 0.8, 95.0, 150.0, 160.0, 170.0, 12.0, 3.0, 0.3, 5, 0.01, 4),
            row(2, 0.01, 6.0, 0.2, 130.0, 138.0, 175.0, 158.0, 2.0, 18.5, 0.1, 0, 0.004, 0)]
    s = g.summarize(rows, "R", {"top_cm": 5.81, "radius_cm": 15.0})
    assert s["frames"] == 3 and s["weapon_in_hand_max_deg"] == 0.02
    assert s["wrist_R_max_deg"] == 14.5 and s["wrist_L_max_deg"] == 0.8
    assert s["elbow_R_range"] == [95.0, 130.0] and s["elbow_L_range"] == [138.0, 150.0]
    assert s["knee_min_deg"] == 158.0 and s["thigh_flex_max_deg"] == 18.5
    assert s["butt_sink_max_cm"] == 0.3 and s["elbow_R_offhinge_max_deg"] == 6.0
    assert (s["weapon_body_pairs_rest"], s["weapon_body_pairs_max"]) == (2, 5)
    assert (s["shield_body_pairs_rest"], s["shield_body_pairs_max"], s["shield_vs_forearm_max_cm"]) == (1, 4, 0.01)
    assert (s["base_top_cm"], s["base_radius_cm"]) == (5.81, 15.0)


def test_summarize_without_weapon_or_frames():
    rows = [row(0, None, 1.0, 1.0, 170.0, 170.0, 178.0, 178.0, 0.0, 0.0, wp=None)]
    s = g.summarize(rows, "L")
    assert s["weapon_in_hand_max_deg"] is None and s["weapon_body_pairs_max"] is None
    assert "wrist_L_max_deg" in s and "base_top_cm" not in s
    assert g.summarize([], "R") == {"frames": 0}


# ------------------------------------------------------------------ C40 (2026-10-14): устойчивый верх подставки
def _quad(x0, y0, x1, y1, z, flip=False):
    q = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    return q[::-1] if flip else q


def test_polygon_faces_area_and_normal_by_winding():
    (z, a, nz), = g.polygon_faces([_quad(0, 0, 2, 1, 5.0)])
    assert (z, a, nz) == (5.0, 2.0, 1.0)
    (_z, a2, nz2), = g.polygon_faces([_quad(0, 0, 2, 1, 5.0, flip=True)])
    assert a2 == 2.0 and nz2 == -1.0  # изнанка вверх — не «смотрит вверх»
    wall = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]
    (_z, _a, nzw), = g.polygon_faces([wall])
    assert abs(nzw) < 1e-12
    assert g.polygon_faces([[(0, 0, 0), (1, 0, 0)], [(0, 0, 0), (1, 0, 0), (2, 0, 0)]]) == []  # вырожденные


def test_robust_base_top_ignores_a_small_bump():
    """Beowulf (C40): видимый верх 5,68 см, бугорок 3 мм до 6,00 см в несколько граней — верх 5,68, не 6,00."""
    top = [_quad(x, y, x + 1, y + 1, 5.68) for x in range(-5, 5) for y in range(-5, 5)]  # 100 см² верха
    bump = [_quad(0, 0, 0.2, 0.2, 6.0)]  # 0,04 см² на 6,00
    lower = [_quad(x, -7, x + 1, -6, 3.11) for x in range(-7, 7)]  # нижний ярус 14 см² (12 % граней вверх)
    walls = [[(0, 0, 5.68), (1, 0, 5.68), (1, 0, 6.0), (0, 0, 6.0)]]
    t = g.robust_base_top(g.polygon_faces(top + bump + lower + walls), 6.0)
    assert t["top"] == 5.68 and t["max_vertex"] == 6.0 and t["fallback"] is None
    assert t["up_faces"] == 115 and 0.0 < t["up_area_share"] < 1.0 and "перцентиль" in t["rule"]
    # без бугорка и нижнего яруса — тот же верх; одна плоскость — её высота
    assert g.robust_base_top(g.polygon_faces(top))["top"] == 5.68


def test_robust_base_top_two_tier_and_fallback():
    # нижний ярус больше верхнего, но верхний > 10 % площади вверх — верх всё равно верхний ярус
    upper = [_quad(x, y, x + 1, y + 1, 5.7) for x in range(-2, 2) for y in range(-2, 2)]   # 16
    lower = [_quad(x, y, x + 1, y + 1, 3.1) for x in range(-6, 6) for y in range(-6, -2)]  # 48
    assert g.robust_base_top(g.polygon_faces(upper + lower), 5.7)["top"] == 5.7
    # не выше максимума вершин (неточный центр грани)
    assert g.robust_base_top([(6.2, 1.0, 1.0)], 6.0)["top"] == 6.0
    # нет граней вверх — максимум вершин и пометка
    walls = [[(0, 0, 0), (1, 0, 0), (1, 0, 4.0), (0, 0, 4.0)]]
    fb = g.robust_base_top(g.polygon_faces(walls), 4.0)
    assert fb["top"] == 4.0 and fb["fallback"] and fb["up_faces"] == 0


def test_summarize_reports_max_vertex_top_only_when_given():
    rows = [row(0, 0.0, 1.0, 0.5, 120.0, 140.0, 177.0, 176.0, 0.5, 0.4)]
    s = g.summarize(rows, "R", {"top_cm": 5.687, "top_max_vertex_cm": 6.0, "radius_cm": 15.0})
    assert (s["base_top_cm"], s["base_top_max_vertex_cm"]) == (5.687, 6.0)
    assert "base_top_max_vertex_cm" not in g.summarize(rows, "R", {"top_cm": 5.81, "radius_cm": 15.0})
