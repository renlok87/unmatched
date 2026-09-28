"""Parser for S08/S09 client traces (FS08Trace, `<timestamp> <payload>`).

Existing fields used (emitted by unreal/Unmatched/Source/Unmatched/S08/
S08FlowGameMode.cpp):
  BOARD WxH cells | control points: (0,0)=(x,y,z) (W-1,H-1)=(x,y,z) | neighbor pair (dist D uu)
  CAMERA dist=D loc=(x,y,z) pitch=-55 yaw=-90
  SHOT ctx viewport=WxH viewTarget=NAME cam=(x,y,z) rot=(pitch,yaw,roll)
  SHOT fighter ID pos=(cx,cy) world=(x,y,z) screen=(sx,sy) projected=0|1 alive=0|1
  SHOT requested: FScreenshotRequest(bShowUI) -> PATH
  ARTPREVIEW selection ownHero=.. selected=.. fighter=NAME reachable=N [fighterId=ID]
  ARTPREVIEW camera focus requested zoom=Z overview=D target=D

Proposed NEW lines ("требуется новая трасса", not emitted by any client yet;
format defined in docs/art-pipeline/qa010/README.md). Written inside a SHOT
block, i.e. between `SHOT ctx` and `SHOT requested`, at capture time:
  SHOT reachable fighter=ID n=N cells=(x,y)(x,y)...
  SHOT plate fighter=ID bbox=(x0,y0,x1,y1) [overlapReachable=N]
  SHOT icon fighter=ID bbox=(x0,y0,x1,y1)
A standalone `PLATE fighter=ID bbox=(...) [overlapReachable=N]` or
`REACHABLE fighter=ID n=N cells=...` line (outside a block) is accepted as the
latest state for the next shot, and marked source="standalone-latest".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

NUM = r"-?\d+(?:\.\d+)?"
TS = re.compile(r"^\s*(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})\s+(.*?)\s*$")
BOARD = re.compile(
    rf"^BOARD (\d+)x(\d+) cells \| control points: \((\d+),(\d+)\)=\(({NUM}),({NUM}),({NUM})\) "
    rf"\((\d+),(\d+)\)=\(({NUM}),({NUM}),({NUM})\) \| neighbor pair \(dist ({NUM}) uu\)")
CAMERA = re.compile(rf"^CAMERA dist=({NUM}) loc=\(({NUM}),({NUM}),({NUM})\) pitch=({NUM}) yaw=({NUM})")
SHOT_CTX = re.compile(
    rf"^SHOT ctx viewport=(\d+)x(\d+) viewTarget=(\S+) cam=\(({NUM}),({NUM}),({NUM})\) "
    rf"rot=\(({NUM}),({NUM}),({NUM})\)")
SHOT_FIGHTER = re.compile(
    rf"^SHOT fighter (\S+) pos=\((-?\d+),(-?\d+)\) world=\(({NUM}),({NUM}),({NUM})\) "
    rf"screen=\(({NUM}),({NUM})\) projected=(\d) alive=(\d)")
SHOT_REQUESTED = re.compile(r"^SHOT requested: (.*?)(?: -> (.+))?$")
CELLS = re.compile(r"\((-?\d+),(-?\d+)\)")
BBOX = rf"\(({NUM}),({NUM}),({NUM}),({NUM})\)"
NEW_REACHABLE = re.compile(r"^(?:SHOT reachable|REACHABLE) fighter=(\S+) n=(\d+) cells=(.*)$")
NEW_PLATE = re.compile(rf"^(?:SHOT plate|PLATE) fighter=(\S+) bbox={BBOX}(?: overlapReachable=(\d+))?")
NEW_ICON = re.compile(rf"^(?:SHOT icon|ICON) fighter=(\S+) bbox={BBOX}")
SELECTION = re.compile(r"^ARTPREVIEW selection ownHero=(\d) selected=(\d) fighter=(.+?) reachable=(\d+)(?: fighterId=(\S+))?")
FOCUS = re.compile(rf"^ARTPREVIEW camera focus requested zoom=({NUM}) overview=({NUM}) target=({NUM})")


class TraceError(ValueError):
    pass


@dataclass
class Board:
    width: int
    height: int
    c00: tuple[float, float, float]
    cmax_index: tuple[int, int]
    cmax: tuple[float, float, float]
    neighbor_dist: float
    line_no: int

    def cell_step(self) -> tuple[float, float]:
        sx = (self.cmax[0] - self.c00[0]) / (self.width - 1) if self.width > 1 else self.neighbor_dist
        sy = (self.cmax[1] - self.c00[1]) / (self.height - 1) if self.height > 1 else self.neighbor_dist
        return sx, sy

    def cell_center(self, x: int, y: int) -> tuple[float, float, float]:
        sx, sy = self.cell_step()
        return (self.c00[0] + x * sx, self.c00[1] + y * sy, self.c00[2])

    def consistency_errors(self) -> list[str]:
        errs = []
        sx, sy = self.cell_step()
        if abs(abs(sx) - self.neighbor_dist) > 0.51 or abs(abs(sy) - self.neighbor_dist) > 0.51:
            errs.append(f"BOARD control points imply cell step ({sx:.1f},{sy:.1f}) != neighbor dist {self.neighbor_dist}")
        if self.cmax_index != (self.width - 1, self.height - 1):
            errs.append(f"BOARD far control point index {self.cmax_index} != ({self.width - 1},{self.height - 1})")
        return errs


@dataclass
class ShotFighter:
    fighter_id: str
    cell: tuple[int, int]
    world: tuple[float, float, float]
    screen: tuple[float, float]
    projected: bool
    alive: bool


@dataclass
class Tagged:
    value: object
    line_no: int
    source: str  # "shot-block" | "standalone-latest"


@dataclass
class ShotBlock:
    index: int
    line_no: int
    viewport: tuple[int, int]
    view_target: str
    cam: tuple[float, float, float]
    rot: tuple[float, float, float]
    fighters: list[ShotFighter] = field(default_factory=list)
    requested: Optional[str] = None
    path: Optional[str] = None
    board: Optional[Board] = None
    reachable: Optional[Tagged] = None   # value: dict(fighter, n, cells)
    plate: Optional[Tagged] = None       # value: dict(fighter, bbox, overlap_reachable)
    icon: Optional[Tagged] = None        # value: dict(fighter, bbox)
    selection: Optional[dict] = None     # latest ARTPREVIEW selection before shot
    focus: Optional[dict] = None         # latest ARTPREVIEW camera focus before shot

    @property
    def name(self) -> str:
        if self.path:
            return re.split(r"[\\/]", self.path.strip())[-1]
        return f"#{self.index}"

    def camera_valid(self) -> bool:
        return not (self.cam == (0.0, 0.0, 0.0) and self.rot == (0.0, 0.0, 0.0))


@dataclass
class Trace:
    path: str
    board: Optional[Board]
    cameras: list[dict]
    shots: list[ShotBlock]
    unknown_new_lines: list[str]

    def find_shot(self, selector: Optional[str], frame_name: Optional[str] = None) -> ShotBlock:
        """selector: '#N' (0-based block index), a PNG basename, or None ->
        match frame_name, else the single camera-valid block."""
        if selector and selector.startswith("#"):
            idx = int(selector[1:])
            for s in self.shots:
                if s.index == idx:
                    return s
            raise TraceError(f"no SHOT block {selector} in {self.path}")
        want = selector or frame_name
        if want:
            base = re.split(r"[\\/]", want)[-1]
            matches = [s for s in self.shots if s.name == base]
            if matches:
                return matches[-1]  # the last write wins on disk
            if selector:
                raise TraceError(f"no SHOT block for {selector!r} in {self.path}")
        valid = [s for s in self.shots if s.camera_valid()]
        if len(valid) == 1:
            return valid[0]
        raise TraceError(
            f"{self.path}: {len(valid)} camera-valid SHOT blocks; pass --shot NAME or #N "
            f"(names: {', '.join(s.name for s in self.shots)})")


def _f(*vals) -> tuple[float, ...]:
    return tuple(float(v) for v in vals)


def _parse_cells(text: str) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in CELLS.findall(text)]


def parse_trace_text(text: str, path: str = "<memory>") -> Trace:
    board: Optional[Board] = None
    cameras: list[dict] = []
    shots: list[ShotBlock] = []
    cur: Optional[ShotBlock] = None
    latest_plate: Optional[Tagged] = None
    latest_reach: Optional[Tagged] = None
    latest_icon: Optional[Tagged] = None
    latest_sel: Optional[dict] = None
    latest_focus: Optional[dict] = None
    unknown_new: list[str] = []

    def close(block: ShotBlock) -> None:
        if block.plate is None and latest_plate is not None:
            block.plate = latest_plate
        if block.reachable is None and latest_reach is not None:
            block.reachable = latest_reach
        if block.icon is None and latest_icon is not None:
            block.icon = latest_icon

    for line_no, raw in enumerate(text.splitlines(), start=1):
        m = TS.match(raw)
        payload = m.group(2) if m else raw.strip()
        if not payload:
            continue
        if (mm := BOARD.match(payload)):
            g = mm.groups()
            board = Board(int(g[0]), int(g[1]), _f(g[4], g[5], g[6]), (int(g[7]), int(g[8])),
                          _f(g[9], g[10], g[11]), float(g[12]), line_no)
            if (int(g[2]), int(g[3])) != (0, 0):
                raise TraceError(f"{path}:{line_no}: first BOARD control point is not (0,0)")
            continue
        if (mm := CAMERA.match(payload)):
            g = mm.groups()
            cameras.append({"line": line_no, "dist": float(g[0]), "loc": _f(g[1], g[2], g[3]),
                            "pitch": float(g[4]), "yaw": float(g[5])})
            continue
        if (mm := SELECTION.match(payload)):
            latest_sel = {"line": line_no, "own_hero": int(mm.group(1)), "selected": int(mm.group(2)),
                          "fighter_name": mm.group(3), "reachable_count": int(mm.group(4)),
                          "fighter_id": mm.group(5)}
            continue
        if (mm := FOCUS.match(payload)):
            latest_focus = {"line": line_no, "zoom": float(mm.group(1)),
                            "overview": float(mm.group(2)), "target": float(mm.group(3))}
            continue
        if (mm := SHOT_CTX.match(payload)):
            if cur is not None:
                close(cur)
                shots.append(cur)
            g = mm.groups()
            cur = ShotBlock(index=len(shots), line_no=line_no, viewport=(int(g[0]), int(g[1])),
                            view_target=g[2], cam=_f(g[3], g[4], g[5]), rot=_f(g[6], g[7], g[8]),
                            board=board, selection=latest_sel, focus=latest_focus)
            continue
        if (mm := SHOT_FIGHTER.match(payload)):
            if cur is None:
                raise TraceError(f"{path}:{line_no}: SHOT fighter outside a SHOT ctx block")
            g = mm.groups()
            cur.fighters.append(ShotFighter(g[0], (int(g[1]), int(g[2])), _f(g[3], g[4], g[5]),
                                            _f(g[6], g[7]), g[8] == "1", g[9] == "1"))
            continue
        if (mm := NEW_REACHABLE.match(payload)):
            cells = _parse_cells(mm.group(3))
            n = int(mm.group(2))
            if len(cells) != n:
                raise TraceError(f"{path}:{line_no}: reachable n={n} but {len(cells)} cells listed")
            value = {"fighter": mm.group(1), "n": n, "cells": cells}
            if payload.startswith("SHOT ") and cur is not None:
                cur.reachable = Tagged(value, line_no, "shot-block")
            else:
                latest_reach = Tagged(value, line_no, "standalone-latest")
            continue
        if (mm := NEW_PLATE.match(payload)):
            g = mm.groups()
            value = {"fighter": g[0], "bbox": _f(g[1], g[2], g[3], g[4]),
                     "overlap_reachable": int(g[5]) if g[5] is not None else None}
            if payload.startswith("SHOT ") and cur is not None:
                cur.plate = Tagged(value, line_no, "shot-block")
            else:
                latest_plate = Tagged(value, line_no, "standalone-latest")
            continue
        if (mm := NEW_ICON.match(payload)):
            g = mm.groups()
            value = {"fighter": g[0], "bbox": _f(g[1], g[2], g[3], g[4])}
            if payload.startswith("SHOT ") and cur is not None:
                cur.icon = Tagged(value, line_no, "shot-block")
            else:
                latest_icon = Tagged(value, line_no, "standalone-latest")
            continue
        if payload.startswith(("SHOT reachable", "SHOT plate", "SHOT icon", "PLATE ", "REACHABLE ")):
            unknown_new.append(f"{line_no}: {payload}")
            continue
        if (mm := SHOT_REQUESTED.match(payload)):
            if cur is not None:
                cur.requested = mm.group(1)
                cur.path = mm.group(2)
                close(cur)
                shots.append(cur)
                cur = None
            continue
    if cur is not None:
        close(cur)
        shots.append(cur)
    return Trace(path=path, board=board, cameras=cameras, shots=shots, unknown_new_lines=unknown_new)


def parse_trace(path: Path) -> Trace:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_trace_text(text, str(path))
