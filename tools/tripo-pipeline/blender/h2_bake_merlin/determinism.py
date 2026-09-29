"""Compare two runs of the H2 bake file by file (system python: numpy, Pillow).

python determinism.py <run_dir_a> <run_dir_b> <out.json> [--subdirs export textures reports preview] [--note TEXT]
                       [--section NAME]

For every file under the given subdirectories of both runs: sha256 equal or not; for PNGs that differ, whether only
metadata chunks differ (pixels equal) or how many pixels differ and by how much; for JSON that differ, whether they
are equal once the run directory of b is written as the one of a (reports carry repo-relative paths); for binary FBX
that differ, which nodes differ (node path + property values, arrays by length). Writes one deterministic JSON (no
host paths: run dirs are given repo-relative when inside the repo; FBX strings that are absolute paths are replaced
by their length, other strings shortened to 60 characters). With --section the result becomes one key of <out>, so
reports/determinism.json can hold several comparisons, each regenerable by this tool.

How the committed reports/determinism.json of 20260929-h2-bake was made (2026-09-29):
  fix_vs_pre_fix   run_a = work/pre-fix (the outputs before the host-path fix, copied back and checked by sha256)
  other_directory  run_b = work/rerun-b (profile copy with run_dir = work/rerun-b; stages maps..sheets from the same
                   work/h2-uv.blend, work/uv, work/bake and source/retopo/uv/bake reports)
"""

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

SUBDIRS = ("export", "textures", "reports", "preview")
DETERMINISM_FILE = "determinism.json"  # reports/determinism.json (this tool's own output) is never compared


def png_pixels(path):
    with Image.open(path) as img:
        return img.mode, np.asarray(img).astype(np.int16)


def compare_png(a, b):
    ma, pa = png_pixels(a)
    mb, pb = png_pixels(b)
    if ma != mb or pa.shape != pb.shape:
        return {"kind": "png", "pixels": "different size/mode", "a": [ma, list(pa.shape)], "b": [mb, list(pb.shape)]}
    d = np.abs(pa - pb)
    if d.ndim == 3:
        d = d.max(-1)
    n = int((d > 0).sum())
    if n == 0:
        return {"kind": "png", "pixels": "identical", "bytes_differ_by": "chunks outside the pixel data (metadata)"}
    return {"kind": "png", "pixels": "different", "pixels_differing": n, "share": C.r(n / d.size, 8), "max_abs_lsb": int(d.max())}


def fbx_nodes(path):
    """Flat list (node path, properties) of a binary FBX; arrays are kept as (type, length, bytes)."""
    b = Path(path).read_bytes()
    if b[:21] != b"Kaydara FBX Binary  \x00":
        raise ValueError("%s: not a binary FBX" % path)
    wide = struct.unpack("<I", b[23:27])[0] >= 7500
    out = []

    def props(o, n):
        res = []
        for _ in range(n):
            t = chr(b[o])
            o += 1
            if t in "YCILFD":
                fmt = {"Y": "<h", "C": "<?", "I": "<i", "L": "<q", "F": "<f", "D": "<d"}[t]
                res.append(struct.unpack_from(fmt, b, o)[0])
                o += struct.calcsize(fmt)
            elif t in "fdlibc":
                ln, enc, cl = struct.unpack_from("<III", b, o)
                o += 12
                raw = b[o:o + cl]
                o += cl
                res.append(("array", t, ln, zlib.decompress(raw) if enc else raw))
            elif t in "SR":
                ln = struct.unpack_from("<I", b, o)[0]
                o += 4
                res.append((t, b[o:o + ln]))
                o += ln
            else:
                raise ValueError("%s: property type %r" % (path, t))
        return res

    def node(o, parent):
        if wide:
            end, n_props, plen = struct.unpack_from("<QQQ", b, o)
            o += 24
        else:
            end, n_props, plen = struct.unpack_from("<III", b, o)
            o += 12
        nl = b[o]
        name = b[o + 1:o + 1 + nl].decode("ascii")
        o += 1 + nl
        if end == 0:
            return None
        here = parent + "/" + name
        out.append((here, props(o, n_props)))
        o += plen
        while o < end:
            nxt = node(o, here)
            if nxt is None:
                break
            o = nxt
        return end

    o = 27
    while o < len(b):
        nxt = node(o, "")
        if nxt is None:
            break
        o = nxt
    return out


def short(v):
    if isinstance(v, tuple) and v[0] == "array":
        return "array %s[%d]" % (v[1], v[2])
    if isinstance(v, tuple):
        s = v[1].decode("utf-8", "replace")
        if re.match(r"^([A-Za-z]:[\\/]|/)", s):
            return "<absolute host path, %d chars>" % len(s)  # the report never carries host paths
        return s if len(s) <= 60 else s[:57] + "..."
    return v


def compare_fbx(a, b):
    na, nb = fbx_nodes(a), fbx_nodes(b)
    if [p for p, _ in na] != [p for p, _ in nb]:
        return {"kind": "fbx", "node_tree": "different", "nodes_a": len(na), "nodes_b": len(nb)}
    diff = [{"node": pa, "a": [short(v) for v in xa], "b": [short(v) for v in xb]}
            for (pa, xa), (_pb, xb) in zip(na, nb) if xa != xb]
    return {"kind": "fbx", "node_tree": "same", "nodes": len(na), "differing_nodes": len(diff), "first_10": diff[:10]}


def json_diff_keys(ja, jb, limit=20):
    diffs = []

    def walk(x, y, path):
        if len(diffs) >= limit:
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                walk(x.get(k), y.get(k), path + "/" + str(k))
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            for i, (u, v) in enumerate(zip(x, y)):
                walk(u, v, "%s[%d]" % (path, i))
        elif x != y:
            diffs.append(path)

    walk(ja, jb, "")
    return diffs


def compare_json(a, b, run_a, run_b):
    """Equal once b's run dir is written as a's? Otherwise the differing keys, as read (a copied run keeps the paths
    of the run it was copied from) or after the substitution, whichever differs in fewer keys."""
    ta = Path(a).read_text(encoding="utf-8")
    tb_raw = Path(b).read_text(encoding="utf-8")
    tb = tb_raw.replace(run_b, run_a)
    if ta == tb:
        return {"kind": "json", "equal_after_run_dir_substitution": True}
    ja = json.loads(ta)
    diffs = min((json_diff_keys(ja, json.loads(t), 10 ** 6) for t in (tb_raw, tb)), key=len)
    return {"kind": "json", "equal_after_run_dir_substitution": False, "differing_keys": len(diffs),
            "differing_keys_first_20": diffs[:20]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("out")
    ap.add_argument("--subdirs", nargs="*", default=list(SUBDIRS))
    ap.add_argument("--note")
    ap.add_argument("--section", help="write the result as this key of <out> (other keys of <out> are kept)")
    a = ap.parse_args()
    ra, rb = Path(a.run_a).resolve(), Path(a.run_b).resolve()
    rel_a, rel_b = C.rel(ra), C.rel(rb)
    files = set()
    for sub in a.subdirs:
        for root in (ra, rb):
            for p in (root / sub).rglob("*"):
                if p.is_file() and p.name != DETERMINISM_FILE:
                    files.add(p.relative_to(root).as_posix())
    identical, different, only = [], {}, {}
    for f in sorted(files):
        fa, fb = ra / f, rb / f
        if not fa.exists() or not fb.exists():
            only[f] = "a" if fa.exists() else "b"
            continue
        if C.sha256(fa) == C.sha256(fb):
            identical.append(f)
            continue
        if f.endswith(".png"):
            different[f] = compare_png(fa, fb)
        elif f.endswith(".json"):
            different[f] = compare_json(fa, fb, rel_a, rel_b)
        elif f.endswith(".fbx"):
            different[f] = compare_fbx(fa, fb)
        else:
            different[f] = {"kind": fa.suffix.lstrip(".") or "bin", "bytes_a": fa.stat().st_size, "bytes_b": fb.stat().st_size}
    rep = {"schema": "unmatched.art-pipeline.h2-determinism-compare/1", "run_a": rel_a, "run_b": rel_b,
           "subdirs": a.subdirs, "files": len(files), "identical_files": len(identical),
           "different_files": len(different), "only_in_one_run": only, "identical": identical, "different": different}
    if a.note:
        rep["note"] = a.note
    if a.section:
        whole = C.load_json(a.out) if Path(a.out).exists() else {}
        whole[a.section] = rep
        rep = whole
    C.write_json(a.out, rep)
    print("DETERMINISM files=%d identical=%d different=%d only=%d" % (len(files), len(identical), len(different), len(only)))


if __name__ == "__main__":
    main()
