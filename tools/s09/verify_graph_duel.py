"""ENV-MAPS: offline proof that a live duel on an original-map board was played on its space graph.

Read-only. Inputs are the two published client traces of one run (run-combat-demo / run-phase2-demo /
run-duel-demo) plus the authoritative action log of that game in the isolated S09 database
(codex-s09-postgres, read through `docker exec ... psql`; no credentials are read or printed).

Checks (each reported; --require-* turn them into exit-code gates):
  moves   every MANEUVER path accepted by the server walks graph LINKS of the topology fixture:
          start -> path[0] -> ... -> path[-1], start taken from the client 'CUE move <fighter>
          (x,y)->(x,y) seq=N' line of the same seq (both traces, deduplicated); each step must be a
          link of backend/prisma/fixtures/boards/<map>.topology.json. CUE moves that no maneuver
          explains (card effects such as PLACE) are listed separately with their graph distance.
  ranged  at least one attack where the attacker and the target were NOT linked but shared a zone
          (server ranged rule, ENV-O6 / GAP-023): the S09AUTO driver line
          'S09AUTO ranged target attacker=A at=S1 target=T at=S2 via=shared-zone (not linked)' followed by
          'ATTACK done seq=N', re-checked against the fixture (no link, common zone) and matched to an
          ATTACK_INITIATED row with the same attacker/target at seq N.
  result  'RESULT seq=N outcome=VICTORY|DEFEAT' on both seats (one each) and a GAME_ENDED row.

Usage:
  python tools/s09/verify_graph_duel.py --host-trace H --joiner-trace J [--game-id ID] [--fixture F]
         [--require-moves] [--require-ranged] [--require-result] [--json OUT]
  python tools/s09/verify_graph_duel.py --self-test
The game id defaults to the 'createGame -> room=<id>' line of the host trace; the fixture defaults to
the topology fixture whose boardId equals the GAME_CREATED payload boardId.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "backend" / "prisma" / "fixtures" / "boards"
CONTAINER = "codex-s09-postgres"
GAME_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

CUE_RE = re.compile(r"CUE move (\S+) \((-?\d+),(-?\d+)\)->\((-?\d+),(-?\d+)\) seq=(\d+)")
ROOM_RE = re.compile(r"createGame -> room=([A-Za-z0-9_-]+)")
RANGED_RE = re.compile(r"S09AUTO ranged target attacker=(\S+) at=(\S+) target=(\S+) at=(\S+) via=shared-zone")
ATTACK_DONE_RE = re.compile(r"ATTACK done seq=(\d+)")
RESULT_RE = re.compile(r"RESULT seq=(\d+) outcome=([A-Z]+) winner=")


class Graph:
    def __init__(self, fx: dict):
        self.board_id = fx["boardId"]
        self.map = fx["map"]
        self.by_pos: dict[tuple[int, int], dict] = {}
        self.by_id: dict[str, dict] = {}
        for s in fx["spaces"]:
            self.by_pos[(s["x"], s["y"])] = s
            self.by_id[s["id"]] = s

    def label(self, p: tuple[int, int]) -> str:
        s = self.by_pos.get(p)
        return s["id"] if s else f"({p[0]},{p[1]})"

    def linked(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        sa, sb = self.by_pos.get(a), self.by_pos.get(b)
        return bool(sa and sb and sb["id"] in sa["links"])

    def dist(self, a: tuple[int, int], b: tuple[int, int]) -> int | None:
        sa, sb = self.by_pos.get(a), self.by_pos.get(b)
        if not sa or not sb:
            return None
        seen = {sa["id"]: 0}
        q = deque([sa["id"]])
        while q:
            u = q.popleft()
            if u == sb["id"]:
                return seen[u]
            for v in self.by_id[u]["links"]:
                if v not in seen:
                    seen[v] = seen[u] + 1
                    q.append(v)
        return None

    def zones_of(self, label: str) -> set[str]:
        s = self.by_id.get(label)
        return set(s["zones"]) if s else set()

    def linked_labels(self, a: str, b: str) -> bool:
        s = self.by_id.get(a)
        return bool(s and b in s["links"])


def load_fixture(path: Path | None, board_id: str | None) -> dict:
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    for f in sorted(FIXTURE_DIR.glob("*.topology.json")):
        fx = json.loads(f.read_text(encoding="utf-8"))
        if fx.get("boardId") == board_id:
            return fx
    raise SystemExit(f"no topology fixture with boardId={board_id} in {FIXTURE_DIR}")


def psql_rows(game_id: str) -> list[dict]:
    if not GAME_ID_RE.match(game_id):
        raise SystemExit(f"refusing game id {game_id!r}")
    sql = (
        "select coalesce(json_agg(json_build_object('type', type, 'seq', \"sequenceNumber\", 'payload', payload)"
        " order by \"sequenceNumber\", timestamp), '[]'::json) from \"GameAction\" where \"gameId\" = '"
        + game_id + "'"
    )
    r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "unmatched", "-d", "unmatched", "-At", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"psql failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout.strip() or "[]")


def parse_cues(texts: list[str]) -> list[dict]:
    seen, out = set(), []
    for t in texts:
        for m in CUE_RE.finditer(t):
            key = (m.group(1), int(m.group(6)))
            if key in seen:
                continue
            seen.add(key)
            out.append({"fighter": m.group(1), "from": (int(m.group(2)), int(m.group(3))),
                        "to": (int(m.group(4)), int(m.group(5))), "seq": int(m.group(6))})
    return sorted(out, key=lambda c: (c["seq"], c["fighter"]))


def check_moves(g: Graph, actions: list[dict], cues: list[dict]) -> dict:
    by_key = {(c["fighter"], c["seq"]): c for c in cues}
    used, moves, problems = set(), [], []
    for a in actions:
        p = a.get("payload") or {}
        if a.get("type") != "MANEUVER" or p.get("action") != "maneuver":
            continue
        for mv in (p.get("input") or {}).get("moves") or []:
            path = [(int(s["x"]), int(s["y"])) for s in mv.get("path") or []]
            if not path:
                continue
            fid = mv.get("fighterId")
            cue = by_key.get((fid, a["seq"]))
            rec = {"seq": a["seq"], "fighter": fid, "path": [g.label(s) for s in path]}
            if not cue:
                rec["status"] = "no-cue"
                problems.append(f"seq {a['seq']} {fid}: no 'CUE move' for this maneuver in either trace")
                moves.append(rec)
                continue
            used.add((fid, a["seq"]))
            # The server accepts a path with or without the start cell first (movement.service.ts).
            steps = [cue["from"]] + (path[1:] if path[0] == cue["from"] else path)
            bad = [(g.label(x), g.label(y)) for x, y in zip(steps, steps[1:]) if not g.linked(x, y)]
            rec.update({"from": g.label(cue["from"]), "to": g.label(cue["to"]), "steps": len(steps) - 1,
                        "endMatchesCue": steps[-1] == cue["to"], "unlinkedSteps": bad})
            rec["status"] = "ok" if not bad and steps[-1] == cue["to"] else "BAD"
            if rec["status"] != "ok":
                problems.append(f"seq {a['seq']} {fid}: unlinked steps {bad} or end != CUE to")
            moves.append(rec)
    effects = []
    for c in cues:
        if (c["fighter"], c["seq"]) in used:
            continue
        effects.append({"seq": c["seq"], "fighter": c["fighter"], "from": g.label(c["from"]), "to": g.label(c["to"]),
                        "linked": g.linked(c["from"], c["to"]), "graphDist": g.dist(c["from"], c["to"])})
    ok_moves = sum(1 for m in moves if m["status"] == "ok")
    return {"maneuverMoves": len(moves), "linkedOk": ok_moves, "stepsChecked": sum(m.get("steps", 0) for m in moves),
            "allLinked": bool(moves) and ok_moves == len(moves), "moves": moves,
            "nonManeuverCueMoves": effects, "problems": problems}


def check_ranged(g: Graph, host_text: str, actions: list[dict]) -> dict:
    lines = host_text.splitlines()
    attacks = [a for a in actions if a.get("type") == "ATTACK_INITIATED"]
    found = []
    for i, line in enumerate(lines):
        m = RANGED_RE.search(line)
        if not m:
            continue
        attacker, a_at, target, t_at = m.groups()
        done = None
        for nxt in lines[i + 1:i + 80]:
            if RANGED_RE.search(nxt):
                break
            d = ATTACK_DONE_RE.search(nxt)
            if d:
                done = int(d.group(1))
                break
        shared = sorted(g.zones_of(a_at) & g.zones_of(t_at))
        row = next((a for a in attacks if (a["payload"].get("input") or {}).get("attackerId") == attacker
                    and (a["payload"].get("input") or {}).get("targetId") == target
                    and (done is None or abs(a["seq"] - done) <= 2)), None)  # done seq = the returned snapshot
        rec = {"attacker": attacker, "attackerAt": a_at, "target": target, "targetAt": t_at,
               "linked": g.linked_labels(a_at, t_at), "sharedZones": shared, "attackDoneSeq": done,
               "serverRow": bool(row)}
        rec["ok"] = (not rec["linked"]) and bool(shared) and done is not None and rec["serverRow"]
        found.append(rec)
    return {"rangedNonAdjacent": sum(1 for r in found if r["ok"]), "candidates": found,
            "attacksTotal": len(attacks)}


def check_result(host_text: str, join_text: str, actions: list[dict]) -> dict:
    mh, mj = RESULT_RE.search(host_text), RESULT_RE.search(join_text)
    outcomes = sorted([mh.group(2) if mh else "-", mj.group(2) if mj else "-"])
    ended = any(a.get("type") == "GAME_ENDED" for a in actions)
    return {"hostOutcome": mh.group(2) if mh else None, "joinerOutcome": mj.group(2) if mj else None,
            "gameEndedRow": ended, "ok": outcomes == ["DEFEAT", "VICTORY"] and ended}


def run(args) -> int:
    host_text = Path(args.host_trace).read_text(encoding="utf-8", errors="replace")
    join_text = Path(args.joiner_trace).read_text(encoding="utf-8", errors="replace")
    game_id = args.game_id
    if not game_id:
        m = ROOM_RE.search(host_text)
        if not m:
            raise SystemExit("no 'createGame -> room=' line in the host trace; pass --game-id")
        game_id = m.group(1)
    actions = psql_rows(game_id)
    created = next((a for a in actions if a.get("type") == "GAME_CREATED"), None)
    board_id = (created or {}).get("payload", {}).get("boardId")
    fx = load_fixture(Path(args.fixture) if args.fixture else None, board_id)
    if board_id and fx["boardId"] != board_id:
        raise SystemExit(f"fixture board {fx['boardId']} != game board {board_id}")
    g = Graph(fx)
    report = {"schema": "unmatched.env-maps.graph-duel-check/1", "gameId": game_id, "boardId": board_id,
              "map": fx["map"], "actions": len(actions),
              "moves": check_moves(g, actions, parse_cues([host_text, join_text])),
              "ranged": check_ranged(g, host_text, actions),
              "result": check_result(host_text, join_text, actions)}
    report["gates"] = {"moves": report["moves"]["allLinked"] and not report["moves"]["problems"],
                       "ranged": report["ranged"]["rangedNonAdjacent"] > 0,
                       "result": report["result"]["ok"]}
    out = json.dumps(report, indent=1, ensure_ascii=False)
    if args.json:
        Path(args.json).write_text(out + "\n", encoding="utf-8")
    print(json.dumps({"gameId": game_id, "map": fx["map"], "gates": report["gates"],
                      "maneuverMoves": report["moves"]["maneuverMoves"], "stepsChecked": report["moves"]["stepsChecked"],
                      "nonManeuverCueMoves": len(report["moves"]["nonManeuverCueMoves"]),
                      "rangedNonAdjacent": report["ranged"]["rangedNonAdjacent"],
                      "result": report["result"]}, ensure_ascii=False))
    failed = [k for k, req in (("moves", args.require_moves), ("ranged", args.require_ranged),
                               ("result", args.require_result)) if req and not report["gates"][k]]
    if failed:
        print("GATES FAILED: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


def self_test() -> int:
    fx = json.loads((FIXTURE_DIR / "marmoreal.topology.json").read_text(encoding="utf-8"))
    g = Graph(fx)
    sp = {s["id"]: s for s in fx["spaces"]}
    pos = lambda sid: (sp[sid]["x"], sp[sid]["y"])  # noqa: E731
    a = fx["spaces"][0]
    b = sp[a["links"][0]]
    c = next(sp[x] for x in b["links"] if x != a["id"])
    far = next(s for s in fx["spaces"] if s["id"] not in a["links"] and s["id"] != a["id"]
               and set(s["zones"]) & set(a["zones"]))
    fails = 0

    def expect(name, cond):
        nonlocal fails
        print(("ok   " if cond else "FAIL ") + name)
        fails += 0 if cond else 1

    def mk(path, seq=3):
        return [{"type": "MANEUVER", "seq": seq, "payload": {"action": "maneuver", "input": {
            "moves": [{"fighterId": "f-0-hero", "path": [{"x": p[0], "y": p[1]} for p in path]}]}}}]

    cue = lambda frm, to, seq=3: [{"fighter": "f-0-hero", "from": pos(frm), "to": pos(to), "seq": seq}]  # noqa: E731
    r = check_moves(g, mk([pos(b["id"]), pos(c["id"])]), cue(a["id"], c["id"]))
    expect("linked two-step path passes", r["allLinked"] and r["stepsChecked"] == 2)
    r = check_moves(g, mk([pos(far["id"])]), cue(a["id"], far["id"]))
    expect("non-linked jump fails", not r["allLinked"] and r["problems"])
    r = check_moves(g, mk([pos(a["id"]), pos(b["id"])]), cue(a["id"], b["id"]))
    expect("path starting at the start space is accepted", r["allLinked"] and r["stepsChecked"] == 1)
    r = check_moves(g, mk([pos(b["id"])]), [])
    expect("maneuver without a CUE is a problem", r["problems"])
    effect = parse_cues([f"CUE move f-1-hero ({a['x']},{a['y']})->({far['x']},{far['y']}) seq=9"])
    r = check_moves(g, [], effect)
    expect("unexplained CUE is listed as an effect move", len(r["nonManeuverCueMoves"]) == 1)
    host = (f"S09AUTO ranged target attacker=f-0-hero at={a['id']} target=f-1-hero at={far['id']} via=shared-zone (not linked)\n"
            "ATTACK sent\nATTACK done seq=12\n")
    acts = [{"type": "ATTACK_INITIATED", "seq": 12, "payload": {"input": {"attackerId": "f-0-hero", "targetId": "f-1-hero"}}}]
    expect("ranged shared-zone attack counted", check_ranged(g, host, acts)["rangedNonAdjacent"] == 1)
    expect("ranged without a server row not counted", check_ranged(g, host, [])["rangedNonAdjacent"] == 0)
    host_adj = host.replace(f"at={far['id']} via", f"at={b['id']} via")
    expect("linked pair is not a ranged proof", check_ranged(g, host_adj, acts)["rangedNonAdjacent"] == 0)
    res = check_result("RESULT seq=80 outcome=VICTORY winner=u1", "RESULT seq=80 outcome=DEFEAT winner=u1",
                       [{"type": "GAME_ENDED", "seq": 80, "payload": {}}])
    expect("one VICTORY + one DEFEAT + GAME_ENDED", res["ok"])
    expect("two VICTORY rejected", not check_result("RESULT seq=1 outcome=VICTORY winner=",
                                                     "RESULT seq=1 outcome=VICTORY winner=",
                                                     [{"type": "GAME_ENDED"}])["ok"])
    print(f"self-test: {'PASS' if not fails else 'FAIL'} ({fails} failed)")
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host-trace")
    ap.add_argument("--joiner-trace")
    ap.add_argument("--game-id")
    ap.add_argument("--fixture")
    ap.add_argument("--json")
    ap.add_argument("--require-moves", action="store_true")
    ap.add_argument("--require-ranged", action="store_true")
    ap.add_argument("--require-result", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.host_trace or not a.joiner_trace:
        ap.error("--host-trace and --joiner-trace are required")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
