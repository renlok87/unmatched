#!/usr/bin/env python3
"""Board topology fixtures (ENV-MAPS, track D): the ORIGINAL maps of Battle of Legends
Vol. 1 (Marmoreal, Sarpedon) as space graphs the game engine plays on.

Unlike tools/art/art_board_fixtures.py (grid approximations, "art fixture, не правила"),
these fixtures carry the real rules topology: every space of the original map, its real
zones, its start slot and its links (the lines printed on the map). The engine treats a
board as a graph as soon as one cell carries `links`: the neighbours of a cell are then
EXACTLY its links (symmetric); lattice (x, y) positions only name the spaces.

Inputs
  scraped-data/api/maps.json (gitignored, main checkout)  zone keys/colours, spacesCount,
      the zone SVG (space centres + zone membership, re-derived here and compared with
      the research numbers), the set key.
  docs/game-design/evidence/ENV-MAPS/2026-09-30-research/<map>.topology.json (committed)
      space ids (M01..M31, S01..S38), centres, zones, starts, edges.
  .../votes.json (committed): the three independent transcriptions per edge / start;
      the build refuses any edge or start that is not unanimous.
  scraped-data/images/maps/<map>.webp (gitignored, ENV-U3): sha256 verified when present.

Output: backend/prisma/fixtures/boards/<map>.topology.json (schema unmatched.board-topology/1).
No SVG path, no image data and no URL is written: only numbers, ids and hashes (ENV-U3).

Lattice placement: art_board_fixtures.choose_grid over the space centres in id order
(optimal assignment to a W x H lattice; Marmoreal 7x6, Sarpedon 9x6); every lattice
position without a space is an explicit {isObstacle: true} cell. A cell's `links` are the
lattice positions of its edge partners; `layout` is its centre in map-image px
(1337 x 866); `start` is its start slot (1..4). Board ids are cuid-shaped and
deterministic: 'c' + 24 hex of sha256("unmatched-board-topology:<map>:v<version>")
(a namespace distinct from the art fixtures).

  build     [--maps P] [--evidence-dir D] [--out-dir D] [--keys k1,k2]   write the fixtures
  check     [--maps P] [--evidence-dir D] [--out-dir D]   rebuild, compare byte-for-byte
  validate  [--out-dir D] [--evidence-dir D] [files...]   schema + invariants (+ evidence)

Status vocabulary: the topology is «измерено» (research 2026-09-30); nothing here is
«художественно принято».
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import art_board_fixtures as ABF  # noqa: E402

REPO = HERE.parents[1]
MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
MAIN_CHECKOUT_MAPS = ABF.MAIN_CHECKOUT_MAPS
MAIN_CHECKOUT_IMAGES = MAIN_CHECKOUT / "scraped-data" / "images" / "maps"
DEFAULT_OUT = REPO / "backend" / "prisma" / "fixtures" / "boards"
EVIDENCE_REL = "docs/game-design/evidence/ENV-MAPS/2026-09-30-research"
DEFAULT_EVIDENCE = REPO / EVIDENCE_REL

SCHEMA = "unmatched.board-topology/1"
EVIDENCE_SCHEMA = "unmatched.board-topology.draft/1"
GENERATOR = "tools/art/board_topology.py"
TOPOLOGY_VERSION = 1
SET_KEY = "battle-of-legends-volume-one"
UU_PER_PX = 0.6666667
SPACE_RADIUS_PX = 63
IMAGE_SIZE = [1337, 866]
CENTRE_TOLERANCE_PX = 0.5  # SVG-derived centre vs the research centre (rounded to 0.1 px)
PASSES = ("passA", "passB", "passC")
ID_RE = ABF.ID_RE
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
FORBIDDEN_TEXT = ("<path", "<svg", "<circle", "<ellipse", "data:image", "http://", "https://", "base64")

# Expected facts per map (research 2026-09-30, README + checks.json + votes.json).
MAPS = {
    "marmoreal": {
        "name": "Marmoreal", "prefix": "M", "spaces": 31, "edges": 42, "lattice": (7, 6),
        "zones": ["gray", "green", "blue", "violet", "purple", "red", "brown", "yellow"],
        "starts": {1: "M13", 2: "M31", 3: "M03", 4: "M11"},
        # M22-M29 and M22-M30 run under the glass bridge M25-M26: no junction, no extra space.
        "crossings": [[["M22", "M29"], ["M25", "M26"]], [["M22", "M30"], ["M25", "M26"]]],
    },
    "sarpedon": {
        "name": "Sarpedon", "prefix": "S", "spaces": 38, "edges": 61, "lattice": (9, 6),
        "zones": ["green", "yellow", "brown", "red", "purple", "blue"],
        "starts": {1: "S20", 2: "S32", 3: "S03", 4: "S14"},
        "crossings": [],
    },
}
DEFAULT_KEYS = tuple(MAPS)


# ------------------------------------------------------------------ helpers
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def topology_board_id(key: str, version: int = TOPOLOGY_VERSION) -> str:
    return "c" + hashlib.sha256(f"unmatched-board-topology:{key}:v{version}".encode("utf-8")).hexdigest()[:24]


def edge_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def segments_cross(p1, p2, p3, p4) -> bool:
    """Proper intersection of the open segments p1p2 and p3p4 (shared end points and
    collinear touching do not count)."""
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def chord_crossings(centres: dict[str, tuple[float, float]], edges: list[list[str]]) -> list[list[list[str]]]:
    """Pairs of edges whose straight chords between space centres cross (no shared space)."""
    out = []
    for (a, b), (c, d) in itertools.combinations(sorted(edge_key(*e) for e in edges), 2):
        if len({a, b, c, d}) < 4:
            continue
        if segments_cross(centres[a], centres[b], centres[c], centres[d]):
            out.append(sorted([[a, b], [c, d]]))
    return sorted(out)


def graph_connected(ids: list[str], adj: dict[str, set]) -> bool:
    if not ids:
        return False
    seen = {ids[0]}
    q = deque([ids[0]])
    while q:
        u = q.popleft()
        for v in adj.get(u, ()):
            if v not in seen:
                seen.add(v)
                q.append(v)
    return len(seen) == len(ids)


def lattice_placement(spaces: list[dict]) -> tuple[int, int, dict[str, tuple[int, int]]]:
    """choose_grid of the art fixtures over the space centres, spaces in id order."""
    ordered = sorted(spaces, key=lambda s: s["id"])
    grid, _ = ABF.choose_grid([{"px": [s["layout"]["x"], s["layout"]["y"]]} for s in ordered])
    placed = {s["id"]: (int(x), int(y)) for s, (x, y) in zip(ordered, grid["placed"])}
    return grid["width"], grid["height"], placed


def lattice_neighbour_stats(spaces: list[dict], edges: list[list[str]]) -> dict:
    pos = {s["id"]: (s["x"], s["y"]) for s in spaces}
    at = {v: k for k, v in pos.items()}
    linked = {edge_key(*e) for e in edges}
    pairs = set()
    for sid, (x, y) in pos.items():
        for dx, dy in ((1, 0), (0, 1)):
            other = at.get((x + dx, y + dy))
            if other:
                pairs.add(edge_key(sid, other))
    not_linked = sorted(pairs - linked)
    return {
        "latticeNeighbourPairs": len(pairs),
        "latticeNeighbourPairsLinked": len(pairs & linked),
        "latticeNeighbourPairsNotLinked": len(not_linked),
        "latticeNeighboursNotLinked": [list(p) for p in not_linked],
        "linksBetweenNonLatticeNeighbours": len(linked - pairs),
    }


def _pretty(v, level: int) -> str:
    """Indented JSON (1 space per level) with lists of scalars / of scalar lists inline."""
    pad = " " * level
    flat = lambda e: not isinstance(e, (list, dict))  # noqa: E731
    if isinstance(v, list) and all(flat(e) or (isinstance(e, list) and all(map(flat, e))) for e in v):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[\n" + ",\n".join(f"{pad} {_pretty(e, level + 1)}" for e in v) + f"\n{pad}]"
    if isinstance(v, dict) and v:
        return "{\n" + ",\n".join(f"{pad} {json.dumps(k, ensure_ascii=False)}: {_pretty(e, level + 1)}"
                                  for k, e in v.items()) + f"\n{pad}}}"
    return json.dumps(v, ensure_ascii=False)


def dump(doc: dict) -> str:
    """Deterministic JSON (LF, UTF-8): nested blocks indented, one entry per line in the
    long lists (zones, spaces, edges, crossings, cells)."""
    one_per_line = ("zones", "spaces", "edges", "cells", "crossings")
    items = list(doc.items())
    out = ["{"]
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if k in one_per_line and isinstance(v, list) and v:
            inner = ",\n".join("  " + json.dumps(e, ensure_ascii=False) for e in v)
            out.append(f" {json.dumps(k)}: [\n{inner}\n ]{comma}")
        else:
            out.append(f" {json.dumps(k)}: {_pretty(v, 1)}{comma}")
    out.append("}")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ inputs
def load_evidence(evidence_dir: Path, key: str) -> tuple[dict, dict]:
    topo = json.loads((evidence_dir / f"{key}.topology.json").read_text(encoding="utf-8"))
    votes = json.loads((evidence_dir / "votes.json").read_text(encoding="utf-8"))
    if topo.get("schema") != EVIDENCE_SCHEMA or topo.get("map") != key:
        raise ValueError(f"{key}: evidence topology schema/map mismatch")
    if key not in votes:
        raise ValueError(f"{key}: votes.json has no entry")
    return topo, votes[key]


def check_votes(key: str, topo: dict, votes: dict) -> dict:
    """Every evidence edge and start must be unanimous across the three passes; returns
    the counts recorded as provenance."""
    edges = {"-".join(edge_key(*e)) for e in topo["edges"]}
    voted = votes.get("votes") or {}
    if set(voted) != edges:
        raise ValueError(f"{key}: votes.json edges != evidence edges "
                         f"(+{sorted(set(voted) - edges)} -{sorted(edges - set(voted))})")
    unanimous = sum(sorted(v) == sorted(PASSES) for v in voted.values())
    if unanimous != len(edges):
        raise ValueError(f"{key}: {len(edges) - unanimous} edge(s) not unanimous")
    starts_ev = {str(s["start"]): s["id"] for s in topo["spaces"] if s.get("start") is not None}
    st = votes.get("starts") or {}
    starts_unanimous = sum(set(st.get(slot, {}).values()) == {sid} and set(st.get(slot, {})) == set(PASSES)
                           for slot, sid in starts_ev.items())
    if starts_unanimous != len(starts_ev) or set(st) != set(starts_ev):
        raise ValueError(f"{key}: start slots not unanimous / not matching the evidence")
    web_edges = set(votes.get("web_edges") or [])
    web_starts = votes.get("web_starts") or {}
    return {
        "edgesUnanimous": f"{unanimous}/{len(edges)}",
        "startsUnanimous": f"{starts_unanimous}/{len(starts_ev)}",
        "externalEdgesAgree": f"{len(web_edges & edges)}/{len(edges)}" + ("" if web_edges <= edges else " (+extra)"),
        "externalStartsAgree": f"{sum(web_starts.get(k) == v for k, v in starts_ev.items())}/{len(starts_ev)}",
    }


def svg_crosscheck(key: str, m: dict, topo: dict) -> dict:
    """Re-derive centres and zones from the zone SVG of maps.json and compare them with
    the research numbers: same count, every centre within CENTRE_TOLERANCE_PX, same zones."""
    svg_spaces = ABF.extract_spaces(m)
    if len(svg_spaces) != m.get("spacesCount") or len(svg_spaces) != len(topo["spaces"]):
        raise ValueError(f"{key}: SVG spaces {len(svg_spaces)} / spacesCount {m.get('spacesCount')} / "
                         f"evidence {len(topo['spaces'])}")
    used = set()
    worst = 0.0
    zones_equal = 0
    for s in topo["spaces"]:
        j, d = min(((j, math.dist(t["px"], s["px"])) for j, t in enumerate(svg_spaces)), key=lambda t: t[1])
        if d > CENTRE_TOLERANCE_PX or j in used:
            raise ValueError(f"{key}: {s['id']} has no unique SVG centre within {CENTRE_TOLERANCE_PX} px (d={d:.3f})")
        used.add(j)
        worst = max(worst, d)
        if sorted(svg_spaces[j]["zones"]) != sorted(s["zones"]):
            raise ValueError(f"{key}: {s['id']} zones {s['zones']} != SVG zones {svg_spaces[j]['zones']}")
        zones_equal += 1
    return {"spacesMatched": f"{len(used)}/{len(topo['spaces'])}", "zonesEqual": f"{zones_equal}/{len(topo['spaces'])}",
            "maxCentreDeviationPx": round(worst, 3)}


def verify_image(key: str, expected_sha: str, images_dir: Path) -> str:
    """'verified' / 'absent' (gitignored, ENV-U3); a present image with another hash fails."""
    p = images_dir / f"{key}.webp"
    if not p.is_file():
        return "absent"
    got = sha256_bytes(p.read_bytes())
    if got != expected_sha:
        raise ValueError(f"{key}: image sha256 {got} != evidence {expected_sha}")
    return "verified"


# ------------------------------------------------------------------ build
def build_topology(key: str, m: dict, maps_sha: str, topo: dict, votes: dict) -> dict:
    exp = MAPS[key]
    if m.get("key") != key or m.get("name") != exp["name"]:
        raise ValueError(f"{key}: maps.json entry key/name mismatch")
    if (m.get("set") or {}).get("key") != SET_KEY:
        raise ValueError(f"{key}: maps.json set {(m.get('set') or {}).get('key')!r} != {SET_KEY}")
    zone_keys = [z["key"] for z in m["zones"]]
    if zone_keys != exp["zones"]:
        raise ValueError(f"{key}: zone keys {zone_keys} != expected {exp['zones']}")
    src = topo["source"]
    if list(src.get("size") or []) != IMAGE_SIZE or not SHA_RE.match(src.get("sha256", "")):
        raise ValueError(f"{key}: evidence source image size/sha256 malformed")
    vote_counts = check_votes(key, topo, votes)
    svg = svg_crosscheck(key, m, topo)

    ev_spaces = sorted(topo["spaces"], key=lambda s: s["id"])
    ids = [s["id"] for s in ev_spaces]
    if ids != [f"{exp['prefix']}{i:02d}" for i in range(1, exp["spaces"] + 1)]:
        raise ValueError(f"{key}: space ids are not {exp['prefix']}01..{exp['prefix']}{exp['spaces']:02d}")
    if any(s.get("r") != SPACE_RADIUS_PX for s in ev_spaces):
        raise ValueError(f"{key}: evidence space radius != {SPACE_RADIUS_PX}")
    edges = sorted({edge_key(*e) for e in topo["edges"]})
    if len(edges) != len(topo["edges"]):
        raise ValueError(f"{key}: duplicate edge in the evidence")
    if any(a == b or a not in ids or b not in ids for a, b in edges):
        raise ValueError(f"{key}: an evidence edge is a self-loop or names an unknown space")
    partners: dict[str, list[str]] = {sid: [] for sid in ids}
    for a, b in edges:
        partners[a].append(b)
        partners[b].append(a)

    spaces = []
    for s in ev_spaces:
        spaces.append({
            "id": s["id"],
            "layout": {"x": s["px"][0], "y": s["px"][1]},
            "zones": [k for k in zone_keys if k in s["zones"]],
            "start": s.get("start"),
            "links": sorted(partners[s["id"]]),
        })
    w, h, placed = lattice_placement(spaces)
    if (w, h) != exp["lattice"]:
        raise ValueError(f"{key}: lattice {w}x{h} != expected {exp['lattice'][0]}x{exp['lattice'][1]}")
    spaces = [{"id": s["id"], "x": placed[s["id"]][0], "y": placed[s["id"]][1], **{k: v for k, v in s.items() if k != "id"}}
              for s in spaces]
    by_pos = {(s["x"], s["y"]): s for s in spaces}
    pos_of = {s["id"]: (s["x"], s["y"]) for s in spaces}

    cells = []
    for y in range(h):
        for x in range(w):
            s = by_pos.get((x, y))
            if s is None:
                cells.append({"x": x, "y": y, "isObstacle": True})
                continue
            cell = {"x": x, "y": y, "spaceId": s["id"], "zones": s["zones"], "layout": s["layout"]}
            if s["start"] is not None:
                cell["start"] = s["start"]
            links = sorted((pos_of[p] for p in s["links"]), key=lambda p: (p[1], p[0]))
            cell["links"] = [{"x": px, "y": py} for px, py in links]
            cells.append(cell)

    centres = {s["id"]: (s["layout"]["x"], s["layout"]["y"]) for s in spaces}
    crossings = chord_crossings(centres, [list(e) for e in edges])
    if crossings != sorted(sorted(c) for c in exp["crossings"]):
        raise ValueError(f"{key}: chord crossings {crossings} != expected {exp['crossings']}")

    degree: dict[str, int] = {}
    for s in spaces:
        degree[str(len(s["links"]))] = degree.get(str(len(s["links"])), 0) + 1
    zone_counts = {k: sum(k in s["zones"] for s in spaces) for k in zone_keys}
    zset = {s["id"]: set(s["zones"]) for s in spaces}
    no_shared_zone = [list(e) for e in edges if not (zset[e[0]] & zset[e[1]])]
    starts = {str(s["start"]): s["id"] for s in sorted(spaces, key=lambda s: s["start"] or 0) if s["start"]}
    stats = lattice_neighbour_stats(spaces, [list(e) for e in edges])

    fixture = {
        "schema": SCHEMA,
        "map": key,
        "name": exp["name"],
        "set": SET_KEY,
        "boardId": topology_board_id(key),
        "status": "измерено",
        "generator": {"tool": GENERATOR, "topologyVersion": TOPOLOGY_VERSION},
        "source": {
            "image": f"scraped-data/images/maps/{key}.webp",
            "sha256": src["sha256"],
            "size": IMAGE_SIZE,
            "provenance": {
                "imagePolicy": "ENV-U3: the map image and every texture derived from it stay out of git "
                               "(imported by script); only its sha256 is recorded here",
                "mapsJson": {"path": "scraped-data/api/maps.json", "gitignored": True, "sha256": maps_sha,
                             "mapId": m.get("id"), "mapKey": key, "setKey": SET_KEY,
                             "spacesCount": m.get("spacesCount"), "zonesCount": m.get("zonesCount")},
                "centresAndZones": {
                    "from": "zone SVG of maps.json (circle/ellipse/disk path = one space; half-disk/wedge "
                            "path = one zone's share of a multizone space; see tools/art/art_board_fixtures.py)",
                    "svgCrossCheck": svg,
                    "pixelReverification": "zones of all 69 spaces of both maps independently re-derived from the "
                                           "image pixels (Lab, 36 sectors) by the research critic: 69/69 equal to the SVG",
                    "evidence": f"{EVIDENCE_REL}/{key}.topology.json",
                },
                "edges": {
                    "from": "three independent transcriptions of the map image (passA visual by region, passB pixel "
                            "algorithm, passC per-degree rim exits); an edge is kept only if all three agree",
                    "evidence": f"{EVIDENCE_REL}/votes.json",
                    "unanimous": vote_counts["edgesUnanimous"],
                    "externalCrossCheck": {"source": "the-unmatched.club map graph (reconciliation only, not shipped)",
                                           "agree": vote_counts["externalEdgesAgree"]},
                },
                "starts": {
                    "from": "the same three transcriptions",
                    "evidence": f"{EVIDENCE_REL}/votes.json",
                    "unanimous": vote_counts["startsUnanimous"],
                    "externalCrossCheck": {"source": "web_starts of votes.json (reconciliation only; the research "
                                                     "README also reports unbrewed-p2p CV starts 4/4)",
                                           "agree": vote_counts["externalStartsAgree"]},
                },
                "rules": "Battle of Legends Vol. 1 rulebook: adjacent = connected by a line; multizone spaces are "
                         "in all their zones; 2 players use start slots 1 (first player) and 2",
            },
        },
        "uuPerPx": UU_PER_PX,
        "spaceRadiusPx": SPACE_RADIUS_PX,
        "lattice": {"width": w, "height": h},
        "zones": [{"key": z["key"], "color": z["color"]} for z in m["zones"]],
        "spaces": spaces,
        "edges": [list(e) for e in edges],
        "crossings": [{"edges": c, "junction": False} for c in crossings],
        "cells": cells,
        "summary": {
            "spaces": len(spaces),
            "edges": len(edges),
            "obstacleCells": w * h - len(spaces),
            "connected": True,
            "degreeHistogram": dict(sorted(degree.items(), key=lambda kv: int(kv[0]))),
            "multizoneSpaces": sum(len(s["zones"]) > 1 for s in spaces),
            "tripleZoneSpaces": sum(len(s["zones"]) > 2 for s in spaces),
            "zoneSpaceCounts": zone_counts,
            "starts": starts,
            "edgesWithoutSharedZone": len(no_shared_zone),
            **stats,
        },
    }
    errs = validate_fixture(fixture)
    if errs:
        raise ValueError(f"{key}: built fixture is invalid: {errs}")
    return fixture


# ------------------------------------------------------------------ validation
def validate_fixture(fx: dict) -> list[str]:
    """Schema + invariants of one topology fixture (needs no gitignored input)."""
    errs: list[str] = []
    key = fx.get("map")
    exp = MAPS.get(key)
    if fx.get("schema") != SCHEMA:
        errs.append("schema")
    if exp is None:
        return errs + [f"unknown map {key!r}"]
    if fx.get("name") != exp["name"] or fx.get("set") != SET_KEY:
        errs.append("name/set")
    if not ID_RE.match(str(fx.get("boardId", ""))) or fx.get("boardId") != topology_board_id(key):
        errs.append("boardId not the deterministic cuid-shaped topology id")
    text = json.dumps(fx, ensure_ascii=False)
    for bad in FORBIDDEN_TEXT:
        if bad in text:
            errs.append(f"embedded SVG/image/URL data ({bad!r})")
    src = fx.get("source") or {}
    if (src.get("image") != f"scraped-data/images/maps/{key}.webp" or not SHA_RE.match(str(src.get("sha256", "")))
            or src.get("size") != IMAGE_SIZE or not isinstance(src.get("provenance"), dict)):
        errs.append("source image/sha256/size/provenance")
    if fx.get("uuPerPx") != UU_PER_PX or fx.get("spaceRadiusPx") != SPACE_RADIUS_PX:
        errs.append("uuPerPx/spaceRadiusPx")

    # zones: unique keys, the map's keys (violet and purple stay two zones on Marmoreal)
    zlist = fx.get("zones") or []
    zkeys = [z.get("key") for z in zlist]
    if zkeys != exp["zones"]:
        errs.append(f"zone keys {zkeys} != map zone keys {exp['zones']}")
    if len(set(zkeys)) != len(zkeys):
        errs.append("duplicate zone key")
    if any(not COLOR_RE.match(str(z.get("color", ""))) for z in zlist):
        errs.append("zone colour not #RRGGBB")
    zone_set = set(zkeys)

    # lattice + cells: every position exactly once, row-major
    lat = fx.get("lattice") or {}
    w, h = lat.get("width"), lat.get("height")
    if (w, h) != exp["lattice"]:
        errs.append(f"lattice {w}x{h} != {exp['lattice'][0]}x{exp['lattice'][1]}")
        return errs
    cells = fx.get("cells") or []
    if [(c.get("x"), c.get("y")) for c in cells] != [(x, y) for y in range(h) for x in range(w)]:
        errs.append("cells are not exactly the W x H lattice, once each, row-major")
        return errs
    cell_at = {(c["x"], c["y"]): c for c in cells}

    # spaces
    spaces = fx.get("spaces") or []
    ids = [s.get("id") for s in spaces]
    if ids != [f"{exp['prefix']}{i:02d}" for i in range(1, exp["spaces"] + 1)]:
        errs.append(f"space ids != {exp['prefix']}01..{exp['prefix']}{exp['spaces']:02d} ({len(ids)} spaces)")
    sp = {s["id"]: s for s in spaces if "id" in s}
    pos_of = {}
    for s in spaces:
        sid = s.get("id")
        xy = (s.get("x"), s.get("y"))
        if not (isinstance(xy[0], int) and isinstance(xy[1], int) and 0 <= xy[0] < w and 0 <= xy[1] < h):
            errs.append(f"{sid}: lattice position {xy} outside {w}x{h}")
            continue
        if xy in pos_of.values():
            errs.append(f"{sid}: lattice position {xy} used twice")
        pos_of[sid] = xy
        lo = s.get("layout") or {}
        if not (isinstance(lo.get("x"), (int, float)) and isinstance(lo.get("y"), (int, float))
                and 0 <= lo["x"] <= IMAGE_SIZE[0] and 0 <= lo["y"] <= IMAGE_SIZE[1]):
            errs.append(f"{sid}: layout outside the image")
        zs = s.get("zones") or []
        if not zs or len(set(zs)) != len(zs) or not set(zs) <= zone_set:
            errs.append(f"{sid}: zones {zs} empty / duplicated / not map zone keys")
        elif zs != [k for k in zkeys if k in zs]:
            errs.append(f"{sid}: zones not in map zone order")
        st = s.get("start")
        if st is not None and st not in (1, 2, 3, 4):
            errs.append(f"{sid}: start {st!r} not in 1..4")
        links = s.get("links") or []
        if links != sorted(set(links)) or sid in links or not set(links) <= set(sp):
            errs.append(f"{sid}: links not sorted/unique/known or self-linked")

    # starts 1..4 unique and as researched
    starts = {}
    for s in spaces:
        if s.get("start") is not None:
            if s["start"] in starts:
                errs.append(f"start {s['start']} on {starts[s['start']]} and {s['id']}")
            starts[s["start"]] = s["id"]
    if starts != exp["starts"]:
        errs.append(f"starts {starts} != {exp['starts']}")

    # edges: endpoints are spaces, unique, sorted, symmetric with links, connected
    edges = fx.get("edges") or []
    ekeys = []
    for e in edges:
        if not (isinstance(e, list) and len(e) == 2 and e[0] in sp and e[1] in sp and e[0] < e[1]):
            errs.append(f"edge {e} endpoints not two spaces in id order")
            continue
        ekeys.append((e[0], e[1]))
    if ekeys != sorted(set(ekeys)):
        errs.append("edges not sorted/unique")
    if len(edges) != exp["edges"]:
        errs.append(f"{len(edges)} edges != {exp['edges']}")
    from_links = {edge_key(a, b) for a, s in sp.items() for b in s.get("links") or []}
    if from_links != set(ekeys):
        errs.append("links and edges disagree")
    for a, s in sp.items():
        for b in s.get("links") or []:
            if b in sp and a not in (sp[b].get("links") or []):
                errs.append(f"asymmetric link {a}->{b}")
    adj = {sid: set(s.get("links") or []) for sid, s in sp.items()}
    if not graph_connected(ids, adj):
        errs.append("space graph not connected")

    # cells <-> spaces
    has_links = False
    for (x, y), c in cell_at.items():
        s = next((sp[i] for i, p in pos_of.items() if p == (x, y)), None)
        if s is None:
            if c != {"x": x, "y": y, "isObstacle": True}:
                errs.append(f"non-space cell {(x, y)} must be exactly {{x, y, isObstacle: true}}")
            continue
        if c.get("isObstacle"):
            errs.append(f"space {s['id']} on an obstacle cell {(x, y)}")
        want_links = sorted((pos_of[b] for b in s.get("links") or [] if b in pos_of), key=lambda p: (p[1], p[0]))
        want = {"x": x, "y": y, "spaceId": s["id"], "zones": s.get("zones"), "layout": s.get("layout")}
        if s.get("start") is not None:
            want["start"] = s["start"]
        want["links"] = [{"x": px, "y": py} for px, py in want_links]
        if c != want:
            errs.append(f"cell {(x, y)} != its space {s['id']}")
        has_links = has_links or bool(c.get("links"))
    if not has_links:
        errs.append("no cell carries links: the engine would fall back to the grid")

    # lattice placement reproducible from the layouts (art_board_fixtures.choose_grid)
    if not errs:
        pw, ph, placed = lattice_placement(spaces)
        if (pw, ph) != (w, h) or placed != pos_of:
            errs.append("lattice placement is not choose_grid over the layouts")

    # crossings of straight chords: exactly the documented ones, no junction
    if not errs:
        centres = {sid: (s["layout"]["x"], s["layout"]["y"]) for sid, s in sp.items()}
        got = chord_crossings(centres, [list(e) for e in ekeys])
        rec = fx.get("crossings") or []
        if [c.get("edges") for c in rec] != got or any(c.get("junction") is not False for c in rec):
            errs.append("crossings do not match the chord crossings of the edges (junction must be false)")
        if got != sorted(sorted(c) for c in exp["crossings"]):
            errs.append(f"chord crossings {got} != documented {exp['crossings']}")

    # summary is a pure recomputation
    if not errs:
        summ = fx.get("summary") or {}
        stats = lattice_neighbour_stats(spaces, [list(e) for e in ekeys])
        for k, v in stats.items():
            if summ.get(k) != v:
                errs.append(f"summary.{k} != recomputed")
        if stats["latticeNeighbourPairsNotLinked"] < 1:
            errs.append("no lattice-neighbour pair without a link: the fixture cannot prove the engine uses links")
        if (summ.get("spaces"), summ.get("edges"), summ.get("obstacleCells")) != (len(spaces), len(ekeys), w * h - len(spaces)):
            errs.append("summary counts")
        if summ.get("starts") != {str(k): v for k, v in sorted(starts.items())}:
            errs.append("summary.starts")
        if summ.get("zoneSpaceCounts") != {k: sum(k in s["zones"] for s in spaces) for k in zkeys}:
            errs.append("summary.zoneSpaceCounts")
    return errs


def validate_against_evidence(fx: dict, topo: dict) -> list[str]:
    """The fixture carries exactly the committed research numbers (ids, centres, zone sets,
    starts, edges, image hash)."""
    errs = []
    ev = {s["id"]: s for s in topo["spaces"]}
    sp = {s["id"]: s for s in fx.get("spaces") or []}
    if set(ev) != set(sp):
        return [f"space ids differ from the evidence: +{sorted(set(sp) - set(ev))} -{sorted(set(ev) - set(sp))}"]
    for sid, e in ev.items():
        s = sp[sid]
        if [s["layout"]["x"], s["layout"]["y"]] != e["px"]:
            errs.append(f"{sid}: layout != evidence centre")
        if sorted(s["zones"]) != sorted(e["zones"]):
            errs.append(f"{sid}: zones != evidence")
        if s.get("start") != e.get("start"):
            errs.append(f"{sid}: start != evidence")
    if sorted(edge_key(*e) for e in topo["edges"]) != [tuple(e) for e in fx.get("edges") or []]:
        errs.append("edges != evidence")
    if (fx.get("source") or {}).get("sha256") != topo["source"]["sha256"]:
        errs.append("image sha256 != evidence")
    return errs


# ------------------------------------------------------------------ commands
def _load_maps(path: Path) -> tuple[list[dict], str] | None:
    if not path.is_file():
        print(f"maps.json not found at {path} (gitignored, main checkout only)")
        return None
    return ABF.load_maps(path)


def build_all(maps_path: Path, evidence_dir: Path, keys,
              images_dir: Path = MAIN_CHECKOUT_IMAGES) -> dict[str, dict] | None:
    loaded = _load_maps(maps_path)
    if loaded is None:
        return None
    maps, sha = loaded
    out = {}
    for key in keys:
        m = next((x for x in maps if x.get("key") == key), None)
        if m is None:
            raise ValueError(f"map {key!r} not in maps.json")
        topo, votes = load_evidence(evidence_dir, key)
        out[key] = build_topology(key, m, sha, topo, votes)
        # not recorded in the fixture (its bytes must not depend on a gitignored file)
        print(f"{key}: local image sha256 {verify_image(key, topo['source']['sha256'], images_dir)}")
    return out


def _print_summary(key: str, fx: dict, path) -> None:
    s = fx["summary"]
    print(f"{key}: {fx['lattice']['width']}x{fx['lattice']['height']} id={fx['boardId']} spaces={s['spaces']} "
          f"edges={s['edges']} obstacles={s['obstacleCells']} starts={s['starts']} "
          f"latticeNeighboursNotLinked={s['latticeNeighbourPairsNotLinked']} "
          f"linksBetweenNonLatticeNeighbours={s['linksBetweenNonLatticeNeighbours']} "
          f"crossings={len(fx['crossings'])} -> {path}")


def cmd_build(a) -> int:
    keys = a.keys.split(",") if a.keys else list(DEFAULT_KEYS)
    built = build_all(Path(a.maps), Path(a.evidence_dir), keys)
    if built is None:
        return 2
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for key, fx in built.items():
        p = out / f"{key}.topology.json"
        p.write_bytes(dump(fx).encode("utf-8"))
        _print_summary(key, fx, p)
    return 0


def cmd_check(a) -> int:
    out = Path(a.out_dir)
    built = build_all(Path(a.maps), Path(a.evidence_dir), list(DEFAULT_KEYS))
    if built is None:
        return 2
    bad = 0
    for key, fx in built.items():
        p = out / f"{key}.topology.json"
        same = p.is_file() and p.read_bytes() == dump(fx).encode("utf-8")
        print(f"{p.name}: byte-identical to a fresh build {'PASS' if same else 'FAIL'}")
        bad += not same
    return 0 if not bad else 1


def cmd_validate(a) -> int:
    files = [Path(f) for f in a.files] if a.files else sorted(Path(a.out_dir).glob("*.topology.json"))
    if not files:
        print(f"no topology fixtures in {a.out_dir}")
        return 1
    bad = 0
    for f in files:
        fx = json.loads(f.read_text(encoding="utf-8"))
        errs = validate_fixture(fx)
        ev_path = Path(a.evidence_dir) / f"{fx.get('map')}.topology.json"
        if ev_path.is_file():
            errs += validate_against_evidence(fx, json.loads(ev_path.read_text(encoding="utf-8")))
        else:
            errs.append(f"evidence {ev_path} missing")
        print(f"{f.name}: {'PASS' if not errs else 'FAIL ' + '; '.join(errs)}")
        if not errs:
            _print_summary(fx["map"], fx, f)
        bad += bool(errs)
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "check"):
        p = sub.add_parser(name)
        p.add_argument("--maps", default=str(MAIN_CHECKOUT_MAPS))
        p.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE))
        p.add_argument("--out-dir", default=str(DEFAULT_OUT))
        if name == "build":
            p.add_argument("--keys", default="")
    v = sub.add_parser("validate")
    v.add_argument("--out-dir", default=str(DEFAULT_OUT))
    v.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE))
    v.add_argument("files", nargs="*")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "check": cmd_check, "validate": cmd_validate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
