"""ASSET-TABLE-BASE-001 T2b: the moss detail textures of the upper-lip band (system Python: numpy + PIL).

  python -B art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2b_textures.py \
      --params art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2b/reports/tray-t2b-params.json

The rock itself reuses the T2 set (T_TableBase_T2_{BC,N,ORM}, Rock058-derived). New here (CC0 Moss002, ambientCG, already
in the local library - no download):
  export/T_TableBase_T2b_Moss_BC.png  sRGB 1024: Moss002 Color, saturation partly kept (saturation_keep) so the MI tint
                                      (Marmoreal moss green + petals / Sarpedon dark damp) drives the hue, mean luma
                                      normalised to target_mean_luma_srgb;
  export/T_TableBase_T2b_Moss_N.png   linear 1024: Moss002 NormalDX (DirectX, flip_green false in UE), resized.
Both tile (the source is a seamless 2K tile; a box resize keeps it seamless). reports/textures-report.json: sha256 of
sources and outputs, stats.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True)
    a = ap.parse_args(argv)
    pp = Path(a.params).resolve()
    P = json.loads(pp.read_text(encoding="utf-8"))
    M = P["moss_textures"]
    src = Path(M["source_dir"])
    sid = M["source_id"]
    col_p, nrm_p = src / f"{sid}_2K-JPG_Color.jpg", src / f"{sid}_2K-JPG_NormalDX.jpg"
    out = (REPO / P["run_dir"] / "export").resolve()
    out.mkdir(parents=True, exist_ok=True)
    size = int(M["size"])
    c = np.asarray(Image.open(col_p).convert("RGB").resize((size, size), Image.BOX), dtype=np.float64) / 255.0
    luma = c @ np.array([0.2126, 0.7152, 0.0722])
    k = float(M["saturation_keep"])
    c = luma[..., None] + (c - luma[..., None]) * k
    luma2 = c @ np.array([0.2126, 0.7152, 0.0722])
    c = np.clip(c * (float(M["target_mean_luma_srgb"]) / max(luma2.mean(), 1e-6)), 0.0, 1.0)
    bc_path = out / f"{M['prefix']}_BC.png"
    Image.fromarray((c * 255.0 + 0.5).astype(np.uint8)).save(bc_path, optimize=True)
    n = Image.open(nrm_p).convert("RGB").resize((size, size), Image.BOX)
    n_path = out / f"{M['prefix']}_N.png"
    n.save(n_path, optimize=True)
    hsv = np.asarray(Image.fromarray((c * 255).astype(np.uint8)).convert("HSV"), dtype=np.float64) / 255.0
    rep = {"schema": "unmatched.table-base-t2b.textures/1", "status": "measured",
           "sources": {"id": sid, "license": "CC0 1.0 (ambientCG)", "color": {"path": col_p.as_posix(), "sha256": sha(col_p)},
                       "normalDX": {"path": nrm_p.as_posix(), "sha256": sha(nrm_p)}},
           "outputs": {p.name: {"path": p.relative_to(REPO).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size,
                                "size": [size, size]} for p in (bc_path, n_path)},
           "stats": {"bcMeanLumaSrgb": round(float((c @ np.array([0.2126, 0.7152, 0.0722])).mean()), 4),
                     "bcMeanSaturation": round(float(hsv[..., 1].mean()), 4),
                     "bcMeanHueDeg": round(float(hsv[..., 0].mean() * 360.0), 1)},
           "ue": {"BC": "sRGB, TC_Default, Wrap", "N": "linear, TC_Normalmap, DirectX (flip_green false), Wrap"},
           "rockSetReused": P["rock_textures"]}
    rp = REPO / P["run_dir"] / "reports" / "textures-report.json"
    rp.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("T2B-TEXTURES ok", json.dumps(rep["stats"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
