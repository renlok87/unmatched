"""VS-3 CP-03...CP-06 tests (plain Python, no UE): the decks of King Arthur and Medusa against the registry - the keys of
the backend content (S01 capture of the content API = gameDeckLists), 16 + 11 cards, 30 copies each, every card in RU and
EN, the two original backs; the RU-name part of the import report (ВР-CP16).

  python -m pytest tools/art/cards/test_card_decks.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import card_deck_names as N  # noqa: E402
import ue_import_card_media as M  # noqa: E402

REG = json.loads(M.REGISTRY.read_text(encoding="utf-8"))
CARDS = {(e["key"], e["lang"]): e for e in REG["entries"] if e["kind"] == "card"}
BACKS = {e["key"]: e for e in REG["entries"] if e["kind"] == "back"}


def test_deck_keys_are_the_backend_decks():
    for hero, unique in (("king-arthur", 16), ("medusa", 11)):
        deck = N.s01_cards(hero)
        assert len(deck) == unique
        assert sum(c["count"] for c in deck) == 30
        keys = {c["key"] for c in deck}
        reg_keys = {k for (k, _lang) in CARDS if k.startswith(hero + ":")}
        assert keys == reg_keys, sorted(keys ^ reg_keys)
        for k in keys:
            assert (k, "ru") in CARDS and (k, "en") in CARDS


def test_feint_and_regroup_are_two_cards_each():
    # CP-03 / CP-04 'dont': Arthur's Feint / Regroup (boost 1) are not Medusa's (boost 2) - separate keys and scans
    for name in ("feint", "regroup"):
        a, m = CARDS[(f"king-arthur:{name}", "ru")], CARDS[(f"medusa:{name}", "ru")]
        assert a["object"] != m["object"] and a["sha256"] != m["sha256"]


def test_backs_per_hero():
    assert set(BACKS) == {"back:king-arthur", "back:medusa"}
    for b in BACKS.values():
        assert b["src"] == [768, 1051] and b["pad"] == [1024, 2048]
        assert b["object"].startswith("/Game/S08/UI/CardBacks/T_CardBack_")
    # ВР-VS2-CP-03: 5 px a side of 768 = 1.30 % <= 1.4 %
    assert 2 * 5 / 768 <= 0.014


def test_ru_names_section():
    sec = N.names_section()
    assert sec["count"] == 27
    assert sec["copies"] == {"king-arthur": 30, "medusa": 30}
    kinds = {}
    for d in sec["discrepancies"]:
        kinds.setdefault(d["kind"], []).append(d["key"])
    # the scan of Second Shot prints another name than the data / scrape (ВР-CP16)
    assert "medusa:second-shot" in kinds.get("scan-differs", [])
    if N.db_snapshot() is not None:
        # the reference DB snapshot: Card.nameRu holds the EN text for all 27 MVP cards
        assert len(kinds.get("nameRu-is-en", [])) == 27
    if "no-ru-in-scrape" in kinds:
        # GAP-016: King Arthur has RU titles only for Feint and Regroup in the scrape
        assert sorted(k for k in kinds["no-ru-in-scrape"] if k.startswith("king-arthur:")) == sorted(
            k for k in N.SCAN_RU if k.startswith("king-arthur:"))
    for c in sec["cards"]:
        assert "nameRuScan" not in c or c["key"] in N.SCAN_RU


def test_import_report_lists_the_names():
    rep = json.loads(M.REPORT.read_text(encoding="utf-8"))
    assert rep["ruNames"]["count"] == 27
    assert any(d["key"] == "medusa:second-shot" and d["kind"] == "scan-differs" for d in rep["ruNames"]["discrepancies"])
