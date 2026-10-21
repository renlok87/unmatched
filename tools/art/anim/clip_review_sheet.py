"""AN-18 (ВР-17): acceptance sheets of the 16 D-11 clips from -BenchClipPose (AN-17) frames.

Commands
  run    one bench launch per map x character of --heroes (REQUIRED, no default: every registered hero would be one
         packaged launch per map) through tools/art/render/live_tune.py bench. Per map, the first launch of each fixture
         group (the heroes that get the same --fixture file) shoots K1 + K2x1.6 over the AN-17 pose union plus the card
         frames of that group; the others shoot K2x1.6 only, over the poses of their own character (K1 does not depend
         on the focus fighter). The MVP run (--heroes KingArthur,Merlin,Medusa,Harpy) shoots exactly the AN-17 union.
         --fixture passes a bench fixture variant (a new character on the scene, new-character-registration.md D-2) on
         to live_tune.py bench --fixture:
           FILE (one map) | marmoreal=FILE,sarpedon=FILE (every hero of the run)
           | <Key>:marmoreal=FILE,sarpedon=FILE;<Key2>:... (F159: per hero - several new heroes in one call, each in its
             own fixture and its own K1 launch; a part without '<Key>:' is the default of the other heroes).
         K1 poses (2026-10-21): the AN-17 MVP union only when the launch group has an MVP hero
         (KingArthur/Merlin/Medusa/Harpy); a group of new heroes shoots only its own card frames (Beowulf: 23 poses
         instead of 37, 46 PNG instead of 74 per board).
         --parallel-maps (default; --no-parallel-maps = serial): the maps run at once, one client per map
         (-BenchFps=60 each; a frame is ~2.2 ms GPU; 2026-10-21 both clients held 60 fps, the frames of the map that
         ran beside the other stayed inside the bench-to-bench noise): the
         run holds the GPU token C:/tmp/unmatched-gpu.lock for its whole length and every launch takes the per-map
         lock C:/tmp/unmatched-gpu-<map>.lock instead (render_bench / live_tune sessions keep waiting for the token).
         --shot-delay S (default 0): -BenchShotDelay=S. The 3 s after the measurement window only waited for a
         ProfileGPU frame, which -BenchNoProfileGPU never takes; 0 gives the same frames (2026-10-21: R1 vs R3 meanAbs
         0.38-0.44 against the bench-to-bench 0.35-0.42, 0 px over 24 outside the bench noise) at 4.7 s instead of
         8.0 s a PNG. A build without the flag (before 2026-10-21) ignores it; --shot-delay 3 = the old timing.
         --k1-from DIR (RC-09): no launch shoots K1; every hero shoots K2x1.6 of its own cards only, and the sheet takes
         K1 from the finished launches DIR/<map>/<Key> (checked: a K1 launch covers the hero's card poses, with the same
         fixture file and - packaged - the same staged build).
         A launch whose folder holds exit=0 is skipped only when its run-stamp.json matches: the same BuildStamp.json of
         the staged packaged client (commit, sourceHash, builtAt), views, poses and fixture; any repackage re-runs it
         (editor launches always re-run). --force re-runs everything.
           python tools/art/anim/clip_review_sheet.py run --packaged --heroes <Key>[,<Key>...] [--maps marmoreal,sarpedon]
               [--fixture ...] [--k1-from DIR] [--force] [--no-parallel-maps] [--shot-delay 3]
  sheet  for the clip cards given by --cards AN-..,AN-.. or --heroes <Key>,.. (REQUIRED; the four cards per hero):
         rows = the key frames of the clip (column keyframes of the card; Idle - the
         quarters of the loop), columns = Marmoreal K1 (figure crop by figrect + 25 %), Marmoreal K2x1.6, Sarpedon K1
         (crop), Sarpedon K2x1.6; colour / gray Rec.709 / deuteranopia (Machado 2009, 1.0) JPEGs <= 2 MB, frames.json.
         A card with any cell without a frame is NOT written (the committed sheet stays; exit 1, the gaps listed);
         --allow-missing draws "нет кадра" cells instead (drafts outside docs/ only). --k1-from DIR as in run.
           python tools/art/anim/clip_review_sheet.py sheet --heroes <Key> [--frames C:/tmp/visual/AN-18] [--k1-from DIR]
               [--out docs/.../VISUAL]
  --check  self-test on synthetic frames and traces (no engine).

The source PNG frames stay outside git (C:/tmp/visual/AN-18/<map>/<hero>/); only the sheets and frames.json are
committed (EVIDENCE RULE ВР-VS4-01: board frames without HUD).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools/art/visual"))
from sheet import _font, deuteranopia, gray709  # noqa: E402
from visual_common import load_cards  # noqa: E402

FRAMES_DEFAULT = Path("C:/tmp/visual/AN-18")
OUT_DEFAULT = REPO / "docs/game-design/evidence/VISUAL"
MANIFEST = REPO / "docs/art-pipeline/animation-library/clip-manifest.json"
LIVE_TUNE = REPO / "tools/art/render/live_tune.py"
# the staged packaged client of live_tune.py bench --packaged and its stamp (tools/s08/package-client.ps1)
STAGED_STAMP = REPO / "unreal/Unmatched/Saved/StagedBuilds/Windows/BuildStamp.json"
RUN_STAMP = "run-stamp.json"  # written by run next to live_tune's exit.txt: build, views, poses, fixture of the launch
MVP_KEYS = ("KingArthur", "Merlin", "Medusa", "Harpy")
MAPS = {"marmoreal": ("Marmoreal original", "c121b47f8d6eb28daccb76d05"),
        "sarpedon": ("Sarpedon original", "c7fa64a26c29a0835f2383e63")}
FPS = 24
FRAME_MS = 1000.0 / FPS
CLIPS = ("Idle", "LungeAttack", "HitReact", "DeathSettle")


class Hero(NamedTuple):
    character: str  # manifest / rig-contract character (clip-manifest.json "character")
    prefix: str  # manifest clip id prefix: <prefix>-<Clip>
    idle_s: float  # Idle length (s): fallback key of a trace fighter, used only while unique among HEROES
    cards: tuple[str, ...]  # the anim.csv clip cards, explicit, in CLIPS order (Idle, LungeAttack, HitReact, DeathSettle)


# hero key (= -BenchClipPoseFighter, = the frames folder <frames>/<map>/<Key>) -> its record.
# Registering a new character is ONE record here plus its 4 clip cards in docs/game-design/visual/06-tasks/anim.csv
# (the next free AN numbers; title "<Name> — <state> (<Clip>), клип D-11"; columns timing and keyframes):
#   "<Key>": Hero("<Character>", "<PRE>", <IdleSeconds>, ("AN-<idle>", "AN-<lunge>", "AN-<hit>", "AN-<death>")),
HEROES = {
    "KingArthur": Hero("Arthur", "ARTH", 2.5, ("AN-01", "AN-02", "AN-03", "AN-04")),
    "Merlin": Hero("Merlin", "MER", 3.0, ("AN-05", "AN-06", "AN-07", "AN-08")),
    "Medusa": Hero("Medusa", "MED", 56.0 / 24.0, ("AN-09", "AN-10", "AN-11", "AN-12")),
    "Harpy": Hero("Harpy", "HAR", 2.0, ("AN-13", "AN-14", "AN-15", "AN-16")),
    "Angel": Hero("Angel", "ANG", 2.5, ("AN-133", "AN-134", "AN-135", "AN-136")),
    "AncientLeshen": Hero("AncientLeshen", "LESH", 56.0 / 24.0, ("AN-137", "AN-138", "AN-139", "AN-140")),
    "Achilles": Hero("Achilles", "ACH", 2.5, ("AN-141", "AN-142", "AN-143", "AN-144")),
    "Beowulf": Hero("Beowulf", "BEO", 2.5, ("AN-145", "AN-146", "AN-147", "AN-148")),
    "BruceLee": Hero("BruceLee", "BRUC", 2.5, ("AN-156", "AN-157", "AN-158", "AN-159")),
    "DrWatson": Hero("Watson", "WAT", 56.0 / 24.0, ("AN-164", "AN-165", "AN-166", "AN-167")),
}
IDLE_EPS = 0.01
IDLE_Q = (0, 25, 50, 75)
# the AN-17 pose union of the four build profiles (card AN-17, column keyframes); the K1 launch adds the card frames
# of every registered character (union_tokens(cards)), so a new character's poses outside it are shot too
UNION = {"LungeAttack": (0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14), "HitReact": (0, 2, 4, 5, 7, 8, 10),
         "DeathSettle": (0, 3, 6, 7, 8, 9, 12, 13, 16, 17, 21)}
VIEW_K1, VIEW_K2 = "K1", "K2x1.6"
ROOT_DELTA_MAX = 0.5
SHEET_MAX_BYTES = 2_000_000
CROP_H, K2_W, LABEL_W, GAP = 256, 640, 190, 8
BG, FG, FG2, ACCENT = (24, 30, 46), (236, 236, 240), (176, 182, 196), (242, 193, 78)  # card.navy, text.*

RE_LINE = re.compile(r"^\S+ (.*)$")
RE_CLIPPOSE = re.compile(r"ARTPREVIEW clippose fighter=(\S+) clip=(\S+) frame=(\d+) t=([\d.]+) len=([\d.]+) "
                         r"rootDeltaUU=(-?[\d.]+)")
RE_FIGRECT = re.compile(r"ARTPREVIEW figrect fighter=(\S+) view=(\S+) x=(-?[\d.]+) y=(-?[\d.]+) w=([\d.]+) h=([\d.]+)")
RE_SHOT = re.compile(r"BENCH shot view=(\S+) saved=(\d) path=(.+)$")
RE_FOCUS = re.compile(r"BENCH clip-pose poses=\d+ views=\d+ fighter=(\S+)")
RE_FIXTURE = re.compile(r"-BenchFixture=(\S+)")
RE_SHOTNAME = re.compile(r"bench-(.+?)-(Idle|LungeAttack|HitReact|DeathSettle)-(f\d+|q\d+)-1920x1080\.png$")
RE_FIXTURE_HERO = re.compile(r"^([A-Za-z]\w+):(.+)$")  # '<Key>:<spec>'; 'C:/x.json' (one letter) stays a file


class SheetError(Exception):
    pass


# ---- the character registry -------------------------------------------------------------------------------------------

def clip_cards() -> dict[str, tuple[str, str]]:
    """card id -> (hero key, clip), from the explicit cards of HEROES (read at call time)."""
    out: dict[str, tuple[str, str]] = {}
    for key, hero in HEROES.items():
        if len(hero.cards) != len(CLIPS):
            raise SheetError(f"HEROES[{key}]: {len(hero.cards)} cards, want {len(CLIPS)} ({', '.join(CLIPS)})")
        for cid, clip in zip(hero.cards, CLIPS):
            if cid in out:
                raise SheetError(f"card {cid} registered twice: {out[cid][0]} and {key}")
            out[cid] = (key, clip)
    return out


def registry_errors(cards: dict) -> list[str]:
    """Every registered card exists in 06-tasks/*.csv and its title names its clip, e.g. '(LungeAttack)'."""
    try:
        reg = clip_cards()
    except SheetError as e:
        return [str(e)]
    errs = []
    for cid, (key, clip) in reg.items():
        card = cards.get(cid)
        if card is None:
            errs.append(f"{key} {clip}: card {cid} not in docs/game-design/visual/06-tasks/*.csv")
        elif f"({clip})" not in card.get("title", ""):
            errs.append(f"{key} {clip}: card {cid} is {card.get('title', '')!r}, not a {clip} clip card")
    return errs


def check_registry(cards: dict) -> None:
    errs = registry_errors(cards)
    if errs:
        raise SheetError("HEROES registry: " + "; ".join(errs))


def unique_idle_keys() -> dict[str, float]:
    """Hero key -> Idle length, for the keys whose Idle length no other registered character shares (+-IDLE_EPS)."""
    return {k: h.idle_s for k, h in HEROES.items()
            if not any(o != k and abs(h.idle_s - oh.idle_s) < IDLE_EPS for o, oh in HEROES.items())}


# ---- the pose lists ---------------------------------------------------------------------------------------------------

def card_keyframes(card: dict, clip: str) -> list[str]:
    """Pose tokens of a card row: Idle -> q0..q75; else every 'к.N' of the keyframes column below the clip length."""
    if clip == "Idle":
        return [f"q{q}" for q in IDLE_Q]
    frames = sorted({int(n) for n in re.findall(r"к\.(\d+)", card.get("keyframes", ""))})
    return [f"f{n:02d}" for n in frames]


def contact_frame(card: dict) -> int | None:
    m = re.search(r"Contact к\.(\d+)", card.get("timing", "") + " " + card.get("keyframes", ""))
    return int(m.group(1)) if m else None


def pose_arg(tokens: dict[str, list[str]]) -> str:
    parts = []
    for clip in CLIPS:
        toks = tokens.get(clip) or []
        if toks:
            parts.append(clip + "@" + ",".join(t if t.startswith("q") else str(int(t[1:])) for t in toks))
    return ";".join(parts)


def union_tokens(cards: dict | None = None, heroes: list[str] | None = None) -> dict[str, list[str]]:
    """The K1 pose list: the AN-17 union, plus (given the cards) the card frames of the given characters (default every
    registered one). run passes the heroes of one K1 launch (RC-09: the union does not grow with the roster). A group
    without an MVP hero (heroes given, none in MVP_KEYS) skips the AN-17 union: its sheets need only its own cards
    (2026-10-21: 28 of the 74 PNG of a new hero's K1 launch were MVP poses no sheet of it used)."""
    mvp = heroes is None or any(h in MVP_KEYS for h in heroes)
    frames = {c: set(fr) if mvp else set() for c, fr in UNION.items()}
    if cards is not None:
        for cid, (key, clip) in clip_cards().items():
            if heroes is not None and key not in heroes:
                continue
            if clip != "Idle" and cid in cards:
                frames[clip] |= {int(t[1:]) for t in card_keyframes(cards[cid], clip)}
    out = {"Idle": [f"q{q}" for q in IDLE_Q]}
    out.update({c: [f"f{n:02d}" for n in sorted(fr)] for c, fr in frames.items()})
    return out


def hero_tokens(cards: dict, hero: str) -> dict[str, list[str]]:
    return {clip: card_keyframes(cards[cid], clip) for cid, (h, clip) in clip_cards().items() if h == hero}


def parse_fixtures(spec: str, maps: list[str]) -> dict[str, str]:
    """--fixture: 'FILE' (exactly one map) or 'marmoreal=FILE,sarpedon=FILE' -> {map: file}."""
    if not spec:
        return {}
    if "=" not in spec:
        if len(maps) != 1:
            raise SheetError("--fixture FILE needs exactly one --maps entry; else --fixture marmoreal=A,sarpedon=B")
        return {maps[0]: spec}
    out = {}
    for part in (p for p in spec.split(",") if p):
        m, _, f = part.partition("=")
        if m not in MAPS or not f:
            raise SheetError(f"--fixture entry {part!r}: want <{'|'.join(MAPS)}>=<file>")
        out[m] = f
    return out


def parse_fixture_map(spec: str, maps: list[str], heroes: list[str] | None = None) -> dict[str, dict[str, str]]:
    """--fixture -> {'*': {map: file}, '<Key>': {map: file}}. Parts split by ';': '<Key>:<spec>' is the fixture of one
    hero (F159), a part without a key is the default of every other hero; <spec> is the parse_fixtures form."""
    out: dict[str, dict[str, str]] = {}
    for part in (p.strip() for p in (spec or "").split(";")):
        if not part:
            continue
        m = RE_FIXTURE_HERO.match(part)
        if m:
            key, sub = m.group(1), m.group(2)
            if key not in HEROES:
                raise SheetError(f"--fixture {part!r}: {key} is not a HEROES key ({', '.join(HEROES)})")
            if heroes is not None and key not in heroes:
                raise SheetError(f"--fixture names {key}, which is not in --heroes {','.join(heroes)}")
        else:
            key, sub = "*", part
        if key in out:
            raise SheetError(f"--fixture: {'the default (no <Key>:)' if key == '*' else key} given twice")
        out[key] = parse_fixtures(sub, maps)
    return out


def fixture_for(fmap: dict[str, dict[str, str]], hero: str, map_key: str) -> str:
    """The fixture file of a hero's launch on a map: its own entry, else the default, else '' (the canonical fixture)."""
    return fmap.get(hero, {}).get(map_key) or fmap.get("*", {}).get(map_key) or ""


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def current_build(packaged: bool) -> dict | None:
    """The stamp of the staged packaged client (BuildStamp.json of package-client.ps1); None for editor launches."""
    if not packaged:
        return None
    d = read_json(STAGED_STAMP)
    return {k: d.get(k) for k in ("commit", "sourceHash", "builtAt")} if isinstance(d, dict) else None


def describe_build(b: dict | None) -> str:
    return f"{str(b.get('commit') or '?')[:8]} built {b.get('builtAt') or '?'}" if b else "no stamp"


def cached(out: Path, want: dict) -> tuple[bool, str]:
    """(skip?, why): a finished launch (exit=0) is reused only when run-stamp.json has the same build, views, poses,
    fixture and mode. A missing stamp (older launch, editor launch, no BuildStamp.json) re-runs."""
    ex = out / "exit.txt"
    if not ex.exists() or "exit=0" not in ex.read_text(encoding="utf-8", errors="replace"):
        return False, ""
    st = read_json(out / RUN_STAMP)
    if st is None:
        return False, f"no {RUN_STAMP} (a launch of an older tool)"
    if want["build"] is None:
        return False, ("editor launch: no build stamp to compare" if not want["packaged"]
                       else f"no {STAGED_STAMP.name} of the staged client")
    if st.get("build") != want["build"]:
        return False, f"build changed ({describe_build(st.get('build'))} -> {describe_build(want['build'])})"
    for k in ("packaged", "views", "poses", "fixture"):
        if st.get(k) != want[k]:
            return False, f"{k} changed"
    if st.get("exit") != 0:
        return False, f"exit {st.get('exit')}"
    return True, f"build {describe_build(want['build'])}"


def k1_source_runs(root: Path, map_key: str) -> list[dict]:
    """The launches under root/<map>/ that shot K1 (--k1-from)."""
    d = root / map_key
    if not d.is_dir():
        return []
    runs = []
    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        if (sub / "bench.trace.log").is_file():
            r = parse_run(sub, sub.name if sub.name in HEROES else None)
            if has_k1(r):
                runs.append(r)
    return runs


def k1_names(run: dict) -> set[str]:
    return {n for n, sh in run["shots"].items() if sh["view"] == VIEW_K1 and Path(sh["path"]).is_file()}


def check_k1_source(root: Path, maps: list[str], heroes: list[str], fmap: dict, cards: dict,
                    build: dict | None) -> dict[tuple[str, str], str]:
    """--k1-from: for every map x hero a finished K1 launch under root that covers the hero's card poses, with the
    hero's fixture file and (packaged) the current build. Returns {(map, hero): launch folder}; else SheetError."""
    found = {}
    for map_key in maps:
        runs = k1_source_runs(root, map_key)
        if not runs:
            raise SheetError(f"--k1-from {root}: no launch with K1 frames under {map_key}/ (shoot K1 first: run without "
                             "--k1-from)")
        for hero in heroes:
            need = {f"bench-{VIEW_K1}-{clip}-{t}-1920x1080.png" for clip, toks in hero_tokens(cards, hero).items()
                    for t in toks}
            fx = Path(fixture_for(fmap, hero, map_key)).name if fixture_for(fmap, hero, map_key) else ""
            ok = [r for r in runs if need <= k1_names(r) and (not fx or r["fixture"] == fx)]
            if not ok:
                raise SheetError(f"--k1-from {root}/{map_key}: no K1 launch covers the {len(need)} K1 poses of {hero}"
                                 + (f" with fixture {fx}" if fx else "") + " (shoot K1 with this hero on the scene)")
            if build is not None:
                same = [r for r in ok if r.get("build") == build]
                if not same:
                    raise SheetError(f"--k1-from {root}/{map_key}: the K1 launch for {hero} was shot on build "
                                     f"{describe_build(ok[0].get('build'))}, the staged client is "
                                     f"{describe_build(build)}: re-shoot K1")
                ok = same
            found[(map_key, hero)] = ok[0]["run"]
    return found


def need_hint(cmd: str) -> str:
    keys = ", ".join(HEROES)
    if cmd == "run":
        return (f"run needs --heroes <Key>[,<Key>...]: one packaged launch per map x hero (registered: {keys}). A new "
                f"hero: --heroes <Key> --fixture <Key>:marmoreal=...,sarpedon=...; the MVP sheets: --heroes "
                f"{','.join(MVP_KEYS)}")
    return (f"sheet needs --cards AN-..,AN-.. or --heroes <Key>[,<Key>...] (registered: {keys}); it writes into "
            f"{OUT_DEFAULT.relative_to(REPO).as_posix()}/<card> by default, so name the cards of this run only")


def live_tune_has_fixture() -> bool:
    r = subprocess.run([sys.executable, str(LIVE_TUNE), "bench", "--help"], capture_output=True, text=True,
                       cwd=str(REPO))
    return "--fixture" in r.stdout


# ---- run --------------------------------------------------------------------------------------------------------------

def cmd_run(a) -> int:
    heroes = list(dict.fromkeys(h.strip() for h in (getattr(a, "heroes", "") or "").split(",") if h.strip()))
    if not heroes:
        raise SheetError(need_hint("run"))
    cards = load_cards(REPO)
    check_registry(cards)
    maps = [m for m in a.maps.split(",") if m]
    unknown = [m for m in maps if m not in MAPS] + [h for h in heroes if h not in HEROES]
    if unknown:
        raise SheetError(f"unknown map / hero {unknown}; maps {', '.join(MAPS)}, heroes {', '.join(HEROES)}")
    fmap = parse_fixture_map(getattr(a, "fixture", "") or "", maps, heroes)
    if fmap and not live_tune_has_fixture():
        raise SheetError("live_tune.py bench has no --fixture yet (new-character-registration.md D-2)")
    packaged = bool(getattr(a, "packaged", False))
    build = current_build(packaged)
    k1_from = Path(a.k1_from) if getattr(a, "k1_from", None) else None
    if k1_from is not None:
        for (map_key, hero), run in check_k1_source(k1_from, maps, heroes, fmap, cards, build).items():
            print(f"{map_key} {hero}: K1 from {run}", flush=True)
        if build is None:
            print("WARNING: editor launches: the build of the --k1-from frames is not compared", file=sys.stderr)
    parallel = bool(getattr(a, "parallel_maps", False)) and len(maps) > 1
    shot_delay = getattr(a, "shot_delay", None)

    def run_map(map_key: str) -> list[dict]:
        results = []
        k1_owner: dict[str, str] = {}  # fixture file -> the hero whose launch shoots K1 for its group
        for hero in heroes:
            fx = fixture_for(fmap, hero, map_key)
            first = k1_from is None and fx not in k1_owner
            if first:
                k1_owner[fx] = hero
                group = [h for h in heroes if fixture_for(fmap, h, map_key) == fx]
                poses = pose_arg(union_tokens(cards, group))
                print(f"{map_key}: K1 in the {hero} launch (fixture {fx or 'canonical'}, for {', '.join(group)})",
                      flush=True)
            else:
                poses = pose_arg(hero_tokens(cards, hero))
            views = f"{VIEW_K1}+{VIEW_K2}" if first else VIEW_K2
            out = Path(a.frames) / map_key / hero
            want = {"map": map_key, "hero": hero, "packaged": packaged, "views": views, "poses": poses, "fixture": fx,
                    "build": build}
            skip, why = cached(out, want)
            if not a.force:
                if skip:
                    print(f"skip {out} (done, {why})", flush=True)
                    continue
                if why:
                    print(f"rerun {out}: {why}", flush=True)
            cmd = [sys.executable, str(LIVE_TUNE), "bench", "--map", map_key, "--views", views, "--out", str(out),
                   f"--bench-warmup={a.warmup:g}", f"--bench-settle={a.settle:g}", f"--bench-measure={a.measure:g}",
                   f"--extra=-BenchClipPose={poses}", f"--extra=-BenchClipPoseFighter={hero}"]
            if shot_delay is not None:
                cmd.append(f"--extra=-BenchShotDelay={shot_delay:g}")
            if packaged:
                cmd.append("--packaged")
            if fx:
                cmd.append(f"--fixture={fx}")
            if parallel:
                cmd.append(f"--lock={map_gpu_lock(map_key)}")
            t0 = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] {map_key} {hero} views={views}"
                  + (f" shot-delay={shot_delay:g}" if shot_delay is not None else ""), flush=True)
            r = subprocess.run(cmd, cwd=str(REPO))
            results.append({"map": map_key, "hero": hero, "exit": r.returncode, "seconds": round(time.time() - t0)})
            out.mkdir(parents=True, exist_ok=True)
            (out / RUN_STAMP).write_text(json.dumps(dict(want, schema="unmatched.an18-launch/1", exit=r.returncode,
                                                         seconds=results[-1]["seconds"],
                                                         finished=time.strftime("%Y-%m-%dT%H:%M:%S")),
                                                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(json.dumps(results[-1]), flush=True)
        return results

    if not parallel:
        results = [r for m in maps for r in run_map(m)]
        return 0 if all(r["exit"] == 0 for r in results) else 1
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    lt = live_tune_module()
    token = lt.GPU_LOCK
    t0 = time.time()
    lt.lock_acquire(token, f"an18 parallel-maps {','.join(maps)} heroes={','.join(heroes)}",
                    timeout=float(getattr(a, "lock_timeout", 3600.0) or 3600.0))
    try:
        with ThreadPoolExecutor(max_workers=len(maps)) as pool:
            futs = []
            for i, m in enumerate(maps):
                if i:
                    time.sleep(float(getattr(a, "stagger", 10.0) or 0.0))  # the start-up spikes apart
                futs.append(pool.submit(run_map, m))
            results = [r for f in futs for r in f.result()]
    finally:
        lt.lock_release(token)
    print(json.dumps({"parallel_maps": maps, "seconds": round(time.time() - t0), "launches": len(results)}), flush=True)
    return 0 if all(r["exit"] == 0 for r in results) else 1


def map_gpu_lock(map_key: str) -> Path:
    """--parallel-maps: the lock of one map's launches (the run itself holds the shared GPU token)."""
    return live_tune_module().GPU_LOCK.with_name(f"unmatched-gpu-{map_key}.lock")


def live_tune_module():
    if str(LIVE_TUNE.parent) not in sys.path:
        sys.path.insert(0, str(LIVE_TUNE.parent))
    import live_tune  # noqa: PLC0415

    return live_tune


# ---- trace parsing ----------------------------------------------------------------------------------------------------

def parse_run(run: Path, key: str | None = None) -> dict:
    """bench.trace.log of one launch -> shots {file name: {view, clip, token, figrects, clipposes, render}}, artlook,
    focus fighter, fighter -> hero, board / backdrop lines, the bench fixture of the launch.

    fighter -> hero: the focus fighter of the launch ('BENCH clip-pose ... fighter=<id>'; the engine resolves
    -BenchClipPoseFighter=<Key> through Specs()) is the character of the launch folder <frames>/<map>/<Key> (key; by
    default the folder name when it is a HEROES key). Any other fighter gets a key by the Idle length of its clippose
    line only when that length is unique among HEROES (unique_idle_keys) and the key is not the launch's own."""
    if key is None and run.name in HEROES:
        key = run.name
    trace = run / "bench.trace.log"
    if not trace.is_file():
        raise SheetError(f"{trace} missing")
    shots: dict[str, dict] = {}
    poses: list[dict] = []
    pending: list[dict] = []
    rects: list[dict] = []
    render = artlook = focus = ""
    scene: list[str] = []
    for raw in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RE_LINE.match(raw)
        line = m.group(1) if m else raw
        if line.startswith("ARTLOOK ") and not artlook:
            artlook = line
        elif line.startswith("RENDER tag=BENCH"):
            render = line
        elif re.search(r"concept-paste|lit3d|BENCH scene|board=c[0-9a-z]{24}", line) and len(scene) < 12:
            scene.append(line)
        if mm := RE_FOCUS.search(line):
            focus = mm.group(1)
        if line.startswith("BENCH clip-pose pose="):  # closes the clippose lines of one pose (all figures)
            poses, pending = pending, []
        if mm := RE_CLIPPOSE.search(line):
            pending.append({"fighter": mm.group(1), "clip": mm.group(2), "frame": int(mm.group(3)),
                          "t": float(mm.group(4)), "len": float(mm.group(5)), "rootDeltaUU": float(mm.group(6)),
                          "line": line})
        elif mm := RE_FIGRECT.search(line):
            rects.append({"fighter": mm.group(1), "view": mm.group(2), "x": float(mm.group(3)), "y": float(mm.group(4)),
                          "w": float(mm.group(5)), "h": float(mm.group(6))})
        elif mm := RE_SHOT.search(line):
            path = Path(mm.group(3).strip())
            nm = RE_SHOTNAME.search(path.name)
            if nm and mm.group(2) == "1":
                shots[path.name] = {"view": nm.group(1), "clip": nm.group(2), "token": nm.group(3),
                                    "path": str(run / path.name), "figrects": {r["fighter"]: r for r in rects},
                                    "clipposes": list(poses), "render": render}
            rects = []
    heroes: dict[str, str] = {}
    if focus and key:
        heroes[focus] = key
    unique = unique_idle_keys()
    for s in shots.values():
        for p in s["clipposes"]:
            if p["clip"] == "Idle" and p["fighter"] not in heroes:
                for k, idle_len in unique.items():
                    if k != key and abs(p["len"] - idle_len) < IDLE_EPS:
                        heroes[p["fighter"]] = k
    cmdline = (run / "cmdline.txt").read_text(encoding="utf-8").strip() if (run / "cmdline.txt").exists() else ""
    fx = RE_FIXTURE.search(cmdline)
    stamp = read_json(run / RUN_STAMP) or {}
    return {"run": str(run), "shots": shots, "artlook": artlook, "focus": focus, "heroes": heroes, "scene": scene,
            "key": key, "cmdline": cmdline, "fixture": Path(fx.group(1)).name if fx else "",
            "build": stamp.get("build")}


def has_k1(run: dict | None) -> bool:
    return bool(run) and any(s["view"] == VIEW_K1 for s in run["shots"].values())


def k1_run_for(map_runs: dict[str, dict], hero: str, extra: list[dict] | tuple = ()) -> dict | None:
    """The K1 launch of a card: the character's own launch if it shot K1; else a K1 launch with the same fixture file
    as its K2 launch (same build first; --k1-from launches, extra, before the frames folder); else the first one."""
    own = map_runs.get(hero)
    if has_k1(own):
        return own
    cands = [r for r in extra if has_k1(r)] + [map_runs[k] for k in HEROES if has_k1(map_runs.get(k))]
    if own is not None:
        same = [r for r in cands if r["fixture"] == own["fixture"]]
        same.sort(key=lambda r: r.get("build") != own.get("build"))  # stable: the same build first
        if same:
            return same[0]
    return cands[0] if cands else None


def hero_fighter(runs: list[dict], hero: str) -> str:
    """The fighter of a character: the K2 focus of its own launch, else the first id the traces map to it."""
    for r in runs:
        if r["focus"] and r["heroes"].get(r["focus"]) == hero:
            return r["focus"]
    ids = sorted(f for r in runs for f, h in r["heroes"].items() if h == hero)
    if not ids:
        raise SheetError(f"no fighter of {hero} in the traces")
    return ids[0]


# ---- composition ------------------------------------------------------------------------------------------------------

def crop_box(rects: list[dict], img_w: int, img_h: int, margin: float = 0.25) -> tuple[int, int, int, int]:
    """Union of the figure rects of all rows (the figure does not jump between rows) + margin on every side."""
    x0 = min(r["x"] for r in rects)
    y0 = min(r["y"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)
    mw, mh = (x1 - x0) * margin, (y1 - y0) * margin
    box = [int(max(0, x0 - mw)), int(max(0, y0 - mh)), int(min(img_w, x1 + mw)), int(min(img_h, y1 + mh))]
    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
        raise SheetError(f"degenerate crop {box}")
    return box[0], box[1], box[2], box[3]


def window_box(rects: list[dict], img_w: int, img_h: int, w: int, h: int) -> tuple[int, int, int, int]:
    """A w x h window (native pixels) centred on the union of the figure rects, kept inside the frame."""
    cx = (min(r["x"] for r in rects) + max(r["x"] + r["w"] for r in rects)) / 2
    cy = (min(r["y"] for r in rects) + max(r["y"] + r["h"] for r in rects)) / 2
    x0 = int(min(max(0, round(cx - w / 2)), max(0, img_w - w)))
    y0 = int(min(max(0, round(cy - h / 2)), max(0, img_h - h)))
    return x0, y0, x0 + w, y0 + h


def token_label(token: str, clip_len: float) -> tuple[int, float]:
    if token.startswith("q"):
        frame = round(int(token[1:]) / 100.0 * clip_len * FPS)
    else:
        frame = int(token[1:])
    return frame, frame * FRAME_MS


def git_short(path: str) -> str:
    r = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h", "--", path], capture_output=True, text=True)
    return r.stdout.strip() or "—"


def build_stamp(runs: list[dict]) -> str:
    cmd = runs[0]["cmdline"] if runs else ""
    if "UnrealEditor" in cmd:
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short=8", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
        return f"editor build (UnrealEditor -game), worktree HEAD {head} — черновик, Frames пересоберёт в пакете"
    builds = {json.dumps(r["build"], sort_keys=True) for r in runs if r.get("build")}
    if builds:  # the build the frames were shot on (run-stamp.json), not whatever is staged now
        return "packaged " + "; ".join(describe_build(json.loads(b)) for b in sorted(builds))
    stamp = read_json(STAGED_STAMP)
    if isinstance(stamp, dict) and stamp.get("commit"):
        return "packaged " + str(stamp["commit"])[:8]
    return "packaged"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def compose(cid: str, title: str, header: list[str], rows: list[dict], cols: list[str]) -> Image.Image:
    f_title, f_body, f_cap = _font(26), _font(18), _font(16)
    crop_ws = {}
    for c in cols:
        if c.endswith("K1"):
            crop_ws[c] = max((r["cells"][c].width for r in rows if r["cells"].get(c) is not None), default=CROP_H)
    widths = [crop_ws.get(c, K2_W) for c in cols]
    row_h = max(CROP_H, K2_W * 9 // 16) + 2 * GAP
    head_h = 46 + 26 * len(header) + 34
    W = LABEL_W + sum(widths) + GAP * (len(cols) + 1)
    H = head_h + row_h * len(rows) + GAP
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((GAP * 2, 10), f"{cid} · {title}", font=f_title, fill=ACCENT)
    for i, line in enumerate(header):
        d.text((GAP * 2, 48 + 26 * i), line, font=f_body, fill=FG2)
    x = LABEL_W + GAP
    for c, w in zip(cols, widths):
        d.text((x, head_h - 28), c, font=f_cap, fill=FG)
        x += w + GAP
    for i, r in enumerate(rows):
        y = head_h + row_h * i
        d.line([(0, y), (W, y)], fill=(60, 66, 84), width=1)
        d.text((GAP * 2, y + GAP + 4), r["label"], font=f_body, fill=FG)
        d.text((GAP * 2, y + GAP + 30), r["sub"], font=f_cap, fill=FG2)
        x = LABEL_W + GAP
        for c, w in zip(cols, widths):
            img = r["cells"].get(c)
            if img is None:
                d.rectangle([x, y + GAP, x + w, y + GAP + CROP_H], outline=(200, 60, 60), width=2)
                d.text((x + 8, y + GAP + 8), "нет кадра", font=f_cap, fill=(230, 90, 90))
            else:
                sheet.paste(img, (x + (w - img.width) // 2, y + GAP))
            x += w + GAP
    return sheet


def save_jpeg(img: Image.Image, path: Path) -> int:
    for q in (88, 84, 80, 76, 72, 68, 64, 60):
        img.save(path, "JPEG", quality=q, optimize=True, progressive=True)
        if path.stat().st_size <= SHEET_MAX_BYTES:
            return q
    raise SheetError(f"{path} > {SHEET_MAX_BYTES} bytes at quality 60")


def sheet_cards(a, reg: dict) -> set[str]:
    """--cards and / or --heroes (the four cards of each) -> card ids; neither -> SheetError (no 'every card' default)."""
    cards_arg = [c.strip() for c in (getattr(a, "cards", "") or "").split(",") if c.strip()]
    heroes_arg = [h.strip() for h in (getattr(a, "heroes", "") or "").split(",") if h.strip()]
    if not cards_arg and not heroes_arg:
        raise SheetError(need_hint("sheet"))
    bad = [h for h in heroes_arg if h not in HEROES]
    if bad:
        raise SheetError(f"--heroes {bad} not in HEROES ({', '.join(HEROES)})")
    only = set(cards_arg) | {cid for h in heroes_arg for cid in HEROES[h].cards}
    if only - set(reg):
        raise SheetError(f"--cards {sorted(only - set(reg))} are not clip cards of HEROES ({', '.join(reg)})")
    return only


def cmd_sheet(a) -> int:
    cards = load_cards(REPO)
    check_registry(cards)
    reg = clip_cards()
    only = sheet_cards(a, reg)
    manifest = {c["id"]: c for c in json.loads(MANIFEST.read_text(encoding="utf-8"))["clips"]
                if c.get("role") == "production"}
    frames_root = Path(a.frames)
    k1_from = Path(a.k1_from) if getattr(a, "k1_from", None) else None
    allow_missing = bool(getattr(a, "allow_missing", False))
    runs: dict[str, dict[str, dict]] = {}
    k1_extra: dict[str, list[dict]] = {}
    for map_key in MAPS:
        runs[map_key] = {}
        for hero in HEROES:
            d = frames_root / map_key / hero
            if (d / "bench.trace.log").exists():
                runs[map_key][hero] = parse_run(d, hero)
        k1_extra[map_key] = k1_source_runs(k1_from, map_key) if k1_from else []
    stamp = build_stamp([r for m in runs.values() for r in m.values()])
    summary = {"cards": {}, "problems": []}
    for cid, (hero, clip) in reg.items():
        if cid not in only:
            continue
        card = cards[cid]
        char, prefix = HEROES[hero].character, HEROES[hero].prefix
        if f"{prefix}-{clip}" not in manifest:
            raise SheetError(f"{cid}: no production clip {prefix}-{clip} in {MANIFEST.name}")
        mf = manifest[f"{prefix}-{clip}"]
        clip_len = float(mf["duration_s"]["measured"])
        n_frames = round(clip_len * FPS)
        contact = contact_frame(card) if clip == "LungeAttack" else None
        fbx = mf["source"]["files"][0]["path"]
        warns = sorted(set(re.findall(r"WARN: ([^)]*)\)", mf.get("notes", "")) and
                           [w.strip() for w in re.search(r"WARN: ([^)]*)\)", mf["notes"]).group(1).split(",")]))
        tokens = card_keyframes(card, clip)
        cols, problems, sources = [], [], []
        launches = {}
        rows = [{"token": t, "cells": {}} for t in tokens]
        for map_key, (map_name, board) in MAPS.items():
            mr = runs.get(map_key, {})
            k1_run, k2_run = k1_run_for(mr, hero, k1_extra.get(map_key, [])), mr.get(hero)
            launches[map_key] = {VIEW_K1: k1_run["run"] if k1_run else None, VIEW_K2: k2_run["run"] if k2_run else None}
            all_runs = [r for r in (k1_run, k2_run) if r]
            fighter = hero_fighter(all_runs, hero) if all_runs else ""
            if k1_run and k2_run and k1_run is not k2_run and k1_run["fixture"] != k2_run["fixture"]:
                problems.append(f"{map_key} K1 from the {k1_run['key']} launch (fixture {k1_run['fixture'] or '?'}), K2 "
                                f"from fixture {k2_run['fixture'] or '?'}: {fighter} may be another figure in K1; shoot "
                                f"K1 in the {hero} launch (run --heroes {hero},... --fixture ...)")
            if (k1_run and k2_run and k1_run is not k2_run and k1_run.get("build") and k2_run.get("build")
                    and k1_run["build"] != k2_run["build"]):
                problems.append(f"{map_key} K1 ({k1_run['run']}) shot on build {describe_build(k1_run['build'])}, K2 on "
                                f"{describe_build(k2_run['build'])}: re-shoot K1 on the current build")
            short = map_name.split()[0]
            c1, c2 = f"{short} K1", f"{short} K2×1,6"
            cols += [c1, c2]
            k1_shots, k2_shots = [], []
            for row in rows:
                for view, run, col in ((VIEW_K1, k1_run, c1), (VIEW_K2, k2_run, c2)):
                    name = f"bench-{view}-{clip}-{row['token']}-1920x1080.png"
                    shot = run["shots"].get(name) if run else None
                    if not shot or not Path(shot["path"]).is_file():
                        problems.append(f"{map_key} {view} {row['token']}: no frame")
                        row["cells"][col] = None
                        continue
                    pose = [p for p in shot["clipposes"] if p["fighter"] == fighter]
                    if not pose:
                        problems.append(f"{map_key} {view} {row['token']}: no clippose line of {fighter}")
                    for p in shot["clipposes"]:
                        if abs(p["rootDeltaUU"]) > ROOT_DELTA_MAX:
                            problems.append(f"{map_key} {name}: rootDeltaUU={p['rootDeltaUU']} ({p['fighter']})")
                    if "reference=1" not in shot["render"]:
                        problems.append(f"{map_key} {name}: RENDER reference!=1")
                    if "heroes=v2" not in run["artlook"]:
                        problems.append(f"{map_key} {name}: ARTLOOK without heroes=v2")
                    src = Path(shot["path"])
                    sources.append({"map": map_key, "board": board, "view": view, "pose": row["token"], "file": str(src),
                                    "sha256": sha256(src), "render": shot["render"],
                                    "clippose": pose[0]["line"] if pose else "",
                                    "figrect": shot["figrects"].get(fighter)})
                    if view == VIEW_K1:
                        k1_shots.append((row, col, src, shot["figrects"].get(fighter)))
                    else:
                        k2_shots.append((row, col, src, shot["figrects"].get(fighter)))
                    if pose:
                        row["t"], row["len"] = pose[0]["t"], pose[0]["len"]
            rects = [r for (_, _, _, r) in k1_shots if r]
            if k1_shots and len(rects) == len(k1_shots):
                with Image.open(k1_shots[0][2]) as probe:
                    box = crop_box(rects, probe.width, probe.height)
                for row, col, src, _ in k1_shots:
                    crop = Image.open(src).convert("RGB").crop(box)
                    row["cells"][col] = crop.resize((max(1, round(crop.width * CROP_H / crop.height)), CROP_H),
                                                    Image.LANCZOS)
            elif k1_shots:
                problems.append(f"{map_key} K1: figrect of {fighter} missing")
            # ВР-VS8-08: K2x1.6 at 1:1 - a 640x360 window of the frame centred on the figure (the whole frame scaled to
            # 640 px leaves the figure ~48 px tall, the pose unreadable); the whole frames stay in the sources
            k2_rects = [r for (_, _, _, r) in k2_shots if r]
            if k2_shots and len(k2_rects) == len(k2_shots):
                with Image.open(k2_shots[0][2]) as probe:
                    box = window_box(k2_rects, probe.width, probe.height, K2_W, K2_W * 9 // 16)
                for row, col, src, _ in k2_shots:
                    row["cells"][col] = Image.open(src).convert("RGB").crop(box)
            elif k2_shots:
                problems.append(f"{map_key} K2: figrect of {fighter} missing")
            for run in all_runs:
                if run and not any(board in s for s in run["scene"]) and board not in run["cmdline"]:
                    pass  # the fixture names the board; the trace check is in frames.json (scene lines)
        for row in rows:
            frame, ms = token_label(row["token"], clip_len)
            q = f" ({row['token']})" if row["token"].startswith("q") else ""
            row["label"] = f"к.{frame}{q}"
            mark = "  Contact" if contact is not None and frame == contact else ""
            row["sub"] = f"{ms:.0f} мс{mark}"
        header = [f"{char} · {clip} · {clip_len * 1000:.0f} мс = {n_frames} к. при {FPS} fps"
                  + (f" · Contact к.{contact} = {contact * FRAME_MS:.0f} мс" if contact is not None else "")
                  + (" · петля" if mf.get("loop") else ""),
                  f"клип {mf['id']} ({Path(fbx).name}, коммит {git_short(fbx)}) · сборка: {stamp}",
                  "доски: Marmoreal original c121b47f8d6eb28daccb76d05 (вклейка) · Sarpedon original "
                  "c7fa64a26c29a0835f2383e63 (lit3d) · K1 — кроп по figrect + 25 %, K2×1,6 — окно 640×360 1:1 у фигуры"]
        title = card["title"]
        out = Path(a.out) / cid
        missing = [f"{c} {r['token']}" for r in rows for c in cols if r["cells"].get(c) is None]
        if missing and not allow_missing:  # RB-12: never paint "нет кадра" over a committed sheet
            problems.append(f"sheet NOT written: {len(missing)} of {len(rows) * len(cols)} cells without a frame "
                            f"({', '.join(missing[:6])}{', …' if len(missing) > 6 else ''}); {out} untouched "
                            "(--allow-missing draws the gaps, for drafts outside docs/)")
            summary["cards"][cid] = {"rows": len(rows), "problems": len(problems), "written": False,
                                     "missingCells": len(missing)}
            summary["problems"] += [f"{cid}: {p}" for p in problems]
            print(f"{cid} {hero} {clip}: NOT written, {len(missing)} cells without a frame", flush=True)
            continue
        img = compose(cid, title, header, rows, cols)
        out.mkdir(parents=True, exist_ok=True)
        arr = np.asarray(img)
        qual = {}
        for name, data in (("sheet-color.jpg", arr), ("sheet-gray.jpg", gray709(arr)),
                           ("sheet-deutan.jpg", deuteranopia(arr))):
            qual[name] = save_jpeg(Image.fromarray(data, "RGB"), out / name)
        artlooks = sorted({r["artlook"] for m in runs.values() for r in m.values()})
        scene = sorted({s for m in runs.values() for r in m.values() for s in r["scene"]})
        frames_json = {"card": cid, "title": title, "clip": mf["id"], "fbx": fbx, "clipCommit": git_short(fbx),
                       "lengthS": clip_len, "frames": n_frames, "contactFrame": contact, "loop": mf.get("loop"),
                       "manifestWarns": warns, "build": stamp, "rows": tokens,
                       "rootDeltaMaxUU": max((abs(float(re.search(r"rootDeltaUU=(-?[\d.]+)", s["clippose"]).group(1)))
                                              for s in sources if s["clippose"]), default=None),
                       "artlook": artlooks, "sceneTrace": scene, "jpegQuality": qual, "problems": problems,
                       "launches": launches, "sources": sources}
        (out / "frames.json").write_text(json.dumps(frames_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        summary["cards"][cid] = {"rows": len(rows), "problems": len(problems), "rootDeltaMaxUU": frames_json["rootDeltaMaxUU"],
                                 "written": True, "bytes": {n: (out / n).stat().st_size for n in qual}}
        summary["problems"] += [f"{cid}: {p}" for p in problems]
        print(f"{cid} {hero} {clip}: rows={len(rows)} problems={len(problems)} -> {out}", flush=True)
    print(json.dumps({k: v for k, v in summary.items() if k != "cards"}, ensure_ascii=False, indent=1)[:4000])
    return 0 if not summary["problems"] else 1


# ---- self-test --------------------------------------------------------------------------------------------------------

SYNTH_FIGHTERS = {"f-1-hero": ("KingArthur", 2.5, (900, 500)), "f-1-sk0": ("Merlin", 3.0, (1100, 520)),
                  "f-0-hero": ("Medusa", 56 / 24, (700, 480)), "f-0-sk0": ("Harpy", 2.0, (500, 600))}


def _synthetic(root: Path, fighters: dict | None = None, heroes: list[str] | None = None, fixture: str = "",
               toks: dict | None = None) -> None:
    """Fake launches: 1920x1080 frames with a coloured block per figure; traces in the bench format. fighters: id ->
    (hero key, Idle length, (x, y)); heroes: the launches in run order (the first one also shoots K1); fixture: the
    -BenchFixture file name written to cmdline.txt; toks: the K1 pose list (default the AN-17 union)."""
    fighters = fighters or SYNTH_FIGHTERS
    # only heroes that have a synthetic fighter: a new HEROES record (pilot 2026-10-13, Angel) must not break --check
    heroes = heroes or [h for h in HEROES if any(v[0] == h for v in fighters.values())]
    toks = toks or union_tokens()
    lens = {"LungeAttack": 0.583, "HitReact": 0.417, "DeathSettle": 0.875}
    for map_key in MAPS:
        for hero in heroes:
            run = root / map_key / hero
            run.mkdir(parents=True, exist_ok=True)
            first = hero == heroes[0]
            views = [VIEW_K1, VIEW_K2] if first else [VIEW_K2]
            focus = next(f for f, v in fighters.items() if v[0] == hero)
            lines = ["2026.10.08-00.00.00 ARTLOOK art=1 source=default heroes=v2",
                     f"2026.10.08-00.00.00 BENCH clip-pose poses=35 views={len(views)} fighter={focus}",
                     f"2026.10.08-00.00.00 BENCH scene board={MAPS[map_key][1]}"]
            for clip in CLIPS:
                for t in toks[clip]:
                    for fid, (_, idle, _) in fighters.items():
                        ln = idle if clip == "Idle" else lens[clip]
                        fr = round(int(t[1:]) / 100 * ln * FPS) if t[0] == "q" else int(t[1:])
                        lines.append(f"2026.10.08-00.00.01 ARTPREVIEW clippose fighter={fid} clip={clip} frame={fr} "
                                     f"t={fr / FPS:.3f} len={ln:.3f} rootDeltaUU=0.00")
                    lines.append(f"2026.10.08-00.00.01 BENCH clip-pose pose=1/35 clip={clip} posed={len(fighters)}")
                    for v in views:
                        lines.append("2026.10.08-00.00.02 RENDER tag=BENCH rhi=D3D12 reference=1")
                        img = Image.new("RGB", (1920, 1080), (40, 70, 40))
                        dr = ImageDraw.Draw(img)
                        for fid, (_, _, (x, y)) in fighters.items():
                            dr.rectangle([x, y, x + 60, y + 120], fill=(200, 60, 60))
                            lines.append(f"2026.10.08-00.00.02 ARTPREVIEW figrect fighter={fid} view={v} x={x} y={y} "
                                         "w=60 h=120")
                        name = f"bench-{v}-{clip}-{t}-1920x1080.png"
                        img.save(run / name)
                        lines.append(f"2026.10.08-00.00.03 BENCH shot view={v} saved=1 path={run}/{name}")
            (run / "bench.trace.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
            fx = f" -BenchFixture=C:/x/Config/Bench/{fixture}" if fixture else ""
            (run / "cmdline.txt").write_text(f"UnrealEditor.exe -game{fx}\n", encoding="utf-8")


def cmd_check(_a) -> int:
    fails = []
    cards = load_cards(REPO)
    fails += [f"registry: {e}" for e in registry_errors(cards)]
    # the explicit card map keeps the MVP numbers AN-01..AN-16 (4 per character in CLIPS order)
    mvp = {f"AN-{4 * h + c + 1:02d}": (k, clip) for h, k in enumerate(("KingArthur", "Merlin", "Medusa", "Harpy"))
           for c, clip in enumerate(CLIPS)}
    reg = clip_cards()
    if {c: v for c, v in reg.items() if c in mvp} != mvp:
        fails.append("card map of the four MVP characters != AN-01..AN-16")
    # poses: the card rows give the expected key frames and every one is in the AN-17 union
    expect = {"AN-02": ["f00", "f02", "f04", "f07", "f09", "f12", "f14"], "AN-06": ["f00", "f03", "f06", "f08", "f10",
              "f12", "f14"], "AN-16": ["f00", "f03", "f08", "f13", "f17", "f21"], "AN-01": ["q0", "q25", "q50", "q75"]}
    for cid, want in expect.items():
        got = card_keyframes(cards[cid], reg[cid][1])
        if got != want:
            fails.append(f"keyframes {cid}: {got} != {want}")
    for cid, (hero, clip) in mvp.items():  # the MVP K1 pose list stays the AN-17 union (a new character may extend it)
        if clip != "Idle" and not set(card_keyframes(cards[cid], clip)) <= set(union_tokens()[clip]):
            fails.append(f"{cid}: frames outside the union")
    if contact_frame(cards["AN-02"]) != 7 or contact_frame(cards["AN-06"]) != 8:
        fails.append("contact frames AN-02 / AN-06")
    if pose_arg(union_tokens()).count(",") != 31:
        fails.append(f"union pose arg {pose_arg(union_tokens())}")
    if token_label("q50", 2.5) != (30, 1250.0) or token_label("f07", 0.583)[0] != 7:
        fails.append("token_label")
    if window_box([{"x": 10, "y": 1000, "w": 40, "h": 60}], 1920, 1080, 640, 360) != (0, 720, 640, 1080):
        fails.append("window_box")
    if crop_box([{"x": 100, "y": 100, "w": 40, "h": 80}], 1920, 1080) != (90, 80, 150, 200):
        fails.append(f"crop_box {crop_box([{'x': 100, 'y': 100, 'w': 40, 'h': 80}], 1920, 1080)}")
    px = np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8)
    g = gray709(px)
    if not (g[0, 0, 0] == 54 and g[0, 1, 0] == 182):
        fails.append(f"gray709 {g.tolist()}")
    dd = deuteranopia(px)
    if abs(int(dd[0, 0, 0]) - int(dd[0, 0, 1])) > 60:  # red and green move towards yellow-brown, R ~ G
        fails.append(f"deuteranopia red {dd[0, 0].tolist()}")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _synthetic(root / "frames")
        ns = argparse.Namespace(frames=str(root / "frames"), out=str(root / "out"), cards="AN-02,AN-09,AN-13")
        rc = cmd_sheet(ns)
        if rc != 0:
            fails.append("sheet on synthetic frames reported problems")
        for cid in ("AN-02", "AN-09", "AN-13"):
            for n in ("sheet-color.jpg", "sheet-gray.jpg", "sheet-deutan.jpg", "frames.json"):
                p = root / "out" / cid / n
                if not p.is_file():
                    fails.append(f"missing {cid}/{n}")
                elif n.endswith(".jpg") and p.stat().st_size > SHEET_MAX_BYTES:
                    fails.append(f"{cid}/{n} too big")
            fj = json.loads((root / "out" / cid / "frames.json").read_text(encoding="utf-8"))
            if any(not x["clippose"] for x in fj["sources"]):
                fails.append(f"{cid}: a source without its clippose line")
            if len(fj["sources"]) != len(fj["rows"]) * 4:
                fails.append(f"{cid}: sources {len(fj['sources'])} != rows x 4")
        with Image.open(root / "out" / "AN-02" / "sheet-gray.jpg") as im:
            a = np.asarray(im).astype(int)
            if np.abs(a[..., 0] - a[..., 1]).max() > 8:
                fails.append("gray sheet not gray")
        # a missing frame: the card is not written, the sheet already there stays byte for byte
        before = sha256(root / "out" / "AN-02" / "sheet-color.jpg")
        (root / "frames" / "sarpedon" / "KingArthur" / "bench-K2x1.6-LungeAttack-f07-1920x1080.png").unlink()
        if cmd_sheet(argparse.Namespace(frames=str(root / "frames"), out=str(root / "out"), cards="AN-02")) != 1:
            fails.append("sheet with a missing frame did not fail")
        if sha256(root / "out" / "AN-02" / "sheet-color.jpg") != before:
            fails.append("sheet with a missing frame overwrote the old sheet")
    print(json.dumps({"check": "PASS" if not fails else "FAIL", "fails": fails}, ensure_ascii=False, indent=1))
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # RB-11: the Bash pipe of an agent is cp1251
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="self-test on synthetic frames")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("--frames", default=str(FRAMES_DEFAULT))
    r.add_argument("--maps", default=",".join(MAPS))
    r.add_argument("--heroes", default="", help="REQUIRED: HEROES keys, one launch per map x hero (no default)")
    r.add_argument("--packaged", action="store_true")
    r.add_argument("--warmup", type=float, default=30.0)
    r.add_argument("--settle", type=float, default=3.0)
    r.add_argument("--measure", type=float, default=1.0)
    r.add_argument("--force", action="store_true", help="re-run launches that already finished")
    r.add_argument("--fixture", default="", help="bench fixture variant: FILE (one map) or marmoreal=FILE,sarpedon=FILE "
                                                  "(every hero) or <Key>:marmoreal=FILE,sarpedon=FILE;<Key2>:... (per "
                                                  "hero); Config/Bench file, passed to live_tune.py bench --fixture")
    r.add_argument("--k1-from", default=None, metavar="DIR",
                   help="no K1 launch: K1 comes from the finished launches DIR/<map>/<Key> (checked), K2 only")
    r.add_argument("--parallel-maps", action=argparse.BooleanOptionalAction, default=True,
                   help="the maps at once (default; one client per map, per-map GPU lock under the run's GPU token; "
                        "validated 2026-10-21); --no-parallel-maps = one map after the other")
    r.add_argument("--stagger", type=float, default=10.0, help="--parallel-maps: seconds between the map starts")
    r.add_argument("--lock-timeout", type=float, default=3600.0, help="--parallel-maps: wait for the GPU token, s")
    r.add_argument("--shot-delay", type=float, default=0.0,
                   help="-BenchShotDelay=S: s from the measurement window to the shot without ProfileGPU (default 0, "
                        "validated 2026-10-21; 3 = the old timing; a build without the flag ignores it)")
    s = sub.add_parser("sheet")
    s.add_argument("--frames", default=str(FRAMES_DEFAULT))
    s.add_argument("--out", default=str(OUT_DEFAULT))
    s.add_argument("--cards", default="", help="comma list of clip cards (this or --heroes is required)")
    s.add_argument("--heroes", default="", help="the four clip cards of these HEROES keys")
    s.add_argument("--k1-from", default=None, metavar="DIR", help="K1 launches DIR/<map>/<Key> (as in run --k1-from)")
    s.add_argument("--allow-missing", action="store_true",
                   help="write a card with gaps ('нет кадра' cells) instead of refusing it; drafts outside docs/ only")
    a = ap.parse_args(argv)
    try:
        if a.check:
            return cmd_check(a)
        if a.cmd == "run":
            return cmd_run(a)
        if a.cmd == "sheet":
            return cmd_sheet(a)
    except SheetError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
