"""Debug overlay for the plate check (writes a new PNG; input untouched)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .projection import ProjectionReport, project_cell
from .trace import ShotBlock


def draw_plate_overlay(frame: Path, out: Path, shot: ShotBlock, proj: ProjectionReport, res: dict) -> None:
    with Image.open(frame) as im:
        base = im.convert("RGB")
    vw, vh = proj.camera.viewport
    sx, sy = base.width / vw, base.height / vh
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    checked = {tuple(c["cell"]): c for c in res.get("cells", [])}
    board = shot.board
    for y in range(board.height):
        for x in range(board.width):
            pc = project_cell(proj.camera, board, x, y)
            if not pc["quad"]:
                continue
            q = [(a * sx, b * sy) for a, b in pc["quad"]]
            c = checked.get((x, y))
            if c is None:
                d.polygon(q, outline=(160, 160, 160, 200))
            elif c["overlapped"]:
                d.polygon(q, fill=(255, 0, 0, 90), outline=(255, 0, 0, 255))
            else:
                d.polygon(q, outline=(0, 255, 120, 255))
    x0, y0, x1, y1 = res["plate"]["bbox"]
    d.rectangle([x0 * sx, y0 * sy, x1 * sx, y1 * sy], outline=(255, 60, 255, 255), width=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB").save(out, format="PNG")
