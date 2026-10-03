#!/usr/bin/env python3
"""Board-art helpers (stage 3 T3.2): the maps.json space extraction, the lattice choice and the board profile validator.

RETIRED OUTPUT (2026-10-04, user decision «Давай оставим только доски, которые осуществлены на реальных досках из
игры.», docs/game-design/decisions/2026-10-04-real-boards-only.md): this tool used to write ART FIXTURE grid
approximations of real maps ("art fixture, не правила": backend/prisma/fixtures/art-boards/*.art-fixture.json, the
"ART FIXTURE · Sherwood Forest 8x5" / "T. Rex Paddock 7x5" Board rows and their UE profiles). Those boards, files and
profiles are gone, and the `build` command, the fixture schema and the light-section check went with them. Old runs on
them stay history. What stays here:
  * the maps.json reader and the SVG space extraction (decode_devalue_maps, extract_spaces) and the deterministic
    lattice choice (choose_grid) - tools/art/board_topology.py (the original-map topology fixtures) and
    tools/art/map_surface/build_map_textures.py use them;
  * `check`: the validator of unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json (light budgets, W4-A render
    blocks, night fog / map grade, T4.2 zone content, readability, map frame / backdrop).

Source data: scraped-data/api/maps.json (SvelteKit devalue payload, gitignored, only
in the main checkout). Per zone, `svgGroup` holds the zone's shapes on the map image:
a <circle> is a single-zone space; a <path> is the zone's share of a multizone space
(a half disk for two zones, a 1/3 wedge for three). Space centres:
  circle / ellipse -> (cx, cy)
  disk path        -> mean of its anchors (closed, cubic curves only, anchors on one
                      circle of a space-sized radius: a whole single-zone space)
  half disk path   -> midpoint of its only straight segment (the diameter)
  wedge path       -> vertex between its two straight segments (the disk centre)
A shape repeated verbatim within one zone counts once. Pieces of different zones within
20 px are one space. The counts are checked against the map's `spacesCount`.

Grid choice (deterministic): for W in 6..10, H in 4..6 (W*H >= spaces) the space
centres are assigned to the cell centres of a W x H lattice spanning their bounding box
by an optimal assignment (Hungarian, cost = squared distance in cell units). Among
the lattices whose space cells are 4-connected (orthogonal moves, the game's movement
rule) the one with the smallest maximum displacement wins; ties -> smaller total
cost, then fewer cells, then smaller W. fixture_board_id() keeps the id scheme of the
retired fixtures ('c' + 24 hex of sha256("unmatched-art-fixture:<key>:v<version>")) so
the topology tests can prove their ids never collide with it.

  check   [--profiles <json>]   validate the UE board profiles (exit 1 on an error)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
MAIN_CHECKOUT_MAPS = Path("C:/Users/ren/WebstormProjects/unmached/unmached/scraped-data/api/maps.json")
FIXTURE_VERSION = 1
CLUSTER_PX = 20.0
W_RANGE = range(6, 11)
H_RANGE = range(4, 7)
ID_RE = re.compile(r"^c[a-z0-9]{24}$")


# ------------------------------------------------------------------ source
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def decode_devalue_maps(doc: dict) -> list[dict]:
    """maps.json is a SvelteKit devalue payload: nodes[2].data is a flat array whose
    objects/arrays hold indices into the same array (negative = null)."""
    nodes = doc.get("nodes") or []
    if len(nodes) < 3 or not isinstance(nodes[2], dict) or "data" not in nodes[2]:
        raise ValueError("maps.json: nodes[2].data missing (not a devalue payload)")
    data = nodes[2]["data"]

    def hydrate(index, depth=0):
        if depth > 64:
            raise ValueError("maps.json: devalue nesting too deep")
        if not isinstance(index, int) or index < 0:
            return None
        value = data[index]
        if isinstance(value, dict):
            return {k: hydrate(v, depth + 1) for k, v in value.items()}
        if isinstance(value, list):
            return [hydrate(v, depth + 1) for v in value]
        return value

    root = hydrate(0)
    maps = root.get("maps") if isinstance(root, dict) else None
    if not isinstance(maps, list):
        raise ValueError("maps.json: root.maps missing")
    return maps


_TOKEN = re.compile(r"[MCLZmclz]|-?\d+(?:\.\d+)?(?:e-?\d+)?")
# A closed path of cubic curves only is a whole disk drawn as a path (Sarpedon, yellow):
# its distinct anchor points must lie on one circle of a space-sized radius.
DISK_PATH_RADIUS_PX = (40.0, 90.0)
DISK_PATH_TOLERANCE_PX = 1.0


def _disk_path_center(anchors: list[tuple[float, float]]) -> tuple[float, float] | None:
    pts = []
    for p in anchors:
        if all(math.hypot(p[0] - q[0], p[1] - q[1]) > 1e-6 for q in pts):
            pts.append(p)
    if len(pts) < 3:
        return None
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    radii = [math.hypot(p[0] - cx, p[1] - cy) for p in pts]
    r = sum(radii) / len(radii)
    if not (DISK_PATH_RADIUS_PX[0] <= r <= DISK_PATH_RADIUS_PX[1]):
        return None
    if max(abs(x - r) for x in radii) > DISK_PATH_TOLERANCE_PX:
        return None
    return cx, cy


def path_center(d: str) -> tuple[tuple[float, float], str]:
    """Centre of a zone's share of a multizone space (see module docstring); a closed
    curve-only path whose anchors lie on one space-sized circle is a whole single-zone
    space ("circle")."""
    toks = _TOKEN.findall(d)
    i = 0
    cmd = None
    pos = None
    lines = []  # (from, to) of every straight segment
    anchors = []  # every segment end point (the M start included)
    arity = {"M": 2, "C": 6, "L": 2}
    while i < len(toks):
        t = toks[i]
        if t in "MCLZmclz":
            if t.islower():
                raise ValueError(f"relative path command {t!r} not supported")
            cmd = t
            i += 1
            continue
        if cmd is None or cmd == "Z":
            raise ValueError(f"number without a command in path: {d[:60]}")
        n = arity[cmd]
        nums = [float(x) for x in toks[i:i + n]]
        if len(nums) != n:
            raise ValueError(f"truncated {cmd} in path: {d[:60]}")
        i += n
        end = (nums[-2], nums[-1])
        if cmd == "L":
            lines.append((pos, end))
        pos = end
        anchors.append(end)
    if len(lines) == 1:
        (a, b) = lines[0]
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), "half"
    if len(lines) >= 2:
        return lines[0][1], "wedge"
    disk = _disk_path_center(anchors)
    if disk is not None:
        return disk, "circle"
    raise ValueError(f"path without a straight segment: {d[:60]}")


# <circle cx cy r> and <ellipse cx cy rx ry> (Sarpedon draws its whole spaces as ellipses
# with rx ~= ry ~= 62.7) are both a whole single-zone space.
_CIRCLE = re.compile(r'<(?:circle|ellipse)\b[^>]*\bcx="(-?[\d.]+)"[^>]*\bcy="(-?[\d.]+)"')
_PATH = re.compile(r'<path\b[^>]*\bd="([^"]+)"')


def extract_spaces(m: dict) -> list[dict]:
    """Real spaces of one map with their zone keys (map zone order kept). A shape repeated
    verbatim within one zone (Sarpedon, brown: two wedges drawn twice each) is one piece."""
    pieces = []
    for zone in m.get("zones") or []:
        svg = zone.get("svgGroup") or ""
        seen = set()
        for cx, cy in _CIRCLE.findall(svg):
            if ("c", cx, cy) in seen:
                continue
            seen.add(("c", cx, cy))
            pieces.append((float(cx), float(cy), zone["key"], "circle"))
        for d in _PATH.findall(svg):
            if ("p", d) in seen:
                continue
            seen.add(("p", d))
            (x, y), kind = path_center(d)
            pieces.append((x, y, zone["key"], kind))
    spaces: list[dict] = []
    for x, y, key, kind in pieces:
        for s in spaces:
            if math.hypot(s["px"][0] - x, s["px"][1] - y) < CLUSTER_PX:
                if key not in s["zones"]:
                    s["zones"].append(key)
                s["pieces"].append(kind)
                break
        else:
            spaces.append({"px": [x, y], "zones": [key], "pieces": [kind]})
    for s in spaces:
        # single circle or 2 halves / 3 wedges; a circle never shares a space
        kinds = sorted(set(s["pieces"]))
        if kinds == ["circle"] and len(s["pieces"]) != 1:
            raise ValueError(f"{m.get('key')}: two circles collapse at {s['px']}")
        if "circle" in kinds and len(kinds) > 1:
            raise ValueError(f"{m.get('key')}: circle mixed with a multizone piece at {s['px']}")
        if len(s["zones"]) != len(s["pieces"]):
            raise ValueError(f"{m.get('key')}: duplicate zone piece at {s['px']}")
    spaces.sort(key=lambda s: (round(s["px"][1], 3), round(s["px"][0], 3)))
    return spaces


# ------------------------------------------------------------------ assignment
def hungarian(cost: list[list[float]]) -> list[int]:
    """Minimum-cost assignment of n rows to distinct columns of an n x m matrix
    (n <= m). Returns col index per row. Classic O(n^2 m) potentials method."""
    n = len(cost)
    m = len(cost[0]) if n else 0
    if n > m:
        raise ValueError("more rows than columns")
    inf = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    out = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def connected4(cells: set[tuple[int, int]]) -> bool:
    if not cells:
        return False
    start = min(cells)
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in cells and n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(cells)


def fit_grid(spaces: list[dict], w: int, h: int) -> dict:
    xs = [s["px"][0] for s in spaces]
    ys = [s["px"][1] for s in spaces]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    dx = (x1 - x0) / (w - 1)
    dy = (y1 - y0) / (h - 1)
    lattice = [(i, j) for j in range(h) for i in range(w)]
    cost = [[((s["px"][0] - (x0 + i * dx)) / dx) ** 2 + ((s["px"][1] - (y0 + j * dy)) / dy) ** 2
             for (i, j) in lattice] for s in spaces]
    cols = hungarian(cost)
    placed = [lattice[c] for c in cols]
    costs = [cost[r][c] for r, c in enumerate(cols)]
    return {"width": w, "height": h, "placed": placed, "maxCost": max(costs), "sumCost": sum(costs),
            "connected4": connected4(set(placed))}


def choose_grid(spaces: list[dict]) -> tuple[dict, list[dict]]:
    candidates = []
    for w in W_RANGE:
        for h in H_RANGE:
            if w * h < len(spaces):
                continue
            candidates.append(fit_grid(spaces, w, h))
    ok = [c for c in candidates if c["connected4"]]
    if not ok:
        raise ValueError("no 4-connected grid approximation in the searched range")
    ok.sort(key=lambda c: (round(c["maxCost"], 9), round(c["sumCost"], 9), c["width"] * c["height"], c["width"]))
    summary = [{"grid": f"{c['width']}x{c['height']}", "maxDisplacementCells": round(math.sqrt(c["maxCost"]), 4),
                "meanSquaredDisplacementCells": round(c["sumCost"] / len(spaces), 4),
                "connected4": c["connected4"]} for c in sorted(candidates, key=lambda c: (c["width"], c["height"]))]
    return ok[0], summary


# ------------------------------------------------------------------ ids
def fixture_board_id(key: str, version: int = FIXTURE_VERSION) -> str:
    return "c" + hashlib.sha256(f"unmatched-art-fixture:{key}:v{version}".encode("utf-8")).hexdigest()[:24]


def load_maps(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    return decode_devalue_maps(json.loads(raw.decode("utf-8"))), sha256_bytes(raw)


# ------------------------------------------------------------------ validation
def check_profiles(profiles: dict) -> list[str]:
    """The whole S08ArtBoardProfiles document: light budgets and render / night blocks, T4.2 content, the map-image
    board blocks (readability, map frame, backdrop)."""
    errs = []
    lights = profiles.get("lightProfiles", {})
    for lid, lp in lights.items():
        d = lp.get("directional") or {}
        pts = lp.get("points") or []
        if not d or d.get("castShadows") is not True:
            errs.append(f"light {lid}: exactly one directional light with a shadow required")
        if len(pts) > 6:
            errs.append(f"light {lid}: {len(pts)} point lights > 6")
        if any(p.get("castShadows") for p in pts):
            errs.append(f"light {lid}: point lights must not cast shadows")
        errs += check_render_blocks(lid, lp)
    errs += check_content_blocks(profiles)
    for b in profiles.get("boards", []):
        errs += check_readability_block(b.get("id", "?"), b)
        errs += check_frame_backdrop_blocks(b.get("id", "?"), b)
    return errs


GLYPH_NAMES = ("diamond", "bar1", "bars2", "bars3", "hbars2", "square", "cross", "x", "tee", "chevron", "ring")


def check_content_blocks(profiles: dict) -> list[str]:
    """T4.2 content: every zone style (and the fallback) names a /Game/ zone MI, and glyphMeshes maps each known
    glyph name to a /Game/ static mesh; every glyph a style uses has a mesh. Assets themselves are checked by the UE
    automation test Unmatched.S08.BoardArt.ZoneContent (parent, LayerColor, bounds)."""
    errs = []
    styles = dict(profiles.get("zoneStyles") or {})
    styles["(fallback)"] = profiles.get("fallbackZoneStyle") or {}
    for key, st in styles.items():
        mi = st.get("materialInstance")
        if not (isinstance(mi, str) and mi.startswith("/Game/") and " " not in mi):
            errs.append(f"zone style {key}: materialInstance {mi!r} is not a /Game/ package path")
    meshes = profiles.get("glyphMeshes") or {}
    for glyph, path in meshes.items():
        if glyph not in GLYPH_NAMES:
            errs.append(f"glyphMeshes: unknown glyph {glyph!r}")
        if not (isinstance(path, str) and path.startswith("/Game/") and " " not in path):
            errs.append(f"glyphMeshes {glyph}: {path!r} is not a /Game/ package path")
    for key, st in styles.items():
        if st.get("glyph") and st["glyph"] not in meshes:
            errs.append(f"zone style {key}: glyph {st['glyph']!r} has no glyph mesh")
    return errs


def check_render_blocks(lid: str, lp: dict) -> list[str]:
    """W4-A render rules (engine gate memo §1 items 1 and 3, G01): explicit
    units (points in candelas, directional in lux), a Movable SkyLight from a
    /Game/ cubemap instead of a point 'fill' ambient, a fixed exposure
    (histogram, min == max brightness, bias) and, if present, a CSM block."""
    errs = []
    units = lp.get("units") or {}
    if units.get("point") != "candelas" or units.get("directional") != "lux":
        errs.append(f"light {lid}: units must be {{point: candelas, directional: lux}} (G01), got {units or None}")
    sky = lp.get("sky") or {}
    if (sky.get("source") != "cubemap" or not str(sky.get("cubemap", "")).startswith("/Game/")
            or not isinstance(sky.get("intensity"), (int, float)) or sky.get("intensity") <= 0):
        errs.append(f"light {lid}: sky needs source=cubemap, a /Game/ cubemap and intensity > 0")
    if any(p.get("role") == "fill" for p in lp.get("points") or []):
        errs.append(f"light {lid}: a point 'fill' ambient is replaced by the SkyLight (memo §1 item 3)")
    ex = lp.get("exposure") or {}
    mn, mx = ex.get("minBrightness"), ex.get("maxBrightness")
    if (ex.get("method") != "histogram-fixed" or not isinstance(mn, (int, float)) or not isinstance(mx, (int, float))
            or mn <= 0 or abs(mn - mx) > 1e-6 or not isinstance(ex.get("bias"), (int, float))):
        errs.append(f"light {lid}: exposure needs method=histogram-fixed, minBrightness == maxBrightness > 0 and bias")
    elif isinstance(ex.get("ev100"), (int, float)) and abs(2 ** ex["ev100"] - mn) > 1e-3:
        errs.append(f"light {lid}: exposure ev100 {ex['ev100']} != log2(minBrightness {mn})")
    sh = (lp.get("directional") or {}).get("shadow")
    if sh is not None:
        if not (isinstance(sh.get("distanceUU"), (int, float)) and sh["distanceUU"] > 0
                and isinstance(sh.get("cascades"), int) and 1 <= sh["cascades"] <= 4
                and 0 <= float(sh.get("contactShadowLength", 0.0)) <= 0.1):
            errs.append(f"light {lid}: directional.shadow needs distanceUU > 0, cascades 1..4, contactShadowLength 0..0.1")
    errs += check_night_blocks(lid, lp)
    return errs


def _nums(v, n, lo, hi) -> bool:
    return (isinstance(v, list) and len(v) == n and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                         and lo <= x <= hi for x in v))


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check_night_blocks(lid: str, lp: dict) -> list[str]:
    """ENV-MAPS P2 (profile rev 9): the optional "fog" (ExponentialHeightFog) and "mapGrade" (M_MapBoard MID night
    grade) blocks, the same ranges as S08BoardArt.cpp ParseRenderBlocks (a broken block rejects the profile)."""
    errs = []
    fog = lp.get("fog")
    if fog is not None:
        start, end = fog.get("startDistanceUU"), fog.get("endDistanceUU", 0)
        if not (isinstance(fog, dict) and _nums(fog.get("colorLinear"), 3, 0.0, 10.0)
                and _num(fog.get("density")) and 0 < fog["density"] <= 1
                and _num(fog.get("heightFalloff")) and 0 < fog["heightFalloff"] <= 2
                and _num(fog.get("heightZ")) and abs(fog["heightZ"]) <= 100000
                and _num(start) and 0 <= start <= 100000
                and _num(end) and (end == 0 or start < end <= 1000000)
                and _num(fog.get("maxOpacity", 1.0)) and 0 <= fog.get("maxOpacity", 1.0) <= 1):
            errs.append(f"light {lid}: fog needs colorLinear [r,g,b] 0..10, density 0..1, heightFalloff 0..2, heightZ, "
                        "startDistanceUU >= 0, endDistanceUU 0 or > start, maxOpacity 0..1")
    grade = lp.get("mapGrade")
    if grade is not None:
        if not (isinstance(grade, dict) and _num(grade.get("nightEV")) and -4 <= grade["nightEV"] <= 2
                and _num(grade.get("nightSaturation")) and 0 <= grade["nightSaturation"] <= 1.5
                and _num(grade.get("lift")) and 0 <= grade["lift"] <= 20
                and ("nightTintLinear" not in grade or _nums(grade["nightTintLinear"], 3, 0.0, 4.0))):
            errs.append(f"light {lid}: mapGrade needs nightEV -4..2, nightSaturation 0..1.5, lift 0..20 and an optional "
                        "nightTintLinear [r,g,b] 0..4")
        # ENV-MAPS P4 (M_MapBoard graph v2): optional mask-only zone-separation terms, identity when absent
        elif not ((_num(grade.get("maskSaturation", 1.0)) and 0 <= grade.get("maskSaturation", 1.0) <= 3)
                  and (_num(grade.get("liftSaturation", 1.0)) and 0 <= grade.get("liftSaturation", 1.0) <= 3)
                  and ("maskInverseTintLinear" not in grade or _nums(grade["maskInverseTintLinear"], 3, 0.0, 4.0))):
            errs.append(f"light {lid}: mapGrade optional maskSaturation 0..3, liftSaturation 0..3 and "
                        "maskInverseTintLinear [r,g,b] 0..4")
    return errs


def _hex(v) -> bool:
    return isinstance(v, str) and len(v) == 7 and v[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in v[1:])


READ_RING_RADIUS_UU = 36.0  # S08MapSurfaceSpec::RingRadiusUU


def check_readability_block(bid: str, board: dict) -> list[str]:
    """ENV-MAPS P4: the optional board "readability" block, the same rules as S08BoardArt.cpp ParseReadability:
    map-image boards only (a grid with the block is rejected), every present sub-block complete and in range."""
    if "readability" not in board:
        return []
    errs = []
    r = board["readability"]
    if board.get("surface") != "map-image":
        return [f"board {bid}: readability is for map-image boards only"]
    if not isinstance(r, dict):
        return [f"board {bid}: readability must be an object"]
    for flag in ("labelPlates", "leaderPip"):
        if flag in r and not isinstance(r[flag], bool):
            errs.append(f"board {bid}: readability.{flag} must be true|false")

    def rng(o, key, lo, hi, default):
        v = o.get(key, default)
        return _num(v) and lo <= v <= hi

    if "reach" in r:
        reach = r["reach"]
        ok = (isinstance(reach, dict) and all(_hex(reach[k]) for k in ("colorSrgb", "strokeSrgb") if k in reach)
              and rng(reach, "segments", 12, 96, 48) and float(reach.get("segments", 48)).is_integer()
              and rng(reach, "widthUU", 1, 6, 3.5) and rng(reach, "strokeUU", 0.25, 3, 1.0))
        if not ok:
            errs.append(f"board {bid}: readability.reach needs colorSrgb / strokeSrgb #RRGGBB, segments 12..96 (whole), "
                        "widthUU 1..6, strokeUU 0.25..3")
        else:
            half = reach.get("widthUU", 3.5) / 2 + reach.get("strokeUU", 1.0)
            if READ_RING_RADIUS_UU + half > 40 or READ_RING_RADIUS_UU - half < 30:
                errs.append(f"board {bid}: readability.reach widthUU / 2 + strokeUU must keep the ring between r 30 and r 40")
    if "contactShadow" in r:
        cs = r["contactShadow"]
        if not (isinstance(cs, dict) and rng(cs, "diameterUU", 20, 160, 64) and rng(cs, "strength", 0, 1, 0.5)
                and rng(cs, "softness", 0.1, 1, 0.55)):
            errs.append(f"board {bid}: readability.contactShadow needs diameterUU 20..160, strength 0..1, softness 0.1..1")
    if "frameWood" in r:
        fw = r["frameWood"]
        if not (isinstance(fw, dict) and rng(fw, "valueScaleSrgb", 0.2, 1, 0.7) and rng(fw, "saturation", 0, 1, 0.75)):
            errs.append(f"board {bid}: readability.frameWood needs valueScaleSrgb 0.2..1 and saturation 0..1")
    return errs


def check_frame_backdrop_blocks(bid: str, board: dict) -> list[str]:
    """ENV-MAPS P5 track C: the optional "mapFrame" ({"kit": "frame-002"}, mapImage.frameUU 24) and "backdrop" blocks,
    the same rules as S08BoardArt.cpp ParseMapFrame / ParseBackdrop (map-image boards only; the backdrop rules and the
    camera model are mirrored in tools/art/map_surface/backdrop.py)."""
    errs = []
    for key in ("mapFrame", "backdrop"):
        if key in board and board.get("surface") != "map-image":
            errs.append(f"board {bid}: {key} is for map-image boards only")
    if errs:
        return errs
    if "mapFrame" in board:
        mf = board["mapFrame"]
        if not isinstance(mf, dict) or mf.get("kit") != "frame-002":
            errs.append(f"board {bid}: mapFrame.kit must be 'frame-002'")
        elif set(mf) - {"kit", "note"}:
            errs.append(f"board {bid}: mapFrame.{sorted(set(mf) - {'kit', 'note'})[0]} is not a field (kit, note)")
        elif (board.get("mapImage") or {}).get("frameUU", 24) != 24:
            errs.append(f"board {bid}: mapFrame kit frame-002 needs mapImage.frameUU 24")
    if "backdrop" in board:
        sys.path.insert(0, str(REPO / "tools" / "art" / "map_surface"))
        import backdrop as backdrop_lib  # noqa: E402  (plain Python mirror of the C++ parser + camera model)
        errs += backdrop_lib.validate_block(board["backdrop"], backdrop_lib.map_half(board), bid)
    return errs


# ------------------------------------------------------------------ commands
def cmd_check(a) -> int:
    profiles_path = Path(a.profiles)
    if not profiles_path.is_file():
        print(f"profiles {profiles_path}: not found")
        return 1
    errs = check_profiles(json.loads(profiles_path.read_text(encoding="utf-8")))
    print(f"profiles {profiles_path.name}: {'PASS' if not errs else 'FAIL ' + '; '.join(errs)}")
    return 0 if not errs else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    a = ap.parse_args(argv)
    return {"check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
