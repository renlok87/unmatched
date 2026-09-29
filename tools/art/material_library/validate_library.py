"""Validator of the UM material library v1 (tiles, report, CC0 sources, presets).

Checks (each result: {"check", "ok", "detail"}; exit code 1 when any fails):
  files            presets / sources / report / README / cc0-raw manifest exist
  tile_files       every tile of the report exists, sha256 and size match, RGB, square 512/1024
  presets_tiles    presets classes 0..15 = report classes 1..15, same ids, same tile paths and sizes
  licenses         every manifest asset is CC0; sources.json covers all manifest ids once, same zip sha256
  source_mapping   used sets <-> classes built from them; unused sets have a reason; procedural classes listed
  raw_files        (only with --verify-raw, when cc0-raw is present) zip and source-file sha256
  seamless         wrap-pair / p99 interior-pair difference <= SEAM_MAX per axis, for N.xy, R, G, B
  normal_dx        DetailN: unit length, z > 0, xy mean ~ 0; DirectX sign: corr(N.y, -dB/drow) > 0 and >= half of
                   corr(N.x, -dB/dcol) (when B has relief; a G-flipped map gives corr_y ~ -corr_x); the source NormalDX was the G-inverted NormalGL
  preset_physics   metallic in {0, 1}; metal BC = reference F0 (oxide film: low-F0 band with a reference);
                   dielectric BC Y in [0.02, 0.9], channels <= 0.9; specular/F0 consistent and in the dielectric
                   band; roughness ranges ordered, measured values equal the report; Cloth <=> cloth block with a
                   formula-consistent sheen colour; tiles per metre consistent; every cited source defined

  python tools/art/material_library/validate_library.py [--root <repo>] [--verify-raw] [--json out.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
PRESETS = "docs/art-pipeline/material-library/um-material-presets-v1.json"
SOURCES = "docs/art-pipeline/material-library/sources.json"
README = "docs/art-pipeline/material-library/README.md"
REPORT = "art/material-library/v1/textures-report.json"
MANIFEST = "art/material-library/cc0-raw/manifest.json"

SEAM_MAX = 1.25
DIEL_Y = (0.02, 0.9)
DIEL_MAX_CHANNEL = 0.9
DIEL_F0 = (0.02, 0.06)
METAL_F0_TOL = 0.02
METAL_MIN_Y = 0.45
OXIDE_Y = (0.05, 0.35)
SHADING_MODELS = {"DefaultLit", "Cloth"}
LUM = np.array([0.2126, 0.7152, 0.0722])


def y_of(c) -> float:
    return float(np.dot(LUM, np.asarray(c, dtype=np.float64)))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------- image metrics
def seam_ratio(a: np.ndarray) -> tuple[float, float]:
    """Wrap-pair mean |difference| / p99 of the interior pair differences, per axis (x, y)."""
    if a.ndim == 2:
        a = a[..., None]
    a = a.astype(np.float64)
    cx = np.abs(a[:, 1:] - a[:, :-1]).mean(axis=(0, 2))
    cy = np.abs(a[1:] - a[:-1]).mean(axis=(1, 2))
    ex = np.abs(a[:, 0] - a[:, -1]).mean()
    ey = np.abs(a[0] - a[-1]).mean()

    def r(e, ref):
        if ref > 1e-9:
            return float(e / ref)
        return 0.0 if e < 1e-9 else float("inf")

    return r(ex, np.percentile(cx, 99)), r(ey, np.percentile(cy, 99))


def _blur_torus(a: np.ndarray, sigma: float) -> np.ndarray:
    n0, n1 = a.shape
    f0, f1 = np.fft.fftfreq(n0)[:, None], np.fft.fftfreq(n1)[None, :]
    return np.real(np.fft.ifft2(np.fft.fft2(a) * np.exp(-2.0 * (np.pi * sigma) ** 2 * (f0 ** 2 + f1 ** 2))))


def _corr(a, b) -> float:
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 1e-12 else 0.0


def normal_convention(n_rgb: np.ndarray, height01: np.ndarray) -> dict:
    """n_rgb uint8 (H, W, 3), height01 float (H, W). corr > 0 on both axes = DirectX (G = -dh/drow)."""
    n = n_rgb.astype(np.float64) / 255.0 * 2.0 - 1.0
    ln = np.linalg.norm(n, axis=-1)
    out = {"len_p1": float(np.percentile(ln, 1)), "len_p99": float(np.percentile(ln, 99)),
           "min_z": float(n[..., 2].min()), "mean_x": float(n[..., 0].mean()), "mean_y": float(n[..., 1].mean()),
           "height_std": float(height01.std()), "corr_y": None, "corr_x": None}
    if out["height_std"] > 0.01:
        h = _blur_torus(height01, 1.0)
        dr = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
        dc = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
        out["corr_y"] = _corr(n[..., 1], -dr)
        out["corr_x"] = _corr(n[..., 0], -dc)
    return out


def dx_sign_ok(corr_x: float, corr_y: float) -> bool:
    """DirectX: N.y agrees with -dh/drow as N.x agrees with -dh/dcol. An OpenGL (G-flipped) map gives
    corr_y ~ -corr_x; the x axis is identical in both conventions and shows that normal and height agree at all."""
    return max(corr_x, corr_y) >= 0.05 and corr_y > 0.0 and corr_y >= 0.5 * corr_x


# ------------------------------------------------------------------------------------------------ validate
class Results(list):
    def add(self, check: str, ok: bool, detail: str = ""):
        self.append({"check": check, "ok": bool(ok), "detail": detail})


def validate(root: Path = REPO, verify_raw: bool = False) -> list[dict]:
    root = Path(root)
    res = Results()
    paths = {"presets": root / PRESETS, "sources": root / SOURCES, "report": root / REPORT,
             "readme": root / README, "manifest": root / MANIFEST}
    missing = [k for k, p in paths.items() if not p.is_file()]
    res.add("files", not missing, f"missing: {missing}" if missing else "all present")
    if any(k in missing for k in ("presets", "sources", "report", "manifest")):
        return res
    presets, sources = load_json(paths["presets"]), load_json(paths["sources"])
    report, manifest = load_json(paths["report"]), load_json(paths["manifest"])
    tiles = {}
    _check_tiles(root, report, res, tiles)
    _check_presets_vs_report(presets, report, res)
    _check_licenses(manifest, sources, res)
    _check_mapping(sources, presets, report, res)
    if verify_raw:
        _check_raw(root, manifest, report, res)
    _check_seams(tiles, res)
    _check_normals(tiles, report, res)
    _check_physics(presets, report, res)
    return res


def _check_tiles(root, report, res, tiles):
    bad = []
    for c in report.get("classes", []):
        maps = {}
        for o in c.get("outputs", []):
            p = root / o["path"]
            if not p.is_file():
                bad.append(f"{o['path']}: missing")
                continue
            if sha256_file(p) != o.get("sha256"):
                bad.append(f"{o['path']}: sha256 differs from the report")
            if p.stat().st_size != o.get("bytes"):
                bad.append(f"{o['path']}: size differs from the report")
            im = Image.open(p)
            if im.mode != "RGB" or im.size[0] != im.size[1] or im.size[0] not in (512, 1024) \
                    or im.size[0] != c.get("size"):
                bad.append(f"{o['path']}: {im.mode} {im.size}, expected RGB square {c.get('size')}")
            maps[o["map"]] = np.asarray(im.convert("RGB"))
        if set(maps) == {"DetailN", "DetailRMH"}:
            tiles[c["class"]] = maps
        else:
            bad.append(f"{c.get('class')}: maps {sorted(maps)}")
    res.add("tile_files", not bad and bool(tiles), "; ".join(bad) or f"{len(tiles)} classes x 2 maps, sha256 ok")


def _check_presets_vs_report(presets, report, res):
    bad = []
    pcs = presets.get("classes", [])
    idx = [c.get("index") for c in pcs]
    if idx != list(range(len(pcs))) or len(pcs) > int(presets.get("matId", {}).get("maxClasses", 16)) or len(pcs) > 16:
        bad.append(f"preset indices {idx} must be 0..N-1 with N <= 16")
    if not pcs or pcs[0].get("family") != "passthrough":
        bad.append("index 0 must be the passthrough (legacy_bake) class")
    rep = {c["index"]: c for c in report.get("classes", [])}
    for c in pcs[1:]:
        r = rep.get(c.get("index"))
        if r is None or r["class"] != c.get("id"):
            bad.append(f"index {c.get('index')} {c.get('id')}: not in the report as the same class")
            continue
        outs = {o["map"]: o["path"] for o in r["outputs"]}
        d = c.get("detail", {})
        if d.get("DetailN") != outs.get("DetailN") or d.get("DetailRMH") != outs.get("DetailRMH"):
            bad.append(f"{c['id']}: tile paths differ from the report")
        if d.get("tileSizePx") != r.get("size"):
            bad.append(f"{c['id']}: tileSizePx {d.get('tileSizePx')} != report size {r.get('size')}")
    extra = set(rep) - {c.get("index") for c in pcs}
    if extra:
        bad.append(f"report classes without a preset: {sorted(extra)}")
    res.add("presets_tiles", not bad, "; ".join(bad) or f"{len(pcs)} presets (incl. index 0) match the report")


def _check_licenses(manifest, sources, res):
    bad = []
    assets = {a["id"]: a for a in manifest.get("assets", [])}
    for a in assets.values():
        if "CC0" not in str(a.get("license", "")):
            bad.append(f"{a['id']}: license {a.get('license')!r} is not CC0")
    ids = [s.get("id") for s in sources.get("sets", [])]
    if sorted(ids) != sorted(assets) or len(set(ids)) != len(ids):
        bad.append(f"sources.json sets {sorted(ids)} != manifest assets {sorted(assets)}")
    for s in sources.get("sets", []):
        a = assets.get(s.get("id"))
        if a is None:
            continue
        if s.get("zipSha256") != a.get("sha256"):
            bad.append(f"{s['id']}: zipSha256 differs from the manifest")
        if "CC0" not in str(s.get("license", "")):
            bad.append(f"{s['id']}: sources.json license is not CC0")
    res.add("licenses", not bad, "; ".join(bad) or f"{len(assets)} sets, all CC0, sha256 = manifest")


def _check_mapping(sources, presets, report, res):
    bad = []
    classes = {c.get("id") for c in presets.get("classes", [])}
    built = {c["class"]: c.get("build", {}).get("source") for c in report.get("classes", [])}
    used_by_class = {}
    for s in sources.get("sets", []):
        st = s.get("status")
        if st == "используется":
            if s.get("class") not in classes:
                bad.append(f"{s['id']}: used for unknown class {s.get('class')!r}")
            elif built.get(s["class"]) != s["id"]:
                bad.append(f"{s['id']}: class {s['class']} is built from {built.get(s['class'])!r}")
            used_by_class[s.get("class")] = s["id"]
        elif st == "не используется":
            if s.get("class") is not None or len(str(s.get("reason", "")).strip()) < 20:
                bad.append(f"{s['id']}: unused set needs class null and a reason")
        else:
            bad.append(f"{s.get('id')}: status {st!r}")
    proc = {p.get("class") for p in sources.get("procedural", [])}
    for cls, src in built.items():
        if str(src).startswith("procedural:"):
            if cls not in proc:
                bad.append(f"{cls}: procedural but not listed in sources.json procedural")
        elif used_by_class.get(cls) != src:
            bad.append(f"{cls}: source {src} not marked as used for it")
    res.add("source_mapping", not bad, "; ".join(bad) or
            f"{len(used_by_class)} sets used, {len(sources.get('sets', [])) - len(used_by_class)} unused with reasons, "
            f"{len(proc)} procedural")


def _check_raw(root, manifest, report, res):
    raw = root / "art" / "material-library" / "cc0-raw"
    bad, n = [], 0
    for a in manifest.get("assets", []):
        z = raw / Path(a["file"].split("file=")[-1]).name
        if z.is_file():
            n += 1
            if sha256_file(z) != a["sha256"]:
                bad.append(f"{z.name}: sha256 differs from the manifest")
    for c in report.get("classes", []):
        for f in c.get("sourceFiles", []):
            p = root / f["file"]
            if p.is_file():
                n += 1
                if sha256_file(p) != f["sha256"]:
                    bad.append(f"{f['file']}: sha256 differs from the report")
    res.add("raw_files", not bad and n > 0, "; ".join(bad) or (f"{n} raw files verified" if n else "cc0-raw absent"))


def _check_seams(tiles, res):
    bad, worst = [], 0.0
    for cls, m in tiles.items():
        n = m["DetailN"].astype(np.float64)
        rmh = m["DetailRMH"].astype(np.float64)
        for name, arr in (("N.xy", n[..., :2]), ("R", rmh[..., 0]), ("G", rmh[..., 1]), ("B", rmh[..., 2])):
            rx, ry = seam_ratio(arr)
            worst = max(worst, rx, ry)
            if rx > SEAM_MAX or ry > SEAM_MAX:
                bad.append(f"{cls} {name}: seam ratio ({rx:.3f}, {ry:.3f}) > {SEAM_MAX}")
    res.add("seamless", not bad and bool(tiles), "; ".join(bad) or f"worst ratio {worst:.3f} <= {SEAM_MAX}")


def _check_normals(tiles, report, res):
    bad = []
    if "DirectX" not in str(report.get("normalConvention", "")):
        bad.append("report normalConvention is not DirectX")
    rep = {c["class"]: c for c in report.get("classes", [])}
    for cls, m in tiles.items():
        k = normal_convention(m["DetailN"], m["DetailRMH"][..., 2].astype(np.float64) / 255.0)
        if not (0.9 <= k["len_p1"] and k["len_p99"] <= 1.1):
            bad.append(f"{cls}: |n| p1..p99 {k['len_p1']:.3f}..{k['len_p99']:.3f}")
        if k["min_z"] <= 0.0:
            bad.append(f"{cls}: z <= 0")
        if abs(k["mean_x"]) > 0.06 or abs(k["mean_y"]) > 0.06:
            bad.append(f"{cls}: xy mean ({k['mean_x']:.3f}, {k['mean_y']:.3f}) not ~0")
        if k["corr_y"] is not None and not dx_sign_ok(k["corr_x"], k["corr_y"]):
            bad.append(f"{cls}: not DirectX vs its height: corr y {k['corr_y']:.3f}, x {k['corr_x']:.3f}")
        conv = rep.get(cls, {}).get("build", {}).get("convention")
        if conv is not None and (not conv.get("sourceIsDirectX")
                                 or conv.get("meanAbs_DX_G_minus_inverted_GL_G", 1.0) >= 0.01):
            bad.append(f"{cls}: source NormalDX is not the G-inverted NormalGL")
    res.add("normal_dx", not bad and bool(tiles), "; ".join(bad) or "DirectX, unit length, sign checked vs height")


def _fuzz(bc, intensity, tint):
    y = y_of(bc)
    return [intensity * ((1 - tint) + tint * c / y) * y ** 0.5 for c in bc]


def _check_physics(presets, report, res):
    bad = []
    refs = set(presets.get("references", {}))
    f0 = presets.get("referenceF0", {})
    rep = {c["class"]: c for c in report.get("classes", [])}

    def cites(c, block, name):
        for s in (block or {}).get("source", []) if isinstance(block, dict) else []:
            if s not in refs:
                bad.append(f"{c['id']}.{name}: source {s!r} not in references")

    for c in presets.get("classes", []):
        cid = c.get("id")
        if c.get("family") == "passthrough":
            continue
        met = c.get("metallic")
        if met not in (0, 1):
            bad.append(f"{cid}: metallic {met} not in {{0, 1}}")
        if (c.get("family") == "metal") != (met == 1):
            bad.append(f"{cid}: family {c.get('family')} vs metallic {met}")
        sm = c.get("shadingModel")
        if sm not in SHADING_MODELS:
            bad.append(f"{cid}: shadingModel {sm!r}")
        bc = c.get("baseColor", {})
        typ = bc.get("typicalLinear")
        if not (isinstance(typ, list) and len(typ) == 3 and all(0.0 <= float(x) <= 1.0 for x in typ)):
            bad.append(f"{cid}: baseColor.typicalLinear {typ}")
            continue
        for name in ("baseColor", "roughness", "specular", "cloth", "edgeWear", "subsurfaceApprox"):
            cites(c, c.get(name), name)
        if met == 1:
            if c.get("specular") is not None:
                bad.append(f"{cid}: metals take no specular")
            if bc.get("mode") != "preset-f0":
                bad.append(f"{cid}: metal BC mode must be preset-f0")
            if bc.get("oxideFilm"):
                lo, hi = bc.get("luminanceRange", [None, None])
                if lo is None or not (OXIDE_Y[0] <= lo <= y_of(typ) <= hi <= OXIDE_Y[1]):
                    bad.append(f"{cid}: oxide film Y {y_of(typ):.3f} / range {bc.get('luminanceRange')} outside {OXIDE_Y}")
                if not any(s in refs and s != "ART-DIR" for s in bc.get("source", [])):
                    bad.append(f"{cid}: oxide film BC needs a reference source")
            else:
                ref = f0.get(bc.get("referenceF0"), {}).get("linear")
                if ref is None:
                    bad.append(f"{cid}: referenceF0 {bc.get('referenceF0')!r} unknown")
                elif max(abs(a - b) for a, b in zip(typ, ref)) > METAL_F0_TOL:
                    bad.append(f"{cid}: BC {typ} is not F0 {bc.get('referenceF0')} {ref} (tol {METAL_F0_TOL})")
                if y_of(typ) < METAL_MIN_Y:
                    bad.append(f"{cid}: metal BC Y {y_of(typ):.3f} < {METAL_MIN_Y} (not a bare-metal F0)")
            if not (0.0 <= float(bc.get("bakeLuminanceModulation", 0.0)) <= 0.2):
                bad.append(f"{cid}: bakeLuminanceModulation > 0.2 would move BC off F0")
            w = c.get("edgeWear", {})
            if w.get("enabled") and y_of(w.get("wornBaseColorLinear", typ)) < METAL_MIN_Y:
                bad.append(f"{cid}: worn metal BC must be a bare-metal F0")
        else:
            lo, hi = bc.get("luminanceRange", [None, None])
            if lo is None or not (DIEL_Y[0] <= lo < hi <= DIEL_Y[1]):
                bad.append(f"{cid}: dielectric luminanceRange {bc.get('luminanceRange')} outside {DIEL_Y}")
            elif not (lo - 1e-6 <= y_of(typ) <= hi + 1e-6):
                bad.append(f"{cid}: typical BC Y {y_of(typ):.3f} outside its range")
            if float(bc.get("maxChannel", 1.0)) > DIEL_MAX_CHANNEL or max(typ) > DIEL_MAX_CHANNEL:
                bad.append(f"{cid}: dielectric channel above {DIEL_MAX_CHANNEL}")
            sp = c.get("specular") or {}
            v, f = sp.get("value"), sp.get("f0")
            if v is None or f is None or abs(0.08 * float(v) - float(f)) > 0.002 or not (DIEL_F0[0] <= f <= DIEL_F0[1]):
                bad.append(f"{cid}: specular {v} / F0 {f} inconsistent or outside {DIEL_F0}")
        r = c.get("roughness", {})
        rng = r.get("range", [None, None])
        try:
            if not (0.0 <= rng[0] <= r["typical"] <= rng[1] <= 1.0 and 0.0 <= r["variation"] <= 0.5):
                bad.append(f"{cid}: roughness {r.get('typical')} / {rng} / variation {r.get('variation')}")
        except (TypeError, KeyError):
            bad.append(f"{cid}: roughness block incomplete")
            continue
        build = rep.get(cid, {}).get("build", {})
        if r.get("sourceKind") == "measured":
            if build.get("roughnessAmplitude") is None:
                bad.append(f"{cid}: measured roughness but the report has no measurement")
            else:
                if abs(r["variation"] - build["roughnessAmplitude"]) > 0.002:
                    bad.append(f"{cid}: variation {r['variation']} != measured {build['roughnessAmplitude']}")
                if abs(r["typical"] - build["roughnessMedian"]) > 0.01:
                    bad.append(f"{cid}: typical {r['typical']} != measured median {build['roughnessMedian']}")
        cl = c.get("cloth")
        if sm == "Cloth":
            if not cl:
                bad.append(f"{cid}: Cloth shading model without a cloth block")
            else:
                sc = cl.get("sheenColor", {})
                if not (0.0 < float(cl.get("clothAmount", 0)) <= 1.0 and 0.0 <= float(cl.get("sheenRoughness", -1)) <= 1.0):
                    bad.append(f"{cid}: clothAmount / sheenRoughness out of range")
                exp = _fuzz(typ, float(sc.get("intensity", 0)), float(sc.get("tint", 0)))
                got = sc.get("typicalLinear") or [9, 9, 9]
                if max(abs(a - b) for a, b in zip(exp, got)) > 0.002 or max(got) > 1.0:
                    bad.append(f"{cid}: sheenColor.typicalLinear {got} != formula {[round(x, 4) for x in exp]}")
        elif cl:
            bad.append(f"{cid}: cloth block on a {sm} class")
        d = c.get("detail", {})
        tpm, ws = d.get("tilesPerMeter"), d.get("tileWorldSizeM")
        if not (tpm and ws and tpm > 0 and abs(tpm * ws - 1.0) <= 0.03):
            bad.append(f"{cid}: tilesPerMeter {tpm} vs tileWorldSizeM {ws}")
        if not (0.0 < float(d.get("normalStrength", 0)) <= 2.0):
            bad.append(f"{cid}: normalStrength")
        if cid == "skin" and ("subsurfaceApprox" not in c or sm != "DefaultLit"):
            bad.append("skin: DefaultLit with subsurfaceApprox required (no Subsurface model)")
    res.add("preset_physics", not bad, "; ".join(bad) or
            "metallic binary, metal BC = F0 (oxide band referenced), dielectric BC/F0 in range, "
            "measured roughness = report, cloth sheen = formula")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate the UM material library v1")
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--verify-raw", action="store_true", help="also hash cc0-raw zips/files when present")
    ap.add_argument("--json", help="write the results to this file")
    a = ap.parse_args(argv)
    res = validate(Path(a.root), a.verify_raw)
    for r in res:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['check']:15s} {r['detail']}")
    ok = all(r["ok"] for r in res)
    if a.json:
        Path(a.json).write_text(json.dumps({"ok": ok, "results": res}, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
