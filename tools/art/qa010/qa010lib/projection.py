"""Pinhole model of the S08 board camera (stdlib only).

Mirrors UE: FRotationMatrix axes from (pitch, yaw, roll) in degrees, camera
FOV = *horizontal* FOV (UE default AspectRatio_MaintainXFOV; the client sets
35 deg in AS08FlowGameMode::SetupCameraForBoard), screen origin top-left.
The model is validated per shot against the client's own
`SHOT fighter ... world=(..) screen=(..) projected=1` pairs; a shot whose
residual exceeds the tolerance must not be used for geometry verdicts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from .geometry import Point, clip_polygon_to_rect, polygon_area
from .trace import Board, ShotBlock

NEAR_CLIP_UU = 10.0  # UE default GNearClippingPlane


@dataclass
class Camera:
    pos: tuple[float, float, float]
    rot: tuple[float, float, float]  # pitch, yaw, roll (deg)
    hfov_deg: float
    viewport: tuple[int, int]

    def axes(self):
        p, y, r = (math.radians(v) for v in self.rot)
        sp, cp = math.sin(p), math.cos(p)
        sy, cy = math.sin(y), math.cos(y)
        sr, cr = math.sin(r), math.cos(r)
        forward = (cp * cy, cp * sy, sp)
        right = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
        up = (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp)
        return forward, right, up

    def project(self, world: Sequence[float]) -> Optional[tuple[float, float, float]]:
        """-> (screen_x, screen_y, depth) or None behind the near plane."""
        f, r, u = self.axes()
        d = (world[0] - self.pos[0], world[1] - self.pos[1], world[2] - self.pos[2])
        depth = d[0] * f[0] + d[1] * f[1] + d[2] * f[2]
        if depth <= NEAR_CLIP_UU:
            return None
        xr = d[0] * r[0] + d[1] * r[1] + d[2] * r[2]
        yu = d[0] * u[0] + d[1] * u[1] + d[2] * u[2]
        w, h = self.viewport
        focal = (w * 0.5) / math.tan(math.radians(self.hfov_deg) * 0.5)
        return (w * 0.5 + xr / depth * focal, h * 0.5 - yu / depth * focal, depth)


def camera_from_shot(shot: ShotBlock, hfov_deg: float) -> Camera:
    return Camera(pos=shot.cam, rot=shot.rot, hfov_deg=hfov_deg, viewport=shot.viewport)


def fighter_pairs(shot: ShotBlock) -> list[tuple[tuple[float, float, float], tuple[float, float]]]:
    return [(f.world, f.screen) for f in shot.fighters if f.projected]


def residuals(cam: Camera, pairs) -> list[float]:
    out = []
    for world, screen in pairs:
        p = cam.project(world)
        if p is None:
            out.append(float("inf"))
        else:
            out.append(math.hypot(p[0] - screen[0], p[1] - screen[1]))
    return out


def fit_camera_position(cam: Camera, pairs, iterations: int = 20) -> Camera:
    """Gauss-Newton refinement of the camera *position* only (rotation and FOV
    fixed) against the client's projected fighter pairs. The trace prints the
    camera location rounded to whole uu; at K2 zoom that alone moves points by
    several pixels, while the client's screen values are rounded to 0.5 px."""
    if len(pairs) < 2:
        return cam
    pos = list(cam.pos)
    eps = 0.01
    for _ in range(iterations):
        def resid(pv):
            c = Camera(tuple(pv), cam.rot, cam.hfov_deg, cam.viewport)
            rs = []
            for world, screen in pairs:
                p = c.project(world)
                if p is None:
                    return None
                rs.extend([p[0] - screen[0], p[1] - screen[1]])
            return rs
        r0 = resid(pos)
        if r0 is None:
            return cam
        jac = []
        for k in range(3):
            pv = list(pos)
            pv[k] += eps
            rk = resid(pv)
            if rk is None:
                return cam
            jac.append([(a - b) / eps for a, b in zip(rk, r0)])
        # normal equations J^T J dx = -J^T r (3x3)
        jtj = [[sum(jac[i][n] * jac[j][n] for n in range(len(r0))) for j in range(3)] for i in range(3)]
        jtr = [sum(jac[i][n] * r0[n] for n in range(len(r0))) for i in range(3)]
        try:
            dx = _solve3(jtj, [-v for v in jtr])
        except ZeroDivisionError:
            break
        pos = [pos[k] + dx[k] for k in range(3)]
        if max(abs(v) for v in dx) < 1e-4:
            break
    return Camera(tuple(pos), cam.rot, cam.hfov_deg, cam.viewport)


def _solve3(a, b):
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ZeroDivisionError("singular")
        m[col], m[piv] = m[piv], m[col]
        for r in range(3):
            if r != col:
                fac = m[r][col] / m[col][col]
                for c in range(col, 4):
                    m[r][c] -= fac * m[col][c]
    return [m[i][3] / m[i][i] for i in range(3)]


@dataclass
class ProjectionReport:
    camera: Camera
    mode: str                  # "trace" | "fit"
    pairs: int
    residual_max_trace: Optional[float]
    residual_max_used: Optional[float]
    tolerance_px: float
    ok: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "camera_pos": [round(v, 3) for v in self.camera.pos],
            "camera_rot": list(self.camera.rot),
            "hfov_deg": self.camera.hfov_deg,
            "viewport": list(self.camera.viewport),
            "validation_pairs": self.pairs,
            "residual_max_px_trace_camera": _r(self.residual_max_trace),
            "residual_max_px_used_camera": _r(self.residual_max_used),
            "tolerance_px": self.tolerance_px,
            "ok": self.ok,
            "reason": self.reason,
        }


def _r(v):
    return None if v is None else (None if math.isinf(v) else round(v, 3))


def build_projection(shot: ShotBlock, hfov_deg: float, tolerance_px: float,
                     mode: str = "auto", min_pairs: int = 2) -> ProjectionReport:
    """mode: 'trace' uses the traced camera; 'fit' refines its position on the
    fighter pairs; 'auto' = trace if within tolerance, else fit."""
    cam = camera_from_shot(shot, hfov_deg)
    if not shot.camera_valid():
        return ProjectionReport(cam, "trace", 0, None, None, tolerance_px, False,
                                "SHOT ctx camera is (0,0,0)/(0,0,0): view target not initialised")
    pairs = fighter_pairs(shot)
    if len(pairs) < min_pairs:
        return ProjectionReport(cam, "trace", len(pairs), None, None, tolerance_px, False,
                                f"only {len(pairs)} projected fighter pairs to validate the camera model")
    r_trace = max(residuals(cam, pairs))
    used, used_mode, r_used = cam, "trace", r_trace
    if mode == "fit" or (mode == "auto" and r_trace > tolerance_px):
        fitted = fit_camera_position(cam, pairs)
        r_fit = max(residuals(fitted, pairs))
        if mode == "fit" or r_fit < r_trace:
            used, used_mode, r_used = fitted, "fit", r_fit
    ok = r_used <= tolerance_px
    reason = "ok" if ok else f"projection residual {r_used:.2f}px > tolerance {tolerance_px}px"
    return ProjectionReport(used, used_mode, len(pairs), r_trace, r_used, tolerance_px, ok, reason)


def cell_world_quad(board: Board, x: int, y: int, cell_size: Optional[float] = None,
                    grow: float = 0.0) -> list[tuple[float, float, float]]:
    cx, cy, cz = board.cell_center(x, y)
    h = (cell_size if cell_size is not None else board.neighbor_dist) * 0.5 + grow
    return [(cx - h, cy - h, cz), (cx + h, cy - h, cz), (cx + h, cy + h, cz), (cx - h, cy + h, cz)]


def board_world_rect(board: Board, margin_cells: float = 0.0) -> list[tuple[float, float, float]]:
    """World rectangle of the whole board, grown by margin_cells * cell size."""
    s = board.neighbor_dist
    a = board.cell_center(0, 0)
    b = board.cell_center(board.width - 1, board.height - 1)
    x0, x1 = min(a[0], b[0]) - s * 0.5, max(a[0], b[0]) + s * 0.5
    y0, y1 = min(a[1], b[1]) - s * 0.5, max(a[1], b[1]) + s * 0.5
    m = margin_cells * s
    z = a[2]
    return [(x0 - m, y0 - m, z), (x1 + m, y0 - m, z), (x1 + m, y1 + m, z), (x0 - m, y1 + m, z)]


def project_polygon(cam: Camera, world_pts) -> Optional[list[Point]]:
    out = []
    for w in world_pts:
        p = cam.project(w)
        if p is None:
            return None
        out.append((p[0], p[1]))
    return out


def project_cell(cam: Camera, board: Board, x: int, y: int) -> dict:
    """Projected quad of one cell plus its part inside the viewport."""
    quad = project_polygon(cam, cell_world_quad(board, x, y))
    if quad is None:
        return {"cell": [x, y], "quad": None, "visible": [], "area": 0.0, "visible_area": 0.0}
    w, h = cam.viewport
    vis = clip_polygon_to_rect(quad, (0.0, 0.0, float(w), float(h)))
    return {"cell": [x, y], "quad": quad, "visible": vis,
            "area": polygon_area(quad), "visible_area": polygon_area(vis)}
