"""VS-3 CP-14 tests (plain Python, no UE): the card frame import plan of ue_import_card_media.py --frames (16 textures of
the CP-13 package, the 9-slice margins of its verification.json, x2 = twice x1, corner <= 13 px), G-TOKENS of the frame
PNGs (every opaque pixel within dE76 <= 3 of a token: card.navy, card.cream, state.pending, state.warning, card.glyph,
mark.keyline), the material builder contract, and the import reports once they exist.

  python -m pytest tools/art/cards/test_card_frames.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_card_face_material as MAT  # noqa: E402
import ue_import_card_media as M  # noqa: E402

TOKENS = json.loads((M.REPO / "docs/unreal/contracts/hud/hud-style-tokens.json").read_text(encoding="utf-8"))["colors"]


def token_hex(name: str) -> str:
    e = TOKENS[name]
    while "hex" not in e:
        e = TOKENS[e["alias"]]
    return e["hex"]


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def test_plan_sixteen_textures_with_the_cp13_margins():
    plan = M.plan_frames()
    assert M.check_frames(plan) == []
    assert len(plan) == 8 and sum(len(e["assets"]) for e in plan) == 16
    keys = {e["key"]: e for e in plan}
    assert set(keys) == {"card.frame.idle", "card.frame.hover", "card.frame.selected", "card.frame.warning",
                         "card.frame.flash", "card.frame.focus", "card.frame.mini", "card.frame.new"}
    assert keys["card.frame.idle"]["margins"] == {"x1": [11, 11, 11, 11], "x2": [21, 21, 21, 21]}
    assert keys["card.frame.selected"]["margins"]["x1"] == [13, 13, 13, 13]
    assert keys["card.frame.focus"]["sizes"]["x1"] == [468, 648]
    assert keys["card.frame.mini"]["sizes"] == {"x1": [48, 67], "x2": [96, 134]}
    assert keys["card.frame.new"]["nineSlice"] is False
    for e in plan:
        assert e["assets"]["x1"] == f"T_UmCardFrame_{e['state'].replace('-', '_')}_x1"
        assert e["files"]["x1"].startswith("art/imagegen/card-frame-v1-codex/vector/")


def test_frame_pngs_use_only_token_colours():
    # G-TOKENS (CP-14 p. 5): the edge hex equals the tokens (dE76 <= 3); the CP-13 palette of six tokens
    palette = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in (
        token_hex("card.navy"), token_hex("card.cream"), token_hex("state.pending"), token_hex("state.warning"),
        token_hex("card.glyph"), token_hex("mark.keyline"))], dtype=float)
    lab_palette = srgb_to_lab(palette)
    for e in M.plan_frames():
        for scale in ("x1", "x2"):
            rgba = np.asarray(Image.open(M.REPO / e["files"][scale]).convert("RGBA"), dtype=float)
            opaque = rgba[rgba[..., 3] == 255][:, :3]
            if not len(opaque):
                continue
            lab = srgb_to_lab(opaque)
            d = np.sqrt(((lab[:, None, :] - lab_palette[None, :, :]) ** 2).sum(-1)).min(axis=1)
            assert float(d.max()) <= 3.0, (e["state"], scale, float(d.max()))
            # the window is transparent (the scan shows through)
            if e["nineSlice"] and e["key"] != "card.frame.focus":
                h, w = rgba.shape[:2]
                assert rgba[h // 2, w // 2, 3] == 0


def test_material_builder_contract():
    info, errors = MAT.check()
    assert errors == []
    assert info["parameters"] == ["Desaturation", "Face", "Opacity", "UVRect"]


def test_reports_when_present():
    rep = M.FRAME_REPORT
    if rep.exists():
        r = json.loads(rep.read_text(encoding="utf-8"))
        assert r["count"] == 16 and len(r["frames"]) == 8
        assert all(t["asset"].startswith("/Game/S08/UI/Skins/CardFrame/T_UmCardFrame_") for f in r["frames"] for t in f["textures"])
    if MAT.REPORT.exists():
        r = json.loads(MAT.REPORT.read_text(encoding="utf-8"))
        assert r["ok"] and r["build"]["action"] in ("created", "rebuilt", "unchanged")
        if "params" in r["build"]:
            assert r["build"]["params"]["texture"] == ["Face"]
        ps = r["build"].get("stats", {}).get("psInstructions", 0)
        assert ps == 0 or ps <= MAT.BUDGET_PS_INSTRUCTIONS
