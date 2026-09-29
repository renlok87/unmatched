#!/usr/bin/env python3
"""W4-A: neutral "studio dome" radiance map for the -ArtPreview SkyLight.

The engine gate memo (C:/tmp/p0-review/engine-gate-memo.md, §1 item 3) replaces
the point-light "ambient" of the board light profiles with a Movable SkyLight.
A captured sky would be black (the diorama has no sky), and the engine's
starter cubemaps carry a sun/sky bias. This script writes a deterministic,
colour-neutral long-lat Radiance HDR instead; the profile tints and scales it
(Config/ArtBoards/S08ArtBoardProfiles.json lightProfiles.*.sky).

Layout (equirectangular, row 0 = zenith): upper hemisphere radiance
0.6 (horizon) .. 1.0 (zenith) = a soft overhead dome; lower hemisphere 0.25
(the "room/table" below the tray); a 6 degree smoothstep blends the two.
Values are linear and scale-free: SkyLight.Intensity multiplies them.

  python tools/art/render/make_ambient_dome_hdr.py --out <file.hdr>
Byte-identical output for the same arguments (no timestamps in the header).
"""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

WIDTH, HEIGHT = 128, 64
UPPER_HORIZON, UPPER_ZENITH, LOWER = 0.6, 1.0, 0.25
BLEND_DEG = 6.0


def radiance(elev_deg: float) -> float:
    s = math.sin(math.radians(max(elev_deg, 0.0)))
    upper = UPPER_HORIZON + (UPPER_ZENITH - UPPER_HORIZON) * s
    t = min(max((elev_deg + BLEND_DEG) / (2.0 * BLEND_DEG), 0.0), 1.0)
    t = t * t * (3.0 - 2.0 * t)
    return LOWER + (upper - LOWER) * t


def rgbe(v: float) -> bytes:
    if v < 1e-32:
        return b"\x00\x00\x00\x00"
    m, e = math.frexp(v)
    scale = m * 256.0 / v
    c = int(v * scale)
    return bytes((c, c, c, e + 128))


def build() -> bytes:
    header = (b"#?RADIANCE\n# unmatched W4-A ambient dome (tools/art/render/make_ambient_dome_hdr.py)\n"
              b"FORMAT=32-bit_rle_rgbe\n\n" + f"-Y {HEIGHT} +X {WIDTH}\n".encode("ascii"))
    rows = []
    for y in range(HEIGHT):
        elev = 90.0 - (y + 0.5) * 180.0 / HEIGHT
        px = rgbe(radiance(elev))
        rows.append(px * WIDTH)  # flat (non-RLE) scanlines
    return header + b"".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = build()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"{out} {len(data)} bytes sha256 {hashlib.sha256(data).hexdigest()}")
    for elev in (90, 45, 10, 0, -10, -90):
        print(f"  elev {elev:>4} deg radiance {radiance(elev):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
