#!/usr/bin/env python3
"""Extract the layout around the project's UClass registration statics from an MSVC link map.

ART-004 WITH_RELOAD A/B (v3-live-hookup diagnosis, "How to check" step 4): with
-NoLiveCoding the project's Z_Registration_Info_UClass_* statics are 24 bytes
while the precompiled engine writes 16 bytes at offset 16 (bytes 16..31). This
tool lists every Z_Registration_Info_UClass_* symbol of the Unmatched module
with its address, the gap to the next symbol in address order and that next
symbol, i.e. what the 8 out-of-bounds bytes would overwrite.

  python tools/art/art004_map_registration.py <Unmatched.map> --out <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

LINE = re.compile(r"^\s*([0-9a-f]{4}):([0-9a-f]{8})\s+(\S+)\s+([0-9a-f]{16})\s+(.*)$", re.IGNORECASE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("map")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pattern", default="Z_Registration_Info_UClass_")
    a = ap.parse_args()
    mp = Path(a.map)
    h = hashlib.sha256()
    syms = []  # (rva, name, objinfo)
    section = None
    with mp.open("rb") as f:
        for raw in f:
            h.update(raw)
            line = raw.decode("latin-1").rstrip("\r\n")
            if "Publics by Value" in line:
                section = "public"
            elif line.strip().startswith("Static symbols"):
                section = "static"
            m = LINE.match(line)
            if m and section:
                syms.append((int(m.group(4), 16), m.group(3), m.group(5).strip(), section))
    syms.sort(key=lambda s: s[0])
    out = []
    for i, (rva, name, obj, sec) in enumerate(syms):
        if a.pattern in name and "AS08" in name or (a.pattern in name and "ASmokeGameMode" in name):
            nxt = next(((r, n, o) for r, n, o, _ in syms[i + 1:] if r > rva), None)
            prev = syms[i - 1] if i else None
            out.append({"symbol": name, "rva": hex(rva), "object": obj, "section": sec,
                        "next": {"symbol": nxt[1], "rva": hex(nxt[0]), "object": nxt[2],
                                 "gapBytes": nxt[0] - rva} if nxt else None,
                        "previous": {"symbol": prev[1], "rva": hex(prev[0])} if prev else None})
    doc = {"schema": "unmatched.art004-map-registration/1", "map": mp.name, "mapSha256": h.hexdigest(),
           "symbolsParsed": len(syms), "entries": out,
           "reading": "gapBytes = distance to the next symbol. A 24-byte static (WITH_RELOAD=0) followed by another "
                      "symbol at +24 means the engine's 16-byte store at offset 16 overwrites that symbol's first 8 bytes."}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for e in out:
        n = e["next"] or {}
        print(e["symbol"], e["rva"], "->", n.get("symbol"), n.get("gapBytes"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
