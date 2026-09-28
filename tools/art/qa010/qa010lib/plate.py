"""K-2 check: the fighter plate must not cover clickable cells of the current
selection (03 §3 К-2, стр. 107: «плашка фигурки не перекрывает соседние
кликабельные клетки (или перекрывает только те, что вне текущего выбора)»).

Stdlib only. Geometry is exact: projected cell quads (from BOARD + SHOT ctx,
validated against the client's own SHOT fighter projections) are clipped to
the viewport and intersected with the plate rectangle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .geometry import Rect, clip_polygon_to_rect, normalize_rect, polygon_area, rect_area
from .projection import ProjectionReport, project_cell
from .trace import ShotBlock

NEW_TRACE_FORMAT = {
    "reachable": "SHOT reachable fighter=<fighterId> n=<N> cells=(x,y)(x,y)...",
    "plate": "SHOT plate fighter=<fighterId> bbox=(x0,y0,x1,y1) [overlapReachable=<N>]",
    "icon": "SHOT icon fighter=<fighterId> bbox=(x0,y0,x1,y1)",
}


@dataclass
class PlateParams:
    max_overlap_fraction: float = 0.0   # 03 стр. 107 «не перекрывает» -> 0 (ПРЕДЛОЖЕНИЕ: 03 — черновик)
    overlap_epsilon_px2: float = 0.5    # numeric noise when the plate edge touches a cell edge
    cells: str = "reachable"            # reachable | all


def check_plate(shot: ShotBlock, proj: ProjectionReport, params: PlateParams,
                plate_bbox: Optional[Rect] = None, reachable: Optional[list[tuple[int, int]]] = None,
                plate_source: str = "cli", reachable_source: str = "cli") -> dict:
    board = shot.board
    out: dict = {"shot": shot.name, "shot_index": shot.index, "projection": proj.to_dict()}
    if board is None:
        out.update(status="insufficient_input", reason="no BOARD line before the SHOT block")
        return out
    missing = []
    client_overlap = None
    if plate_bbox is None and shot.plate is not None:
        plate_bbox = normalize_rect(shot.plate.value["bbox"])
        plate_source = f"trace:{shot.plate.source}@line{shot.plate.line_no}"
        client_overlap = shot.plate.value.get("overlap_reachable")
    if plate_bbox is None:
        missing.append("plate")
    if params.cells == "all":
        reachable = [(x, y) for y in range(board.height) for x in range(board.width)]
        reachable_source = "all-cells (строже нормы: проверяются все клетки)"
    elif reachable is None and shot.reachable is not None:
        reachable = [tuple(c) for c in shot.reachable.value["cells"]]
        reachable_source = f"trace:{shot.reachable.source}@line{shot.reachable.line_no}"
    if reachable is None:
        missing.append("reachable")
    if missing:
        hint = {}
        if shot.selection is not None:
            hint["existing_selection_line"] = shot.selection
        out.update(status="requires_new_trace",
                   reason="trace has no " + " / ".join(missing) + " for this shot; требуется новая трасса",
                   required_lines={k: NEW_TRACE_FORMAT[k] for k in missing}, existing_hint=hint)
        return out
    if not proj.ok:
        out.update(status="insufficient_input", reason=proj.reason)
        return out
    w, h = proj.camera.viewport
    plate = normalize_rect(plate_bbox)
    plate_vis = clip_polygon_to_rect([(plate[0], plate[1]), (plate[2], plate[1]),
                                      (plate[2], plate[3]), (plate[0], plate[3])], (0, 0, w, h))
    plate_info = {"bbox": list(plate), "source": plate_source, "area_px2": round(rect_area(plate), 2),
                  "visible_area_px2": round(polygon_area(plate_vis), 2)}
    reach_set = {tuple(c) for c in reachable}
    bad_cells = [c for c in reach_set if not (0 <= c[0] < board.width and 0 <= c[1] < board.height)]
    if bad_cells:
        out.update(status="insufficient_input", reason=f"reachable cells outside BOARD: {sorted(bad_cells)}")
        return out
    checked, others = [], []
    for y in range(board.height):
        for x in range(board.width):
            pc = project_cell(proj.camera, board, x, y)
            vis = pc["visible"]
            ov = polygon_area(clip_polygon_to_rect(vis, plate)) if vis else 0.0
            frac = ov / pc["visible_area"] if pc["visible_area"] > 0 else 0.0
            row = {"cell": [x, y], "visible_area_px2": round(pc["visible_area"], 2),
                   "overlap_px2": round(ov, 2), "overlap_fraction": round(frac, 4),
                   "overlapped": ov > params.overlap_epsilon_px2}
            (checked if (x, y) in reach_set else others).append(row)
    eps = params.overlap_epsilon_px2
    offscreen = [r["cell"] for r in checked if r["visible_area_px2"] <= eps]
    checked_info = {"source": reachable_source, "count": len(checked),
                    "visible": len(checked) - len(offscreen), "offscreen": offscreen}
    # Nothing-checked guards: a pass needs a visible plate and at least one
    # visible checked cell. A collapsed / not yet laid out UMG widget has zero
    # geometry (LocalToViewport), and the client then also writes
    # overlapReachable=0, so the cross-check agrees: trace error, never pass.
    empty = []
    if not checked:
        empty.append(f"empty reachable list ({reachable_source}): нечего проверять")
    elif len(offscreen) == len(checked):
        empty.append(f"all {len(checked)} checked cells are outside the {w}x{h} viewport: "
                     "ни одна клетка выбора не видна")
    if plate_info["area_px2"] <= eps:
        empty.append(f"plate bbox {list(plate)} has zero area ({plate_source}): "
                     "свёрнутый или не размеченный виджет")
    elif plate_info["visible_area_px2"] <= eps:
        empty.append(f"plate bbox {list(plate)} is outside the {w}x{h} viewport (visible area 0)")
    if empty:
        out.update(status="insufficient_input",
                   reason="; ".join(empty) + " — ошибка трассы или кадра, не pass",
                   plate=plate_info, checked_cells=checked_info)
        return out
    violations = [r for r in checked if r["overlapped"] and r["overlap_fraction"] > params.max_overlap_fraction]
    tool_overlap_count = sum(1 for r in checked if r["overlapped"])
    issues = []
    if shot.plate is not None and shot.reachable is not None and plate_source.startswith("trace")             and reachable_source.startswith("trace")             and shot.plate.value["fighter"] != shot.reachable.value["fighter"]:
        issues.append(f"plate fighter {shot.plate.value['fighter']} != reachable fighter "
                      f"{shot.reachable.value['fighter']} (проверено против выбора, как есть)")
    if offscreen:
        issues.append(f"{len(offscreen)} of {len(checked)} checked cells are outside the viewport "
                      f"and were not checked: {offscreen}")
    if plate_info["visible_area_px2"] < plate_info["area_px2"] - eps:
        issues.append(f"plate is partly outside the viewport: visible {plate_info['visible_area_px2']} "
                      f"of {plate_info['area_px2']} px2")
    cross = None
    if client_overlap is not None:
        cross = {"client_overlapReachable": client_overlap, "tool_overlap_count": tool_overlap_count,
                 "agree": client_overlap == tool_overlap_count}
    result = "pass" if not violations else "fail"
    if cross is not None and not cross["agree"]:
        result = "fail"
    out.update(
        status="measured", result=result,
        plate=plate_info,
        checked_cells=checked_info,
        violations=violations,
        overlapped_non_selection_cells=[r["cell"] for r in others if r["overlapped"]],
        client_cross_check=cross,
        issues=issues,
        cells=checked,
        params={"max_overlap_fraction": params.max_overlap_fraction,
                "max_overlap_fraction_status": "ПРЕДЛОЖЕНИЕ: 03 §3 К-2 стр. 107 (03 — черновик v0.1)",
                "overlap_epsilon_px2": params.overlap_epsilon_px2, "cells": params.cells},
    )
    return out
