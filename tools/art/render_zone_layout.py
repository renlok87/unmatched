"""Render a review-only zone diagram from the pinned S04 board contract."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


COLORS = {
    "blue": ("#5e9dec", "&#9670;"),
    "red": ("#e77d78", "&#9650;"),
}


def render(contract_path: Path, output_path: Path) -> None:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    width, height = contract["width"], contract["height"]
    cells = {(cell["x"], cell["y"]): cell for cell in contract["cells"]}
    if len(cells) != width * height:
        raise ValueError("This review diagram requires a complete rectangular board")

    size, gap, left, top = 102, 5, 65, 91
    board_width = width * size + (width - 1) * gap
    board_height = height * size + (height - 1) * gap
    canvas_width = left + board_width + 275
    canvas_height = top + board_height + 94
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-label="Runtime Cobble City zone diagram, {width} by {height}">',
        '<rect width="100%" height="100%" fill="#111925"/>',
        f'<text x="{left}" y="36" fill="#f4eee1" font-family="Segoe UI, sans-serif" font-size="24">Cobble City · runtime S01</text>',
        f'<text x="{left}" y="61" fill="#b9c1cb" font-family="Segoe UI, sans-serif" font-size="15">{width} × {height} cells · source: S04 board-contract.json · diagram only</text>',
    ]

    for y in range(height):
        lines.append(f'<text x="{left - 31}" y="{top + y * (size + gap) + size / 2 + 6}" fill="#c4cad3" font-family="monospace" font-size="14">{y}</text>')
        for x in range(width):
            zones = cells[x, y]["zones"]
            if not zones:
                color, glyph = "#b9b6ac", "&#9675;"
            elif len(zones) == 1:
                color, glyph = COLORS.get(zones[0], ("#d9c98f", "&#9679;"))
            else:
                color, glyph = "#d9c98f", "+"
            px = left + x * (size + gap)
            py = top + y * (size + gap)
            label = html.escape("+".join(zones) or "no zone")
            lines += [
                f'<rect x="{px}" y="{py}" width="{size}" height="{size}" rx="7" fill="#293644" stroke="{color}" stroke-width="3"/>',
                f'<rect x="{px + 8}" y="{py + 8}" width="{size - 16}" height="{size - 16}" rx="4" fill="{color}" opacity="0.13"/>',
                f'<text x="{px + size / 2}" y="{py + 46}" text-anchor="middle" fill="{color}" font-family="Segoe UI Symbol, sans-serif" font-size="32">{glyph}</text>',
                f'<text x="{px + size / 2}" y="{py + 73}" text-anchor="middle" fill="#e3e7ec" font-family="monospace" font-size="14">{x}:{y}</text>',
                f'<title>Cell {x}:{y}: {label}</title>',
            ]

    for x in range(width):
        lines.append(f'<text x="{left + x * (size + gap) + size / 2}" y="{top - 16}" text-anchor="middle" fill="#c4cad3" font-family="monospace" font-size="14">{x}</text>')

    lx = left + board_width + 35
    lines += [
        f'<text x="{lx}" y="{top + 15}" fill="#f4eee1" font-family="Segoe UI, sans-serif" font-size="19">Map-specific zones</text>',
        f'<text x="{lx}" y="{top + 53}" fill="#5e9dec" font-family="Segoe UI, sans-serif" font-size="17">blue (diamond): y=0–2</text>',
        f'<text x="{lx}" y="{top + 87}" fill="#e77d78" font-family="Segoe UI, sans-serif" font-size="17">red (triangle): y=3–5</text>',
        f'<text x="{lx}" y="{top + 145}" fill="#c4cad3" font-family="Segoe UI, sans-serif" font-size="14">Outline + glyph + gentle</text>',
        f'<text x="{lx}" y="{top + 167}" fill="#c4cad3" font-family="Segoe UI, sans-serif" font-size="14">local light wash.</text>',
        f'<text x="{lx}" y="{top + 230}" fill="#c4cad3" font-family="Segoe UI, sans-serif" font-size="14">Other maps load their own</text>',
        f'<text x="{lx}" y="{top + 252}" fill="#c4cad3" font-family="Segoe UI, sans-serif" font-size="14">zone layout from boardState.</text>',
        f'<text x="{left}" y="{top + board_height + 38}" fill="#c4cad3" font-family="Segoe UI, sans-serif" font-size="14">Observed runtime layout; not an approved replica of the physical board or a final light rig.</text>',
        '</svg>',
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    render(arguments.contract, arguments.output)
