"""clip_review_sheet.py (AN-18): the character registry of D-3 (skill reference new-character-registration.md).

  python -B -m pytest -q tools/art/anim/tests

The explicit card map (no AN numbers counted from the HEROES order), one-record registration of a new character, the
fighter of a launch by its focus line (Idle length only as a unique fallback), K1 per fixture group (the MVP run shoots
exactly the AN-17 union), the K1 pose union extended by new card frames, the --fixture pass-through and the per-hero
fixture map (F159), --k1-from (RC-09), the launch cache keyed by the staged BuildStamp, the required --heroes / --cards
and the refusal to write a card without frames (RB-12). No engine: synthetic frames and traces.

HEROES is the four MVP records in every test (fixture mvp_heroes, RB-03): a registered pilot or roster hero does not
change these tests; the live registry is checked once, by test_live_registry_is_consistent.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clip_review_sheet as crs  # noqa: E402
from visual_common import load_cards  # noqa: E402

LIVE_HEROES = dict(crs.HEROES)
NEW = "Hector"  # a made-up new character (not a registered one)
NEW_PRE = "HECT"
NEW_CARDS = ("AN-37", "AN-38", "AN-39", "AN-40")
MVP = {"KingArthur": ("AN-01", "AN-02", "AN-03", "AN-04"), "Merlin": ("AN-05", "AN-06", "AN-07", "AN-08"),
       "Medusa": ("AN-09", "AN-10", "AN-11", "AN-12"), "Harpy": ("AN-13", "AN-14", "AN-15", "AN-16")}
STAMP_A = {"schema": "unmatched.staged-build-stamp/1", "commit": "c2432557e21fb7b7ced521d3ab6d606053cc1f43",
           "sourceHash": "c908", "sourceFiles": 478, "builtAt": "2026-10-14T06:41:26+05:00", "skipBuild": True}


@pytest.fixture(autouse=True)
def mvp_heroes(monkeypatch, tmp_path):
    """HEROES = the four MVP records; no staged BuildStamp.json unless a test writes one."""
    monkeypatch.setattr(crs, "HEROES", {k: LIVE_HEROES[k] for k in MVP})
    monkeypatch.setattr(crs, "STAGED_STAMP", tmp_path / "staged" / "BuildStamp.json")


@pytest.fixture(scope="module")
def real_cards():
    return load_cards(crs.REPO)


def write_stamp(stamp: dict, **change) -> None:
    crs.STAGED_STAMP.parent.mkdir(parents=True, exist_ok=True)
    # package-client.ps1 writes it with a BOM (Set-Content -Encoding UTF8, PowerShell 5.1)
    crs.STAGED_STAMP.write_text("\ufeff" + json.dumps(dict(stamp, **change)), encoding="utf-8")


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
    monkeypatch.setitem(crs.HEROES, NEW, crs.Hero(NEW, NEW_PRE, idle, tuple(cards)))


def manifest_with_new(tmp_path: Path) -> Path:
    data = json.loads(crs.MANIFEST.read_text(encoding="utf-8"))
    extra = []
    for c in data["clips"]:
        if c.get("role") == "production" and c["id"].startswith("MED-"):
            n = json.loads(json.dumps(c))
            n["id"] = f"{NEW_PRE}-" + c["id"][4:]
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


def new_setup(monkeypatch, tmp_path, real_cards, idle=2.75, lunge_extra=""):
    register(monkeypatch, idle)
    cards = new_cards(real_cards, lunge_extra=lunge_extra)
    monkeypatch.setattr(crs, "load_cards", lambda _root: cards)
    monkeypatch.setattr(crs, "MANIFEST", manifest_with_new(tmp_path))
    return cards


def sheet(tmp_path: Path, frames: Path, cards: str, **kw) -> tuple[int, dict]:
    ns = argparse.Namespace(frames=str(frames), out=str(tmp_path / "out"), cards=cards, **kw)
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


def test_live_registry_is_consistent(monkeypatch, real_cards):
    """The registered heroes (MVP + pilot + roster) against anim.csv: what --check reports as 'registry:'."""
    monkeypatch.setattr(crs, "HEROES", LIVE_HEROES)
    assert crs.registry_errors(real_cards) == []
    assert {c: v for c, v in crs.clip_cards().items() if c in {x for cs in MVP.values() for x in cs}} == {
        cid: (key, clip) for key, cids in MVP.items() for cid, clip in zip(cids, crs.CLIPS)}


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
    register(monkeypatch, 2.75, ("AN-901", "AN-902", "AN-903", "AN-904"))
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
    # per launch group: the MVP heroes alone keep the AN-17 union, the new hero's frames only in its own group
    assert crs.union_tokens(cards, list(MVP)) == crs.union_tokens()
    # 2026-10-21: a group without an MVP hero shoots only its own card frames (no AN-17 union)
    own = crs.union_tokens(cards, [NEW])
    assert own == {clip: toks for clip, toks in crs.hero_tokens(cards, NEW).items()} | {"Idle": own["Idle"]}
    assert set(own["LungeAttack"]) < set(crs.union_tokens(cards)["LungeAttack"])
    assert crs.union_tokens(cards, [NEW, "Medusa"]) == crs.union_tokens(cards, list(MVP) + [NEW])


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
    new_setup(monkeypatch, tmp_path, real_cards, idle)
    frames = tmp_path / "frames"
    crs._synthetic(frames, fighters=fighters_with_new(idle), heroes=["KingArthur", "Medusa", NEW])
    rc, fj = sheet(tmp_path, frames, "AN-38,AN-10")
    assert rc == 0, fj
    assert fj["AN-38"]["clip"] == f"{NEW_PRE}-LungeAttack" and fj["AN-38"]["problems"] == []
    assert source_fighters(fj["AN-38"]) == {"f-1-sk1"}
    assert source_fighters(fj["AN-10"]) == {"f-0-hero"}
    assert len(fj["AN-38"]["sources"]) == len(fj["AN-38"]["rows"]) * 4


def test_variant_fixture_k1_from_the_first_launch(monkeypatch, tmp_path, real_cards):
    """D-2 variant: the new character in the King Arthur slot, Idle equal to Medusa's; run --heroes <New> only."""
    new_setup(monkeypatch, tmp_path, real_cards, 56.0 / 24.0)
    frames = tmp_path / "frames"
    crs._synthetic(frames, fighters=fighters_with_new(56.0 / 24.0, slot="f-1-hero"), heroes=[NEW],
                   fixture="S08BenchMarmoreal.hector.json")
    rc, fj = sheet(tmp_path, frames, ",".join(NEW_CARDS))
    assert rc == 0, {c: f["problems"] for c, f in fj.items()}
    for cid in NEW_CARDS:
        assert source_fighters(fj[cid]) == {"f-1-hero"}
        assert {s["view"] for s in fj[cid]["sources"]} == {crs.VIEW_K1, crs.VIEW_K2}


def test_k1_from_another_fixture_is_reported(monkeypatch, tmp_path, real_cards):
    new_setup(monkeypatch, tmp_path, real_cards)
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


# ---- sheet: explicit cards, no "нет кадра" over a committed sheet (RB-12) ------------------------------------------------------

def test_sheet_needs_cards_or_heroes(tmp_path):
    for cards in ("", None):
        with pytest.raises(crs.SheetError, match="sheet needs --cards"):
            crs.cmd_sheet(argparse.Namespace(frames=str(tmp_path), out=str(tmp_path / "o"), cards=cards))
    with pytest.raises(crs.SheetError, match="not in HEROES"):
        crs.sheet_cards(argparse.Namespace(cards="", heroes="Nobody"), crs.clip_cards())
    assert crs.sheet_cards(argparse.Namespace(cards="AN-02", heroes="Medusa"), crs.clip_cards()) == {
        "AN-02", *MVP["Medusa"]}


def test_main_requires_the_lists(capsys):
    assert crs.main(["run"]) == 2
    assert crs.main(["sheet"]) == 2
    err = capsys.readouterr().err
    assert "run needs --heroes" in err and "sheet needs --cards" in err


def test_sheet_refuses_a_card_without_frames_and_keeps_the_old_one(tmp_path):
    frames = tmp_path / "frames"
    crs._synthetic(frames)
    rc, fj = sheet(tmp_path, frames, "AN-02")
    assert rc == 0 and fj["AN-02"]["problems"] == []
    old = {n: (tmp_path / "out" / "AN-02" / n).read_bytes() for n in ("sheet-color.jpg", "frames.json")}
    (frames / "marmoreal" / "KingArthur" / "bench-K1-LungeAttack-f04-1920x1080.png").unlink()
    rc, _ = sheet(tmp_path, frames, "AN-02")
    assert rc == 1
    assert {n: (tmp_path / "out" / "AN-02" / n).read_bytes() for n in old} == old
    # no launch at all: nothing is created
    shutil.rmtree(frames / "sarpedon")
    shutil.rmtree(frames / "marmoreal")
    rc, fj = sheet(tmp_path, frames, "AN-14")
    assert rc == 1 and not (tmp_path / "out" / "AN-14").exists()


def test_sheet_allow_missing_draws_the_gaps(tmp_path):
    frames = tmp_path / "frames"
    crs._synthetic(frames)
    (frames / "sarpedon" / "KingArthur" / "bench-K2x1.6-LungeAttack-f07-1920x1080.png").unlink()
    rc, fj = sheet(tmp_path, frames, "AN-02", allow_missing=True)
    assert rc == 1 and (tmp_path / "out" / "AN-02" / "sheet-color.jpg").is_file()
    assert any("no frame" in p for p in fj["AN-02"]["problems"])


# ---- run: explicit heroes, K1 per fixture group, --fixture ------------------------------------------------------------------

class _Done:
    returncode = 0


def run_cmds(monkeypatch, tmp_path, **kw) -> list[list[str]]:
    calls = []

    def fake(cmd, **_k):
        calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "exit.txt").write_text("exit=0 seconds=1\n", encoding="utf-8")
        return _Done()
    monkeypatch.setattr(crs.subprocess, "run", fake)
    a = argparse.Namespace(frames=str(kw.get("frames", tmp_path)), maps=kw.get("maps", "marmoreal"),
                           heroes=kw["heroes"], packaged=kw.get("packaged", True), warmup=30.0, settle=3.0, measure=1.0,
                           force=kw.get("force", True), fixture=kw.get("fixture", ""), k1_from=kw.get("k1_from"))
    assert crs.cmd_run(a) == 0
    return calls


def opt(cmd: list[str], name: str) -> str:
    return cmd[cmd.index(name) + 1]


def extra(cmd: list[str], name: str) -> str:
    return next(x.split("=", 2)[2] for x in cmd if x.startswith(f"--extra=-{name}="))


def test_run_requires_heroes(monkeypatch, tmp_path):
    for heroes in ("", ",", None):
        with pytest.raises(crs.SheetError, match="run needs --heroes"):
            run_cmds(monkeypatch, tmp_path, heroes=heroes)


def test_run_mvp_unchanged(monkeypatch, tmp_path):
    calls = run_cmds(monkeypatch, tmp_path, heroes=",".join(MVP), maps="marmoreal,sarpedon")
    assert len(calls) == 8
    k1 = [c for c in calls if opt(c, "--views") == f"{crs.VIEW_K1}+{crs.VIEW_K2}"]
    assert [opt(c, "--map") for c in k1] == ["marmoreal", "sarpedon"]
    for c in k1:
        assert extra(c, "BenchClipPoseFighter") == "KingArthur"
        assert extra(c, "BenchClipPose") == crs.pose_arg(crs.union_tokens())
    assert not any(x.startswith("--fixture") for c in calls for x in c)


def test_run_mvp_k1_stays_the_an17_union_with_a_new_hero_registered(monkeypatch, tmp_path, real_cards):
    """The MVP frames do not move when a new character with extra frames is registered (RC-09)."""
    new_setup(monkeypatch, tmp_path, real_cards, lunge_extra="к.1 к.13")
    calls = run_cmds(monkeypatch, tmp_path, heroes=",".join(MVP))
    assert extra(calls[0], "BenchClipPose") == crs.pose_arg(crs.union_tokens())


def test_run_first_hero_shoots_k1_with_fixture(monkeypatch, tmp_path, real_cards):
    cards = new_setup(monkeypatch, tmp_path, real_cards, lunge_extra="к.1")
    monkeypatch.setattr(crs, "live_tune_has_fixture", lambda: True)
    calls = run_cmds(monkeypatch, tmp_path, heroes=f"{NEW},Medusa", fixture="S08BenchMarmoreal.hector.json")
    first, second = calls
    assert opt(first, "--views") == f"{crs.VIEW_K1}+{crs.VIEW_K2}"
    assert extra(first, "BenchClipPoseFighter") == NEW
    assert extra(first, "BenchClipPose") == crs.pose_arg(crs.union_tokens(cards))
    assert "LungeAttack@0,1,2," in crs.pose_arg(crs.union_tokens(cards))
    assert opt(second, "--views") == crs.VIEW_K2
    assert all("--fixture=S08BenchMarmoreal.hector.json" in c for c in calls)


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


def test_parse_fixture_map_per_hero():
    maps = ["marmoreal", "sarpedon"]
    spec = "Medusa:marmoreal=m1.json,sarpedon=s1.json;Harpy:marmoreal=m2.json,sarpedon=C:/x/s2.json"
    fmap = crs.parse_fixture_map(spec, maps, ["Medusa", "Harpy", "Merlin"])
    assert fmap == {"Medusa": {"marmoreal": "m1.json", "sarpedon": "s1.json"},
                    "Harpy": {"marmoreal": "m2.json", "sarpedon": "C:/x/s2.json"}}
    assert crs.fixture_for(fmap, "Harpy", "sarpedon") == "C:/x/s2.json"
    assert crs.fixture_for(fmap, "Merlin", "sarpedon") == ""  # no entry, no default: the canonical fixture
    both = crs.parse_fixture_map("marmoreal=d.json,sarpedon=e.json;Harpy:marmoreal=h.json", maps, None)
    assert crs.fixture_for(both, "Harpy", "marmoreal") == "h.json"
    assert crs.fixture_for(both, "Harpy", "sarpedon") == "e.json"  # the default fills the map Harpy does not name
    assert crs.fixture_for(both, "Merlin", "marmoreal") == "d.json"
    assert crs.parse_fixture_map("C:/x/a.json", ["marmoreal"]) == {"*": {"marmoreal": "C:/x/a.json"}}  # a drive letter
    assert crs.parse_fixture_map("", maps) == {}
    with pytest.raises(crs.SheetError, match="Medussa is not a HEROES key"):
        crs.parse_fixture_map("Medussa:marmoreal=a.json", maps)
    with pytest.raises(crs.SheetError, match="not in --heroes"):
        crs.parse_fixture_map("Harpy:marmoreal=a.json", maps, ["Medusa"])
    with pytest.raises(crs.SheetError, match="Harpy given twice"):
        crs.parse_fixture_map("Harpy:marmoreal=a.json;Harpy:sarpedon=b.json", maps)
    with pytest.raises(crs.SheetError, match="exactly one"):
        crs.parse_fixture_map("Harpy:a.json", maps)


def test_run_per_hero_fixture_map_one_call(monkeypatch, tmp_path, real_cards):
    """F159: two new heroes, each in its own fixture variant, one call: each fixture group shoots its own K1."""
    cards = new_setup(monkeypatch, tmp_path, real_cards, lunge_extra="к.1")
    monkeypatch.setattr(crs, "live_tune_has_fixture", lambda: True)
    calls = run_cmds(monkeypatch, tmp_path, heroes=f"KingArthur,Merlin,{NEW},Harpy", maps="marmoreal,sarpedon",
                     fixture=f"{NEW}:marmoreal=M-{NEW}.json,sarpedon=S-{NEW}.json;"
                             "Harpy:marmoreal=M-Harpy.json,sarpedon=S-Harpy.json")
    by = {(opt(c, "--map"), extra(c, "BenchClipPoseFighter")): c for c in calls}
    assert len(by) == 8
    for m, mm in (("marmoreal", "M"), ("sarpedon", "S")):
        assert opt(by[m, "KingArthur"], "--views") == f"{crs.VIEW_K1}+{crs.VIEW_K2}"
        assert opt(by[m, "Merlin"], "--views") == crs.VIEW_K2  # same (canonical) fixture as KingArthur
        assert not any(x.startswith("--fixture") for x in by[m, "KingArthur"] + by[m, "Merlin"])
        assert extra(by[m, "KingArthur"], "BenchClipPose") == crs.pose_arg(crs.union_tokens())
        for hero in (NEW, "Harpy"):
            c = by[m, hero]
            assert opt(c, "--views") == f"{crs.VIEW_K1}+{crs.VIEW_K2}"
            assert f"--fixture={mm}-{hero}.json" in c
            assert extra(c, "BenchClipPose") == crs.pose_arg(crs.union_tokens(cards, [hero]))
    # the new hero's own K1 group: its card frames incl. the extra k.1, no AN-17 union (frame 2 is not on its cards)
    assert "LungeAttack@0,1,3," in extra(by["marmoreal", NEW], "BenchClipPose")


# ---- run: the launch cache follows the staged build ----------------------------------------------------------------------------

def test_run_cache_skips_only_on_the_same_build(monkeypatch, tmp_path):
    write_stamp(STAMP_A)
    frames = tmp_path / "frames"
    kw = dict(heroes="Medusa", frames=frames, force=False)
    assert len(run_cmds(monkeypatch, tmp_path, **kw)) == 1
    st = json.loads((frames / "marmoreal" / "Medusa" / crs.RUN_STAMP).read_text(encoding="utf-8"))
    assert st["build"]["builtAt"] == STAMP_A["builtAt"] and st["exit"] == 0 and st["views"].startswith("K1")
    assert run_cmds(monkeypatch, tmp_path, **kw) == []  # same build: the finished launch is reused
    write_stamp(STAMP_A, builtAt="2026-10-14T09:00:00+05:00")  # a -SkipBuild repackage, same commit
    assert len(run_cmds(monkeypatch, tmp_path, **kw)) == 1
    assert run_cmds(monkeypatch, tmp_path, **kw) == []
    assert len(run_cmds(monkeypatch, tmp_path, **dict(kw, force=True))) == 1  # --force as before
    # other poses (a card changed) or another fixture: re-run
    monkeypatch.setattr(crs, "live_tune_has_fixture", lambda: True)
    assert len(run_cmds(monkeypatch, tmp_path, **dict(kw, fixture="v.json"))) == 1


def test_run_cache_never_skips_without_a_stamp(monkeypatch, tmp_path):
    frames = tmp_path / "frames"
    out = frames / "marmoreal" / "Medusa"
    out.mkdir(parents=True)
    (out / "exit.txt").write_text("exit=0 seconds=500\n", encoding="utf-8")  # an older launch: exit only
    kw = dict(heroes="Medusa", frames=frames, force=False)
    assert len(run_cmds(monkeypatch, tmp_path, **kw)) == 1  # no run-stamp.json
    assert len(run_cmds(monkeypatch, tmp_path, **kw)) == 1  # no BuildStamp.json of the staged client
    write_stamp(STAMP_A)
    assert len(run_cmds(monkeypatch, tmp_path, **dict(kw, packaged=False))) == 1  # editor launches always re-run
    assert len(run_cmds(monkeypatch, tmp_path, **dict(kw, packaged=False))) == 1


def test_build_stamp_reads_the_staged_buildstamp(tmp_path):
    assert crs.current_build(True) is None and crs.build_stamp([]) == "packaged"
    write_stamp(STAMP_A)
    assert crs.current_build(False) is None
    assert crs.current_build(True) == {k: STAMP_A[k] for k in ("commit", "sourceHash", "builtAt")}
    assert crs.build_stamp([]) == "packaged c2432557"
    run = {"cmdline": "Unmatched.exe -Bench", "build": crs.current_build(True)}
    assert crs.build_stamp([run]) == f"packaged c2432557 built {STAMP_A['builtAt']}"


# ---- --k1-from (RC-09): K1 from a finished launch, K2 only -----------------------------------------------------------------------

def k1_dir(tmp_path: Path, build: dict | None = None, fixture: str = "") -> Path:
    """Finished launches with the new hero on the scene: KingArthur shot K1 (union incl. the new card frames)."""
    root = tmp_path / "k1"
    crs._synthetic(root, fighters=fighters_with_new(2.75), heroes=["KingArthur", NEW], fixture=fixture,
                   toks=crs.union_tokens(crs.load_cards(crs.REPO)))
    if build is not None:
        for m in crs.MAPS:
            (root / m / "KingArthur" / crs.RUN_STAMP).write_text(json.dumps({"build": build}), encoding="utf-8")
    return root


def test_run_k1_from_shoots_k2_only(monkeypatch, tmp_path, real_cards):
    cards = new_setup(monkeypatch, tmp_path, real_cards, lunge_extra="к.1")
    root = k1_dir(tmp_path)
    calls = run_cmds(monkeypatch, tmp_path, heroes=f"{NEW},Medusa", maps="marmoreal,sarpedon", k1_from=str(root),
                     packaged=False)
    assert len(calls) == 4 and all(opt(c, "--views") == crs.VIEW_K2 for c in calls)
    for c in calls:
        hero = extra(c, "BenchClipPoseFighter")
        assert extra(c, "BenchClipPose") == crs.pose_arg(crs.hero_tokens(cards, hero))


def test_run_k1_from_checks_poses_fixture_and_build(monkeypatch, tmp_path, real_cards):
    new_setup(monkeypatch, tmp_path, real_cards, lunge_extra="к.1")
    with pytest.raises(crs.SheetError, match="no launch with K1 frames"):
        run_cmds(monkeypatch, tmp_path, heroes=NEW, k1_from=str(tmp_path / "empty"), packaged=False)
    # K1 shot over the AN-17 union only: the new hero's frame к.1 is missing
    root = tmp_path / "k1-short"
    crs._synthetic(root, fighters=fighters_with_new(2.75), heroes=["KingArthur"])
    with pytest.raises(crs.SheetError, match=f"no K1 launch covers the .* poses of {NEW}"):
        run_cmds(monkeypatch, tmp_path, heroes=NEW, k1_from=str(root), packaged=False)
    root = k1_dir(tmp_path)
    monkeypatch.setattr(crs, "live_tune_has_fixture", lambda: True)
    with pytest.raises(crs.SheetError, match=f"with fixture M-{NEW}.json"):
        run_cmds(monkeypatch, tmp_path, heroes=NEW, k1_from=str(root), packaged=False,
                 fixture=f"{NEW}:marmoreal=M-{NEW}.json")
    write_stamp(STAMP_A)  # packaged: the K1 launch must be on the staged build
    with pytest.raises(crs.SheetError, match="re-shoot K1"):
        run_cmds(monkeypatch, tmp_path, heroes=NEW, k1_from=str(root))
    root = k1_dir(tmp_path, build=crs.current_build(True))
    assert len(run_cmds(monkeypatch, tmp_path, heroes=NEW, k1_from=str(root))) == 1


def test_sheet_k1_from(monkeypatch, tmp_path, real_cards):
    new_setup(monkeypatch, tmp_path, real_cards)
    root = k1_dir(tmp_path)
    frames = tmp_path / "frames"
    for m in crs.MAPS:  # this run: the new hero's K2 launch only
        shutil.copytree(root / m / NEW, frames / m / NEW)
    rc, fj = sheet(tmp_path, frames, "AN-38")
    assert rc == 1 and fj == {}  # no K1 at all: not written
    rc, fj = sheet(tmp_path, frames, "AN-38", k1_from=str(root))
    assert rc == 0, fj["AN-38"]["problems"]
    assert source_fighters(fj["AN-38"]) == {"f-1-sk1"}
    assert {s["view"] for s in fj["AN-38"]["sources"]} == {crs.VIEW_K1, crs.VIEW_K2}
    for m in crs.MAPS:
        assert fj["AN-38"]["launches"][m][crs.VIEW_K1] == str(root / m / "KingArthur")
        assert fj["AN-38"]["launches"][m][crs.VIEW_K2] == str(frames / m / NEW)


def test_sheet_reports_k1_and_k2_from_different_builds(monkeypatch, tmp_path, real_cards):
    new_setup(monkeypatch, tmp_path, real_cards)
    frames = tmp_path / "frames"
    crs._synthetic(frames, fighters=fighters_with_new(2.75), heroes=["KingArthur", NEW])
    for m in crs.MAPS:
        (frames / m / "KingArthur" / crs.RUN_STAMP).write_text(json.dumps({"build": {"builtAt": "a"}}), encoding="utf-8")
        (frames / m / NEW / crs.RUN_STAMP).write_text(json.dumps({"build": {"builtAt": "b"}}), encoding="utf-8")
    rc, fj = sheet(tmp_path, frames, "AN-38")
    assert rc == 1 and sum("re-shoot K1 on the current build" in p for p in fj["AN-38"]["problems"]) == 2


def test_self_check_passes():
    assert crs.cmd_check(None) == 0


# ---- run: maps at once, shot delay (2026-10-21) ----------------------------------------------------------------------------

def test_run_parallel_maps_per_map_lock_under_the_gpu_token(monkeypatch, tmp_path):
    lt = crs.live_tune_module()
    token = tmp_path / "gpu.lock"
    monkeypatch.setattr(lt, "GPU_LOCK", token)
    seen = []

    def fake(cmd, **_k):
        seen.append((opt(cmd, "--map"), next(x for x in cmd if x.startswith("--lock=")), token.is_file()))
        out = Path(cmd[cmd.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "exit.txt").write_text("exit=0 seconds=1\n", encoding="utf-8")
        return _Done()

    monkeypatch.setattr(crs.subprocess, "run", fake)
    a = argparse.Namespace(frames=str(tmp_path / "f"), maps="marmoreal,sarpedon", heroes="Medusa", packaged=True,
                           warmup=30.0, settle=3.0, measure=1.0, force=True, fixture="", k1_from=None,
                           parallel_maps=True, stagger=0.0, lock_timeout=5.0, shot_delay=0.0)
    assert crs.cmd_run(a) == 0
    assert sorted(m for m, _l, _t in seen) == ["marmoreal", "sarpedon"]
    for m, lock, held in seen:
        assert lock == f"--lock={token.with_name(f'unmatched-gpu-{m}.lock')}"
        assert held  # the run holds the shared token while the maps shoot
    assert not token.exists()  # released


def test_run_shot_delay_is_passed_only_when_given(monkeypatch, tmp_path):
    calls = run_cmds(monkeypatch, tmp_path, heroes="Medusa")
    assert not any(x.startswith("--extra=-BenchShotDelay=") for c in calls for x in c)
    assert not any(x.startswith("--lock=") for c in calls for x in c)  # serial: live_tune's own GPU token
    calls2 = []

    def fake(cmd, **_k):
        calls2.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "exit.txt").write_text("exit=0 seconds=1\n", encoding="utf-8")
        return _Done()

    monkeypatch.setattr(crs.subprocess, "run", fake)
    a = argparse.Namespace(frames=str(tmp_path / "g"), maps="marmoreal", heroes="Medusa", packaged=True, warmup=30.0,
                           settle=3.0, measure=1.0, force=True, fixture="", k1_from=None, shot_delay=0.0)
    assert crs.cmd_run(a) == 0
    assert extra(calls2[0], "BenchShotDelay") == "0"


def test_run_new_hero_alone_skips_the_mvp_union(monkeypatch, tmp_path, real_cards):
    cards = new_setup(monkeypatch, tmp_path, real_cards, lunge_extra="к.1")
    monkeypatch.setattr(crs, "live_tune_has_fixture", lambda: True)
    calls = run_cmds(monkeypatch, tmp_path, heroes=NEW, fixture="S08BenchMarmoreal.hector.json")
    assert extra(calls[0], "BenchClipPose") == crs.pose_arg(crs.union_tokens(cards, [NEW]))
    n_new = crs.pose_arg(crs.union_tokens(cards, [NEW])).count(",")
    n_union = crs.pose_arg(crs.union_tokens(cards)).count(",")
    assert n_new < n_union
