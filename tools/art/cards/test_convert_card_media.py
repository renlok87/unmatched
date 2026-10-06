"""CP-01 tests: tools/art/cards/convert_card_media.py on the real local scrape (skipped when it is absent).

  python -m pytest tools/art/cards/test_convert_card_media.py -q
Every run writes into tmp_path only (outputs and report); the scrape is read, never changed (the wrong-sha case
corrupts a temporary COPY of one scan).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convert_card_media as C  # noqa: E402

SCRAPED = C.scraped_root(None)
pytestmark = pytest.mark.skipif(not (SCRAPED / "images" / "decks").is_dir(),
                                reason=f"no local scrape at {SCRAPED} (gitignored, ENV-U3)")


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    out = tmp_path_factory.mktemp("ue-media")
    report = out / "report.json"
    res = C.run(SCRAPED, out, report, db=False)
    return out, report, res


def test_sixty_files_all_pixel_equal(converted):
    out, report, res = converted
    assert res["count"] == 60
    assert res["counts"] == {"avatar": 2, "back": 2, "card": 54, "sidekick": 2}
    assert res["allPixelEqual"] is True
    assert all(e["pixelEqual"] and e["maxAbsDelta"] == 0 for e in res["files"])
    assert res["registry"]["cards"] == 27
    assert json.loads(report.read_text(encoding="utf-8"))["count"] == 60


def test_card_sources_match_the_registry(converted):
    _, _, res = converted
    reg = json.loads(C.REGISTRY.read_text(encoding="utf-8"))
    want = {f"{c['stableContentKey']}.{lang}": c[lang]["sha256"] for c in reg["cards"] for lang in ("ru", "en")}
    got = {e["key"]: e["in"]["sha256"] for e in res["files"] if e["kind"] == "card"}
    assert got == want


def test_sizes_and_names(converted):
    out, _, res = converted
    by_kind = {}
    for e in res["files"]:
        by_kind.setdefault(e["kind"], []).append(e)
        png = out / e["out"]["path"]
        with Image.open(png) as im:
            assert im.format == "PNG" and im.mode == "RGBA"
            assert list(im.size) == e["size"] == e["outSize"]
    ru = [e for e in by_kind["card"] if e["key"].endswith(".ru")]
    en = [e for e in by_kind["card"] if e["key"].endswith(".en")]
    assert len(ru) == len(en) == 27
    assert all(e["size"] == [287, 398] for e in ru)
    assert all(e["size"] == [250, 349] for e in en)
    dash = next(e for e in en if e["key"] == "medusa:dash.en")
    assert dash["in"]["format"] == "webp"
    sizes = {e["out"]["path"]: e["size"] for e in res["files"] if e["kind"] != "card"}
    assert sizes == {"avatars/king-arthur.png": [800, 800], "avatars/medusa.png": [402, 402],
                     "sidekicks/king-arthur-merlin.png": [128, 128], "sidekicks/medusa-harpies.png": [128, 128],
                     "backs/king-arthur.png": [768, 1051], "backs/medusa.png": [768, 1051]}
    assert len(list((out / "cards" / "medusa").glob("*.png"))) == 22
    assert len(list((out / "cards" / "king-arthur").glob("*.png"))) == 32


def test_pixels_equal_decoded_source(converted):
    out, _, res = converted
    for e in res["files"][::7] + [f for f in res["files"] if f["kind"] != "card"]:
        src = C.scrape_path(SCRAPED, e["in"]["path"])
        with Image.open(src) as a, Image.open(out / e["out"]["path"]) as b:
            assert np.array_equal(np.asarray(a.convert("RGBA")), np.asarray(b.convert("RGBA"))), e["key"]


def test_rerun_is_a_noop(converted):
    out, report, _ = converted
    before = report.read_bytes()
    mtimes = {p: p.stat().st_mtime_ns for p in out.rglob("*.png")}
    res = C.run(SCRAPED, out, report, db=False)
    assert res["_run"]["actions"] == {"written": 0, "unchanged": 60}
    assert report.read_bytes() == before
    assert {p: p.stat().st_mtime_ns for p in out.rglob("*.png")} == mtimes


def _copy_scrape(dst: Path) -> None:
    reg = json.loads(C.REGISTRY.read_text(encoding="utf-8"))
    rels = [c[lang]["path"] for c in reg["cards"] for lang in ("ru", "en")]
    rels += [f"scraped-data/images/heroes/{r}" for r in C.EXPECTED_HERO_MEDIA]
    rels += [f"scraped-data/api/heroes/{h}.json" for h in C.HEROES]
    for rel in rels:
        src = C.scrape_path(SCRAPED, rel)
        tgt = C.scrape_path(dst, rel)
        tgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, tgt)


def test_wrong_sha_is_refused(tmp_path):
    scrape = tmp_path / "scrape"
    _copy_scrape(scrape)
    reg = json.loads(C.REGISTRY.read_text(encoding="utf-8"))
    victim = reg["cards"][0]
    path = C.scrape_path(scrape, victim["ru"]["path"])
    path.write_bytes(path.read_bytes() + b"\0")  # the temporary copy only
    out = tmp_path / "out"
    with pytest.raises(C.ConvertError) as err:
        C.run(scrape, out, tmp_path / "r.json", db=False)
    assert f"{victim['stableContentKey']}.ru" in str(err.value) and "sha256" in str(err.value)
    hero, card = victim["stableContentKey"].split(":")
    assert not (out / "cards" / hero / f"{card}.ru.png").exists()
    assert not (tmp_path / "r.json").exists()
    check = C.run(scrape, out, None, check=True)
    assert not check["ok"] and len(check["errors"]) == 1


def test_missing_source_names_the_key(tmp_path):
    scrape = tmp_path / "scrape"
    _copy_scrape(scrape)
    (scrape / "images" / "heroes" / "sidekicks" / "G42WIKYZ1cmwACVwMggzM.webp").unlink()
    with pytest.raises(C.ConvertError) as err:
        C.run(scrape, tmp_path / "out", None, db=False)
    assert "portrait:medusa:harpies" in str(err.value) and "not found" in str(err.value)


def test_devalue_decoder_and_registry_hash():
    doc = {"nodes": [None, None, {"data": [{"fetchedHero": 1}, {"name": 2, "sidekicks": 3}, "X", [4], {"name": 2}]}]}
    root = C.decode_devalue(doc, "t")
    assert root == {"fetchedHero": {"name": "X", "sidekicks": [{"name": "X"}]}}
    with pytest.raises(C.ConvertError):
        C.decode_devalue({"nodes": []}, "t")
    # the registry hash is taken as git stores the blob (CRLF -> LF), so a core.autocrlf checkout reports the same value
    # (the card cites ac32ed5b...0c5883 for the 27-card registry)
    crlf = C.REGISTRY.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    tmp_hash = C.hashlib.sha256(crlf.replace(b"\r\n", b"\n")).hexdigest()
    assert C.sha256_text_lf(C.REGISTRY) == tmp_hash and len(tmp_hash) == 64
