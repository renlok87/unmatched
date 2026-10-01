"""ASSET-TABLE-BASE-001 T2 (the shared rocky tray of the map boards): tileable BC / N / ORM from CC0 Rock058.

System Python (numpy + PIL), CPU only, no Blender / UE. Run from the repository root:
  python -B art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2_textures.py \
      --params art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2/reports/tray-t2-params.json

Why Rock058 and not the T1 atlas: SM_TableBase_T2 is a modular kit (rock chunks instanced along the perimeter), so
its UV0 is a world-scale box projection that TILES (UE Wrap addressing; M_UM_Figure samples TexCoord0 directly). The
T1 textures (T_TableBase_*) are a Tripo UV atlas and cannot tile. The rock is therefore the CC0 ambientCG set Rock058
(2K, seamless; raw files out of git under art/material-library/cc0-raw, manifest sha256 checked), toned to the SAME
stone as the T1 skirt ("единая каменная подложка"): the mean colour of the T1 skirt texels of T_TableBase_BC.png is
measured here (high-detail texels outside the lip rectangle) and Rock058 is moved onto it. Only per-pixel operations
are applied, so the result stays seamless (checked: wrap-around edge jump vs. interior column jump).

Outputs (in <run>/export): T_TableBase_T2_BC.png (sRGB), T_TableBase_T2_N.png (linear, DirectX = Rock058 NormalDX,
UE flip_green off), T_TableBase_T2_ORM.png (linear: R = Rock058 AO, G = roughness remapped, B = metallic 0).
Report: <run>/reports/textures-report.json (sources + sha256, measured T1 tone, tone curve, results, tiling check).
Nothing here is an art decision; every number is a measurement or a PROPOSED default of the params file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
SCHEMA = "unmatched.table-base-t2.textures/1"
LUMA = np.array([0.2126, 0.7152, 0.0722])


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def s2l(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def l2s(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def load(path: Path, mode: str) -> np.ndarray:
    return np.asarray(Image.open(path).convert(mode)).astype(np.float64) / 255.0


def save_png(arr: np.ndarray, path: Path) -> None:
    """8-bit PNG without gAMA / sRGB / cHRM / iCCP chunks (UE decides sRGB by the import setting)."""
    a = np.clip(np.round(arr * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(a, "RGB").save(path, optimize=False, compress_level=9)
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    out, pos = bytearray(data[:8]), 8
    while pos < len(data):
        n = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        if kind not in (b"gAMA", b"sRGB", b"cHRM", b"iCCP", b"tIME", b"tEXt", b"iTXt", b"zTXt"):
            out += data[pos:pos + 12 + n]
        pos += 12 + n
    path.write_bytes(bytes(out))


def local_std(lum: np.ndarray, k: int = 9) -> np.ndarray:
    """k x k standard deviation with an integral image (edge padding)."""
    p = k // 2
    a = np.pad(lum, p, mode="edge")
    s1 = np.pad(a.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    s2 = np.pad((a * a).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    h, w = lum.shape

    def box(s):
        return s[k:k + h, k:k + w] - s[0:h, k:k + w] - s[k:k + h, 0:w] + s[0:h, 0:w]
    m1, m2 = box(s1) / (k * k), box(s2) / (k * k)
    return np.sqrt(np.maximum(m2 - m1 * m1, 0.0))


def measure_t1(bc_path: Path, lip_rect_px: list) -> dict:
    """Mean linear colour of the T1 skirt: texels with above-median local detail (the dilated gutters are smooth)
    outside the lip rectangle (the texture-bombed lip strips, T1 report)."""
    srgb = load(bc_path, "RGB")
    lin = s2l(srgb)
    lum = lin @ LUMA
    mask = np.ones(lum.shape, bool)
    x0, y0, x1, y1 = lip_rect_px
    mask[y0:y1, x0:x1] = False
    std = local_std(lum)
    sel = mask & (std > np.percentile(std[mask], 50))
    mean = lin[sel].mean(0)
    return {"path": rel(bc_path), "sha256": sha256(bc_path), "lipRectExcludedPx_x0y0x1y1": lip_rect_px,
            "texels": int(sel.sum()), "linearMean": [round(float(v), 5) for v in mean],
            "luminanceMean": round(float(lum[sel].mean()), 5),
            "luminanceP10P50P90": [round(float(v), 5) for v in np.percentile(lum[sel], [10, 50, 90])],
            "contrastStdOverMean": round(float(lum[sel].std() / lum[sel].mean()), 4)}


def tiling_jump(a: np.ndarray) -> dict:
    """Mean |difference| across the wrap-around seam vs. between neighbouring interior columns / rows (seamless:
    the seam is no worse than the interior)."""
    col = float(np.abs(a[:, 0] - a[:, -1]).mean())
    row = float(np.abs(a[0, :] - a[-1, :]).mean())
    inner_c = float(np.abs(np.diff(a, axis=1)).mean())
    inner_r = float(np.abs(np.diff(a, axis=0)).mean())
    return {"seamColumn": round(col, 5), "interiorColumn": round(inner_c, 5), "seamRow": round(row, 5),
            "interiorRow": round(inner_r, 5),
            "seamless": col <= 2.0 * inner_c + 1e-4 and row <= 2.0 * inner_r + 1e-4}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--params", required=True)
    a = ap.parse_args(argv)
    params_path = Path(a.params).resolve()
    P = json.loads(params_path.read_text(encoding="utf-8"))
    run = (REPO / P["run_dir"]).resolve()
    T = P["textures"]
    src_dir = Path(T["rock_dir"])
    manifest_path = Path(T["cc0_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(x for x in manifest["assets"] if x["id"] == T["rock_id"])
    files = {k: src_dir / f"{T['rock_id']}_2K-JPG_{v}.jpg" for k, v in
             (("color", "Color"), ("normal_dx", "NormalDX"), ("ao", "AmbientOcclusion"), ("rough", "Roughness"))}
    for k, f in files.items():
        if not f.is_file():
            raise SystemExit(f"missing Rock058 source {f} (unzip {entry['file']} into {src_dir})")
    zip_path = src_dir.parent / f"{T['rock_id']}_2K-JPG.zip"
    zip_ok = zip_path.is_file() and sha256(zip_path) == entry["sha256"]
    t1 = measure_t1(REPO / T["t1_bc"], T["t1_lip_rect_px"])

    # ---- BC: Rock058 colour -> the T1 skirt stone (per pixel only: stays seamless)
    lin = s2l(load(files["color"], "RGB"))
    lum = np.maximum(lin @ LUMA, 1e-5)
    knee = float(np.percentile(lum, T["highlight_knee_percentile"]))
    lum_c = np.where(lum <= knee, lum, knee + (lum - knee) * T["highlight_slope"])  # Rock058's orange rim lights
    chroma = lin / lum[..., None]
    chroma_mean = chroma.reshape(-1, 3).mean(0)
    t1_tint = np.array(t1["linearMean"]) / t1["luminanceMean"]
    keep = T["chroma_variation_keep"]
    tint = (1.0 + (chroma / chroma_mean - 1.0) * keep) * t1_tint  # Rock058 variation around the T1 hue
    target = t1["luminanceMean"] * T["luminance_vs_t1_skirt"]
    shaped = np.power(lum_c / lum_c.mean(), T["contrast_gamma"])
    lum_out = target * shaped / shaped.mean()
    out_lin = np.clip(lum_out[..., None] * tint, 0.0, 1.0)
    bc = l2s(out_lin)
    # ---- N: Rock058 NormalDX (DirectX, as UE expects; no flip)
    n = load(files["normal_dx"], "RGB")
    # ---- ORM
    ao = load(files["ao"], "L")
    ao = 1.0 - (1.0 - ao) * T["ao_strength"]
    rough = load(files["rough"], "L")
    rough = np.clip(T["roughness_mean"] + (rough - rough.mean()) * T["roughness_variation"], *T["roughness_clamp"])
    orm = np.stack([ao, rough, np.zeros_like(ao)], axis=-1)

    export = run / "export"
    export.mkdir(parents=True, exist_ok=True)
    outs = {"BC": (export / "T_TableBase_T2_BC.png", bc, "sRGB"),
            "N": (export / "T_TableBase_T2_N.png", n, "linear, DirectX (Rock058 NormalDX), UE TC_Normalmap flip_green false"),
            "ORM": (export / "T_TableBase_T2_ORM.png", orm, "linear, R = AO, G = roughness, B = metallic (UE TC_Masks)")}
    report = {
        "schema": SCHEMA, "status": "measured", "asset": "ASSET-TABLE-BASE-001 / SM_TableBase_T2",
        "claims": {"art_accepted": False},
        "script_sha256": sha256(HERE), "params": rel(params_path), "params_sha256": sha256(params_path),
        "rock": {"id": T["rock_id"], "license": entry.get("license"), "page": entry.get("page"),
                 "zip": rel(zip_path), "zipSha256Manifest": entry["sha256"], "zipSha256Matches": zip_ok,
                 "files": {k: {"path": f.name, "sha256": sha256(f)} for k, f in files.items()},
                 "note": "raw CC0 files stay out of git (art/material-library/cc0-raw/.gitignore); only the derived "
                         "textures below are outputs"},
        "t1Skirt": t1,
        "tone": {"highlightKnee": round(knee, 5), "highlightSlope": T["highlight_slope"],
                 "rockLuminanceMean": round(float(lum.mean()), 5),
                 "rockChromaMean": [round(float(v), 4) for v in chroma_mean],
                 "t1Tint": [round(float(v), 4) for v in t1_tint], "chromaVariationKeep": keep,
                 "targetLuminanceMean": round(target, 5), "contrastGamma": T["contrast_gamma"]},
        "outputs": {},
    }
    for key, (path, arr, space) in outs.items():
        save_png(arr, path)
        info = {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size, "size": list(arr.shape[:2]),
                "space": space, "channelMean": [round(float(v), 4) for v in arr.reshape(-1, 3).mean(0)],
                "tiling": tiling_jump(arr.mean(-1))}
        if key == "BC":
            lo = s2l(np.asarray(Image.open(path)).astype(np.float64) / 255.0)
            ll = lo @ LUMA
            info.update(linearMean=[round(float(v), 5) for v in lo.reshape(-1, 3).mean(0)],
                        luminanceMean=round(float(ll.mean()), 5),
                        luminanceP10P50P90=[round(float(v), 5) for v in np.percentile(ll, [10, 50, 90])],
                        contrastStdOverMean=round(float(ll.std() / ll.mean()), 4),
                        vsT1SkirtLuminance=round(float(ll.mean() / t1["luminanceMean"]), 4))
        report["outputs"][key] = info
    report["checks"] = {
        "sources_present": True,
        "zip_sha256_matches_manifest": zip_ok,
        "all_seamless": all(v["tiling"]["seamless"] for v in report["outputs"].values()),
        "bc_luminance_within_10pct_of_target": abs(report["outputs"]["BC"]["luminanceMean"] / target - 1) <= 0.10,
    }
    report["checks_passed"] = all(report["checks"].values())
    (run / "reports").mkdir(parents=True, exist_ok=True)
    out_path = run / "reports" / "textures-report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("T2-TEXTURES", json.dumps(report["checks"]), {k: v["sha256"][:12] for k, v in report["outputs"].items()})
    return 0 if report["checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
