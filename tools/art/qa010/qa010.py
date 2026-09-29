#!/usr/bin/env python3
"""QA-010 evidence tools. Read-only on inputs; writes only to paths you pass.

  python tools/art/qa010/qa010.py derive  FRAME_OR_DIR... --out DIR
  python tools/art/qa010/qa010.py luma    FRAME... [--region NAME=KIND:ARGS ...] [--trace T]
  python tools/art/qa010/qa010.py c9      FRAME --game SPEC --decor SPEC [--trace T] [--accept-proxy]
  python tools/art/qa010/qa010.py plate   --trace T [--shot NAME|#N] [--frame PNG] [--plate-bbox ..] [--reachable ..]
  python tools/art/qa010/qa010.py icon    FRAME (--bbox x0,y0,x1,y1 | --trace T) [--mask PNG]
  python tools/art/qa010/qa010.py project --trace T [--shot NAME|#N | --all]
  python tools/art/qa010/qa010.py checklist --config CFG.json --out-md X.md --out-json X.json
  python tools/art/qa010/qa010.py render  --trace T [--shot NAME] [--frame PNG] [--reference R]

Exit codes: 0 ok/pass, 1 measured fail, 2 usage or input error,
3 insufficient input / требуется новая трасса / c9 on a proxy layer mask
(without --accept-proxy). render: 0 on the W4-A render reference, 1 off it,
3 no RENDER fingerprint in the SHOT block (every pre-W4 frame).
Formats, thresholds (all «предложено») and sources: docs/art-pipeline/qa010/README.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from qa010lib import VERSION  # noqa: E402
from qa010lib.geometry import parse_bbox  # noqa: E402
from qa010lib.trace import TraceError, parse_trace  # noqa: E402

DEFAULT_THRESHOLDS = HERE / "thresholds.proposed.json"
EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_INSUFFICIENT = 0, 1, 2, 3
DERIVED_SUFFIXES = (".gray.png", ".deuteranopia.png")


def load_thresholds(path: Path | None) -> dict:
    p = path or DEFAULT_THRESHOLDS
    return json.loads(Path(p).read_text(encoding="utf-8"))


def emit(result: dict, json_path: str | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if json_path:
        out = Path(json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)


def sha256_path(path: Path) -> str:
    """stdlib hash (plate/project must run without numpy/Pillow)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_info(path: Path, rgb) -> dict:
    return {"path": str(path).replace("\\", "/"), "sha256": sha256_path(path),
            "size": [int(rgb.shape[1]), int(rgb.shape[0])]}


def frame_ref(path: Path, shot) -> dict:
    """Frame a trace-only result (plate/project) is bound to: the checklist
    matches it against frames.K*.path; matches_shot says whether the SHOT
    block used for the geometry is that frame's block (by PNG name)."""
    return {"path": str(path).replace("\\", "/"), "sha256": sha256_path(path) if path.is_file() else None,
            "matches_shot": shot.name.lower() == path.name.lower()}


def projection_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--trace", help="client trace log (S08/S09 FS08Trace format)")
    p.add_argument("--shot", help="SHOT block: PNG basename from 'SHOT requested', or #N (0-based)")
    p.add_argument("--hfov", type=float, help="horizontal FOV deg (default from thresholds: 35)")
    p.add_argument("--tolerance-px", type=float, help="max projection residual vs SHOT fighter pairs")
    p.add_argument("--camera-mode", choices=("auto", "trace", "fit"),
                   help="trace camera as printed, fit position on fighter pairs, or auto")


def resolve_projection(args, th: dict, frame_name: str | None = None):
    """-> (trace, shot, ProjectionReport) or raises TraceError."""
    from qa010lib.projection import build_projection
    trace = parse_trace(Path(args.trace))
    shot = trace.find_shot(args.shot, frame_name)
    pj = th["projection"]
    proj = build_projection(shot, args.hfov or pj["hfov_deg"], args.tolerance_px or pj["tolerance_px"],
                            args.camera_mode or pj["camera_mode"])
    return trace, shot, proj


def trace_context(args, th: dict, frame_name: str | None):
    from qa010lib.regions import TraceContext
    if not getattr(args, "trace", None):
        return None, None
    trace, shot, proj = resolve_projection(args, th, frame_name)
    if shot.board is None:
        raise TraceError(f"{args.trace}: no BOARD line before SHOT block {shot.name}")
    ctx = TraceContext(board=shot.board, camera=proj.camera, projection=proj.to_dict())
    return ctx, {"trace": str(args.trace).replace("\\", "/"), "shot": shot.name, "shot_index": shot.index,
                 "shot_matches_frame": bool(frame_name) and shot.name.lower() == frame_name.lower(),
                 "projection": proj.to_dict()}


# ------------------------------------------------------------------ derive --

def iter_frames(inputs: list[str]):
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            for f in sorted(p.rglob("*.png")):
                if not f.name.endswith(DERIVED_SUFFIXES):
                    yield f, p
        elif p.is_file():
            yield p, p.parent
        else:
            raise FileNotFoundError(item)


def unique_output_stems(pairs) -> list[tuple[Path, Path]]:
    """Map (src, root) -> (src, relative output stem) without collisions.
    Evidence names repeat across runs (phase2-board-host-1920x1080.png in every
    run dir), so colliding stems are extended with parent directory names
    until unique; a remaining collision (same file twice) is dropped."""
    items = []
    seen_src = set()
    for src, root in pairs:
        key = src.resolve()
        if key in seen_src:
            continue
        seen_src.add(key)
        if src.is_relative_to(root):
            rel, above = src.relative_to(root), root.resolve()
        else:
            rel, above = Path(src.name), key.parent
        items.append([src, rel.with_suffix(""), above])  # above = next dir to prepend on collision
    for _ in range(64):
        counts: dict[str, int] = {}
        for it in items:
            counts[str(it[1]).lower()] = counts.get(str(it[1]).lower(), 0) + 1
        dups = [it for it in items if counts[str(it[1]).lower()] > 1]
        if not dups:
            break
        for it in dups:
            parent = it[2]
            if parent.name:
                it[1] = Path(parent.name) / it[1]
                it[2] = parent.parent
    else:
        raise ValueError("could not derive unique output names")
    return [(src, stem) for src, stem, _ in items]


def cmd_derive(args) -> int:
    from qa010lib import color
    from qa010lib.imageio import load_rgb, save_rgb, sha256_file
    out_dir = Path(args.out)
    entries = []
    for src, stem in unique_output_stems(iter_frames(args.inputs)):
        gray_p = out_dir / (str(stem) + ".gray.png")
        deut_p = out_dir / (str(stem) + ".deuteranopia.png")
        for o in (gray_p, deut_p):
            if o.resolve() == src.resolve():
                raise SystemExit(f"refusing to overwrite input {src}")
        rgb = load_rgb(src)
        save_rgb(gray_p, color.grayscale(rgb))
        save_rgb(deut_p, color.deuteranopia(rgb))
        entries.append({
            "input": str(src).replace("\\", "/"), "input_sha256": sha256_file(src),
            "size": [int(rgb.shape[1]), int(rgb.shape[0])],
            "gray": {"path": str(gray_p).replace("\\", "/"), "sha256": sha256_file(gray_p)},
            "deuteranopia": {"path": str(deut_p).replace("\\", "/"), "sha256": sha256_file(deut_p)},
        })
    if not entries:
        print("no PNG inputs found", file=sys.stderr)
        return EXIT_USAGE
    manifest = {
        "command": "derive", "tool": VERSION,
        "method": {
            "gray": "Rec.709 luma Y' = 0.2126R'+0.7152G'+0.0722B' on 8-bit sRGB values, round half up, replicated to RGB",
            "deuteranopia": "Machado, Oliveira, Fernandes 2009, severity 1.0; IEC 61966-2-1 sRGB decode -> "
                            "matrix on linear RGB -> clip [0,1] -> sRGB encode -> round half up",
            "matrix": color.MACHADO_DEUTERANOPIA_1_0.tolist(),
            "alpha": "ignored (not composited)",
        },
        "entries": entries,
    }
    man_path = Path(args.json) if args.json else out_dir / "qa010-derive-manifest.json"
    emit(manifest, str(man_path))
    return EXIT_OK


# -------------------------------------------------------------------- luma --

def build_regions(specs, size, ctx, base_dir=None):
    from qa010lib.regions import parse_region
    return [parse_region(s, size, ctx, base_dir) for s in specs or []]


def cmd_luma(args) -> int:
    from qa010lib.imageio import load_rgb
    from qa010lib.regions import luma_stats
    th = load_thresholds(args.thresholds)
    stride = args.stride or th["luma"]["stride"]
    frames = []
    for f in args.frames:
        p = Path(f)
        rgb = load_rgb(p)
        size = (rgb.shape[1], rgb.shape[0])
        ctx, tmeta = trace_context(args, th, p.name) if args.trace else (None, None)
        specs = list(args.region or [])
        if args.regions_json:
            specs += [f"{k}={v}" for k, v in json.loads(Path(args.regions_json).read_text(encoding="utf-8")).items()]
        regions = build_regions(specs, size, ctx)
        entry = {**frame_info(p, rgb), "stats": luma_stats(rgb, None, stride), "regions": {}}
        if tmeta:
            entry["trace"] = tmeta
        for r in regions:
            entry["regions"][r.name] = {"spec": r.spec, "proxy": r.proxy, "note": r.note,
                                        "stats": luma_stats(rgb, r.mask, stride)}
        frames.append(entry)
    emit({"command": "luma", "tool": VERSION, "stride": stride,
          "definition": "Rec.709 luma on 8-bit sRGB; percentile = sorted[floor(n*q)] as tools/s05/s05_frame_measure.ps1",
          "frames": frames}, args.json)
    return EXIT_OK


# ---------------------------------------------------------------------- c9 --

def union_mask(regions, shape):
    import numpy as np
    m = np.zeros(shape, dtype=bool)
    for r in regions:
        m |= r.mask
    return m


def cmd_c9(args) -> int:
    from qa010lib.checks import C9Params, check_c9
    from qa010lib.imageio import load_rgb, save_mask
    from qa010lib.layers import proxy_regions
    tha = load_thresholds(args.thresholds)
    th = tha["c9"]
    p = Path(args.frame)
    rgb = load_rgb(p)
    size = (rgb.shape[1], rgb.shape[0])
    ctx, tmeta = trace_context(args, tha, p.name) if args.trace else (None, None)
    game = build_regions(args.game, size, ctx)
    decor = build_regions(args.decor, size, ctx)
    excl = build_regions(args.exclude, size, ctx)
    if not game or not decor:
        print("c9 needs at least one --game and one --decor region", file=sys.stderr)
        return EXIT_USAGE
    lo, hi = th["ev_range_proposed"]
    if args.ev_range:
        lo, hi = (float(v) for v in args.ev_range.split(","))
    params = C9Params(
        ev_min_normative=th["ev_min_normative"] if args.ev_min is None else args.ev_min,
        ev_range_proposed=(lo, hi),
        chroma_min_delta_proposed=th["chroma_min_delta_proposed"] if args.chroma_min_delta is None else args.chroma_min_delta,
        statistic=args.statistic or th["statistic"],
        min_pixels=args.min_pixels or th["min_pixels"],
        allow_overlap=args.allow_overlap)
    shape = rgb.shape[:2]
    gm, dm = union_mask(game, shape), union_mask(decor, shape)
    em = union_mask(excl, shape) if excl else None
    proxies = proxy_regions([("game", r.spec, r.kind, r.proxy, r.note) for r in game]
                            + [("decor", r.spec, r.kind, r.proxy, r.note) for r in decor])
    proxy_specs = {p["spec"] for p in proxies}
    res = check_c9(rgb, gm, dm, params, em, proxies)
    if args.save_masks:
        d = Path(args.save_masks)
        save_mask(d / f"{p.stem}.c9-game.png", gm)
        save_mask(d / f"{p.stem}.c9-decor.png", dm)
    out = {"command": "c9", "tool": VERSION, "frame": frame_info(p, rgb),
           "interpretation": ("С-9 по 17 AD-AC-33 (свежее 03): НОРМАТИВ — игровой слой «ярче» декора "
                              "(ΔEV > 0 по относительной яркости в линейном свете); диапазон +0.3..+0.7 EV и "
                              "«насыщеннее» (ΔC*ab > 0) — ПРЕДЛОЖЕНИЕ 03 С-9. Декор — слой L3 (фасады, фонарь, "
                              "ящики; 03 §4.1); маски слоёв — вход (stencil, 17 §11.10, или ручная маска). "
                              "trace-ring (поднос L4), trace-cells как декор и frame — прокси: результат "
                              "«proxy», не норматив."),
           "game_region": [{"spec": r.spec, "kind": r.kind, "proxy": r.spec in proxy_specs, "note": r.note}
                           for r in game],
           "decor_region": {"spec": "; ".join(r.spec for r in decor), "kinds": [r.kind for r in decor],
                            "proxy": any(r.spec in proxy_specs for r in decor),
                            "note": "; ".join(r.note for r in decor if r.note)},
           "exclude_region": [r.spec for r in excl], **({"trace": tmeta} if tmeta else {}), **res}
    if res["status"] == "measured" and res["layer_basis"]["proxy"]:
        out["proxy_accepted_by_flag"] = bool(args.accept_proxy)
    emit(out, args.json)
    if res["status"] != "measured":
        return EXIT_INSUFFICIENT
    if res["layer_basis"]["proxy"]:
        specs = ", ".join(sorted(proxy_specs))
        if not args.accept_proxy:
            print(f"qa010 c9: proxy layer mask ({specs}): no normative С-9 result (result_normative=proxy); "
                  "нужна stencil- или ручная маска L3. --accept-proxy gates the exit code on the proxy "
                  "measurement (still not normative).", file=sys.stderr)
            return EXIT_INSUFFICIENT
        norm, prop = res["result_on_proxy"]["normative"], res["result_on_proxy"]["proposed"]
    else:
        norm, prop = res["result_normative"], res["result_proposed"]
    return EXIT_OK if norm == "pass" and (not args.gate_proposed or prop == "pass") else EXIT_FAIL


# ------------------------------------------------------------------- plate --

def parse_cells_arg(text: str):
    cells = []
    for part in text.replace(" ", "").split(";"):
        if part:
            a, b = part.strip("()").split(",")
            cells.append((int(a), int(b)))
    return cells


def cmd_plate(args) -> int:
    from qa010lib.plate import PlateParams, check_plate
    th = load_thresholds(args.thresholds)
    tp = th["plate"]
    frame_name = Path(args.frame).name if args.frame else None
    trace, shot, proj = resolve_projection(args, th, frame_name)
    params = PlateParams(
        max_overlap_fraction=tp["max_overlap_fraction"] if args.max_overlap_fraction is None else args.max_overlap_fraction,
        overlap_epsilon_px2=tp["overlap_epsilon_px2"], cells=args.cells)
    plate_bbox = parse_bbox(args.plate_bbox) if args.plate_bbox else None
    reachable = parse_cells_arg(args.reachable) if args.reachable else None
    res = check_plate(shot, proj, params, plate_bbox, reachable)
    out = {"command": "plate", "tool": VERSION, "trace": str(args.trace).replace("\\", "/"),
           **({"frame": frame_ref(Path(args.frame), shot)} if args.frame else {}), **res}
    if args.overlay and args.frame and res.get("status") in ("measured",):
        from qa010lib.overlay import draw_plate_overlay
        draw_plate_overlay(Path(args.frame), Path(args.overlay), shot, proj, res)
        out["overlay"] = str(args.overlay).replace("\\", "/")
    emit(out, args.json)
    st = res.get("status")
    if st == "measured":
        return EXIT_OK if res["result"] == "pass" else EXIT_FAIL
    return EXIT_INSUFFICIENT


# -------------------------------------------------------------------- icon --

def cmd_icon(args) -> int:
    from qa010lib.checks import IconParams, check_icon
    from qa010lib.imageio import load_mask, load_rgb
    th = load_thresholds(args.thresholds)
    ti = th["icon"]
    p = Path(args.frame)
    rgb = load_rgb(p)
    bbox_src = "cli"
    tmeta = None
    if args.bbox:
        bb = parse_bbox(args.bbox)
    elif args.trace:
        trace, shot, proj = resolve_projection(args, th, p.name)
        tmeta = {"trace": str(args.trace).replace("\\", "/"), "shot": shot.name}
        if shot.icon is None:
            emit({"command": "icon", "tool": VERSION, "frame": frame_info(p, rgb), "trace": tmeta,
                  "status": "requires_new_trace",
                  "reason": "no 'SHOT icon' line for this shot; требуется новая трасса или --bbox",
                  "required_lines": {"icon": "SHOT icon fighter=<fighterId> bbox=(x0,y0,x1,y1)"}}, args.json)
            return EXIT_INSUFFICIENT
        bb = shot.icon.value["bbox"]
        vw, vh = shot.viewport
        sx, sy = rgb.shape[1] / vw, rgb.shape[0] / vh
        bb = (bb[0] * sx, bb[1] * sy, bb[2] * sx, bb[3] * sy)
        bbox_src = f"trace:{shot.icon.source}@line{shot.icon.line_no}"
    else:
        print("icon needs --bbox or --trace with a 'SHOT icon' line", file=sys.stderr)
        return EXIT_USAGE
    ibox = (int(round(bb[0])), int(round(bb[1])), int(round(bb[2])), int(round(bb[3])))
    if args.mask_texture:
        # W5b-R icon rev 3: native size only, masks from the drawn texture, presence guard
        import hashlib
        import numpy as np
        from PIL import Image
        from qa010lib.checks import check_icon_token
        mt, tt = Path(args.mask_texture), Path(args.token_texture or "")
        if not tt.is_file():
            print("--mask-texture needs --token-texture", file=sys.stderr)
            return EXIT_USAGE
        with Image.open(mt) as im:
            glyph_alpha = np.asarray(im.convert("RGBA"), dtype=np.float64)[..., 3] / 255.0
        with Image.open(tt) as im:
            token = np.asarray(im.convert("RGBA"), dtype=np.uint8)
        res = check_icon_token(rgb, ibox, glyph_alpha, token, mask_alpha=args.mask_alpha,
                               min_contrast=ti["min_contrast_ratio"] if args.min_contrast is None else args.min_contrast)
        sha = lambda q: hashlib.sha256(q.read_bytes()).hexdigest()  # noqa: E731
        out = {"command": "icon", "method": "rev 3 (W5b-R): token masks from the drawn texture, native size",
               "tool": VERSION, "frame": frame_info(p, rgb), "bbox_source": bbox_src,
               **({"trace": tmeta} if tmeta else {}),
               "mask_texture": {"path": str(mt).replace("\\", "/"), "sha256": sha(mt), "alpha": args.mask_alpha},
               "token_texture": {"path": str(tt).replace("\\", "/"), "sha256": sha(tt)}, **res}
        emit(out, args.json)
        if res["status"] == "insufficient_input":
            return EXIT_INSUFFICIENT
        if res["status"] != "measured":
            return EXIT_INSUFFICIENT
        return EXIT_OK if res["result"] == "pass" else EXIT_FAIL
    sizes = tuple(int(s) for s in args.sizes.split(",")) if args.sizes else tuple(ti["sizes_px"])
    params = IconParams(
        sizes=sizes,
        min_contrast_ratio=ti["min_contrast_ratio"] if args.min_contrast is None else args.min_contrast,
        min_luma_delta=ti["min_luma_delta"] if args.min_luma_delta is None else args.min_luma_delta,
        fg_coverage=ti["fg_coverage"], bg_coverage=ti["bg_coverage"], ring_frac=ti["ring_frac"],
        ring_min_px=ti["ring_min_px"], min_fg_fraction=ti["min_fg_fraction"],
        background=args.background or ti["background"])
    mask = None
    if args.mask:
        mask = load_mask(Path(args.mask))
    res = check_icon(rgb, ibox, params, mask)
    out = {"command": "icon", "tool": VERSION, "frame": frame_info(p, rgb), "bbox_source": bbox_src,
           **({"trace": tmeta} if tmeta else {}), **res}
    emit(out, args.json)
    if res["status"] != "measured":
        return EXIT_INSUFFICIENT
    return EXIT_OK if res["result"] == "pass" else EXIT_FAIL


# ----------------------------------------------------------------- project --

def cmd_project(args) -> int:
    from qa010lib.projection import build_projection, project_cell
    th = load_thresholds(args.thresholds)
    pj = th["projection"]
    hfov = args.hfov or pj["hfov_deg"]
    tol = args.tolerance_px or pj["tolerance_px"]
    mode = args.camera_mode or pj["camera_mode"]
    trace = parse_trace(Path(args.trace))
    if args.all:
        shots = trace.shots
    else:
        shots = [trace.find_shot(args.shot, Path(args.frame).name if args.frame else None)]
    out_shots = []
    worst = 0.0
    all_ok = True
    for s in shots:
        proj = build_projection(s, hfov, tol, mode)
        entry = {"shot": s.name, "shot_index": s.index, "line": s.line_no, "projection": proj.to_dict()}
        if s.focus is not None:
            entry["zoom_source"] = {**s.focus, "note": "зум задан 'ARTPREVIEW camera focus' (флаг -ArtPreviewFocusZoom): "
                                    "по E4 кадр помечается «тестовый флаг», пока нет трассы шагов колеса"}
        if proj.ok and s.board is not None:
            full = partial = off = 0
            cells = []
            for y in range(s.board.height):
                for x in range(s.board.width):
                    pc = project_cell(proj.camera, s.board, x, y)
                    frac = pc["visible_area"] / pc["area"] if pc["area"] else 0.0
                    full += frac >= 0.999
                    partial += 0 < frac < 0.999
                    off += frac <= 0
                    if not args.all:
                        cells.append({"cell": pc["cell"], "area_px2": round(pc["area"], 1),
                                      "visible_fraction": round(frac, 4),
                                      "quad": [[round(a, 2), round(b, 2)] for a, b in (pc["quad"] or [])]})
            entry["cells_in_frame"] = {"total": s.board.width * s.board.height, "full": full,
                                       "partial": partial, "offscreen": off}
            if cells:
                entry["cells"] = cells
            worst = max(worst, proj.residual_max_used or 0.0)
        elif s.camera_valid():
            all_ok = False
        out_shots.append(entry)
    fref = {"frame": frame_ref(Path(args.frame), shots[0])} if args.frame and not args.all else {}
    emit({"command": "project", "tool": VERSION, "trace": str(args.trace).replace("\\", "/"), **fref,
          "board": None if trace.board is None else {
              "width": trace.board.width, "height": trace.board.height,
              "c00": trace.board.c00, "cmax": trace.board.cmax, "neighbor_dist": trace.board.neighbor_dist,
              "consistency_errors": trace.board.consistency_errors()},
          "shots": out_shots, "worst_residual_px_valid_shots": round(worst, 3)}, args.json)
    return EXIT_OK if all_ok else EXIT_INSUFFICIENT


# --------------------------------------------------------------- checklist --

def cmd_render(args) -> int:
    """W4-A RENDER fingerprint of one SHOT against docs/art-pipeline/render-reference.json."""
    art = HERE.parent
    if str(art) not in sys.path:
        sys.path.insert(0, str(art))
    import render_fingerprint as RF
    ref = RF.load_reference(Path(args.reference) if args.reference else None)
    shot_name = args.shot or (Path(args.frame).name if args.frame else None)
    lines = RF.read_lines(Path(args.trace))
    block = RF.fingerprint_for_shot(lines, shot_name)
    fp = block["render"] if block else None
    ok, reasons = RF.check(fp, ref)
    out = {"command": "render", "tool": VERSION, "trace": str(args.trace).replace("\\", "/"),
           "shot": (block or {}).get("shot") or shot_name, "blockFound": block is not None,
           "fingerprint": fp, "reference": ok, "reasons": reasons,
           "status": "reference" if ok else ("missing" if fp is None else "off-reference"),
           "referenceFile": "docs/art-pipeline/render-reference.json", "referenceRevision": ref.get("revision")}
    if args.frame:
        fr = Path(args.frame)
        out["frame"] = {"path": str(fr).replace("\\", "/"), "sha256": sha256_path(fr) if fr.is_file() else None,
                        "matches_shot": (out["shot"] or "").lower() == fr.name.lower()}
    emit(out, args.json)
    if fp is None:
        return EXIT_INSUFFICIENT
    return EXIT_OK if ok else EXIT_FAIL


def cmd_checklist(args) -> int:
    from qa010lib.checklist import build_checklist, render_markdown
    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cl = build_checklist(cfg, cfg_path.parent)
    md = render_markdown(cl)
    if args.out_md:
        Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_md).write_text(md, encoding="utf-8", newline="\n")
    emit(cl, args.out_json)
    return EXIT_OK


# -------------------------------------------------------------------- main --

def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # cp1251 console/pipe on Windows otherwise
    ap = argparse.ArgumentParser(prog="qa010", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--thresholds", type=Path, help=f"thresholds JSON (default {DEFAULT_THRESHOLDS.name})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("derive", help="grayscale + deuteranopia derivatives (batch over files/dirs)")
    d.add_argument("inputs", nargs="+")
    d.add_argument("--out", required=True, help="output directory (inputs are never modified)")
    d.add_argument("--json", help="manifest path (default OUT/qa010-derive-manifest.json)")
    d.set_defaults(func=cmd_derive)

    lu = sub.add_parser("luma", help="Rec.709 luma p50/p90 per frame and per region")
    lu.add_argument("frames", nargs="+")
    lu.add_argument("--region", action="append", help="NAME=KIND:ARGS (repeatable)")
    lu.add_argument("--regions-json", help="JSON {name: 'KIND:ARGS'}")
    lu.add_argument("--stride", type=int)
    lu.add_argument("--json")
    projection_args(lu)
    lu.set_defaults(func=cmd_luma)

    c = sub.add_parser("c9", help="С-9: game layer vs decor layer (EV + chroma)")
    c.add_argument("frame")
    c.add_argument("--game", action="append", required=True, help="region spec (repeatable, union)")
    c.add_argument("--decor", action="append", required=True, help="region spec (repeatable, union)")
    c.add_argument("--exclude", action="append", help="region spec removed from both layers (e.g. HUD)")
    c.add_argument("--ev-min", type=float)
    c.add_argument("--ev-range", help="lo,hi (proposed band)")
    c.add_argument("--chroma-min-delta", type=float)
    c.add_argument("--statistic", choices=("mean", "median"))
    c.add_argument("--min-pixels", type=int)
    c.add_argument("--allow-overlap", action="store_true")
    c.add_argument("--gate-proposed", action="store_true", help="exit 1 also when proposed band/chroma fail")
    c.add_argument("--accept-proxy", action="store_true",
                   help="with a proxy layer mask, exit 0/1 from the proxy measurement instead of 3 "
                        "(JSON stays result_normative=proxy; never a normative result)")
    c.add_argument("--save-masks", help="directory for the effective game/decor masks (debug)")
    c.add_argument("--json")
    projection_args(c)
    c.set_defaults(func=cmd_c9)

    pl = sub.add_parser("plate", help="K-2: HUD plate bbox vs projected reachable cells")
    projection_args(pl)
    pl.add_argument("--frame", help="PNG (for SHOT matching by name and --overlay)")
    pl.add_argument("--plate-bbox", help="x0,y0,x1,y1 in traced viewport pixels (overrides trace)")
    pl.add_argument("--reachable", help="x,y;x,y cells (overrides trace)")
    pl.add_argument("--cells", choices=("reachable", "all"), default="reachable")
    pl.add_argument("--max-overlap-fraction", type=float)
    pl.add_argument("--overlay", help="write a debug overlay PNG (needs --frame)")
    pl.add_argument("--json")
    pl.set_defaults(func=cmd_plate)

    ic = sub.add_parser("icon", help="combat icon contrast at 24/32/48 px")
    ic.add_argument("frame")
    ic.add_argument("--bbox", help="x0,y0,x1,y1 frame pixels (half-open)")
    ic.add_argument("--mask", help="icon mask PNG (frame-sized or bbox-sized); default auto Otsu")
    ic.add_argument("--mask-texture", help="W5b-R icon rev 3: glyph mask PNG N x N of the drawn token (alpha = glyph)")
    ic.add_argument("--mask-alpha", type=float, default=0.5, help="glyph = mask alpha >= this (rev 3)")
    ic.add_argument("--token-texture", help="rev 3: the token PNG N x N that is drawn (shape, rim, body, guard)")
    ic.add_argument("--sizes", help="comma list, default 24,32,48")
    ic.add_argument("--min-contrast", type=float)
    ic.add_argument("--min-luma-delta", type=float)
    ic.add_argument("--background", choices=("bbox", "ring"))
    ic.add_argument("--json")
    projection_args(ic)
    ic.set_defaults(func=cmd_icon)

    pr = sub.add_parser("project", help="validate the camera model and list projected cells")
    projection_args(pr)
    pr.add_argument("--frame")
    pr.add_argument("--all", action="store_true", help="summarise every SHOT block")
    pr.add_argument("--json")
    pr.set_defaults(func=cmd_project)

    rd = sub.add_parser("render", help="W4-A RENDER fingerprint of a SHOT vs the render reference")
    rd.add_argument("--trace", required=True)
    rd.add_argument("--shot", help="PNG basename from 'SHOT requested' (default: --frame name / single block)")
    rd.add_argument("--frame", help="PNG the result is bound to (checklist frames.K*.path)")
    rd.add_argument("--reference", help="reference JSON (default docs/art-pipeline/render-reference.json)")
    rd.add_argument("--json")
    rd.set_defaults(func=cmd_render)

    ck = sub.add_parser("checklist", help="QA-010 checklist markdown + json")
    ck.add_argument("--config", required=True)
    ck.add_argument("--out-md")
    ck.add_argument("--out-json")
    ck.set_defaults(func=cmd_checklist)

    args = ap.parse_args(argv)
    if args.cmd in ("plate", "project") and not args.trace:
        ap.error(f"{args.cmd} needs --trace")
    try:
        return args.func(args)
    except (TraceError, ValueError, FileNotFoundError) as exc:
        print(f"qa010 {args.cmd}: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
