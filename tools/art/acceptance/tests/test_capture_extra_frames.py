"""Добавочные кадры съёмки приёмки (пилот 2026-10-14): pose-04b (F77), pose-05 (F129), close-attack (F74).

Без Blender: кость атаки из заявки и флага, роли кадров, совместимость с validate_card (новые кадры не обязательны —
старые карточки проходят), помощники кадрирования _framing (портретная панель, ракурс по видимости).

    python -m pytest tools/art/acceptance/tests -q -p no:cacheprovider
"""
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import capture_acceptance_set as cap  # noqa: E402
import validate_card as vc  # noqa: E402
from _framing import ang_diff, best_visible_azimuth, panel_fit_scale, view_fit_scale  # noqa: E402

LESHEN_CARD = '''ASSET_ID: ASSET-ANCIENT-LESHEN-001
WEAPON_HAND: none
SIDE_VIEW: left
WEAPON_BONE: null                   # контракт weapon_bone null
WEAPON_SOCKET_BONE: "hand.R"        # сокет Weapon = когти правой кисти
DECISIONS:
  WEAPON_SOCKET_BONE: "delegated: удар когтями правой кисти"
'''


def test_card_scalars_quotes_null_comments():
    v = cap.card_scalars(LESHEN_CARD)
    assert v == {"WEAPON_HAND": "none", "WEAPON_SOCKET_BONE": "hand.R"}  # первое вхождение, не строка DECISIONS
    v = cap.card_scalars("WEAPON_HAND: right\nWEAPON_SOCKET_BONE: null  # оружие\n")
    assert v == {"WEAPON_HAND": "right", "WEAPON_SOCKET_BONE": None}


def test_resolve_attack_flag_and_card():
    card = cap.card_scalars(LESHEN_CARD)
    assert cap.resolve_attack(None, card) == ("hand.R", "asset-card WEAPON_HAND none → WEAPON_SOCKET_BONE")
    assert cap.resolve_attack("none", card) == (None, "--attack-bone none")
    assert cap.resolve_attack("foot.R", {"WEAPON_HAND": "right"}) == ("foot.R", "--attack-bone")
    assert cap.resolve_attack(None, {"WEAPON_HAND": "right", "WEAPON_SOCKET_BONE": None}) == (None, None)
    assert cap.resolve_attack(None, {"WEAPON_HAND": "none", "WEAPON_SOCKET_BONE": None}) == (None, None)
    assert cap.resolve_attack(None, None) == (None, None)


def test_find_asset_card_walks_up(tmp_path):
    asset = tmp_path / "ASSET-X-001"
    run = asset / "20261014-h2-lookdev-r3" / "export"
    run.mkdir(parents=True)
    assert cap.find_asset_card(run) is None
    (asset / "asset-card.yaml").write_text("WEAPON_HAND: none\n", encoding="utf-8")
    assert cap.find_asset_card(run) == asset / "asset-card.yaml"


def test_new_frames_are_additive_for_validate_card():
    """Новые кадры не входят в обязательный набор validate_card: карточки наборов до 2026-10-14 валидны."""
    required = set(vc.MODEL_FRAMES) | set(vc.POSE_FRAMES)
    for name in cap.RIG_EXTRA + [cap.ATTACK_FRAME]:
        assert name not in required
        assert cap.STALE.fullmatch(name)  # повторный прогон в тот же --out их удаляет
    assert set(cap.FIXED + cap.RIG_ONLY) <= required | {"uv-layout.png"}  # прежние имена не тронуты
    assert cap.CROPPED <= set(cap.RIG_EXTRA)


def test_roles_cover_every_frame_name():
    names = (cap.FIXED + cap.RIG_ONLY + cap.RIG_EXTRA + [cap.ATTACK_FRAME, "uv-layout.png", "sheet.png", "tone.json",
                                                          "frames.json"] + list(cap.COMPARE.values()))
    missing = [n for n in names if not cap.ROLES.get(n)]
    assert missing == []
    assert "F129" in cap.ROLES["pose-05.jpg"] and "F77" in cap.ROLES["pose-04b.jpg"] and "F74" in cap.ROLES[cap.ATTACK_FRAME]
    assert set(cap.PANELS) == {"close-hands-", "close-attack-"}


def test_panel_fit_scale_portrait():
    """Портретная панель 1:2: высокая кисть с когтями вписывается по высоте, широкая — по ширине (половина высоты)."""
    tall = np.array([[0, 0, -0.1], [0, 0, 0.1], [0.02, 0, 0], [-0.02, 0, 0]])  # 0,2 м в высоту, 0,04 в ширину
    assert panel_fit_scale(tall, (0, 0, 0), 0, 0, margin=1.0) == pytest.approx(0.2)
    wide = np.array([[-0.1, 0, 0], [0.1, 0, 0], [0, 0, 0.01], [0, 0, -0.01]])  # 0,2 м в ширину
    assert panel_fit_scale(wide, (0, 0, 0), 0, 0, margin=1.0) == pytest.approx(0.4)  # ширина панели = 0,5 высоты
    assert panel_fit_scale(tall, (0, 0, 0), 0, 0) == pytest.approx(0.2 * 1.15)
    assert view_fit_scale(wide, (0, 0, 0), 0, 0, margin=1.0) == pytest.approx(0.2)  # квадрат — без удвоения


def test_best_visible_azimuth_excludes_main_view_and_prefers_front():
    vis = {0: 0.245, 30: 0.19, 60: 0.11, 90: 0.30, 120: 0.18, 150: 0.17, 180: 0.15, 210: 0.13, 240: 0.12,
           270: 0.16, 300: 0.18, 330: 0.25}
    # Achilles r3: pose-04 az 70; 90 (0,30) ближе 60° к 70 — не берётся; лучший из остальных — 330
    assert best_visible_azimuth(vis, 70) == (330, 0.25)
    assert best_visible_azimuth({30: 0.4, 330: 0.4, 180: 0.4}, 100, 60) == (30, 0.4)  # равенство → ближе к фронту
    assert best_visible_azimuth({60: 0.9, 90: 0.9}, 70) == (None, None)
    assert ang_diff(350, 10) == 20 and ang_diff(70, 250) == 180
