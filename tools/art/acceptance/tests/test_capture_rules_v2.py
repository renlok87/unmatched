"""Правила съёмки v2 (проверочный прогон Beowulf 2026-10-14, пакет B): C22 отсечение задних граней, C30 ракурс
close-hands по видимости кисти, C36 UV без оболочки cloth_shell. Без Blender: выбор правил (профиль H2 прогона или
заявка), помощники _framing; съёмка Blender на игрушке — тест h2_bake test_skill_check_b (shell_copy_mask на выходе
add_cloth_shell).

    python -m pytest tools/art/acceptance/tests -q -p no:cacheprovider
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import capture_acceptance_set as cap  # noqa: E402
from _framing import best_panel_azimuth, shell_copy_mask, zero_uv_area_mask  # noqa: E402

REPO = HERE.parents[3]
BEOWULF_T4 = "art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2-bake-h2-t4.json"
MEDUSA = "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"


def lookdev_run(root, src_profile):
    (root / "export").mkdir(parents=True)
    fbx = root / "export" / "SK_X_H2LD.fbx"
    fbx.write_bytes(b"fbx")
    (root / "reports").mkdir()
    (root / "reports" / "run-manifest.json").write_text(json.dumps({"source_profile": {"path": src_profile}}),
                                                        encoding="utf-8")
    return fbx


def test_rules_from_the_run_profile(tmp_path):
    assert cap.detect_rules(lookdev_run(tmp_path / "b", BEOWULF_T4))[0] == 2  # Beowulf: profile_version 2
    assert cap.detect_rules(lookdev_run(tmp_path / "m", MEDUSA))[0] == 1  # Medusa: the MVP, version 1
    # the committed Beowulf look-dev run (run-manifest -> source_profile) and the Achilles pilot run
    beo = REPO / "art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2-lookdev-t5/export/SK_Beowulf_H2LD.fbx"
    ach = REPO / "art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2-lookdev-r3/export/SK_Achilles_H2LD.fbx"
    if beo.parent.parent.joinpath("reports", "run-manifest.json").is_file():
        assert cap.detect_rules(beo)[0] == 2
    if ach.parent.parent.joinpath("reports", "run-manifest.json").is_file():
        assert cap.detect_rules(ach)[0] == 1


def test_rules_from_the_card_and_unknown(tmp_path):
    fbx = tmp_path / "SK_Prop.fbx"
    fbx.write_bytes(b"fbx")
    assert cap.detect_rules(fbx, "ASSET_ID: ASSET-ANGEL-001\n") == (1, "asset-card ASSET_ID ASSET-ANGEL-001")
    assert cap.detect_rules(fbx, "ASSET_ID: ASSET-BEOWULF-001\nWEAPON_HAND: right\n")[0] == 2
    assert cap.detect_rules(fbx)[0] is None  # no profile, no card: the old frames


def test_best_panel_azimuth_keeps_a_visible_default():
    assert best_panel_azimuth({35: 0.62, 210: 0.95}, 35) == (35, 0.62, False)
    # Beowulf hand.L behind the shield from az 35: the inside of the shield arm wins; a tie goes to the nearer angle
    assert best_panel_azimuth({35: 0.08, 0: 0.2, 210: 0.81, 240: 0.81}, 35) == (240, 0.81, True)
    assert best_panel_azimuth({-35: 0.0, 180: 0.5, 240: 0.5}, -35) == (240, 0.5, True)
    assert best_panel_azimuth({35: 0.3, 90: 0.1}, 35) == (35, 0.3, False)  # nothing better: the default stays


def sheet():
    uv = np.array([[[0, 0], [1, 0], [0, 1]], [[1, 0], [1, 1], [0, 1]]], float) * 0.1
    co = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[1, 0, 0], [1, 1, 0], [0, 1, 0]]], float) * 0.1
    return uv, co


def test_shell_copy_mask_pairs_only_close_reversed_copies():
    uv, co = sheet()
    copy_uv, copy_co = uv[:, ::-1], co[:, ::-1] - np.array([0, 0, 0.0003])  # П3-3: reversed winding, 0.3 mm inward
    bridge_uv = np.array([[[0.1, 0], [0, 0], [0, 0]]])
    bridge_co = np.array([[[0.1, 0, 0], [0, 0, 0], [0, 0, -0.0003]]])
    t_uv = np.concatenate([uv, copy_uv, bridge_uv])
    t_co = np.concatenate([co, copy_co, bridge_co])
    assert shell_copy_mask(t_uv, t_co).tolist() == [False, False, True, True, False]
    assert zero_uv_area_mask(t_uv).tolist() == [False, False, False, False, True]
    far = copy_co + np.array([0, 0, 0.05])  # a real UV overlap 5 cm away is not a shell copy
    assert not shell_copy_mask(np.concatenate([uv, copy_uv]), np.concatenate([co, far])).any()
    same = uv.copy()  # a duplicate with the same winding is not a copy either
    assert not shell_copy_mask(np.concatenate([uv, same]), np.concatenate([co, co])).any()
    assert shell_copy_mask(np.zeros((0, 3, 2)), np.zeros((0, 3, 3))).tolist() == []
