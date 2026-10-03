#!/usr/bin/env python3
"""Art Tuner fold (docs/art-pipeline/ART-TUNER-PLAN.md section 4, tools/art/ART-TUNER.md): writes the values the artist
saved in the game (unreal/Unmatched/Config/ArtBoards/S08ArtTuner.overrides.json) into the board profiles
(unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json) by editing the TEXT: only the changed values are replaced
(new optional keys are inserted in the style of their object), so the hand formatting, the key order, the long one-line
board entries and the line endings stay exactly as they are. Never re-serializes the document.

  python tools/art/art_tuner_fold.py --dry-run          # the unified diff, nothing written
  python tools/art/art_tuner_fold.py --check            # exit 1 when the file has values not in the profile yet
  python tools/art/art_tuner_fold.py                    # apply: profile written, revision + 1, the folded boards archived
  python tools/art/art_tuner_fold.py --board sarpedon-original --force   # one board; take the artist's value on a conflict

Checks before anything is written:
  * anchors ("/boards/4/id": "sarpedon-original") - the board index still means that board;
  * "was" - the profile still has the value the artist started from; another value (another session changed it) is a
    conflict: refused with an explanation unless --force;
  * the result parses, every entry reads back, and every other value of the document is unchanged.
After an apply the folded board blocks go to docs/art-pipeline/art-tuner-saves/<time>-<board>.overrides.json (in git) and
leave the overrides file (deleted when empty).

Exit codes: 0 ok (or nothing to do), 1 --check found pending values, 2 refused (conflict / anchor / bad input).
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
OVERRIDES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtTuner.overrides.json"
ARCHIVE = REPO / "docs/art-pipeline/art-tuner-saves"
SCHEMA = "unmatched.art-tuner-overrides/1"


class FoldError(Exception):
    def __init__(self, msg: str, code: int = 2):
        super().__init__(msg)
        self.code = code


# ---- a JSON scanner that keeps the text positions ------------------------------------------------------------------

@dataclass
class Node:
    kind: str  # object | array | string | number | literal
    start: int
    end: int  # exclusive
    members: list = field(default_factory=list)  # object: [(key, key_start, Node)], array: [Node]


class Scanner:
    def __init__(self, text: str):
        self.t = text
        self.i = 0

    def ws(self):
        t = self.t
        while self.i < len(t) and t[self.i] in " \t\r\n":
            self.i += 1

    def parse(self) -> Node:
        self.ws()
        node = self.value()
        self.ws()
        if self.i != len(self.t):
            raise FoldError(f"trailing text at {self.i}")
        return node

    def value(self) -> Node:
        t = self.t
        if self.i >= len(t):
            raise FoldError("unexpected end of the document")
        c = t[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"':
            s = self.i
            self.string()
            return Node("string", s, self.i)
        s = self.i
        while self.i < len(t) and t[self.i] not in ",]} \t\r\n":
            self.i += 1
        word = t[s:self.i]
        if not word:
            raise FoldError(f"bad value at {s}")
        return Node("literal" if word in ("true", "false", "null") else "number", s, self.i)

    def string(self) -> str:
        t = self.t
        s = self.i
        self.i += 1
        while t[self.i] != '"':
            self.i += 2 if t[self.i] == "\\" else 1
        self.i += 1
        return json.loads(t[s:self.i])

    def obj(self) -> Node:
        n = Node("object", self.i, -1)
        self.i += 1
        self.ws()
        if self.t[self.i] == "}":
            self.i += 1
            n.end = self.i
            return n
        while True:
            self.ws()
            ks = self.i
            key = self.string()
            self.ws()
            if self.t[self.i] != ":":
                raise FoldError(f"':' expected at {self.i}")
            self.i += 1
            self.ws()
            n.members.append((key, ks, self.value()))
            self.ws()
            c = self.t[self.i]
            self.i += 1
            if c == "}":
                n.end = self.i
                return n
            if c != ",":
                raise FoldError(f"',' or '}}' expected at {self.i - 1}")

    def arr(self) -> Node:
        n = Node("array", self.i, -1)
        self.i += 1
        self.ws()
        if self.t[self.i] == "]":
            self.i += 1
            n.end = self.i
            return n
        while True:
            self.ws()
            n.members.append(self.value())
            self.ws()
            c = self.t[self.i]
            self.i += 1
            if c == "]":
                n.end = self.i
                return n
            if c != ",":
                raise FoldError(f"',' or ']' expected at {self.i - 1}")


def split_pointer(p: str) -> list[str]:
    if p == "":
        return []
    if not p.startswith("/"):
        raise FoldError(f"not a JSON pointer: {p}")
    return [s.replace("~1", "/").replace("~0", "~") for s in p[1:].split("/")]


def find(node: Node, segments: list[str]) -> tuple[Node | None, int]:
    """The node at the pointer, or (deepest existing node, how many segments it consumed)."""
    cur = node
    for depth, seg in enumerate(segments):
        nxt = None
        if cur.kind == "object":
            for k, _, v in cur.members:
                if k == seg:
                    nxt = v
        elif cur.kind == "array" and seg.isdigit() and int(seg) < len(cur.members):
            nxt = cur.members[int(seg)]
        if nxt is None:
            return None, depth
        cur = nxt
    return cur, len(segments)


def node_at(node: Node, segments: list[str]) -> Node:
    cur = node
    for seg in segments:
        cur = find(cur, [seg])[0]
    return cur


def pointer_get(doc, segments: list[str]):
    cur = doc
    for seg in segments:
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        elif isinstance(cur, list) and seg.isdigit() and int(seg) < len(cur):
            cur = cur[int(seg)]
        else:
            raise KeyError("/".join(segments))
    return cur


def pointer_set(doc, segments: list[str], value):
    cur = doc
    for seg in segments[:-1]:
        if isinstance(cur, list):
            cur = cur[int(seg)]
        else:
            cur = cur.setdefault(seg, {})
    if isinstance(cur, list):
        cur[int(segments[-1])] = value
    else:
        cur[segments[-1]] = value


def same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-9
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


# ---- the overrides file (raw value text kept: "7.5" stays 7.5) ------------------------------------------------------

@dataclass
class Entry:
    pointer: str
    value: object
    value_text: str
    was: object
    has_was: bool


@dataclass
class Board:
    board: str
    profile: str
    anchors: dict
    entries: list


def load_overrides(path: Path) -> tuple[dict, list[Board], str]:
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("schema") != SCHEMA:
        raise FoldError(f"{path}: schema must be {SCHEMA}")
    root = Scanner(text).parse()
    boards = []
    for bi, b in enumerate(doc.get("boards", [])):
        bnode = node_at(root, ["boards", str(bi)])
        entries = []
        for ei, e in enumerate(b.get("entries", [])):
            if "pointer" not in e or "value" not in e:
                raise FoldError(f"{path}: {b.get('board')} entries[{ei}] needs pointer + value")
            vnode = node_at(bnode, ["entries", str(ei), "value"])
            entries.append(Entry(e["pointer"], e["value"], text[vnode.start:vnode.end], e.get("was"), "was" in e))
        boards.append(Board(b.get("board", ""), b.get("profile", ""), b.get("anchors", {}) or {}, entries))
    return doc, boards, text


# ---- text edits -----------------------------------------------------------------------------------------------------

def object_style(text: str, obj: Node) -> tuple[str, str, bool, str]:
    """(colon, comma, one-line, member indent) of an object as written."""
    inner = text[obj.start:obj.end]
    colon = ": " if any(text[v.start - 2:v.start] == ": " for _, _, v in obj.members) or not obj.members else ":"
    one_line = "\n" not in inner
    comma = ", " if one_line and (", \"" in inner or not obj.members) else ","
    indent = ""
    if not one_line and obj.members:
        ks = obj.members[-1][1]
        line_start = text.rfind("\n", 0, ks) + 1
        indent = text[line_start:ks]
    return colon, comma, one_line, indent


def render(value, colon: str, comma: str) -> str:
    """A new nested value in the style of the object it goes into (one line)."""
    if isinstance(value, dict):
        return "{" + comma.join(f"{json.dumps(k, ensure_ascii=False)}{colon}{render(v, colon, comma)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + comma.join(render(v, colon, comma) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def array_text(old_text: str, value_text: str) -> str:
    """An array value in the separator style of the array it replaces ([0.6,0.71] vs [0.6, 0.71])."""
    try:
        items = json.loads(value_text)
    except json.JSONDecodeError:
        return value_text
    if not isinstance(items, list):
        return value_text
    sep = ", " if ", " in old_text else ","
    inner = Scanner(value_text).parse()
    parts = [value_text[m.start:m.end] for m in inner.members]
    return "[" + sep.join(parts) + "]"


@dataclass
class FoldResult:
    text: str
    applied: list
    skipped: list
    conflicts: list


def fold_text(profile_text: str, boards: list[Board], force: bool = False, bump: bool = True) -> FoldResult:
    doc = json.loads(profile_text)
    root = Scanner(profile_text).parse()
    edits: list[tuple[int, int, str]] = []
    inserts: dict[int, dict] = {}  # object start -> nested dict of new keys
    expected = copy.deepcopy(doc)
    applied, skipped, conflicts = [], [], []
    for b in boards:
        anchor_bad = []
        for ptr, want in b.anchors.items():
            try:
                got = pointer_get(doc, split_pointer(ptr))
            except KeyError:
                got = None
            if got != want:
                anchor_bad.append(f"{ptr} = {got!r}, the file expects {want!r}")
        if anchor_bad:
            conflicts.append(f"{b.board}: anchor mismatch ({'; '.join(anchor_bad)}) - the board index moved; nothing of this board folded")
            continue
        for e in b.entries:
            seg = split_pointer(e.pointer)
            node, depth = find(root, seg)
            try:
                current = pointer_get(doc, seg)
                exists = True
            except KeyError:
                current, exists = None, False
            if exists and same(current, e.value):
                skipped.append(f"{e.pointer}: already {e.value_text}")
                continue
            if e.has_was and e.was is not None and exists and not same(current, e.was):
                msg = f"{e.pointer}: the profile has {json.dumps(current)}, the artist started from {json.dumps(e.was)} -> {e.value_text}"
                if not force:
                    conflicts.append(msg)
                    continue
                skipped.append("forced " + msg)
            if e.has_was and e.was is None and exists and not force:
                conflicts.append(f"{e.pointer}: a new key in the save, but the profile has it now ({json.dumps(current)})")
                continue
            if node is not None:
                old = profile_text[node.start:node.end]
                new = array_text(old, e.value_text) if node.kind == "array" else e.value_text
                edits.append((node.start, node.end, new))
            else:
                parent, used = find(root, seg[:depth])
                if parent is None or parent.kind != "object":
                    conflicts.append(f"{e.pointer}: cannot insert (the existing part is not an object)")
                    continue
                cur = inserts.setdefault(parent.start, {"node": parent, "keys": {}})["keys"]
                rest = seg[used:]
                for s in rest[:-1]:
                    cur = cur.setdefault(s, {})
                cur[rest[-1]] = e.value
            pointer_set(expected, seg, e.value)
            applied.append(f"{e.pointer}: {json.dumps(current) if exists else '(new)'} -> {e.value_text}")
    if conflicts and not force:
        return FoldResult(profile_text, applied, skipped, conflicts)
    for start, info in inserts.items():
        obj = info["node"]
        colon, comma, one_line, indent = object_style(profile_text, obj)
        pieces = [f"{json.dumps(k, ensure_ascii=False)}{colon}{render(v, colon, comma)}" for k, v in info["keys"].items()]
        close = obj.end - 1
        if one_line:
            text = (comma if obj.members else "") + comma.join(pieces)
            # before the closing brace (after the last member's value)
            at = obj.members[-1][2].end if obj.members else close
            edits.append((at, at, text))
        else:
            nl = "\r\n" if "\r\n" in profile_text else "\n"
            at = obj.members[-1][2].end if obj.members else obj.start + 1
            lead = [("," if (obj.members or i) else "") + nl + indent for i in range(len(pieces))]
            edits.append((at, at, "".join(l + p for l, p in zip(lead, pieces))))
    if applied and bump and isinstance(doc.get("revision"), int):
        rev = node_at(root, ["revision"])
        edits.append((rev.start, rev.end, str(doc["revision"] + 1)))
        expected["revision"] = doc["revision"] + 1
    out = profile_text
    for start, end, new in sorted(edits, key=lambda x: (x[0], x[1]), reverse=True):
        out = out[:start] + new + out[end:]
    if out != profile_text:
        try:
            result = json.loads(out)
        except json.JSONDecodeError as ex:
            raise FoldError(f"internal: the folded text does not parse ({ex}) - nothing written") from ex
        if not same(result, expected):
            raise FoldError("internal: the folded document differs from the profile + the entries - nothing written")
    return FoldResult(out, applied, skipped, conflicts)


def inline_changes(old: str, new: str, context: int = 48) -> list[str]:
    """The changed spans of one long line, compared token by token (numbers, words, punctuation):
    '...context [-old-]{+new+} context...'."""
    tok = re.compile(r'[A-Za-z0-9_.#+-]+|\s+|.')
    a, b = tok.findall(old), tok.findall(new)
    out = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        left = "".join(a[:i1])[-context:]
        right = "".join(a[i2:])[:context]
        out.append(f"   ...{left}[-{''.join(a[i1:i2])}-]{{+{''.join(b[j1:j2])}+}}{right}...")
    return out


def diff(a: str, b: str, name: str) -> str:
    """Unified diff; a long changed line (the one-line board entries) is shown as its changed spans with context."""
    al = a.splitlines(keepends=True)
    bl = b.splitlines(keepends=True)
    nl = "\n"
    out = [f"--- a/{name}{nl}+++ b/{name}{nl}"]
    sm = difflib.SequenceMatcher(None, al, bl, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        out.append(f"@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@{nl}")
        if tag == "replace" and i2 - i1 == j2 - j1:
            for k, (x, y) in enumerate(zip(al[i1:i2], bl[j1:j2])):
                x0, y0 = x.rstrip("\r\n"), y.rstrip("\r\n")
                if len(x0) <= 300 and len(y0) <= 300:
                    out += ["-" + x0 + nl, "+" + y0 + nl]
                else:
                    out.append(f"~ line {i1 + k + 1} ({len(x0)} chars), changed spans:{nl}")
                    out += [c + nl for c in inline_changes(x0, y0)]
            continue
        out += ["-" + x.rstrip("\r\n") + nl for x in al[i1:i2]] + ["+" + y.rstrip("\r\n") + nl for y in bl[j1:j2]]
    return "".join(out) if len(out) > 1 else ""


def write_atomic(path: Path, data: bytes):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def archive(overrides_path: Path, doc: dict, folded: list[str], archive_dir: Path) -> Path | None:
    keep = [b for b in doc.get("boards", []) if b.get("board") not in folded]
    gone = [b for b in doc.get("boards", []) if b.get("board") in folded]
    if not gone:
        return None
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = archive_dir / f"{stamp}-{'+'.join(folded)}.overrides.json"
    out = dict(doc, boards=gone, foldedAt=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if keep:
        rest = dict(doc, boards=keep)
        write_atomic(overrides_path, (json.dumps(rest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    else:
        overrides_path.unlink()
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--overrides", default=str(OVERRIDES))
    ap.add_argument("--profiles", default=str(PROFILES))
    ap.add_argument("--archive-dir", default=str(ARCHIVE))
    ap.add_argument("--board", action="append", help="fold only this board id (repeat)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    mode.add_argument("--check", action="store_true", help="exit 1 when values are pending (prints the diff)")
    ap.add_argument("--force", action="store_true", help="on a conflict take the artist's value")
    ap.add_argument("--no-bump", action="store_true", help="keep the profile revision")
    ap.add_argument("--no-archive", action="store_true", help="keep the overrides file as it is after an apply")
    a = ap.parse_args(argv)
    try:
        ov_path = Path(a.overrides)
        prof_path = Path(a.profiles)
        if not ov_path.exists():
            print(json.dumps({"ok": True, "note": f"no overrides file ({ov_path}): nothing to fold"}, ensure_ascii=False))
            return 0
        doc, boards, _ = load_overrides(ov_path)
        if a.board:
            boards = [b for b in boards if b.board in a.board]
        raw = prof_path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
        res = fold_text(text, boards, force=a.force, bump=not a.no_bump)
        report = {"ok": not res.conflicts or a.force, "profiles": str(prof_path), "overrides": str(ov_path),
                  "applied": res.applied, "skipped": res.skipped, "conflicts": res.conflicts}
        d = diff(text, res.text, prof_path.name)
        if res.conflicts and not a.force:
            print(json.dumps(report, ensure_ascii=False, indent=1))
            return 2
        if a.dry_run or a.check:
            if d:
                sys.stdout.write(d)
            report["pending"] = bool(d)
            print(json.dumps(report, ensure_ascii=False, indent=1))
            return 1 if (a.check and d) else 0
        if d:
            write_atomic(prof_path, (b"\xef\xbb\xbf" if bom else b"") + res.text.encode("utf-8"))
            sys.stdout.write(d)
        if not a.no_archive:
            dest = archive(ov_path, doc, [b.board for b in boards], Path(a.archive_dir))
            report["archived"] = str(dest) if dest else None
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    except FoldError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
