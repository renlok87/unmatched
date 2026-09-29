"""Byte comparison of two H2 bake runs of the same profile (system Python).

    python determinism_check.py <run_a> <run_b> <out.json>

Compares sha256 of: export/*.fbx, textures/**/*.png, work/uv-tris.npz, work/uv-labels.npz, work/bake/*.npy, and the
stage reports with volatile keys removed (seconds, absolute paths, blend hashes that embed paths). Writes the table and
the list of differing files.
"""

import hashlib
import json
import sys
from pathlib import Path

a, b, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3])
VOLATILE = {"seconds", "seconds_total", "import_seconds", "bvh_seconds", "seconds_per_part", "output_blend",
            "highpoly_blend", "authored_blend", "input_blend_sha256", "npy", "path", "preview"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def scrub(x):
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


rows = {}
for pattern in ("export/*.fbx", "textures/*/*.png", "work/uv-tris.npz", "work/uv-labels.npz", "work/bake/*.npy"):
    for fa in sorted(a.glob(pattern)):
        rel = fa.relative_to(a).as_posix()
        fb = b / rel
        rows[rel] = {"a": sha(fa)[:16], "b": sha(fb)[:16] if fb.exists() else None,
                     "equal": fb.exists() and sha(fa) == sha(fb), "bytes": fa.stat().st_size}
for rep in ("h2-lowpoly-report.json", "h2-uv-stage.json", "uv-report.json", "h2-bake-report.json",
            "textures-report.json", "h2-rig-report.json"):
    fa, fb = a / "reports" / rep, b / "reports" / rep
    if not fa.exists() or not fb.exists():
        continue
    ja, jb = scrub(json.loads(fa.read_text(encoding="utf-8"))), scrub(json.loads(fb.read_text(encoding="utf-8")))
    diff = sorted(k for k in set(ja) | set(jb) if ja.get(k) != jb.get(k))
    rows["reports/" + rep + " (volatile keys removed)"] = {"equal": not diff, "differing_keys": diff}
REPO = Path(__file__).resolve().parents[4]


def where(p):
    """Repo-relative path, or a neutral label for a scratch directory outside the repository (no local paths in
    committed reports)."""
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return "scratch:" + p.name


res = {"run_a": where(a), "run_b": where(b), "all_equal": all(r["equal"] for r in rows.values()),
       "differs": sorted(k for k, r in rows.items() if not r["equal"]), "files": rows}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("DETERMINISM", res["all_equal"], res["differs"])
