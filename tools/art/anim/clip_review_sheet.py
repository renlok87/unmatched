"""AN-18 (ВР-17): acceptance sheets of the 16 D-11 clips from -BenchClipPose (AN-17) frames.

Commands
  run    8 bench launches (2 maps x 4 characters) through tools/art/render/live_tune.py bench. The first launch of a map
         (KingArthur) shoots K1 + K2x1.6 over the 35 AN-17 poses; the other three shoot K2x1.6 only, over the poses of
         their own character (K1 does not depend on the focus fighter, it is taken from the first launch).
           python tools/art/anim/clip_review_sheet.py run [--packaged] [--maps marmoreal,sarpedon] [--heroes ...]
  sheet  for every card AN-01...AN-16: rows = the key frames of the clip (column keyframes of the card; Idle - the
         quarters of the loop), columns = Marmoreal K1 (figure crop by figrect + 25 %), Marmoreal K2x1.6, Sarpedon K1
         (crop), Sarpedon K2x1.6; colour / gray Rec.709 / deuteranopia (Machado 2009, 1.0) JPEGs <= 2 MB, frames.json.
           python tools/art/anim/clip_review_sheet.py sheet [--frames C:/tmp/visual/AN-18] [--out docs/.../VISUAL]
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
MAPS = {"marmoreal": ("Marmoreal original", "c121b47f8d6eb28daccb76d05"),
        "sarpedon": ("Sarpedon original", "c7fa64a26c29a0835f2383e63")}
FPS = 24
FRAME_MS = 1000.0 / FPS
CLIPS = ("Idle", "LungeAttack", "HitReact", "DeathSettle")
# hero key (-BenchClipPoseFighter) -> manifest character, manifest id prefix, Idle length (s) that names it in the trace
HEROES = {"KingArthur": ("Arthur", "ARTH", 2.5), "Merlin": ("Merlin", "MER", 3.0),
          "Medusa": ("Medusa", "MED", 56.0 / 24.0), "Harpy": ("Harpy", "HAR", 2.0)}
CARDS = {f"AN-{4 * h + c + 1:02d}": (hero, clip) for h, hero in enumerate(HEROES) for c, clip in enumerate(CLIPS)}
IDLE_Q = (0, 25, 50, 75)
# the AN-17 pose union of the four build profiles (card AN-17, column keyframes)
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
RE_SHOTNAME = re.compile(r"bench-(.+?)-(Idle|LungeAttack|HitReact|DeathSettle)-(f\d+|q\d+)-1920x1080\.png$")


class SheetError(Exception):
    pass


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


def union_tokens() -> dict[str, list[str]]:
    out = {"Idle": [f"q{q}" for q in IDLE_Q]}
    out.update({c: [f"f{n:02d}" for n in fr] for c, fr in UNION.items()})
    return out


def hero_tokens(cards: dict, hero: str) -> dict[str, list[str]]:
    return {clip: card_keyframes(cards[cid], clip) for cid, (h, clip) in CARDS.items() if h == hero}


# ---- run --------------------------------------------------------------------------------------------------------------

def cmd_run(a) -> int:
    cards = load_cards(REPO)
    maps = [m for m in a.maps.split(",") if m]
    heroes = [h for h in a.heroes.split(",") if h]
    for hero in heroes:  # every card pose must be in the union K1 run (K1 cells of all four characters)
        for clip, toks in hero_tokens(cards, hero).items():
            if clip != "Idle" and not set(toks) <= set(union_tokens()[clip]):
                raise SheetError(f"{hero} {clip}: card frames {toks} outside the AN-17 union")
    results = []
    for map_key in maps:
        for hero in heroes:
            first = hero == "KingArthur"
            views = f"{VIEW_K1}+{VIEW_K2}" if first else VIEW_K2
            poses = pose_arg(union_tokens() if first else hero_tokens(cards, hero))
            out = Path(a.frames) / map_key / hero
            if (out / "exit.txt").exists() and "exit=0" in (out / "exit.txt").read_text() and not a.force:
                print(f"skip {out} (done)")
                continue
            cmd = [sys.executable, str(LIVE_TUNE), "bench", "--map", map_key, "--views", views, "--out", str(out),
                   f"--bench-warmup={a.warmup:g}", f"--bench-settle={a.settle:g}", f"--bench-measure={a.measure:g}",
                   f"--extra=-BenchClipPose={poses}", f"--extra=-BenchClipPoseFighter={hero}"]
            if a.packaged:
                cmd.append("--packaged")
            t0 = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] {map_key} {hero} views={views}", flush=True)
            r = subprocess.run(cmd, cwd=str(REPO))
            results.append({"map": map_key, "hero": hero, "exit": r.returncode, "seconds": round(time.time() - t0)})
            print(json.dumps(results[-1]), flush=True)
    return 0 if all(r["exit"] == 0 for r in results) else 1


# ---- trace parsing ----------------------------------------------------------------------------------------------------

def parse_run(run: Path) -> dict:
    """bench.trace.log of one launch -> shots {file name: {view, clip, token, figrects, clipposes, render}}, artlook,
    focus fighter, fighter -> hero (by the Idle length of its clippose line), board / backdrop lines."""
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
    for s in shots.values():
        for p in s["clipposes"]:
            if p["clip"] == "Idle":
                for key, (_, _, idle_len) in HEROES.items():
                    if abs(p["len"] - idle_len) < 0.01:
                        heroes[p["fighter"]] = key
    return {"run": str(run), "shots": shots, "artlook": artlook, "focus": focus, "heroes": heroes, "scene": scene,
            "cmdline": (run / "cmdline.txt").read_text(encoding="utf-8").strip() if (run / "cmdline.txt").exists() else ""}


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
    stamp = REPO / "unreal/Unmatched/Saved/StagedBuilds/Windows/stamp.json"
    if stamp.exists():
        try:
            return "packaged " + json.loads(stamp.read_text(encoding="utf-8")).get("commit", "?")[:8]
        except json.JSONDecodeError:
            pass
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


def cmd_sheet(a) -> int:
    cards = load_cards(REPO)
    manifest = {c["id"]: c for c in json.loads(MANIFEST.read_text(encoding="utf-8"))["clips"]
                if c.get("role") == "production"}
    frames_root = Path(a.frames)
    runs: dict[str, dict[str, dict]] = {}
    for map_key in MAPS:
        runs[map_key] = {}
        for hero in HEROES:
            d = frames_root / map_key / hero
            if (d / "bench.trace.log").exists():
                runs[map_key][hero] = parse_run(d)
    stamp = build_stamp([r for m in runs.values() for r in m.values()])
    only = set(a.cards.split(",")) if a.cards else set(CARDS)
    summary = {"cards": {}, "problems": []}
    for cid, (hero, clip) in CARDS.items():
        if cid not in only:
            continue
        card = cards[cid]
        char, prefix, _ = HEROES[hero]
        mf = manifest[f"{prefix}-{clip}"]
        clip_len = float(mf["duration_s"]["measured"])
        n_frames = round(clip_len * FPS)
        contact = contact_frame(card) if clip == "LungeAttack" else None
        fbx = mf["source"]["files"][0]["path"]
        warns = sorted(set(re.findall(r"WARN: ([^)]*)\)", mf.get("notes", "")) and
                           [w.strip() for w in re.search(r"WARN: ([^)]*)\)", mf["notes"]).group(1).split(",")]))
        tokens = card_keyframes(card, clip)
        cols, problems, sources = [], [], []
        rows = [{"token": t, "cells": {}} for t in tokens]
        for map_key, (map_name, board) in MAPS.items():
            mr = runs.get(map_key, {})
            k1_run, k2_run = mr.get("KingArthur"), mr.get(hero)
            all_runs = [r for r in (k1_run, k2_run) if r]
            fighter = hero_fighter(all_runs, hero) if all_runs else ""
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
        img = compose(cid, title, header, rows, cols)
        out = Path(a.out) / cid
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
                       "sources": sources}
        (out / "frames.json").write_text(json.dumps(frames_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        summary["cards"][cid] = {"rows": len(rows), "problems": len(problems), "rootDeltaMaxUU": frames_json["rootDeltaMaxUU"],
                                 "bytes": {n: (out / n).stat().st_size for n in qual}}
        summary["problems"] += [f"{cid}: {p}" for p in problems]
        print(f"{cid} {hero} {clip}: rows={len(rows)} problems={len(problems)} -> {out}", flush=True)
    print(json.dumps({k: v for k, v in summary.items() if k != "cards"}, ensure_ascii=False, indent=1)[:4000])
    return 0 if not summary["problems"] else 1


# ---- self-test --------------------------------------------------------------------------------------------------------

def _synthetic(root: Path) -> None:
    """Fake launches: 1920x1080 frames with a coloured block per figure; traces in the bench format."""
    fighters = {"f-1-hero": ("KingArthur", 2.5, (900, 500)), "f-1-sk0": ("Merlin", 3.0, (1100, 520)),
                "f-0-hero": ("Medusa", 56 / 24, (700, 480)), "f-0-sk0": ("Harpy", 2.0, (500, 600))}
    lens = {"LungeAttack": 0.583, "HitReact": 0.417, "DeathSettle": 0.875}
    for map_key in MAPS:
        for hero in HEROES:
            run = root / map_key / hero
            run.mkdir(parents=True, exist_ok=True)
            first = hero == "KingArthur"
            views = [VIEW_K1, VIEW_K2] if first else [VIEW_K2]
            toks = union_tokens()
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
            (run / "cmdline.txt").write_text("UnrealEditor.exe -game\n", encoding="utf-8")


def cmd_check(_a) -> int:
    fails = []
    cards = load_cards(REPO)
    # poses: the card rows give the expected key frames and every one is in the AN-17 union
    expect = {"AN-02": ["f00", "f02", "f04", "f07", "f09", "f12", "f14"], "AN-06": ["f00", "f03", "f06", "f08", "f10",
              "f12", "f14"], "AN-16": ["f00", "f03", "f08", "f13", "f17", "f21"], "AN-01": ["q0", "q25", "q50", "q75"]}
    for cid, want in expect.items():
        got = card_keyframes(cards[cid], CARDS[cid][1])
        if got != want:
            fails.append(f"keyframes {cid}: {got} != {want}")
    for cid, (hero, clip) in CARDS.items():
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
    print(json.dumps({"check": "PASS" if not fails else "FAIL", "fails": fails}, ensure_ascii=False, indent=1))
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="self-test on synthetic frames")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("--frames", default=str(FRAMES_DEFAULT))
    r.add_argument("--maps", default=",".join(MAPS))
    r.add_argument("--heroes", default=",".join(HEROES))
    r.add_argument("--packaged", action="store_true")
    r.add_argument("--warmup", type=float, default=30.0)
    r.add_argument("--settle", type=float, default=3.0)
    r.add_argument("--measure", type=float, default=1.0)
    r.add_argument("--force", action="store_true", help="re-run launches that already finished")
    s = sub.add_parser("sheet")
    s.add_argument("--frames", default=str(FRAMES_DEFAULT))
    s.add_argument("--out", default=str(OUT_DEFAULT))
    s.add_argument("--cards", default="", help="comma list, default AN-01..AN-16")
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
