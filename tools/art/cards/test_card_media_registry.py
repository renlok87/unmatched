"""CP-02 tests (plain Python, no UE): the key registry unreal/Unmatched/Config/Cards/S08CardMedia.json written by
tools/art/cards/ue_import_card_media.py, and the UE import report art/cards-v1/ue-import-report.json once it exists.

  python -m pytest tools/art/cards/test_card_media_registry.py -q
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_import_card_media as M  # noqa: E402

REG = json.loads(M.REGISTRY.read_text(encoding="utf-8"))
ENTRIES = REG["entries"]
MVP_CARDS = json.loads((M.REPO / "art/imagegen/mvp-v1/reused-cardart.json").read_text(encoding="utf-8"))["cards"]


def test_schema_and_counts():
    assert REG["schema"] == M.REGISTRY_SCHEMA == "unmatched.s08-card-media/1"
    assert REG["counts"] == {"card": 54, "back": 2, "portrait": 4}
    assert len(ENTRIES) == 60
    ids = [(e["key"], e.get("lang", "")) for e in ENTRIES]
    assert len(set(ids)) == len(ids)
    for e in ENTRIES:
        assert set(e) >= {"key", "kind", "object", "src", "pad", "uv", "sha256"}
        assert re.fullmatch(r"[0-9a-f]{64}", e["sha256"])
        assert ("lang" in e) == (e["kind"] == "card")


def test_uv_is_src_over_pad_and_pad_is_power_of_two():
    for e in ENTRIES:
        (sw, sh), (pw, ph) = e["src"], e["pad"]
        assert pw == M.pow2(sw) and ph == M.pow2(sh), e["key"]
        assert pw & (pw - 1) == 0 and ph & (ph - 1) == 0
        assert e["uv"] == [round(sw / pw, 6), round(sh / ph, 6)]
        assert abs(e["uv"][0] - sw / pw) < 1e-5 and abs(e["uv"][1] - sh / ph) < 1e-5


def test_every_mvp_key_in_both_languages():
    cards = {(e["key"], e["lang"]): e for e in ENTRIES if e["kind"] == "card"}
    assert len(MVP_CARDS) == 27
    for c in MVP_CARDS:
        key = c["stableContentKey"]
        ru, en = cards[(key, "ru")], cards[(key, "en")]
        assert ru["src"] == [287, 398] and ru["pad"] == [512, 512]
        assert en["src"] == [250, 349] and en["pad"] == [256, 512]
        hero, card = key.split(":")
        name = f"T_Card_{hero.replace('-', '_')}_{card.replace('-', '_')}_RU"
        assert ru["object"] == f"/Game/S08/UI/Cards/{hero.replace('-', '_')}/{name}.{name}"


def test_backs_and_portraits():
    backs = {e["key"]: e for e in ENTRIES if e["kind"] == "back"}
    assert set(backs) == {"back:king-arthur", "back:medusa"}
    assert all(b["src"] == [768, 1051] and b["pad"] == [1024, 2048] for b in backs.values())
    assert backs["back:medusa"]["object"] == "/Game/S08/UI/CardBacks/T_CardBack_medusa.T_CardBack_medusa"
    ports = {e["key"]: e for e in ENTRIES if e["kind"] == "portrait"}
    assert set(ports) == set(M.DISC_START)
    assert ports["portrait:king-arthur"]["pad"] == [1024, 1024]
    assert ports["portrait:medusa"]["pad"] == [512, 512]
    assert ports["portrait:medusa:harpies"]["object"].endswith("/T_Portrait_medusa_harpies.T_Portrait_medusa_harpies")
    for p in ports.values():
        cx, cy, d = p["disc"]
        assert 0 < cx < 1 and 0 < cy < 1 and 0 < d <= 1
    # CP-09...CP-12: the accepted CP-07 crops (variant B) replace the ВР-CP01 start numbers
    assert ports["portrait:king-arthur"]["disc"] == [0.49, 0.39, 0.54]
    assert ports["portrait:medusa"]["disc"] == [0.44, 0.29, 0.5]
    assert ports["portrait:king-arthur:merlin"]["disc"] == [0.5, 0.48, 0.69]
    assert ports["portrait:medusa:harpies"]["disc"] == [0.5, 0.48, 0.69]
    assert all(p["discSource"] == M.CROPS_SOURCE for p in ports.values())


def test_discs_are_the_cp07_crops():
    """CP-09...CP-12: every registry disc is the CP-07 portrait-crops.json record (cx, cy, d), nothing else."""
    crops = json.loads(M.CROPS.read_text(encoding="utf-8"))
    assert set(crops) == {"king-arthur", "medusa", "king-arthur/merlin", "medusa/harpies"}
    ports = {e["key"]: e for e in ENTRIES if e["kind"] == "portrait"}
    for key, c in crops.items():
        assert ports["portrait:" + key.replace("/", ":")]["disc"] == [c["cx"], c["cy"], c["d"]], key
    # the source circle in px and the magnification of the CP-09...CP-12 rows at 1080p 100 % (1 px per su)
    src_px = {k: ports[k]["src"][0] * ports[k]["disc"][2] for k in ports}
    assert abs(src_px["portrait:king-arthur"] - 432.0) < 1e-6      # 0.54 x 800
    assert abs(src_px["portrait:medusa"] - 201.0) < 1e-6           # 0.50 x 402
    assert abs(src_px["portrait:medusa:harpies"] - 88.32) < 1e-6   # 0.69 x 128
    # the baked hero-colour ring of the sidekick avatars starts at radius 50 of 64 px (ВР-CP02): the circle stays inside
    for k in ("portrait:king-arthur:merlin", "portrait:medusa:harpies"):
        cx, cy, d = ports[k]["disc"]
        assert (max(abs(cx - 0.5), abs(cy - 0.5)) + d / 2) * 128 < 50.0, k


def test_missing_crops_keep_the_start_numbers(tmp_path):
    items = M.plan_from_convert_report()
    reg = M.build_registry(items, crops=M.load_crops(tmp_path / "none.json"))
    ports = {e["key"]: e for e in reg["entries"] if e["kind"] == "portrait"}
    assert ports["portrait:king-arthur"]["disc"] == [0.49, 0.43, 0.60]
    assert "CP-07" not in reg["decisions"]


def test_paths_only_under_cooked_s08_ui():
    for e in ENTRIES:
        assert e["object"].startswith(("/Game/S08/UI/Cards/", "/Game/S08/UI/CardBacks/", "/Game/S08/UI/Portraits/"))
        pkg, name = e["object"].split(".")
        assert pkg.rsplit("/", 1)[1] == name and "-" not in name


def test_registry_matches_the_cp01_report():
    items = M.plan_from_convert_report()
    assert M.registry_text(M.build_registry(items)) == M.REGISTRY.read_text(encoding="utf-8")
    conv = json.loads(M.CONVERT_REPORT.read_text(encoding="utf-8"))
    out_sha = {f["out"]["sha256"] for f in conv["files"]}
    assert {e["sha256"] for e in ENTRIES} == out_sha


def test_modes_select():
    items = M.plan_from_convert_report()
    assert len(M.select(items, "all", None)) == 60
    assert len(M.select(items, "portraits", None)) == 4
    assert len(M.select(items, "backs", None)) == 2
    assert len(M.select(items, "cards", "medusa")) == 22
    assert len(M.select(items, "cards", "king-arthur")) == 32
    assert M.select(items, "frames", None) == []
    with pytest.raises(RuntimeError):
        M.select(items, "cards", "nobody")
    args = M.parse_args(["--cards", "medusa"])
    assert (args.mode, args.hero) == ("cards", "medusa")
    assert M.parse_args([]).mode == "all"


def test_missing_png_names_the_key(tmp_path):
    items = M.select(M.plan_from_convert_report(), "backs", None)
    errors = M.verify_sources(items, tmp_path)
    assert len(errors) == 2 and errors[0].startswith("back:king-arthur: PNG missing")


@pytest.mark.skipif(not M.REPORT.is_file(), reason="UE import not run in this checkout")
def test_ue_import_report_acceptance():
    rep = json.loads(M.REPORT.read_text(encoding="utf-8"))
    assert rep["count"] == 60 and rep["allOk"] is True
    by = {(t["key"], t.get("lang", "")): t for t in rep["textures"]}
    for e in ENTRIES:
        t = by[(e["key"], e.get("lang", ""))]
        s = t["settings"]
        assert t["sourceSha256"] == e["sha256"]
        assert "PAD_TO_POWER_OF_TWO" in s["powerOfTwoMode"] and s["paddingColor"] == "#061623 a0"
        assert s["mipsExpected"] > 1 and "TMGS_SIMPLE_AVERAGE" in s["mipGen"]
        assert "TF_TRILINEAR" in s["filter"] and "TEXTUREGROUP_UI" in s["lodGroup"]
        assert s["srgb"] is True and "TC_BC7" in s["compression"] and s["neverStream"] is True
        assert s["size"] == e["pad"] and s["srcSize"] == e["src"]
    assert t["asset"].startswith("/Game/S08/UI/")
    # budget of the card: ~21.5 MB in the pak
    assert 20e6 < rep["resourceBytesBC7Total"] < 23e6
