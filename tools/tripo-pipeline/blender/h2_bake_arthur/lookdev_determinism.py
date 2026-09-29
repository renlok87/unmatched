"""Determinism of the look-dev chain of King Arthur (system python): run A (the profile's run_dir) vs run B (the same
chain in another directory, e.g. <run>/work/rerun-b, `run.py --run-dir ...`, without ld_ue_inputs).

    python lookdev_determinism.py <run A> <run B> [--out <report.json>]

Compares byte for byte every file of export/, textures/ (4K masters included), preview/, reports/ and the raw frames of
work/lookdev/render_final/; JSON reports that differ are compared again after replacing the run-B path by the run-A
path (the only expected difference). Writes <run A>/reports/determinism.json by default.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import pure as P  # noqa: E402

SUBS = ("export", "textures", "preview", "reports", "work/lookdev/render_final")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--out")
    a = ap.parse_args()
    ra, rb = Path(a.run_a).resolve(), Path(a.run_b).resolve()
    rel_a, rel_b = P.rel(ra), P.rel(rb)
    same, differ, only_a, json_path_only = [], [], [], []
    for sub in SUBS:
        for fa in sorted((ra / sub).rglob("*")):
            if not fa.is_file() or fa.name in ("determinism.json",) or "ue-inputs" in fa.parts:
                continue
            r = fa.relative_to(ra).as_posix()
            fb = rb / r
            if not fb.exists():
                only_a.append(r)
                continue
            if P.sha256(fa) == P.sha256(fb):
                same.append(r)
                continue
            if fa.suffix == ".json":
                ta = fa.read_text(encoding="utf-8")
                tb = fb.read_text(encoding="utf-8").replace(rel_b, rel_a)
                if ta == tb:
                    json_path_only.append(r)
                    continue
                try:
                    ja, jb = json.loads(ta), json.loads(tb)
                    keys = sorted(k for k in set(ja) | set(jb) if ja.get(k) != jb.get(k)) if isinstance(ja, dict) else []
                except ValueError:
                    keys = []
                differ.append({"file": r, "json_top_keys_differ": keys})
                continue
            e = {"file": r}
            if fa.suffix in (".png", ".jpg"):
                x = np.asarray(Image.open(fa).convert("RGB")).astype(np.int16)
                y = np.asarray(Image.open(fb).convert("RGB")).astype(np.int16)
                if x.shape == y.shape:
                    d = np.abs(x - y).max(axis=2)
                    e.update(pixel_max_abs_diff=int(d.max()), pixel_share_changed=P.r(float((d > 0).mean()), 6))
            differ.append(e)
    frames = [d for d in differ if "pixel_max_abs_diff" in d]
    rep_pixels = {"image_files_differing_in_bytes": len(frames),
                  "pixel_identical": sum(1 for d in frames if d["pixel_max_abs_diff"] == 0),
                  "max_abs_diff_8bit": max([d["pixel_max_abs_diff"] for d in frames] or [0])}
    rep = {"run_a": rel_a, "run_b": rel_b, "compared": len(same) + len(differ) + len(json_path_only),
           "byte_equal": len(same), "images": rep_pixels, "json_equal_after_run_path": json_path_only, "differ": differ, "only_in_a": only_a,
           "note": "ue-inputs/ is written only by run A (ld_ue_inputs: the generator's config points at run A)"}
    out = Path(a.out) if a.out else ra / "reports" / "determinism.json"
    P.write_json(out, rep)
    print("byte equal", len(same), "json equal after path", len(json_path_only), "differ", len(differ), "only in A", len(only_a))
    for d in differ:
        print("  differ", d)


if __name__ == "__main__":
    main()
