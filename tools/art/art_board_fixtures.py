#!/usr/bin/env python3
"""Art-board fixtures (stage 3 T3.2, variant (a)): grid approximations of real maps.

"art fixture, не правила": the real Unmatched maps are graphs of round spaces, not
grids. This tool builds a GRID APPROXIMATION of a real map for the art review only:
every real space becomes one grid cell carrying the space's REAL zone keys (a
multizone space keeps all of its zones), every other grid cell is an obstacle. The
result is written as a committed fixture JSON (backend/prisma/fixtures/art-boards)
that backend/prisma/seed-art-fixture-boards.ts seeds into the ISOLATED test DB only.

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
cost, then fewer cells, then smaller W. Board ids are deterministic cuid-shaped
strings ('c' + 24 hex of sha256("unmatched-art-fixture:<key>:v<version>")), so a
reseed of the isolated DB yields the same ids.

Map images are NOT downloaded, cooked or committed: only their sha256 (recorded
earlier in docs/game-design/evidence/ART-002/PROMPTS.md) is carried as provenance.

  build   --maps <maps.json> [--out-dir DIR] [--keys k1,k2]  write the fixture JSONs
  check   [--maps <maps.json>] [--profiles <json>]           validate committed fixtures
          (schema, ids, W x H, real zone keys, >= 2 multizone cells, 4-connectivity,
          light sections != zones, consistency with the UE board profiles); with
          --maps the fixtures must also be byte-identical to a fresh build.

Status vocabulary: the fixtures and the lighting data are «предложено»; a live run
on them is «измерено»; nothing here is «художественно принято».
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
DEFAULT_OUT = REPO / "backend" / "prisma" / "fixtures" / "art-boards"
DEFAULT_PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
MAIN_CHECKOUT_MAPS = Path("C:/Users/ren/WebstormProjects/unmached/unmached/scraped-data/api/maps.json")
FIXTURE_SCHEMA = "unmatched.art-board-fixture/1"
GENERATOR = "tools/art/art_board_fixtures.py"
FIXTURE_VERSION = 1
CLUSTER_PX = 20.0
W_RANGE = range(6, 11)
H_RANGE = range(4, 7)
CELL_UU = 100.0
ID_RE = re.compile(r"^c[a-z0-9]{24}$")
LABEL = "art fixture, не правила"

# Real map images: sha256 only (fetched once to OS temp for ART-002, never kept in the repo).
MAP_IMAGES = {
    "sherwood-forest": {
        "sha256": "24f84b2dc91eee28a942f568be8e24a14b479bdaac51c11a2fc3dc9382b51162",
        "size": [1337, 742],
    },
    "t-rex-paddock": {
        "sha256": "c08794b2b3d7aae3451f1e0bb93e3d21bdf28d6579b6a5e26cd82f1c9a16e927",
        "size": [1337, 742],
    },
}
MAP_IMAGES_SOURCE = "docs/game-design/evidence/ART-002/PROMPTS.md"
DEFAULT_KEYS = ("sherwood-forest", "t-rex-paddock")


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


# ------------------------------------------------------------------ fixture
def fixture_board_id(key: str, version: int = FIXTURE_VERSION) -> str:
    return "c" + hashlib.sha256(f"unmatched-art-fixture:{key}:v{version}".encode("utf-8")).hexdigest()[:24]


def build_fixture(m: dict, maps_sha256: str) -> dict:
    key = m["key"]
    spaces = extract_spaces(m)
    if len(spaces) != m.get("spacesCount"):
        raise ValueError(f"{key}: {len(spaces)} spaces extracted, map says {m.get('spacesCount')}")
    zone_keys = [z["key"] for z in m["zones"]]
    grid, candidates = choose_grid(spaces)
    w, h = grid["width"], grid["height"]
    by_cell = {}
    for s, (x, y) in zip(spaces, grid["placed"]):
        by_cell[(x, y)] = s
    cells = []
    for y in range(h):
        for x in range(w):
            s = by_cell.get((x, y))
            if s is None:
                cells.append({"x": x, "y": y, "isObstacle": True})
            else:
                cells.append({"x": x, "y": y, "zones": [k for k in zone_keys if k in s["zones"]]})
    mapping = []
    for s, (x, y) in sorted(zip(spaces, grid["placed"]), key=lambda t: (t[1][1], t[1][0])):
        mapping.append({"cell": [x, y], "mapPx": [round(s["px"][0], 2), round(s["px"][1], 2)],
                        "zones": [k for k in zone_keys if k in s["zones"]]})
    counts = {k: 0 for k in zone_keys}
    multi = triple = 0
    for c in cells:
        zs = c.get("zones") or []
        for k in zs:
            counts[k] += 1
        multi += len(zs) > 1
        triple += len(zs) > 2
    img = MAP_IMAGES.get(key)
    fixture = {
        "schema": FIXTURE_SCHEMA,
        "artFixture": True,
        "label": LABEL,
        "status": "предложено",
        "key": key,
        "boardId": fixture_board_id(key),
        "name": f"ART FIXTURE · {m['name']}",
        "set": "art-fixture",
        "generator": {"tool": GENERATOR, "fixtureVersion": FIXTURE_VERSION},
        "source": {
            "mapsJson": "scraped-data/api/maps.json (gitignored; main checkout only)",
            "mapsJsonSha256": maps_sha256,
            "mapId": m.get("id"),
            "mapKey": key,
            "mapName": m.get("name"),
            "mapSizeClass": m.get("size"),
            "spacesCount": m.get("spacesCount"),
            "zonesCount": m.get("zonesCount"),
            "zoneKeys": zone_keys,
            "zoneColors": {z["key"]: z.get("color") for z in m["zones"]},
            "image": ({"sha256": img["sha256"], "sizePx": img["size"], "recordedIn": MAP_IMAGES_SOURCE,
                       "rule": "только sha256: изображение не скачивается, не кукается и не коммитится"}
                      if img else None),
        },
        "method": {
            "spaces": "circle = single-zone space; half-disk / wedge path = one zone's share of a multizone space; "
                      f"pieces within {CLUSTER_PX:g} px are one space",
            "grid": "optimal assignment of space centres to a W x H lattice over their bounding box; "
                    "smallest max displacement among 4-connected lattices (W 6..10, H 4..6)",
            "nonSpaceCells": "isObstacle (not a space on the real map)",
            "notRules": "adjacency, ranges and zones of the real map graph are NOT reproduced; art review only",
            "candidates": candidates,
        },
        "grid": {"width": w, "height": h,
                 "maxDisplacementCells": round(math.sqrt(grid["maxCost"]), 4),
                 "meanSquaredDisplacementCells": round(grid["sumCost"] / len(spaces), 4)},
        "summary": {"cells": w * h, "spaceCells": len(spaces), "obstacleCells": w * h - len(spaces),
                    "zoneCells": len(spaces), "multizoneCells": multi, "tripleZoneCells": triple,
                    "zoneCellCounts": counts, "connected4": grid["connected4"]},
        "cells": cells,
        "spaces": mapping,
    }
    return fixture


def dump(doc) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def load_maps(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    return decode_devalue_maps(json.loads(raw.decode("utf-8"))), sha256_bytes(raw)


# ------------------------------------------------------------------ validation
def board_to_world(profile_at: list[float], w: int, h: int) -> tuple[float, float]:
    """Normalised board coordinates (u, v in -0.5..0.5 of the board extent) -> world XY."""
    return profile_at[0] * w * CELL_UU, profile_at[1] * h * CELL_UU


def cell_world(x: int, y: int, w: int, h: int) -> tuple[float, float]:
    """INT-019: World(x,y) = ((x - (W-1)/2)*100, (y - (H-1)/2)*100)."""
    return (x - (w - 1) / 2.0) * CELL_UU, (y - (h - 1) / 2.0) * CELL_UU


def light_sections_vs_zones(fixture: dict, light: dict) -> dict:
    """Jaccard overlap of each non-ambient point light's section (cells whose centre is
    within half the attenuation radius) with every zone's cells. «Секции света != зоны»:
    a section must not coincide with one zone (max Jaccard < 0.5)."""
    w, h = fixture["grid"]["width"], fixture["grid"]["height"]
    zones: dict[str, set] = {}
    for c in fixture["cells"]:
        for k in c.get("zones") or []:
            zones.setdefault(k, set()).add((c["x"], c["y"]))
    out = {}
    for p in light.get("points", []):
        if p.get("role") == "fill":
            continue
        if "at" in p:
            lx, ly = board_to_world(p["at"], w, h)
        else:
            lx, ly = p["posUU"][0], p["posUU"][1]
        section = {(c["x"], c["y"]) for c in fixture["cells"]
                   if "zones" in c and math.dist(cell_world(c["x"], c["y"], w, h), (lx, ly)) <= 0.5 * p["radiusUU"]}
        best = (0.0, None)
        for k, cells in zones.items():
            union = section | cells
            j = len(section & cells) / len(union) if union else 0.0
            if j > best[0]:
                best = (j, k)
        out[p["name"]] = {"sectionCells": len(section), "maxJaccard": round(best[0], 4), "zone": best[1]}
    return out


def check_fixture(fx: dict) -> list[str]:
    errs = []
    if fx.get("schema") != FIXTURE_SCHEMA:
        errs.append("schema")
    if fx.get("artFixture") is not True or fx.get("label") != LABEL:
        errs.append("art fixture mark missing")
    if not ID_RE.match(fx.get("boardId", "")) or fx["boardId"] != fixture_board_id(fx.get("key", "")):
        errs.append("boardId not the deterministic cuid-shaped id")
    w, h = fx["grid"]["width"], fx["grid"]["height"]
    if len(fx["cells"]) != w * h:
        errs.append("cells != W*H")
    seen = set()
    real = set(fx["source"]["zoneKeys"])
    spaces = set()
    multi = 0
    for c in fx["cells"]:
        xy = (c["x"], c["y"])
        if xy in seen or not (0 <= c["x"] < w and 0 <= c["y"] < h):
            errs.append(f"bad/duplicate cell {xy}")
        seen.add(xy)
        zs = c.get("zones")
        if c.get("isObstacle"):
            if zs:
                errs.append(f"obstacle with zones {xy}")
            continue
        if not zs:
            errs.append(f"space without zones {xy}")
            continue
        if len(set(zs)) != len(zs) or not set(zs) <= real:
            errs.append(f"zones not real/unique at {xy}: {zs}")
        multi += len(zs) > 1
        spaces.add(xy)
    if len(spaces) != fx["source"]["spacesCount"]:
        errs.append("space cells != spacesCount")
    if multi < 2:
        errs.append("fewer than 2 multizone cells")
    if multi != fx["summary"]["multizoneCells"]:
        errs.append("summary.multizoneCells mismatch")
    if not connected4(spaces):
        errs.append("space cells not 4-connected")
    used = {k for c in fx["cells"] for k in c.get("zones") or []}
    if used != real:
        errs.append(f"not every real zone key used: missing {sorted(real - used)}")
    return errs


def check_profiles(fixtures: list[dict], profiles: dict) -> list[str]:
    errs = []
    boards = {b["id"]: b for b in profiles.get("boards", [])}
    styles = profiles.get("zoneStyles", {})
    lights = profiles.get("lightProfiles", {})
    for fx in fixtures:
        matches = [b for b in boards.values() if fx["boardId"] in (b.get("match", {}).get("boardIds") or [])]
        if len(matches) != 1:
            errs.append(f"{fx['key']}: {len(matches)} profile(s) match boardId {fx['boardId']}")
            continue
        b = matches[0]
        mt = b["match"]
        if (mt.get("width"), mt.get("height")) != (fx["grid"]["width"], fx["grid"]["height"]):
            errs.append(f"{fx['key']}: profile size {mt.get('width')}x{mt.get('height')} != fixture")
        if sorted(mt.get("zoneKeys") or []) != sorted(fx["source"]["zoneKeys"]):
            errs.append(f"{fx['key']}: profile zoneKeys != real zone keys")
        exp = b.get("expect") or {}
        s = fx["summary"]
        for k_prof, k_fx in (("cells", "cells"), ("zoneCells", "zoneCells"), ("multizoneCells", "multizoneCells"),
                             ("obstacles", "obstacleCells")):
            if exp.get(k_prof) != s[k_fx]:
                errs.append(f"{fx['key']}: expect.{k_prof}={exp.get(k_prof)} != fixture {s[k_fx]}")
        if exp.get("zoneCellCounts") != s["zoneCellCounts"]:
            errs.append(f"{fx['key']}: expect.zoneCellCounts != fixture")
        glyphs = [styles.get(k, {}).get("glyph") for k in fx["source"]["zoneKeys"]]
        strokes = [styles.get(k, {}).get("stroke") for k in fx["source"]["zoneKeys"]]
        if None in glyphs or len(set(glyphs)) != len(glyphs):
            errs.append(f"{fx['key']}: zone glyphs missing or not unique per board: {glyphs}")
        if None in strokes or len(set(strokes)) != len(strokes):
            errs.append(f"{fx['key']}: zone strokes missing or not unique per board: {strokes}")
        lp = lights.get(b.get("light"))
        if not lp:
            errs.append(f"{fx['key']}: light profile {b.get('light')!r} missing")
            continue
        for name, r in light_sections_vs_zones(fx, lp).items():
            if r["maxJaccard"] >= 0.5:
                errs.append(f"{fx['key']}: light section {name} coincides with zone {r['zone']} (J={r['maxJaccard']})")
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
def cmd_build(a) -> int:
    maps, sha = load_maps(Path(a.maps))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    keys = a.keys.split(",") if a.keys else list(DEFAULT_KEYS)
    for key in keys:
        m = next((x for x in maps if x.get("key") == key), None)
        if m is None:
            print(f"map {key!r} not in maps.json")
            return 2
        fx = build_fixture(m, sha)
        errs = check_fixture(fx)
        if errs:
            print(key, "INVALID", errs)
            return 1
        p = out / f"{key}.art-fixture.json"
        p.write_text(dump(fx), encoding="utf-8", newline="\n")
        s = fx["summary"]
        print(f"{key}: {fx['grid']['width']}x{fx['grid']['height']} id={fx['boardId']} spaces={s['spaceCells']} "
              f"obstacles={s['obstacleCells']} multizone={s['multizoneCells']} triple={s['tripleZoneCells']} "
              f"maxDisp={fx['grid']['maxDisplacementCells']} -> {p}")
    return 0


def cmd_check(a) -> int:
    out = Path(a.out_dir)
    files = sorted(out.glob("*.art-fixture.json"))
    if not files:
        print(f"no fixtures in {out}")
        return 1
    fixtures = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    bad = 0
    for f, fx in zip(files, fixtures):
        errs = check_fixture(fx)
        print(f"{f.name}: {'PASS' if not errs else 'FAIL ' + '; '.join(errs)}")
        bad += bool(errs)
    profiles_path = Path(a.profiles)
    if profiles_path.is_file():
        errs = check_profiles(fixtures, json.loads(profiles_path.read_text(encoding="utf-8")))
        print(f"profiles {profiles_path.name}: {'PASS' if not errs else 'FAIL ' + '; '.join(errs)}")
        bad += bool(errs)
        profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
        for fx in fixtures:
            b = next(b for b in profiles["boards"] if fx["boardId"] in (b["match"].get("boardIds") or []))
            print(f"  {fx['key']} light sections:", json.dumps(
                light_sections_vs_zones(fx, profiles["lightProfiles"][b["light"]]), ensure_ascii=False))
    else:
        print(f"profiles {profiles_path}: not found")
        bad += 1
    if a.maps:
        maps, sha = load_maps(Path(a.maps))
        for f, fx in zip(files, fixtures):
            m = next((x for x in maps if x.get("key") == fx["key"]), None)
            fresh = dump(build_fixture(m, sha)) if m else None
            same = fresh == f.read_text(encoding="utf-8")
            print(f"{f.name}: reproducible from maps.json {'PASS' if same else 'FAIL'}")
            bad += not same
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--maps", default=str(MAIN_CHECKOUT_MAPS))
    b.add_argument("--out-dir", default=str(DEFAULT_OUT))
    b.add_argument("--keys", default="")
    c = sub.add_parser("check")
    c.add_argument("--maps", default="")
    c.add_argument("--out-dir", default=str(DEFAULT_OUT))
    c.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    a = ap.parse_args(argv)
    return {"build": cmd_build, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
