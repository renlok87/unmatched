#!/usr/bin/env python3
"""ENV-MAPS P3: independent cross-check of a live original-map duel (read-only, no credentials).

A second, deliberately simpler implementation next to verify_graph_duel.py (which keys on the S09AUTO
driver lines). This one classifies EVERY server ATTACK_INITIATED row by the board positions of attacker
and target, so a ranged attack on a non-adjacent fighter in a shared zone is found even when the driver
did not label it.

Inputs: the two published client traces of one run + backend/prisma/fixtures/boards/<map>.topology.json
(chosen by the GAME_CREATED boardId) + the GameAction rows of that game (docker exec codex-s09-postgres
psql, read-only).

Positions: every fighter's position is tracked from the client 'CUE move <f> (x,y)->(x,y) seq=N' lines of
both traces (host and joiner must agree on every common (fighter, seq)); the first 'from' of a fighter is
its start. A position before seq N is the 'to' of its last CUE with seq < N.

  moves   every server 'maneuver' path: start (tracked position) -> path[0] -> ... each step an EDGE of
          the fixture; the path end equals the CUE 'to' of that seq.
  attacks each ATTACK_INITIATED row: attacker/target space, linked?, shared zones; 'rangedNonAdjacent'
          = not linked and >= 1 shared zone (the ranged rule on a graph board, ENV-O6 / GAP-023).
  result  one VICTORY + one DEFEAT 'RESULT seq=' line and a GAME_ENDED row.

Usage: python tools/s09/xcheck_graph_duel.py --host-trace H --joiner-trace J [--json OUT]
Exit 0 only if every maneuver step is linked, traces agree, >= 1 ranged non-adjacent attack and the result holds.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "backend" / "prisma" / "fixtures" / "boards"
CONTAINER = "codex-s09-postgres"
ROOM = re.compile(r"createGame -> room=(c[a-z0-9]{24})")
CUE = re.compile(r"CUE move (\S+) \((\d+),(\d+)\)->\((\d+),(\d+)\) seq=(\d+)")
RESULT = re.compile(r"RESULT seq=(\d+) outcome=([A-Z]+) winner=")
RANGED_HEROES = {"f-0-hero": "Medusa (ranged)", "f-1-sk0": "Merlin (ranged)"}


def rows(game_id: str) -> list[dict]:
    if not re.fullmatch(r"c[a-z0-9]{24}", game_id):
        raise SystemExit(f"refusing game id {game_id!r}")
    sql = ("select coalesce(json_agg(json_build_object('seq', \"sequenceNumber\", 'type', type, 'payload', payload)"
           " order by \"sequenceNumber\", timestamp), '[]'::json) from \"GameAction\" where \"gameId\" = '" + game_id + "'")
    r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "unmatched", "-d", "unmatched", "-At", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit("psql failed")
    return json.loads(r.stdout.strip() or "[]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host-trace", required=True)
    ap.add_argument("--joiner-trace", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    ht = Path(a.host_trace).read_text(encoding="utf-8-sig", errors="replace")
    jt = Path(a.joiner_trace).read_text(encoding="utf-8-sig", errors="replace")
    gid = ROOM.search(ht).group(1)
    acts = rows(gid)
    board_id = next(r["payload"]["boardId"] for r in acts if r["type"] == "GAME_CREATED")
    fx = next(json.loads(f.read_text(encoding="utf-8")) for f in sorted(FIXTURES.glob("*.topology.json"))
              if json.loads(f.read_text(encoding="utf-8")).get("boardId") == board_id)
    sid = {(s["x"], s["y"]): s["id"] for s in fx["spaces"]}
    zones = {s["id"]: set(s["zones"]) for s in fx["spaces"]}
    edges = {frozenset(e) for e in fx["edges"]}
    # fixture self-consistency: the edge list equals the per-space link lists
    edges_from_links = {frozenset((s["id"], t)) for s in fx["spaces"] for t in s["links"]}
    problems = [] if edges == edges_from_links else ["fixture edges != spaces[].links"]

    cues: dict = {}
    disagree = []
    for who, text in (("host", ht), ("joiner", jt)):
        for m in CUE.finditer(text):
            f, seq = m.group(1), int(m.group(6))
            mv = (sid.get((int(m.group(2)), int(m.group(3)))), sid.get((int(m.group(4)), int(m.group(5)))))
            if (f, seq) in cues and cues[(f, seq)]["move"] != mv:
                disagree.append({"fighter": f, "seq": seq, "a": cues[(f, seq)]["move"], "b": mv})
            cues.setdefault((f, seq), {"move": mv, "seen": set()})["seen"].add(who)
    order = sorted(cues.items(), key=lambda kv: (kv[0][1], kv[0][0]))
    first = {}
    for (f, _seq), c in order:
        first.setdefault(f, c["move"][0])

    def pos_before(f: str, seq: int):
        p = first.get(f)
        for (g, s), c in order:
            if g == f and s < seq:
                p = c["move"][1]
        return p

    moves, steps, bad = [], 0, 0
    maneuver_cues = set()
    for r in acts:
        inp = (r["payload"] or {}).get("input") or {}
        if r["type"] != "MANEUVER" or (r["payload"] or {}).get("action") != "maneuver":
            continue
        for mv in inp.get("moves") or []:
            f = mv["fighterId"]
            path = [sid.get((p["x"], p["y"])) for p in mv["path"]]
            if not path:
                continue
            start = pos_before(f, r["seq"])
            chain = [start] + path
            unlinked = [[x, y] for x, y in zip(chain, chain[1:]) if frozenset((x, y)) not in edges]
            cue = cues.get((f, r["seq"]))
            end_ok = bool(cue) and cue["move"][1] == path[-1]
            maneuver_cues.add((f, r["seq"]))
            steps += len(path)
            bad += bool(unlinked) or not end_ok
            moves.append({"seq": r["seq"], "fighter": f, "chain": chain, "unlinked": unlinked, "endMatchesCue": end_ok})
    other = [{"seq": s, "fighter": f, "from": c["move"][0], "to": c["move"][1],
              "linked": frozenset(c["move"]) in edges} for (f, s), c in order if (f, s) not in maneuver_cues]

    attacks = []
    for r in acts:
        if r["type"] != "ATTACK_INITIATED":
            continue
        inp = r["payload"]["input"]
        at, tt = pos_before(inp["attackerId"], r["seq"]), pos_before(inp["targetId"], r["seq"])
        linked = frozenset((at, tt)) in edges
        shared = sorted(zones.get(at, set()) & zones.get(tt, set()))
        attacks.append({"seq": r["seq"], "attacker": inp["attackerId"], "attackerAt": at, "target": inp["targetId"],
                        "targetAt": tt, "linked": linked, "sharedZones": shared,
                        "rangedNonAdjacent": (not linked) and bool(shared),
                        "attackerKind": RANGED_HEROES.get(inp["attackerId"], "melee")})
    ranged = [x for x in attacks if x["rangedNonAdjacent"]]
    illegal = [x for x in attacks if not x["linked"] and (not x["sharedZones"] or x["attackerKind"] == "melee")]

    rh, rj = RESULT.findall(ht), RESULT.findall(jt)
    outcomes = sorted({rh[-1][1] if rh else None, rj[-1][1] if rj else None} - {None})
    ended = [r for r in acts if r["type"] == "GAME_ENDED"]
    result_ok = outcomes == ["DEFEAT", "VICTORY"] and len(ended) == 1
    out = {"schema": "unmatched.env-maps.graph-duel-xcheck/1", "gameId": gid, "boardId": board_id, "map": fx["map"],
           "actions": len(acts), "fixtureProblems": problems,
           "cueMoves": len(cues), "cueSeenByBoth": sum(1 for c in cues.values() if c["seen"] == {"host", "joiner"}),
           "cueDisagreements": disagree,
           "maneuver": {"moves": len(moves), "steps": steps, "violations": bad, "detail": moves},
           "nonManeuverMoves": other,
           "attacks": {"total": len(attacks), "rangedNonAdjacent": len(ranged), "illegalLooking": illegal,
                       "detail": attacks},
           "result": {"host": rh[-1] if rh else None, "joiner": rj[-1] if rj else None,
                      "gameEndedRows": len(ended), "ok": result_ok}}
    ok = not problems and not disagree and bad == 0 and moves and ranged and not illegal and result_ok
    out["ok"] = bool(ok)
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: out[k] for k in ("gameId", "map", "cueMoves", "cueSeenByBoth", "ok")} |
                     {"maneuverMoves": len(moves), "steps": steps, "violations": bad, "nonManeuverMoves": len(other),
                      "attacks": len(attacks), "rangedNonAdjacent": len(ranged), "illegalLooking": len(illegal),
                      "result": out["result"]}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
