"""Concept framing of the orthographic preview / look-dev cameras (no bpy; used by st_preview, st_lookdev and lookdev).

The ortho views (front / side / back) are framed like the concept views, so the class-ID pass of ld_preview lies pixel
over pixel on the concept (lookdev.run_measure samples the concept under the render masks) and the compare sheets put
concept and render side by side at the same scale.

Frame config (optional; H2 profile `preview.frame`, look-dev profile `frame`):
  absent            the Medusa H2 canon: 1021 x 1540 px, figure top at y 2 %, base bottom at y 96.8 %, base centre
                    at x 45 %, side view = the figure's LEFT (camera on +X). Old profiles (Medusa) keep their bytes.
  {"checks_report": "<repo path of checks-report.json of tools/art/concept/check_concept_views.py>",
   "side": "left" | "right"}
                    every view from the concept itself: px = measurements.<view>.size, top / bottom / base centre =
                    measurements.<view>.mask.{top_pct, bottom_pct, base_center_x_pct} / 100. This is the frame of a new
                    character (any concept size and aspect, e.g. 3:4 of stage 1).
  {"px": [W, H], "top": t, "bottom": b, "base_x": x, "side": ..., "views": {"<view>": {overrides}}}
                    explicit numbers (shares of the frame), optional per-view overrides.
`side` = SIDE_VIEW of the asset card: which side of the figure the concept `side` view shows. "left": camera on +X
(the figure faces -Y, its left hand is on +X); "right": camera on -X.

Camera: orthographic, sensor fit VERTICAL, ortho_scale = figure_top_m / (bottom - top) (the figure from the base bottom
z = 0 to figure_top_m spans the measured share of the frame height), centre z and the lateral shift that puts the base
centre (x = 0 of the model) at base_x of the frame width."""

import json
from pathlib import Path

VIEWS = ("front", "side", "back")
SIDES = ("left", "right")
DEFAULT = {"px": [1021, 1540], "top": 0.02, "bottom": 0.968, "base_x": 0.45}
DEFAULT_SIDE = "left"


class FrameError(ValueError):
    pass


def _check(view, fr):
    w, h = fr["px"]
    if int(w) <= 0 or int(h) <= 0:
        raise FrameError("frame %s: px must be positive, got %s" % (view, fr["px"]))
    if not (0.0 <= fr["top"] < fr["bottom"] <= 1.0):
        raise FrameError("frame %s: need 0 <= top < bottom <= 1, got top %s bottom %s" % (view, fr["top"], fr["bottom"]))
    if not (0.0 < fr["base_x"] < 1.0):
        raise FrameError("frame %s: base_x must be inside (0, 1), got %s" % (view, fr["base_x"]))
    return {"px": [int(w), int(h)], "top": float(fr["top"]), "bottom": float(fr["bottom"]), "base_x": float(fr["base_x"])}


def resolve(cfg, repo=None, views=VIEWS):
    """-> ({view: {"px": [W, H], "top", "bottom", "base_x"}}, side, source). See the module doc for cfg."""
    if cfg is None:
        return {v: dict(DEFAULT, px=list(DEFAULT["px"])) for v in views}, DEFAULT_SIDE, "default (Medusa H2 canon)"
    if not isinstance(cfg, dict):
        raise FrameError("frame config must be an object, got %r" % (cfg,))
    side = cfg.get("side", DEFAULT_SIDE)
    if side not in SIDES:
        raise FrameError("frame.side must be left or right, got %r" % (side,))
    out = {}
    if "checks_report" in cfg:
        path = Path(cfg["checks_report"])
        if not path.is_absolute():
            if repo is None:
                raise FrameError("frame.checks_report is relative and no repo root was given")
            path = Path(repo) / path
        rep = json.loads(path.read_text(encoding="utf-8"))
        if rep.get("schema") != "unmatched.concept-checks/1":
            raise FrameError("%s: schema must be unmatched.concept-checks/1" % path)
        meas = rep.get("measurements") or {}
        for v in views:
            if v not in meas:
                raise FrameError("%s: no measurements for view %s (views %s)" % (path, v, sorted(meas)))
            m = meas[v]
            mk = m.get("mask") or {}
            try:
                fr = {"px": list(m["size"]), "top": mk["top_pct"] / 100.0, "bottom": mk["bottom_pct"] / 100.0,
                      "base_x": mk["base_center_x_pct"] / 100.0}
            except KeyError as exc:
                raise FrameError("%s: view %s has no %s (needs size and mask.top_pct / bottom_pct / "
                                 "base_center_x_pct)" % (path, v, exc)) from exc
            out[v] = _check(v, fr)
        return out, side, "checks_report %s" % cfg["checks_report"]
    base = {k: cfg.get(k, DEFAULT[k]) for k in DEFAULT}
    per = cfg.get("views") or {}
    for v in views:
        fr = dict(base)
        fr.update({k: per.get(v, {})[k] for k in DEFAULT if k in per.get(v, {})})
        out[v] = _check(v, fr)
    return out, side, "explicit"


def ortho_camera(frame, figure_top_m, view, side=DEFAULT_SIDE):
    """Orthographic camera of one view: {"loc": (x, y, z), "dir": (dx, dy, dz) from the target to the camera,
    "ortho_scale": m, "px": [W, H], "centre_z_m": z}. The arithmetic of the default frame is the one of the H2 / look-dev
    stages before 2026-10-09 (Medusa frames unchanged)."""
    W, H = frame["px"]
    top, bottom, base_x = frame["top"], frame["bottom"], frame["base_x"]
    height_m = float(figure_top_m) / (bottom - top)
    zc = float(figure_top_m) - (0.5 - top) * height_m
    shift = (0.5 - base_x) * height_m * W / H
    if view == "front":
        loc, d = (shift, -3.0, zc), (0, -1, 0)
    elif view == "back":
        loc, d = (-shift, 3.0, zc), (0, 1, 0)
    elif view == "side":
        if side == "left":
            loc, d = (3.0, shift, zc), (1, 0, 0)
        elif side == "right":
            loc, d = (-3.0, -shift, zc), (-1, 0, 0)
        else:
            raise FrameError("side must be left or right, got %r" % (side,))
    else:
        raise FrameError("unknown view %r" % (view,))
    return {"loc": loc, "dir": d, "ortho_scale": height_m, "px": [int(W), int(H)], "centre_z_m": zc,
            "frame": dict(frame)}


def cameras(cfg, figure_top_m, repo=None, views=VIEWS):
    """-> ({view: camera}, side, source) for every view of the frame config."""
    frames, side, source = resolve(cfg, repo, views)
    return {v: ortho_camera(frames[v], figure_top_m, v, side) for v in views}, side, source


def project_base_centre(cam, view):
    """Inverse check for the tests: the x share of the frame where the model origin (base centre, x = y = 0) lands."""
    W, H = cam["px"]
    width_m = cam["ortho_scale"] * W / H
    lx, ly, _ = cam["loc"]
    # camera right vector per view (image +x): front +X, back -X, side left +Y, side right -Y
    right = {(0, -1, 0): (1, 0), (0, 1, 0): (-1, 0), (1, 0, 0): (0, 1), (-1, 0, 0): (0, -1)}[tuple(cam["dir"])]
    offset = -(lx * right[0] + ly * right[1])  # origin relative to the camera centre along image +x
    return 0.5 + offset / width_m
