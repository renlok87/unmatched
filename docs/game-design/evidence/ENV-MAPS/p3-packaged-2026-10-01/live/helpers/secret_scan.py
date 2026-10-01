#!/usr/bin/env python3
"""Secret scan of an evidence dir (values are never printed): backend/.env secret values (passwords, e-mails,
JWT secrets, DATABASE_URL, REDIS_PASSWORD), JWT-like tokens, postgres URLs, and the unredacted room codes of
the given staging dirs. Usage: python secret_scan.py <evidence-dir> [--staging DIR ...] [--extra FILE ...]"""
import argparse, json, re, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("evidence")
ap.add_argument("--staging", action="append", default=[])
ap.add_argument("--extra", action="append", default=[])
a = ap.parse_args()
env = {}
for ln in Path(r"C:\tmp\wt-envmaps\backend\.env").read_text(encoding="utf-8").splitlines():
    if "=" in ln and not ln.lstrip().startswith("#"):
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip().strip('"')
keys = [k for k in env if re.search(r"PASSWORD|EMAIL|SECRET|DATABASE_URL", k) and len(env[k]) >= 6]
needles = {k: env[k] for k in keys}
code_re = re.compile(r"createGame -> room=[A-Za-z0-9_-]+ code=([A-Z0-9-]{4,12})")
codes = set()
for s in a.staging:
    for tp in Path(s).glob("*.trace.log"):
        codes |= set(code_re.findall(tp.read_text(encoding="utf-8", errors="replace")))
for i, c in enumerate(sorted(codes)):
    needles[f"roomCode#{i}"] = c
patterns = {"jwtLike": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
            "postgresUrl": re.compile(r"postgres(?:ql)?://[^\s\"']+"),
            "bearer": re.compile(r"Bearer [A-Za-z0-9._-]{20,}")}
files = [p for p in Path(a.evidence).rglob("*") if p.is_file()] + [Path(x) for x in a.extra]
hits = []
for p in files:
    try:
        t = p.read_bytes().decode("utf-8", errors="ignore")
    except OSError:
        continue
    for k, v in needles.items():
        if v and v in t:
            hits.append({"file": str(p), "kind": k})
    for k, rx in patterns.items():
        if rx.search(t):
            hits.append({"file": str(p), "kind": k})
print(json.dumps({"filesScanned": len(files), "envKeysChecked": sorted(keys), "roomCodesChecked": len(codes),
                  "patterns": sorted(patterns), "hits": hits}, ensure_ascii=False, indent=2))
sys.exit(1 if hits else 0)
