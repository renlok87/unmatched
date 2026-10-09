"""clip_review_sheet.py (AN-18): the character registry of D-3 (skill reference new-character-registration.md).

  python -B -m pytest -q tools/art/anim/tests

The explicit card map (no AN numbers counted from the HEROES order), one-record registration of a new character, the
fighter of a launch by its focus line (Idle length only as a unique fallback), K1 from the first --heroes launch, the
K1 pose union extended by new card frames, the --fixture pass-through. No engine: synthetic frames and traces.
"""
import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clip_review_sheet as crs  # noqa: E402
from visual_common import load_cards  # noqa: E402

NEW = "Achilles"
NEW_CARDS = ("AN-37", "AN-38", "AN-39", "AN-40")
MVP = {"KingArthur": ("AN-01", "AN-02", "AN-03", "AN-04"), "Merlin": ("AN-05", "AN-06", "AN-07", "AN-08"),
       "Medusa": ("AN-09", "AN-10", "AN-11", "AN-12"), "Harpy": ("AN-13", "AN-14", "AN-15", "AN-16")}


@pytest.fixture(scope="module")
def real_cards():
    return load_cards(crs.REPO)


def new_cards(real: dict, lunge_extra: str = "") -> dict:
    """The real cards plus AN-37..AN-40 for the new character: copies of the Medusa clip cards, own titles."""
    out = dict(real)
    for src, cid, clip in zip(MVP["Medusa"], NEW_CARDS, crs.CLIPS):
        card = dict(real[src])
        card["id"] = cid
        card["title"] = f"{NEW} — клип ({clip}), клип D-11"
        if clip == "LungeAttack" and lunge_extra:
            card["keyframes"] = card["keyframes"] + " " + lunge_extra
        out[cid] = card
    return out


def register(monkeypatch, idle: float, cards=NEW_CARDS):
    monkeypatch.setitem(crs.HEROES, NEW, crs.Hero(NEW, "ACH", idle, tuple(cards)))


def manifest_with_new(tmp_path: Path) -> Path:
    data = json.loads(crs.MANIFEST.read_text(encoding="utf-8"))
    extra = []
    for c in data["clips"]:
        if c.get("role") == "production" and c["id"].startswith("MED-"):
            n = json.loads(json.dumps(c))
            n["id"] = "ACH-" + c["id"][4:]
            extra.append(n)
    data["clips"] += extra
    p = tmp_path / "clip-manifest.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def fighters_with_new(idle: float, slot: str = "f-1-sk1") -> dict:
    f = dict(crs.SYNTH_FIGHTERS)
    if slot in f:  # bench fixture variant (D-2): the new character takes the slot of King Arthur
        f[slot] = (NEW, idle, f[slot][2])
    else:
        f[slot] = (NEW, idle, (1300, 500))
    return f


def sheet(tmp_path: Path, frames: Path, cards: str) -> tuple[int, dict]:
    ns = argparse.Namespace(frames=str(frames), out=str(tmp_path / "out"), cards=cards)
    rc = crs.cmd_sheet(ns)
    return rc, {cid: json.loads((tmp_path / "out" / cid / "frames.json").read_text(encoding="utf-8"))
                for cid in cards.split(",") if (tmp_path / "out" / cid / "frames.json").is_file()}


def source_fighters(fj: dict) -> set[str]:
    return {s["clippose"].split("fighter=")[1].split()[0] for s in fj["sources"] if s["clippose"]}


# ---- the explicit card map ---------------------------------------------------------------------------------------------

def test_default_card_numbers_unchanged(real_cards):
    reg = crs.clip_cards()
    assert reg == {cid: (key, clip) for key, cids in MVP.items() for cid, clip in zip(cids, crs.CLIPS)}
    assert crs.registry_errors(real_cards) == []
    assert not hasattr(crs, "CARDS")  # no counted map left to drift


def test_fifth_character_is_one_record_and_keeps_its_own_numbers(monkeypatch, real_cards):
    register(monkeypatch, 2.75)
    reg = crs.clip_cards()
    assert [reg[c] for c in NEW_CARDS] == [(NEW, clip) for clip in crs.CLIPS]
    for cid in ("AN-17", "AN-18", "AN-19", "AN-20"):  # the stand / sheets / step cards stay foreign
        assert cid not in reg
    assert {c: v for c, v in reg.items() if c not in NEW_CARDS} == {
        cid: (key, clip) for key, cids in MVP.items() for cid, clip in zip(cids, crs.CLIPS)}
    assert crs.registry_errors(new_cards(real_cards)) == []
    assert crs.hero_tokens(new_cards(real_cards), NEW) == crs.hero_tokens(real_cards, "Medusa")


def test_registry_rejects_foreign_missing_and_duplicate_cards(monkeypatch, real_cards):
    register(monkeypatch, 2.75, ("AN-17", "AN-18", "AN-19", "AN-20"))  # the old counted numbers
    errs = crs.registry_errors(real_cards)
    assert len(errs) == 4 and all("not a" in e for e in errs)
    with pytest.raises(crs.SheetError, match="HEROES registry"):
        crs.check_registry(real_cards)
    register(monkeypatch, 2.75)
    assert any("not in docs/game-design/visual/06-tasks" in e for e in crs.registry_errors(real_cards))
    register(monkeypatch, 2.75, ("AN-09", "AN-38", "AN-39", "AN-40"))
    with pytest.raises(crs.SheetError, match="AN-09 registered twice"):
        crs.clip_cards()
    register(monkeypatch, 2.75, ("AN-37", "AN-38"))
    with pytest.raises(crs.SheetError, match="2 cards"):
        crs.clip_cards()


# ---- the K1 pose union ---------------------------------------------------------------------------------------------------

def test_union_default_and_extended(monkeypatch, real_cards):
    assert crs.union_tokens(real_cards) == crs.union_tokens()
    assert crs.pose_arg(crs.union_tokens(real_cards)).count(",") == 31
    register(monkeypatch, 2.75)
    cards = new_cards(real_cards, lunge_extra="к.1 к.13")
    lunge = crs.union_tokens(cards)["LungeAttack"]
    assert {"f01", "f13"} <= set(lunge) and lunge == sorted(lunge)
    assert set(crs.union_tokens()["LungeAttack"]) < set(lunge)


# ---- fighter by focus, Idle only while unique ------------------------------------------------------------------------------

def test_unique_idle_keys(monkeypatch):
    assert set(crs.unique_idle_keys()) == set(MVP)
    register(monkeypatch, 2.75)
    assert set(crs.unique_idle_keys()) == set(MVP) | {NEW}
    register(monkeypatch, 56.0 / 24.0)  # the Medusa default of a bow user
    assert set(crs.unique_idle_keys()) == set(MVP) - {"Medusa"}


@pytest.mark.parametrize("idle", [2.75, 56.0 / 24.0])
def test_parse_run_maps_the_focus_to_the_launch_folder(monkeypatch, tmp_path, idle):
    register(monkeypatch, idle)
    frames = tmp_path / "frames"
    crs._synthetic(frames, fighters=fighters_with_new(idle), heroes=["KingArthur", "Medusa", NEW])
    run_new = crs.parse_run(frames / "marmoreal" / NEW)
    run_med = crs.parse_run(frames / "marmoreal" / "Medusa")
    run_k1 = crs.parse_run(frames / "marmoreal" / "KingArthur")
    assert run_new["key"] == NEW and run_new["focus"] == "f-1-sk1" and run_new["heroes"]["f-1-sk1"] == NEW
    assert run_med["heroes"]["f-0-hero"] == "Medusa"
    assert crs.hero_fighter([run_k1, run_new], NEW) == "f-1-sk1"
    assert crs.hero_fighter([run_k1, run_med], "Medusa") == "f-0-hero"
    if idle == 2.75:  # unique: the K1 launch alone names it too
        assert run_k1["heroes"]["f-1-sk1"] == NEW
    else:  # shared with Medusa: no Idle guess at all, never the wrong key
        assert "f-1-sk1" not in run_k1["heroes"] and "f-0-hero" not in run_k1["heroes"]
        assert "f-1-sk1" not in run_med["heroes"]


# ---- the sheet for a new character ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("idle", [2.75, 56.0 / 24.0])
def test_sheet_of_a_new_character_uses_its_own_fighter(monkeypatch, tmp_path, real_cards, idle):
    register(monkeypatch, idle)
    monkeypatch.setattr(crs, "load_cards", lambda _root: new_cards(real_cards))
    monkeypatch.setattr(crs, "MANIFEST", manifest_with_new(tmp_path))
    frames = tmp_path / "frames"
    crs._synthetic(frames, fighters=fighters_with_new(idle), heroes=["KingArthur", "Medusa", NEW])
    rc, fj = sheet(tmp_path, frames, "AN-38,AN-10")
    assert rc == 0, fj
    assert fj["AN-38"]["clip"] == "ACH-LungeAttack" and fj["AN-38"]["problems"] == []
    assert source_fighters(fj["AN-38"]) == {"f-1-sk1"}
    assert source_fighters(fj["AN-10"]) == {"f-0-hero"}
    assert len(fj["AN-38"]["sources"]) == len(fj["AN-38"]["rows"]) * 4


def test_variant_fixture_k1_from_the_first_launch(monkeypatch, tmp_path, real_cards):
    """D-2 variant: the new character in the King Arthur slot, Idle equal to Medusa's; run --heroes <New> only."""
    idle = 56.0 / 24.0
    register(monkeypatch, idle)
    monkeypatch.setattr(crs, "load_cards", lambda _root: new_cards(real_cards))
    monkeypatch.setattr(crs, "MANIFEST", manifest_with_new(tmp_path))
    frames = tmp_path / "frames"
    crs._synthetic(frames, fighters=fighters_with_new(idle, slot="f-1-hero"), heroes=[NEW],
                   fixture="S08BenchMarmoreal.achilles.json")
    rc, fj = sheet(tmp_path, frames, ",".join(NEW_CARDS))
    assert rc == 0, {c: f["problems"] for c, f in fj.items()}
    for cid in NEW_CARDS:
        assert source_fighters(fj[cid]) == {"f-1-hero"}
        assert {s["view"] for s in fj[cid]["sources"]} == {crs.VIEW_K1, crs.VIEW_K2}


def test_k1_from_another_fixture_is_reported(monkeypatch, tmp_path, real_cards):
    register(monkeypatch, 2.75)
    monkeypatch.setattr(crs, "load_cards", lambda _root: new_cards(real_cards))
    monkeypatch.setattr(crs, "MANIFEST", manifest_with_new(tmp_path))
    frames = tmp_path / "frames"
    crs._synthetic(frames, fighters=fighters_with_new(2.75), heroes=["KingArthur", NEW], fixture="S08BenchMarmoreal.json")
    for m in crs.MAPS:
        (frames / m / NEW / "cmdline.txt").write_text("UnrealEditor.exe -game -BenchFixture=C:/x/variant.json\n",
                                                      encoding="utf-8")
    rc, fj = sheet(tmp_path, frames, "AN-38")
    assert rc == 1
    assert any("K1 from the KingArthur launch" in p for p in fj["AN-38"]["problems"])


def test_sheet_rejects_unregistered_cards(tmp_path):
    with pytest.raises(crs.SheetError, match="not clip cards"):
        crs.cmd_sheet(argparse.Namespace(frames=str(tmp_path), out=str(tmp_path / "o"), cards="AN-17"))


# ---- run: K1 launch, --fixture ----------------------------------------------------------------------------------------------

class _Done:
    returncode = 0


def run_cmds(monkeypatch, tmp_path, **kw) -> list[list[str]]:
    calls = []
    monkeypatch.setattr(crs.subprocess, "run", lambda cmd, **_k: calls.append(cmd) or _Done())
    a = argparse.Namespace(frames=str(tmp_path), maps=kw.get("maps", "marmoreal"), heroes=kw["heroes"], packaged=True,
                           warmup=30.0, settle=3.0, measure=1.0, force=True, fixture=kw.get("fixture", ""))
    assert crs.cmd_run(a) == 0
    return calls


def test_run_default_unchanged(monkeypatch, tmp_path):
    calls = run_cmds(monkeypatch, tmp_path, heroes=",".join(crs.HEROES), maps="marmoreal,sarpedon")
    assert len(calls) == 8
    k1 = [c for c in calls if c[c.index("--views") + 1] == f"{crs.VIEW_K1}+{crs.VIEW_K2}"]
    assert [c[c.index("--map") + 1] for c in k1] == ["marmoreal", "sarpedon"]
    for c in k1:
        assert "--extra=-BenchClipPoseFighter=KingArthur" in c
        assert f"--extra=-BenchClipPose={crs.pose_arg(crs.union_tokens())}" in c
    assert not any(x.startswith("--fixture") for c in calls for x in c)


def test_run_first_hero_shoots_k1_with_fixture(monkeypatch, tmp_path, real_cards):
    register(monkeypatch, 2.75)
    cards = new_cards(real_cards, lunge_extra="к.1")
    monkeypatch.setattr(crs, "load_cards", lambda _root: cards)
    monkeypatch.setattr(crs, "live_tune_has_fixture", lambda: True)
    calls = run_cmds(monkeypatch, tmp_path, heroes=f"{NEW},Medusa", fixture="S08BenchMarmoreal.achilles.json")
    first, second = calls
    assert first[first.index("--views") + 1] == f"{crs.VIEW_K1}+{crs.VIEW_K2}"
    assert "--extra=-BenchClipPoseFighter=Achilles" in first
    assert f"--extra=-BenchClipPose={crs.pose_arg(crs.union_tokens(cards))}" in first
    assert "LungeAttack@0,1,2," in crs.pose_arg(crs.union_tokens(cards))
    assert second[second.index("--views") + 1] == crs.VIEW_K2
    assert all("--fixture=S08BenchMarmoreal.achilles.json" in c for c in calls)


def test_run_input_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(crs, "live_tune_has_fixture", lambda: False)
    with pytest.raises(crs.SheetError, match="no --fixture yet"):
        run_cmds(monkeypatch, tmp_path, heroes="KingArthur", fixture="x.json")
    with pytest.raises(crs.SheetError, match="unknown map / hero"):
        run_cmds(monkeypatch, tmp_path, heroes="Nobody")


def test_parse_fixtures():
    assert crs.parse_fixtures("", ["marmoreal", "sarpedon"]) == {}
    assert crs.parse_fixtures("a.json", ["sarpedon"]) == {"sarpedon": "a.json"}
    assert crs.parse_fixtures("marmoreal=a.json,sarpedon=b.json", ["marmoreal", "sarpedon"]) == {
        "marmoreal": "a.json", "sarpedon": "b.json"}
    with pytest.raises(crs.SheetError, match="exactly one"):
        crs.parse_fixtures("a.json", ["marmoreal", "sarpedon"])
    with pytest.raises(crs.SheetError, match="want"):
        crs.parse_fixtures("cobble=a.json", ["marmoreal"])


def test_self_check_passes():
    assert crs.cmd_check(None) == 0
