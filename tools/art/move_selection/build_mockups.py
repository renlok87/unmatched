#!/usr/bin/env python3
"""MS-T-00 v2: move-selection mockups on REAL project data (no generated scenes).

Inputs (local; images are gitignored per ENV-U3 and never committed):
  - map art:   scraped-data/images/maps/{marmoreal,sarpedon}.png (the images the backend topology was built from)
  - topology:  backend/prisma/fixtures/boards/{marmoreal,sarpedon}.topology.json (spaces, links, zones, starts)
  - heroes:    scraped-data/images/heroes/minis/*.png and avatars/*.webp (Medusa, King Arthur)
  - cards:     RU card art from art/imagegen/mvp-v1/reused-cardart.json, BOOST from
               docs/game-design/evidence/S01/catalog-medusa.json
  - sidekicks: backend Hero.sidekicks[].avatarUrl (the images the admin shows), cached in
               scraped-data/images/heroes/sidekicks/ (Harpies G42WI..., Merlin 4Rl9O...)
Spec: docs/game-design/move-selection/03-ux-spec.md 4.1-4.5, 8.2, 9 (geometry in uu, colours, strings);
reach and canonical path: 04-technical-design.md 3.1 (FIFO BFS, enemies block, K = spaceId).
Output: scraped-data/derived/move-selection/<id>.png, <id>-gray.png, contact-sheet.png, manifest.json.
Run from the repo root: python tools/art/move_selection/build_mockups.py
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import card_icons as CI  # icon set v2 in the card language (iteration 2)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "scraped-data" / "derived" / "move-selection"
SS = 2          # supersampling factor
S = 1.5         # map image px -> output px

KEY = "#111317"            # mark.keyline
PLATE = {"gold": "#FFC857", "teal": "#4CD2DC"}
P1, P2 = "#E8C06A", "#5A7F9F"          # team colours (D-2)
P1S, P2S = "#DAC576", "#5786A8"        # screen team colours (03 V-14..V-16)
RIM = "#FFFFFF"
ERR = "#D9483F"
CHIP_BG, CHIP_TX = "#161A28", "#F2ECDE"
PEND = "#8A56C6"
PANEL_BG = (18, 21, 32, 236)
FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"
FONT_SYM = "C:/Windows/Fonts/seguisym.ttf"  # lock, hourglass, pin, star, eye, chain glyphs

HEROES = {
    "medusa": {"mini": "scraped-data/images/heroes/minis/UiSptDItsyT0i3wGg7lsQ.png",
               "avatar": "scraped-data/images/heroes/avatars/bI206lUtJUQru-FOD8A74.webp", "name": "Medusa", "move": 3},
    "arthur": {"mini": "scraped-data/images/heroes/minis/q2P9K10o3vHFETym77rtX.png",
               "avatar": "scraped-data/images/heroes/avatars/dgwIAej9v-Omrn0sSVs5i.webp", "name": "King Arthur", "move": 2},
}
SIDEKICKS = {
    "harpy": {"portrait": "scraped-data/images/heroes/sidekicks/G42WIKYZ1cmwACVwMggzM.webp", "name": "Harpies", "move": 3},
    "merlin": {"portrait": "scraped-data/images/heroes/sidekicks/4Rl9Oq9N82zhatbTShnXn.webp", "name": "Merlin", "move": 2},
}
HAND = ["Snipe", "Gaze of Stone", "Gaze of Stone", "Clutching Claws", "Hiss and Slither"]  # = live K1 frame hand

USED_INPUTS: set[str] = set()


def rgba(h: str, a: int = 255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def font(size_px: float, bold: bool = False, text: str = ""):
    if any(ord(ch) >= 0x2190 for ch in text):
        return ImageFont.truetype(FONT_SYM, int(size_px * SS))
    return ImageFont.truetype(FONT_B if bold else FONT, int(size_px * SS))


def load(rel: str) -> Image.Image:
    USED_INPUTS.add(rel)
    return Image.open(ROOT / rel).convert("RGBA")


# ---------------------------------------------------------------- board data (04 3.1)
class Board:
    def __init__(self, name: str):
        rel = f"backend/prisma/fixtures/boards/{name}.topology.json"
        USED_INPUTS.add(rel)
        self.t = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        self.name = name
        self.spaces = {s["id"]: s for s in self.t["spaces"]}
        self.adj = {sid: set() for sid in self.spaces}
        for a, b in self.t["edges"]:
            self.adj[a].add(b)
            self.adj[b].add(a)
        self.uu_per_px = self.t["uuPerPx"]
        self.zone_color = {z["key"]: z["color"] for z in self.t["zones"]}
        self.img = load(f"scraped-data/images/maps/{name}.png")
        self.starts = self.t["summary"]["starts"]

    def reach(self, start: str, max_steps: int, enemies: set[str]):
        dist = {start: 0}
        q = deque([start])
        while q:
            c = q.popleft()
            if dist[c] == max_steps:
                continue
            for n in sorted(self.adj[c]):
                if n in dist or n in enemies:
                    continue
                dist[n] = dist[c] + 1
                q.append(n)
        return dist

    def graph_dist(self, start: str):
        return self.reach(start, 10 ** 6, set())

    def path(self, dist: dict, start: str, dest: str, occupied_other: set[str]):
        if dest == start:
            return []
        if dest not in dist or dest in occupied_other:
            return None
        path, cur = [dest], dest
        while dist[cur] > 1:
            cands = [p for p in self.adj[cur] if p in dist and dist[p] == dist[cur] - 1]
            cur = min(cands)  # K = spaceId on a graph board
            path.insert(0, cur)
        return path

    def shares_zone(self, a: str, b: str) -> bool:
        return bool(set(self.spaces[a]["zones"]) & set(self.spaces[b]["zones"]))


# ---------------------------------------------------------------- geometry helpers
def dash_intervals(count: int, duty: float, phase: float = -90.0):
    period = 360.0 / count
    half = period * duty / 2
    return [(phase + i * period - half, phase + i * period + half) for i in range(count)]


def sub_cut(iv, cut):
    if not cut:
        return [iv]
    segs = [iv]
    for off in (-360, 0, 360):
        c0, c1 = cut[0] + off, cut[1] + off
        new = []
        for s0, s1 in segs:
            if c1 <= s0 or c0 >= s1:
                new.append((s0, s1))
                continue
            if s0 < c0:
                new.append((s0, c0))
            if c1 < s1:
                new.append((c1, s1))
        segs = new
    return segs


def arc_poly(cx, cy, r0, r1, a0, a1):
    n = max(6, int(abs(a1 - a0) / 1.5))
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + r1 * math.cos(a), cy + r1 * math.sin(a)))
    for i in range(n, -1, -1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + r0 * math.cos(a), cy + r0 * math.sin(a)))
    return pts


LEADER_CUT = (75.0, 105.0)  # +-15 deg around +Y (image down), 03 4.1


class Canvas:
    def __init__(self, board: Board, crop=None, pad=(0, 0, 0, 0), bg="#0D0F15"):
        """crop = (x0, y0, x1, y1) in map px; pad = (left, top, right, bottom) in output px."""
        self.b = board
        self.k = S * SS
        self.u = S / board.uu_per_px * SS
        x0, y0, x1, y1 = crop or (0, 0, board.img.width, board.img.height)
        self.crop = (x0, y0)
        mw, mh = int((x1 - x0) * self.k), int((y1 - y0) * self.k)
        L, T, R, B = pad
        self.W, self.H = int(mw + (L + R) * SS), int(mh + (T + B) * SS)
        self.im = Image.new("RGBA", (self.W, self.H), rgba(bg))
        part = board.img.crop((x0, y0, x1, y1)).resize((mw, mh), Image.LANCZOS)
        self.ox, self.oy = L * SS, T * SS
        self.im.alpha_composite(part, (self.ox, self.oy))
        self.map_box = (self.ox, self.oy, self.ox + mw, self.oy + mh)

    # coordinates
    def c(self, sid):
        s = self.b.spaces[sid]["layout"]
        return (self.ox + (s["x"] - self.crop[0]) * self.k, self.oy + (s["y"] - self.crop[1]) * self.k)

    def px(self, x, y):  # output px -> canvas px
        return x * SS, y * SS

    def layer(self):
        return Image.new("RGBA", self.im.size, (0, 0, 0, 0))

    def comp(self, layer):
        self.im.alpha_composite(layer)

    # ---- plate channels (03 4.1/4.2)
    def _bands(self, d, c, r0, r1, ivs, fill):
        for a0, a1 in ivs:
            d.polygon(arc_poly(c[0], c[1], r0, r1, a0, a1), fill=fill)

    def plate_ring(self, sid, color, center=36.0, width=3.5, kl=1.5, dash=None, cut=None, alpha=255):
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        c, u = self.c(sid), self.u
        full = dash is None and cut is None
        ivs = dash_intervals(*dash) if dash else [(-90.0, 270.0)]
        ivs = [x for iv in ivs for x in sub_cut(iv, cut)]
        r_in, r_out, k = (center - width / 2) * u, (center + width / 2) * u, kl * u
        self._bands(d, c, r_in - k, r_out + k, ivs, rgba(KEY, alpha))
        da = 0.0 if full else math.degrees(k / (center * u))
        self._bands(d, c, r_in, r_out, [(a0 + da, a1 - da) for a0, a1 in ivs if a1 - a0 > 2 * da], rgba(color, alpha))
        self.comp(lay)

    def plate_fill(self, sid, color, frac=0.18, occupied=False, cut=None):
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        c, u = self.c(sid), self.u
        a = int(255 * frac)
        r0 = 30.0 * u if occupied else 0.0
        ivs = sub_cut((-90.0, 270.0), cut)
        self._bands(d, c, r0, 34.25 * u, ivs, rgba(color, a))
        self.comp(lay)

    def enemy_hatch(self, sid, color, cut=LEADER_CUT):
        """V-07: 45 deg hatching in the 30-39.25 uu band over a 35 % fill, cut under the leader diamond."""
        c, u = self.c(sid), self.u
        mask = Image.new("L", self.im.size, 0)
        md = ImageDraw.Draw(mask)
        for a0, a1 in sub_cut((-90.0, 270.0), cut):
            md.polygon(arc_poly(c[0], c[1], 30 * u, 39.25 * u, a0, a1), fill=255)
        lay = Image.new("RGBA", self.im.size, rgba(color, int(255 * 0.35)))
        d = ImageDraw.Draw(lay)
        step, r = 5.0 * u, 42 * u
        x = c[0] - 2 * r
        while x < c[0] + 2 * r:
            d.line([(x, c[1] - r), (x + 2 * r, c[1] + r)], fill=rgba(KEY), width=max(1, int(1.6 * u)))
            x += step
        empty = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        self.comp(Image.composite(lay, empty, mask))

    def outline(self, sid, shape, color, alpha=255, solid=True):
        """V-14/V-15 contour in 39.6-41.0 uu: P1 circle, P2 hexagon with corner gaps (D-3)."""
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        c, u = self.c(sid), self.u
        if shape == "circle":
            self._bands(d, c, 39.6 * u, 41.0 * u, [(-90.0, 270.0)], rgba(color, alpha))
        else:
            r = 40.3 * u
            verts = [(c[0] + r * math.cos(math.radians(60 * i)), c[1] + r * math.sin(math.radians(60 * i))) for i in range(6)]
            for i in range(6):
                p, q = verts[i], verts[(i + 1) % 6]
                t0, t1 = 0.16, 0.84
                a = (p[0] + (q[0] - p[0]) * t0, p[1] + (q[1] - p[1]) * t0)
                b = (p[0] + (q[0] - p[0]) * t1, p[1] + (q[1] - p[1]) * t1)
                d.line([a, b], fill=rgba(KEY, alpha), width=int(3.4 * u))
                d.line([a, b], fill=rgba(color, alpha), width=int(1.6 * u))
        self.comp(lay)

    def brackets(self, sid, color):
        """V-16 threat: four corner brackets in the contour band."""
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        c, u = self.c(sid), self.u
        r, L = 40.3 * u, 11 * u
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = c[0] + sx * r * 0.74, c[1] + sy * r * 0.74
                pts = [(x, y - sy * L), (x, y), (x - sx * L, y)]
                d.line(pts, fill=rgba(KEY), width=int(3.6 * u), joint="curve")
                d.line(pts, fill=rgba(color), width=int(2.0 * u), joint="curve")
        self.comp(lay)

    # ---- figures (L4/L7)
    def team_ring(self, sid, team):
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        c, u = self.c(sid), self.u
        if team == 1:
            self._bands(d, c, 22.5 * u, 29.5 * u, [(-90.0, 270.0)], rgba(RIM))
            self._bands(d, c, 23.5 * u, 28.5 * u, [(-90.0, 270.0)], rgba(P1))
        else:
            r = 26.0 * u
            verts = [(c[0] + r * math.cos(math.radians(60 * i + 30)), c[1] + r * math.sin(math.radians(60 * i + 30))) for i in range(6)]
            for i in range(6):
                p, q = verts[i], verts[(i + 1) % 6]
                a = (p[0] + (q[0] - p[0]) * 0.12, p[1] + (q[1] - p[1]) * 0.12)
                b = (p[0] + (q[0] - p[0]) * 0.88, p[1] + (q[1] - p[1]) * 0.88)
                d.line([a, b], fill=rgba(RIM), width=int(6.6 * u))
                d.line([a, b], fill=rgba(P2), width=int(4.6 * u))
        self.comp(lay)

    def leader_diamond(self, sid, team):
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        c, u = self.c(sid), self.u
        cx, cy = c[0], c[1] + 34.5 * u
        rr, rt = 5.6 * u, 4.2 * u
        pts = [(cx, cy - rr), (cx + rt, cy), (cx, cy + rr), (cx - rt, cy)]
        d.polygon(pts, fill=rgba(P1 if team == 1 else P2), outline=rgba(KEY), width=max(1, int(1.2 * u)))
        self.comp(lay)

    def mini(self, sid, rel, ghost=False, grey=False, scale=1.0):
        im = load(rel)
        bbox = im.getbbox()
        im = im.crop(bbox)
        a = im.split()[3]
        h = im.height
        rows = a.crop((0, int(h * 0.92), im.width, h)).getbbox()
        base_w = (rows[2] - rows[0]) if rows else im.width * 0.6
        target = 46.0 * self.u * scale
        f = target / base_w
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
        if grey:
            g = ImageOps.grayscale(im).convert("RGBA")
            g.putalpha(im.split()[3])
            im = Image.blend(g, Image.new("RGBA", im.size, (90, 90, 96, 0)), 0.25)
            im.putalpha(g.split()[3])
        if ghost:  # 45 % dithered, no shadow (03 4.3, MS-C-04)
            bayer = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
            al = im.split()[3].load()
            w, hh = im.size
            for y in range(hh):
                for x in range(w):
                    if al[x, y] and bayer[y % 4][x % 4] >= 7:
                        al[x, y] = 0
            r_, g_, b_, a_ = im.split()
            a_ = a_.point(lambda v: int(v * 0.85))
            im = Image.merge("RGBA", (r_, g_, b_, a_))
        c = self.c(sid)
        base_h = target * 0.28
        pos = (int(c[0] - im.width / 2), int(c[1] + base_h / 2 - im.height))
        lay = self.layer()
        lay.alpha_composite(im, (max(0, pos[0]), max(0, pos[1])) if pos[0] >= 0 and pos[1] >= 0 else (0, 0))
        if pos[0] < 0 or pos[1] < 0:  # rare: clip at canvas edge
            lay = self.layer()
            src = im.crop((max(0, -pos[0]), max(0, -pos[1]), im.width, im.height))
            lay.alpha_composite(src, (max(0, pos[0]), max(0, pos[1])))
        self.comp(lay)

    def token(self, sid, rel, team, grey=False):
        """Sidekick token: project portrait in a disc (no backend sidekick art locally)."""
        u = self.u
        r = int(21 * u)
        im = load(rel)
        side = min(im.size)
        im = im.crop(((im.width - side) // 2, 0, (im.width - side) // 2 + side, side)).resize((2 * r, 2 * r), Image.LANCZOS)
        if grey:
            g = ImageOps.grayscale(im).convert("RGBA")
            im = Image.blend(g, Image.new("RGBA", im.size, (70, 70, 76, 255)), 0.3)
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
        im.putalpha(mask)
        c = self.c(sid)
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        d.ellipse((c[0] - r - 2 * u, c[1] - r - 2 * u, c[0] + r + 2 * u, c[1] + r + 2 * u), fill=rgba(KEY))
        lay.alpha_composite(im, (int(c[0] - r), int(c[1] - r)))
        self.comp(lay)

    # ---- path (L5)
    def path_line(self, pts_sids, color, dashed=False, start_sid=None, arrow=True, dots=True, offsets=None):
        """offsets: {frozenset((a, b)): uu} - sideways shift of links shared by several paths (03 4.2a)."""
        u = self.u
        seq = ([start_sid] if start_sid else []) + pts_sids
        pts = [self.c(s) for s in seq]
        if offsets:
            shifted = []
            for i, (a, b) in enumerate(zip(seq[:-1], seq[1:])):
                off = offsets.get(frozenset((a, b)), 0.0) * u
                (ax, ay), (bx, by) = pts[i], pts[i + 1]
                ln = math.hypot(bx - ax, by - ay) or 1.0
                nx, ny = -(by - ay) / ln * off, (bx - ax) / ln * off
                shifted.append(((ax + nx, ay + ny), (bx + nx, by + ny)))
            pts = [shifted[0][0]] + [((shifted[i][1][0] + shifted[i + 1][0][0]) / 2, (shifted[i][1][1] + shifted[i + 1][0][1]) / 2)
                                    for i in range(len(shifted) - 1)] + [shifted[-1][1]]
        if len(pts) < 2:
            return
        # stop the last segment at the inner ring of the destination
        ex, ey = pts[-1]
        px_, py_ = pts[-2]
        L = math.hypot(ex - px_, ey - py_)
        ux, uy = (ex - px_) / L, (ey - py_) / L
        tip = (ex - ux * 18 * u, ey - uy * 18 * u)
        back = (tip[0] - ux * 14 * u, tip[1] - uy * 14 * u)
        line_pts = pts[:-1] + [back]
        if start_sid:  # start at the edge of the selected fighter's ring
            sx, sy = line_pts[0]
            nx, ny = line_pts[1]
            l0 = math.hypot(nx - sx, ny - sy)
            line_pts[0] = (sx + (nx - sx) / l0 * 31 * u, sy + (ny - sy) / l0 * 31 * u)
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        segs = list(zip(line_pts[:-1], line_pts[1:]))
        for width, col in ((8.0, KEY), (5.0, color)):
            for a, b in segs:
                if dashed:
                    l = math.hypot(b[0] - a[0], b[1] - a[1])
                    n = max(1, int(l / (16 * u)))
                    for i in range(n):
                        t0, t1 = i / n, (i + 0.62) / n
                        d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                                (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=rgba(col), width=int(width * u))
                else:
                    d.line([a, b], fill=rgba(col), width=int(width * u))
            if not dashed:
                for p in line_pts[1:-1]:
                    rr = width / 2 * u
                    d.ellipse((p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr), fill=rgba(col))
        if arrow:
            nxp, nyp = -uy, ux
            w = 9 * u
            tri = [tip, (back[0] + nxp * w, back[1] + nyp * w), (back[0] - nxp * w, back[1] - nyp * w)]
            big = [(tip[0] + ux * 2 * u, tip[1] + uy * 2 * u), (back[0] + nxp * (w + 2.4 * u) - ux * 1.5 * u, back[1] + nyp * (w + 2.4 * u) - uy * 1.5 * u),
                   (back[0] - nxp * (w + 2.4 * u) - ux * 1.5 * u, back[1] - nyp * (w + 2.4 * u) - uy * 1.5 * u)]
            d.polygon(big, fill=rgba(KEY))
            d.polygon(tri, fill=rgba(color))
        if dots:
            for p in pts[1 if start_sid else 0:-1]:
                r1, r0 = 5.5 * u, 4.0 * u
                d.ellipse((p[0] - r1, p[1] - r1, p[0] + r1, p[1] + r1), fill=rgba(KEY))
                d.ellipse((p[0] - r0, p[1] - r0, p[0] + r0, p[1] + r0), fill=rgba(color))
        self.comp(lay)

    def trail_dots(self, sids, color):
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        u = self.u
        for s in sids:
            c = self.c(s)
            r1, r0 = 6.5 * u, 4.8 * u
            d.ellipse((c[0] - r1, c[1] - r1, c[0] + r1, c[1] + r1), fill=rgba(KEY))
            d.ellipse((c[0] - r0, c[1] - r0, c[0] + r0, c[1] + r0), fill=rgba(color))
        self.comp(lay)

    # ---- glyphs and badges (L6), sizes in output px
    def badge(self, xy, text, size=17, bg=CHIP_BG, fg=CHIP_TX, rim=None, bold=True, anchor="mm", pad=(9, 4), circle=False):
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        f = font(size, bold, text)
        tb = d.textbbox((0, 0), text, font=f)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        pw, ph = pad[0] * SS, pad[1] * SS
        w, h = tw + 2 * pw, th + 2 * ph + 2 * SS
        if circle:
            w = h = max(w, h)
        x, y = xy
        if anchor == "mm":
            x0, y0 = x - w / 2, y - h / 2
        elif anchor == "lm":
            x0, y0 = x, y - h / 2
        elif anchor == "rm":
            x0, y0 = x - w, y - h / 2
        else:
            x0, y0 = x, y
        rad = h / 2
        if rim:
            d.rounded_rectangle((x0 - 2 * SS, y0 - 2 * SS, x0 + w + 2 * SS, y0 + h + 2 * SS), radius=rad + 2 * SS, fill=rgba(rim))
        d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=rad, fill=rgba(bg) if isinstance(bg, str) else bg)
        d.text((x0 + w / 2, y0 + h / 2), text, font=f, fill=rgba(fg), anchor="mm")
        self.comp(lay)
        return (x0, y0, x0 + w, y0 + h)

    def paste(self, im, xy, anchor="mm"):
        x, y = xy
        if anchor == "mm":
            x, y = x - im.width / 2, y - im.height / 2
        elif anchor == "lm":
            y = y - im.height / 2
        elif anchor == "mt":
            x = x - im.width / 2
        lay = self.layer()
        lay.alpha_composite(im, (int(x), int(y)))
        self.comp(lay)

    def ic(self, name, xy, size_px, number=None, anchor="mm"):
        self.paste(CI.icon(name, int(size_px * SS), number), xy, anchor)

    def plate_text(self, xy, text, size_px=26, anchor="mm", glyph=None):
        self.paste(CI.plate(text, int(size_px * SS), glyph=glyph), xy, anchor)

    def chip_top(self, sid, text):
        c, u = self.c(sid), self.u
        self.ic("boost", (c[0], c[1] - 40 * u), 30, text)

    def order_badge(self, sid, n, team=1, dx=0.0):
        c, u = self.c(sid), self.u
        self.ic("order" if team == 1 else "order-p2", (c[0] + dx * u, c[1] + 36 * u), 20, str(n), anchor="mt")

    def glyph_x(self, sid):
        self.ic("refuse", self.c(sid), 46)

    def icon(self, xy, rel, size_px):
        im = load(rel)
        im = im.crop(im.getbbox())
        f = size_px * SS / max(im.size)
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
        lay = self.layer()
        lay.alpha_composite(im, (int(xy[0] - im.width / 2), int(xy[1] - im.height / 2)))
        self.comp(lay)

    def glyph_text(self, sid, text, color, dy=0.0, size=26):
        c, u = self.c(sid), self.u
        self.badge((c[0], c[1] + dy * u), text, size=size, bg=KEY, fg=color, circle=True, pad=(7, 2))

    def cursor(self, xy):
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        x, y = xy
        s = SS * 1.25
        pts = [(0, 0), (0, 26), (7, 20), (12, 31), (16, 29), (11, 18), (20, 18)]
        d.polygon([(x + px_ * s, y + py_ * s) for px_, py_ in pts], fill=(255, 255, 255, 255), outline=rgba(KEY), width=int(1.5 * SS))
        self.comp(lay)

    def zone_dots(self, sid, anchor_xy):
        x, y = anchor_xy
        dsz = 26 * SS
        for i, z in enumerate(self.b.spaces[sid]["zones"][:3]):
            self.paste(CI.zone_disc(dsz, self.b.zone_color[z]), (x + i * (dsz + 4 * SS), y), anchor="lm")

    # ---- HUD
    def panel(self, box_out_px, lines, title=None):
        """lines: list of (text, colour, bold, icon_rel_or_None)."""
        x0, y0, x1, y1 = [v * SS for v in box_out_px]
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle((x0, y0, x1, y1), radius=10 * SS, fill=CI.CREAM)
        d.rounded_rectangle((x0 + 3 * SS, y0 + 3 * SS, x1 - 3 * SS, y1 - 3 * SS), radius=8 * SS, fill=CI.NAVY_2)
        if title:
            d.rounded_rectangle((x0 + 3 * SS, y0 + 3 * SS, x1 - 3 * SS, y0 + 40 * SS), radius=8 * SS, fill=CI.NAVY)
        self.comp(lay)
        y = y0 + 14 * SS
        if title:
            ImageDraw.Draw(self.im).text((x0 + 16 * SS, y0 + 22 * SS), title.upper(), font=CI.bahn(int(19 * SS)),
                                         fill=CI.CREAM, anchor="lm")
            y += 34 * SS
        for text, col, bold, icon in lines:
            xt = x0 + 16 * SS
            if icon:
                im = load(icon).convert("RGBA")
                side = min(im.size)
                im = im.crop(((im.width - side) // 2, 0, (im.width - side) // 2 + side, side)).resize((32 * SS, 32 * SS), Image.LANCZOS)
                m = Image.new("L", im.size, 0)
                ImageDraw.Draw(m).ellipse((0, 0, im.width - 1, im.height - 1), fill=255)
                im.putalpha(m)
                self.im.alpha_composite(im, (int(xt), int(y - 4 * SS)))
                xt += 40 * SS
            ImageDraw.Draw(self.im).text((xt, y), text, font=font(16, bold), fill=rgba(col))
            y += 40 * SS

    def button(self, box_out_px, text, enabled=True):
        x0, y0, x1, y1 = [v * SS for v in box_out_px]
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle((x0, y0, x1, y1), radius=8 * SS, fill=CI.CREAM if enabled else rgba("#5A5F6E"))
        d.rounded_rectangle((x0 + 2 * SS, y0 + 2 * SS, x1 - 2 * SS, y1 - 2 * SS), radius=7 * SS,
                            fill=CI.NAVY if enabled else rgba("#22252F"))
        d.text(((x0 + x1) / 2, (y0 + y1) / 2), text.upper(), font=CI.bahn(int(17 * SS)),
               fill=CI.CREAM if enabled else rgba("#7C8090"), anchor="mm")
        self.comp(lay)

    def text(self, xy_out_px, text, size=16, color="#F2ECDE", bold=False, anchor="la"):
        ImageDraw.Draw(self.im).text((xy_out_px[0] * SS, xy_out_px[1] * SS), text, font=font(size, bold), fill=rgba(color), anchor=anchor)

    def final(self):
        return self.im.resize((self.W // SS, self.H // SS), Image.LANCZOS).convert("RGB")


# ---------------------------------------------------------------- scene setup
class Setup:
    """Deterministic mid-game position on a real map: P1 Medusa + 3 Harpies, P2 King Arthur + Merlin."""

    def __init__(self, b: Board):
        self.b = b
        m = b.starts["1"]
        gd = b.graph_dist(m)
        nb = sorted(b.adj[m])
        ring2 = sorted(s for s, v in gd.items() if v == 2)
        self.medusa = m
        self.harpies = (nb + ring2)[:3]
        taken = {m, *self.harpies}
        self.arthur = sorted((s for s, v in gd.items() if v == 4 and s not in taken), key=lambda s: (len(b.adj[s]) * -1, s))[0]
        ga = b.graph_dist(self.arthur)
        self.merlin = sorted(s for s, v in ga.items() if v == 2 and gd.get(s, 0) >= 5 and s not in taken)[0]
        self.p1 = {self.medusa, *self.harpies}
        self.p2 = {self.arthur, self.merlin}

    def occupied(self):
        return self.p1 | self.p2


def draw_figures(cv: Canvas, st: Setup, selected=None, grey=(), skip=()):
    for s in sorted(st.occupied(), key=lambda s: cv.c(s)[1]):
        if s in skip:
            continue
        team = 1 if s in st.p1 else 2
        if s in (st.medusa, st.arthur):
            cv.team_ring(s, team)
            cv.leader_diamond(s, team)
    if selected:  # V-05 selection ring: thin ring just outside the team ring
        lay = cv.layer()
        d = ImageDraw.Draw(lay)
        c, u = cv.c(selected), cv.u
        d.ellipse((c[0] - 31 * u, c[1] - 31 * u, c[0] + 31 * u, c[1] + 31 * u), outline=rgba(RIM), width=int(1.6 * u))
        cv.comp(lay)
    for s in sorted(st.occupied(), key=lambda s: cv.c(s)[1]):
        if s in skip:
            continue
        if s == st.medusa:
            cv.mini(s, HEROES["medusa"]["mini"], grey=s in grey)
        elif s == st.arthur:
            cv.mini(s, HEROES["arthur"]["mini"])
        elif s == st.merlin:
            cv.token(s, SIDEKICKS["merlin"]["portrait"], 2)
        else:
            cv.token(s, SIDEKICKS["harpy"]["portrait"], 1, grey=s in grey)


def reach_tiers(b: Board, st: Setup, mover: str, move: int, max_boost: int):
    enemies = st.p2 if mover in st.p1 else st.p1
    dist = b.reach(mover, move + max_boost, enemies)
    occupied_other = st.occupied() - {mover}
    base = sorted(s for s, v in dist.items() if 1 <= v <= move and s not in occupied_other)
    boost = sorted(s for s, v in dist.items() if move < v <= move + max_boost and s not in occupied_other)
    gd = b.graph_dist(mover)
    blocked = sorted(s for s in enemies if gd.get(s, 99) <= move + max_boost)
    return dist, base, boost, blocked


def draw_reach(cv: Canvas, st: Setup, color, base, boost, blocked, move):
    for s in base:
        cv.plate_fill(s, color)
        cv.plate_ring(s, color)
    for s in boost:
        cv.plate_ring(s, color, dash=(12, 0.6))
    for s in blocked:
        cv.enemy_hatch(s, color, cut=LEADER_CUT if s == st.arthur else None)


def draw_boost_chips(cv: Canvas, dist, boost, move):
    for s in boost:
        cv.chip_top(s, f"+{dist[s] - move}")


# ---------------------------------------------------------------- scenes
def hand_tray(cv: Canvas, y_out, selected_idx=None, x_out=None):
    cards = json.loads((ROOT / "art/imagegen/mvp-v1/reused-cardart.json").read_text(encoding="utf-8"))["cards"]
    USED_INPUTS.add("art/imagegen/mvp-v1/reused-cardart.json")
    by_title = {c["title"]: c for c in cards if c["stableContentKey"].startswith("medusa:")}
    w_card, h_card, gap = 287, 398, 22
    total = len(HAND) * w_card + (len(HAND) - 1) * gap
    x = x_out if x_out is not None else (cv.W / SS - total) / 2
    for i, t in enumerate(HAND):
        c = by_title[t]
        rel = c.get("ru", {}).get("path") or c["en"]["path"]
        im = load(rel).resize((w_card * SS, h_card * SS), Image.LANCZOS)
        yy = y_out - (26 if i == selected_idx else 0)
        if i == selected_idx:
            lay = cv.layer()
            ImageDraw.Draw(lay).rounded_rectangle(((x - 5) * SS, (yy - 5) * SS, (x + w_card + 5) * SS, (yy + h_card + 5) * SS),
                                                  radius=10 * SS, fill=rgba(P1S))
            cv.comp(lay)
        cv.im.alpha_composite(im, (int(x * SS), int(yy * SS)))
        cv.badge(((x + w_card / 2) * SS, (yy + h_card + 16) * SS), f"{i + 1}", size=13, circle=True, pad=(5, 1))
        x += w_card + gap


def scene_reach(name: str, colour_key: str, out_id: str):
    """MS-C-02/03: selected Medusa (move 3), boost tier up to the best BOOST in hand (+4), hover path with badge."""
    b = Board(name)
    st = Setup(b)
    color = PLATE[colour_key]
    cv = Canvas(b, pad=(430, 70, 0, 20))
    dist, base, boost, blocked = reach_tiers(b, st, st.medusa, 3, 4)
    draw_reach(cv, st, color, base, boost, blocked, 3)
    hover = sorted((s for s in base if dist[s] == 3), key=lambda s: (-len(b.spaces[s]["zones"]), s))[0]
    path = b.path(dist, st.medusa, hover, st.occupied() - {st.medusa})
    draw_figures(cv, st, selected=st.medusa)
    cv.path_line(path, color, start_sid=st.medusa)
    draw_boost_chips(cv, dist, boost, 3)
    hc = cv.c(hover)
    cv.cursor((hc[0] + 10 * SS, hc[1] + 6 * SS))
    cv.plate_text((hc[0] + 74 * SS, hc[1] + 46 * SS), "3/3", 28)
    cv.text((20, 18), f"{b.t['name']} · {out_id} · подложка {color} · реальная карта и топология", 18, bold=True)
    cv.panel((16, 80, 410, 420), [
        (f"Medusa  {st.medusa}  · движение 3", "#F2ECDE", True, HEROES["medusa"]["avatar"]),
        (f"Harpies 1  {st.harpies[0]}: не ходит", "#B9BDC9", False, SIDEKICKS["harpy"]["portrait"]),
        (f"Harpies 2  {st.harpies[1]}: не ходит", "#B9BDC9", False, SIDEKICKS["harpy"]["portrait"]),
        (f"Harpies 3  {st.harpies[2]}: не ходит", "#B9BDC9", False, SIDEKICKS["harpy"]["portrait"]),
        ("Буст: нет  (в руке до +4)", "#F2ECDE", False, None),
        (f"Наведение: {st.medusa} → {hover}  3/3", "#F2ECDE", False, None),
    ], title="Манёвр · карта добрана")
    cv.text((16, 440), "Легенда:", 15, "#B9BDC9", True)
    legend = [("сплошное кольцо — достижимо (V-01)", None), ("пунктир + «+N» — только с бустом (V-02)", None),
              ("штриховка — враг, блок (V-07)", None), ("линия, точки, стрелка — путь (V-03)", None)]
    for i, (t, _) in enumerate(legend):
        cv.text((24, 466 + i * 26), "• " + t, 14, "#D7DAE3")
    return cv.final(), {"board": name, "plate": color, "selected": st.medusa, "base": base, "boostTier": boost,
                        "enemyBlocked": blocked, "hover": hover, "path": path, "positions": positions(st)}


def positions(st: Setup):
    return {"Medusa": st.medusa, "Harpies": st.harpies, "King Arthur": st.arthur, "Merlin": st.merlin}


def scene_closeup(colour_key="gold"):
    """MS-C-04: assigned destination: double ring, ghost, order badge, zones, attack-from."""
    b = Board("marmoreal")
    st = Setup(b)
    color = PLATE[colour_key]
    dist, base, boost, blocked = reach_tiers(b, st, st.medusa, 3, 4)
    dest = sorted((s for s in base if dist[s] == 3), key=lambda s: (-len(b.spaces[s]["zones"]), s))[0]
    path = b.path(dist, st.medusa, dest, st.occupied() - {st.medusa})
    xs = [b.spaces[s]["layout"]["x"] for s in [st.medusa] + path]
    ys = [b.spaces[s]["layout"]["y"] for s in [st.medusa] + path]
    m = 150
    crop = (max(0, min(xs) - m), max(0, min(ys) - m - 60), min(b.img.width, max(xs) + m + 120), min(b.img.height, max(ys) + m))
    cv = Canvas(b, crop=crop, pad=(0, 50, 0, 0))
    cv.k *= 1.0
    for s in base:
        if s != dest and s not in path:
            cv.plate_ring(s, color, alpha=110)
    cv.plate_fill(dest, color)
    cv.plate_ring(dest, color)
    cv.plate_ring(dest, color, center=26.0, width=3.0)
    draw_figures(cv, st, selected=st.medusa)
    cv.path_line(path, color, start_sid=st.medusa)
    cv.mini(dest, HEROES["medusa"]["mini"], ghost=True)
    cv.order_badge(dest, 1)
    c = cv.c(dest)
    u = cv.u
    bx = c[0] + 50 * u
    cv.plate_text((bx, c[1] - 32 * u), "3/3", 30, anchor="lm")
    cv.zone_dots(dest, (bx, c[1] - 4 * u))
    enemies_from = sum(1 for e in st.p2 if e in b.adj[dest] or b.shares_zone(dest, e))
    cv.ic("attack-from", (bx, c[1] + 24 * u), 30, str(enemies_from), anchor="lm")
    cv.text((14, 12), f"MS-C-04 · Marmoreal · цель назначена: {st.medusa} → {dest} · зоны: {', '.join(b.spaces[dest]['zones'])}", 17, bold=True)
    return cv.final(), {"dest": dest, "path": path, "zones": b.spaces[dest]["zones"], "attackFrom": enemies_from}


def scene_boost():
    """MS-C-05: before/after choosing Gaze of Stone (+4): tiers recomputed in the same frame (MS-R-15)."""
    b = Board("marmoreal")
    st = Setup(b)
    color = PLATE["gold"]
    gd = b.graph_dist(st.medusa)
    sel = [s for s, v in gd.items() if v <= 8]
    xs = [b.spaces[s]["layout"]["x"] for s in sel]
    ys = [b.spaces[s]["layout"]["y"] for s in sel]
    crop = (max(0, min(xs) - 90), max(0, min(ys) - 90), min(b.img.width, max(xs) + 90), min(b.img.height, max(ys) + 90))
    halves = []
    for chosen in (None, 4):
        cv = Canvas(b, crop=crop, pad=(0, 60, 0, 0))
        allowance = 3 + (chosen or 0)
        dist, base, boost, blocked = reach_tiers(b, st, st.medusa, allowance, 0 if chosen else 4)
        if chosen:
            base = sorted(s for s, v in dist.items() if 1 <= v <= allowance and s not in st.occupied() - {st.medusa})
            boost = []
        draw_reach(cv, st, color, base, boost, blocked, 3)
        draw_figures(cv, st, selected=st.medusa)
        if not chosen:
            draw_boost_chips(cv, dist, boost, 3)
        cv.text((14, 14), "До выбора буста: база 3 + ярус «+N» до +4" if not chosen else "Выбран Gaze of Stone +4: допуск 7, ярус сплошной", 18, bold=True)
        halves.append(cv.final())
    w = halves[0].width + halves[1].width + 20
    tray_h = 520
    out = Image.new("RGB", (w, halves[0].height + tray_h), (13, 15, 21))
    out.paste(halves[0], (0, 0))
    out.paste(halves[1], (halves[0].width + 20, 0))
    # hand tray with real RU card art; card 2 selected (Gaze of Stone, BOOST 4)
    tray = Canvas.__new__(Canvas)
    tray.im = Image.new("RGBA", (w * SS, tray_h * SS), (13, 15, 21, 255))
    tray.W, tray.H = w * SS, tray_h * SS
    tray.u = 1.0
    hand_tray(tray, 50, selected_idx=1)
    tray.text((24, 14), "Рука (реальные карты Medusa, RU) · строка панели: «Буст: Gaze of Stone +4 (сброс)»", 16, "#F2ECDE", True)
    out.paste(tray.final(), (0, halves[0].height))
    return out, {"hand": HAND, "selected": "Gaze of Stone +4"}


def scene_multi():
    """MS-C-06: three planned moves: Ok, NeedBoost (+k), Conflict (target taken by move 1)."""
    b = Board("marmoreal")
    st = Setup(b)
    color = PLATE["gold"]
    cv = Canvas(b, pad=(520, 70, 0, 20))
    occ = st.occupied()
    dist_m, base_m, _, _ = reach_tiers(b, st, st.medusa, 3, 4)
    d1 = sorted((s for s in base_m if dist_m[s] == 3), key=lambda s: (-len(b.spaces[s]["zones"]), s))[0]
    p1 = b.path(dist_m, st.medusa, d1, occ - {st.medusa})
    h_a, h_b = st.harpies[0], st.harpies[1]
    occ_after = (occ - {st.medusa}) | {d1}
    dist_a = b.reach(h_a, 7, st.p2)
    d2 = sorted(s for s, v in dist_a.items() if v == 5 and s not in occ_after)[0]
    p2 = b.path(dist_a, h_a, d2, occ_after - {h_a})
    dist_b = b.reach(h_b, 3, st.p2)
    p3_dest = d1  # Conflict: d1 is taken by move 1
    p3 = b.path(b.reach(h_b, 10, st.p2), h_b, p3_dest, set())
    cv.plate_fill(d1, color)
    cv.plate_ring(d1, color)
    cv.plate_ring(d1, color, center=26.0, width=3.0)
    cv.plate_ring(d2, color, dash=(12, 0.6))
    cv.plate_ring(d2, color, center=26.0, width=3.0)
    draw_figures(cv, st)
    plans = [[st.medusa] + p1, [h_a] + p2, [h_b] + p3]
    use = {}
    for k, seq in enumerate(plans):
        for a, b2 in zip(seq[:-1], seq[1:]):
            use.setdefault(frozenset((a, b2)), []).append(k)
    offs = [{e: 8.0 * (ks.index(k) - (len(ks) - 1) / 2) for e, ks in use.items() if len(ks) > 1 and k in ks} for k in range(3)]
    cv.path_line(p1, color, start_sid=st.medusa, offsets=offs[0])
    cv.path_line(p2, color, start_sid=h_a, dashed=True, offsets=offs[1])
    cv.path_line(p3, ERR, start_sid=h_b, dashed=True, offsets=offs[2])
    # conflict ring on top (Conflict > Destination in the ring channel, 03 4.2a): dashed double ring in error colour
    cv.plate_ring(p3_dest, ERR, dash=(12, 0.6))
    cv.mini(d1, HEROES["medusa"]["mini"], ghost=True)
    cv.order_badge(d1, 1, dx=-26)
    cv.order_badge(d2, 2)
    cv.chip_top(d2, f"+{len(p2) - 3}")
    cv.ic("conflict", cv.c(p3_dest), 24)
    cv.order_badge(p3_dest, 3, dx=26)
    cv.text((20, 18), "MS-C-06 · Marmoreal · черновик из трёх ходов: Ok / нужен буст / конфликт", 18, bold=True)
    rows = [
        (f"1  Medusa      {st.medusa} → {d1}   3/3", "#F2ECDE", True, HEROES["medusa"]["avatar"]),
        (f"2  Harpies 1   {h_a} → {d2}   {len(p2)}/3 · нужно +{len(p2) - 3}", "#FFC857", True, SIDEKICKS["harpy"]["portrait"]),
        (f"3  Harpies 2   {h_b} → {p3_dest}   ход больше недопустим", ERR, True, SIDEKICKS["harpy"]["portrait"]),
        (f"—  Harpies 3   {st.harpies[2]}: не ходит", "#9EA3B2", False, SIDEKICKS["harpy"]["portrait"]),
        ("Буст: нет", "#F2ECDE", False, None),
    ]
    cv.panel((16, 80, 500, 400), rows, title="Манёвр · карта добрана · отменить манёвр нельзя")
    cv.button((32, 410, 248, 448), "Отменить шаг (Backspace)")
    cv.button((256, 410, 484, 448), "Сбросить черновик (Esc)")
    cv.button((32, 458, 484, 500), "Подтвердить: 3 бойца (Enter)", enabled=False)
    cv.text((32, 510), "Подтвердить нельзя:", 14, "#F2ECDE", True)
    cv.text((32, 534), f"• Harpies 1: нужен буст +{len(p2) - 3}", 14, "#FFC857", True)
    cv.text((32, 558), "• Harpies 2: ход больше недопустим (цель займёт Medusa)", 14, ERR, True)
    return cv.final(), {"moves": [[st.medusa, d1, "Ok"], [h_a, d2, f"NeedBoost +{len(p2) - 3}"], [h_b, p3_dest, "Conflict"]]}


def scene_errors():
    """MS-C-07: refusal X + stop + why text; enemy block with lock; immobilized harpy."""
    b = Board("marmoreal")
    st = Setup(b)
    color = PLATE["gold"]
    cv = Canvas(b, pad=(470, 70, 0, 20))
    dist, base, boost, blocked = reach_tiers(b, st, st.medusa, 3, 4)
    draw_reach(cv, st, color, base, boost, blocked, 3)
    db = b.reach(st.medusa, 10 ** 6, st.p2)  # same blocking rules as the server (enemies are walls)
    free = [s for s in b.spaces if s not in st.occupied()]
    far = sorted((s for s in free if db.get(s, 0) >= 8), key=lambda s: (-db[s], s))
    unreachable = far[0] if far else sorted((s for s in free if s not in db))[0]
    immob = st.harpies[2]
    draw_figures(cv, st, selected=st.medusa, grey={immob})
    draw_boost_chips(cv, dist, boost, 3)
    cv.glyph_x(unreachable)
    c = cv.c(unreachable)
    need = db.get(unreachable)
    why = f"Не хватает шагов: нужно {need}, есть 7" if need else "Туда не пройти"
    cv.plate_text((c[0], c[1] + 58 * cv.u), why, 28)
    for e in blocked:
        ce = cv.c(e)
        cv.ic("enemy", (ce[0] + 36 * cv.u, ce[1] - 36 * cv.u), 30)
    ci = cv.c(immob)
    cv.ic("immobilized", (ci[0], ci[1] - 38 * cv.u), 30)
    cv.text((20, 18), "MS-C-07 · Marmoreal · отказ, блок врагом, обездвиженный боец", 18, bold=True)
    cv.panel((16, 80, 450, 360), [
        (f"Medusa  {st.medusa} · выбрана", "#F2ECDE", True, HEROES["medusa"]["avatar"]),
        (f"Harpies 3: не может двигаться", "#7C8090", False, SIDEKICKS["harpy"]["portrait"]),
        (f"Клик {unreachable}: {why}", ERR, True, None),
        (f"Наведение на врага: «Здесь враг»", "#F2ECDE", False, None),
    ], title="Причины отказа (why.*)")
    return cv.final(), {"unreachable": unreachable, "graphDistance": need, "immobilized": immob, "blocked": blocked}


def scene_opponent():
    """MS-C-08: P1 view after King Arthur's maneuver (move 2 + boost 2 = 4 steps): V-14 origin, V-15 trail and destination."""
    b = Board("sarpedon")
    st = Setup(b)
    cv = Canvas(b, pad=(0, 70, 0, 120))
    origin = st.arthur
    dist = b.reach(origin, 4, st.p1)
    dests = sorted(s for s, v in dist.items() if v == 4 and s not in st.occupied())
    dest = dests[0]
    path = b.path(dist, origin, dest, st.occupied() - {origin})
    st.p2 = {dest, st.merlin}
    st.arthur = dest
    cv.outline(origin, "hex", P2S, alpha=int(255 * 0.6))
    cv.trail_dots(path[:-1], P2S)
    cv.outline(dest, "hex", P2S)
    draw_figures(cv, st)
    cv.text((20, 18), "MS-C-08 · Sarpedon · взгляд P1 после манёвра соперника (подсветка последнего хода V-14/V-15)", 18, bold=True)
    strip_y = cv.H / SS - 100
    lay = cv.layer()
    ImageDraw.Draw(lay).rounded_rectangle((40 * SS, strip_y * SS, (cv.W / SS - 40) * SS, (strip_y + 76) * SS), radius=10 * SS, fill=PANEL_BG)
    cv.comp(lay)
    cv.text((60, strip_y + 12), f"King Arthur: манёвр, буст +2 (Feint): King Arthur {origin}→{dest}", 17, "#F2ECDE", True)
    av = load(HEROES["arthur"]["avatar"]).resize((84 * SS, 84 * SS), Image.LANCZOS)
    m = Image.new("L", av.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, av.width - 1, av.height - 1), fill=255)
    av.putalpha(m)
    cv.im.alpha_composite(av, (int(cv.W - 110 * SS), int(cv.H - 96 * SS)))
    return cv.final(), {"origin": origin, "dest": dest, "path": path}


def scene_sheet(colour_key: str):
    """MS-C-01: states V-01..V-16 + V-04b on crops of real Marmoreal spaces."""
    b = Board("marmoreal")
    st = Setup(b)
    color = PLATE[colour_key]
    tile, cols = 300, 6
    states = ["V-01", "V-02", "V-03", "V-04", "V-04b", "V-05", "V-06", "V-07", "V-08",
              "V-09", "V-10", "V-11", "V-12", "V-13", "V-14", "V-15", "V-16"]
    names = {"V-01": "Достижимо (база)", "V-02": "Только с бустом", "V-03": "На пути", "V-04": "Цель хода",
             "V-04b": "Цель, нужен буст", "V-05": "Старт выбранного", "V-06": "Союзник (сквозь)", "V-07": "Враг (блок)",
             "V-08": "Отказ", "V-09": "Конфликт хода", "V-10": "Отправлено", "V-11": "Pending MOVE",
             "V-12": "Pending PLACE", "V-13": "Подсказка", "V-14": "Последний ход: откуда", "V-15": "Последний ход: куда",
             "V-16": "Угроза"}
    rows = math.ceil(len(states) / cols)
    sheet = Image.new("RGB", (cols * tile, rows * (tile + 40) + 60), (13, 15, 21))
    dsh = ImageDraw.Draw(sheet)
    dsh.text((16, 16), f"MS-C-01 · состояния подложки и значки v2 (язык карт) · Marmoreal · plate {color}", font=ImageFont.truetype(FONT_B, 22), fill=(242, 236, 222))
    empty = [s for s in sorted(b.spaces) if s not in st.occupied()]
    for i, v in enumerate(states):
        occupied_state = v in ("V-05", "V-06", "V-07", "V-15")
        if v == "V-07":
            sid = st.arthur
        elif v in ("V-05", "V-15"):
            sid = st.medusa
        elif v == "V-06":
            sid = st.harpies[0]
        else:
            sid = empty[(i * 3) % len(empty)]
        x, y = b.spaces[sid]["layout"]["x"], b.spaces[sid]["layout"]["y"]
        half = 66
        cv = Canvas(b, crop=(x - half, y - half, x + half, y + half))
        u = cv.u
        if v == "V-01":
            cv.plate_fill(sid, color); cv.plate_ring(sid, color)
        elif v == "V-02":
            cv.plate_ring(sid, color, dash=(12, 0.6)); cv.chip_top(sid, "+2")
        elif v == "V-03":
            c = cv.c(sid)
            lay = cv.layer(); d = ImageDraw.Draw(lay)
            d.line([(0, c[1]), (cv.W, c[1])], fill=rgba(KEY), width=int(8 * u)); d.line([(0, c[1]), (cv.W, c[1])], fill=rgba(color), width=int(5 * u))
            d.ellipse((c[0] - 5.5 * u, c[1] - 5.5 * u, c[0] + 5.5 * u, c[1] + 5.5 * u), fill=rgba(KEY))
            d.ellipse((c[0] - 4 * u, c[1] - 4 * u, c[0] + 4 * u, c[1] + 4 * u), fill=rgba(color)); cv.comp(lay)
        elif v in ("V-04", "V-04b", "V-10"):
            alpha = 178 if v == "V-10" else 255
            cv.plate_fill(sid, color); cv.plate_ring(sid, color, dash=(12, 0.6) if v == "V-04b" else None, alpha=alpha)
            cv.plate_ring(sid, color, center=26.0, width=3.0, alpha=alpha)
            cv.mini(sid, HEROES["medusa"]["mini"], ghost=True, scale=0.75)
            cv.order_badge(sid, 1)
            if v == "V-04b":
                cv.chip_top(sid, "+3")
            if v == "V-10":
                cv.ic("sent", (cv.c(sid)[0] + 40 * u, cv.c(sid)[1] - 38 * u), 30)
        elif v == "V-05":
            cv.team_ring(sid, 1); cv.leader_diamond(sid, 1)
            c = cv.c(sid); lay = cv.layer()
            ImageDraw.Draw(lay).ellipse((c[0] - 31 * u, c[1] - 31 * u, c[0] + 31 * u, c[1] + 31 * u), outline=rgba(RIM), width=int(1.6 * u)); cv.comp(lay)
            cv.mini(sid, HEROES["medusa"]["mini"], scale=0.75)
        elif v == "V-06":
            cv.plate_ring(sid, color, center=36.0, width=1.6, kl=0.8, dash=(16, 0.5), alpha=153)
            cv.token(sid, SIDEKICKS["harpy"]["portrait"], 1)
            cv.ic("ally", (cv.c(sid)[0] + 38 * u, cv.c(sid)[1] - 38 * u), 30)
        elif v == "V-07":
            cv.enemy_hatch(sid, color); cv.team_ring(sid, 2); cv.leader_diamond(sid, 2)
            cv.mini(sid, HEROES["arthur"]["mini"], scale=0.75)
            cv.ic("enemy", (cv.c(sid)[0] + 38 * u, cv.c(sid)[1] - 38 * u), 30)
        elif v == "V-08":
            cv.glyph_x(sid)
        elif v == "V-09":
            cv.plate_ring(sid, ERR, dash=(12, 0.6)); cv.plate_ring(sid, ERR, center=26.0, width=3.0, dash=(10, 0.6))
            cv.ic("conflict", cv.c(sid), 24)
        elif v == "V-11":
            cv.plate_fill(sid, color, frac=0.10); cv.plate_ring(sid, color, dash=(6, 0.6))
            cv.ic("pending-move", cv.c(sid), 34)
        elif v == "V-12":
            cv.plate_ring(sid, color, dash=(6, 0.6))
            cv.ic("pending-place", cv.c(sid), 34)
        elif v == "V-13":
            cv.ic("hint", (cv.c(sid)[0] + 38 * u, cv.c(sid)[1] - 38 * u), 30)
        elif v == "V-14":
            cv.outline(sid, "hex", P2S, alpha=153)
        elif v == "V-15":
            cv.outline(sid, "circle", P1S); cv.team_ring(sid, 1); cv.leader_diamond(sid, 1)
            cv.mini(sid, HEROES["medusa"]["mini"], scale=0.75)
        elif v == "V-16":
            cv.brackets(sid, P2S)
            cv.ic("threat", (cv.c(sid)[0] - 38 * u, cv.c(sid)[1] - 38 * u), 28, "2")
        img = cv.final().resize((tile, tile), Image.LANCZOS)
        gx, gy = (i % cols) * tile, 60 + (i // cols) * (tile + 40)
        sheet.paste(img, (gx, gy))
        dsh.text((gx + 10, gy + tile + 8), f"{v} {names[v]}", font=ImageFont.truetype(FONT_B, 17), fill=(242, 236, 222))
    return sheet, {"plate": color, "states": states}


def scene_icons():
    """MS-C-09: icon set v2 next to real RU cards (the source of the visual language)."""
    items = [("boost", "+2", "V-02/V-04b · чип буста = круг BOOST карты"), ("order", "1", "V-04 · порядок хода = лента карты, P1"),
             ("order-p2", "2", "V-04 · порядок хода, P2"), ("refuse", None, "V-08 · отказ (красный только тут и у «!»)"),
             ("conflict", None, "V-09 · конфликт хода"), ("enemy", None, "V-07 · враг, путь закрыт"),
             ("ally", None, "V-06 · союзник, можно пройти сквозь"), ("sent", None, "V-10 · отправлено"),
             ("pending-move", None, "V-11 · выбор эффекта MOVE"), ("pending-place", None, "V-12 · выбор эффекта PLACE"),
             ("hint", None, "V-13 · подсказка хода"), ("threat", "2", "V-16 · угроза: врагов в досягаемости"),
             ("immobilized", None, "не может двигаться"), ("attack-from", "1", "MS-R-14 · отсюда можно атаковать")]
    W, H = 1900, 980
    im = Image.new("RGBA", (W * SS, H * SS), CI.NAVY_2)
    cv = Canvas.__new__(Canvas)
    cv.im, cv.W, cv.H, cv.u = im, W * SS, H * SS, 1.0
    cv.text((24, 18), "MS-C-09 · значки подбора хода v2 в языке карт Unmatched (Bahnschrift Bold Condensed, navy #061623, крем #F9EBDB)",
            20, "#F9EBDB", True)
    for i, (name, num, label) in enumerate(items):
        col, row = i % 2, i // 2
        x, y = 40 + col * 560, 90 + row * 120
        cv.ic(name, (x * SS, (y + 30) * SS), 56, num, anchor="lm")
        cv.text((x + 150, y + 18), label, 18, "#F9EBDB")
        cv.plate_text(((x + 150) * SS, (y + 60) * SS), f"{name}", 24, anchor="lm")
    cards = json.loads((ROOT / "art/imagegen/mvp-v1/reused-cardart.json").read_text(encoding="utf-8"))["cards"]
    by = {c["title"]: c for c in cards if c["stableContentKey"].startswith("medusa:")}
    x = 1170
    for j, t in enumerate(["Gaze of Stone", "Hiss and Slither", "Snipe", "A Momentary Glance"]):
        card = load(by[t]["ru"]["path"]).resize((330 * SS, 458 * SS), Image.LANCZOS)
        cv.im.alpha_composite(card, (int((x + (j % 2) * 350) * SS), int((90 + (j // 2) * 478) * SS)))
    return cv.final(), {"icons": [i[0] for i in items], "source": "RU card faces of Medusa (reused-cardart.json)"}


# ---------------------------------------------------------------- main
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("MS-C-01a", lambda: scene_sheet("gold")),
        ("MS-C-01b", lambda: scene_sheet("teal")),
        ("MS-C-02a", lambda: scene_reach("marmoreal", "gold", "MS-C-02a")),
        ("MS-C-02b", lambda: scene_reach("marmoreal", "teal", "MS-C-02b")),
        ("MS-C-03a", lambda: scene_reach("sarpedon", "gold", "MS-C-03a")),
        ("MS-C-03b", lambda: scene_reach("sarpedon", "teal", "MS-C-03b")),
        ("MS-C-04", scene_closeup),
        ("MS-C-05", scene_boost),
        ("MS-C-06", scene_multi),
        ("MS-C-07", scene_errors),
        ("MS-C-08", scene_opponent),
        ("MS-C-09", scene_icons),
    ]
    manifest = {"schema": "unmatched.move-selection-mockups/2", "generator": "tools/art/move_selection/build_mockups.py",
                "policy": "ENV-U3: images derive from scraped map/hero/card art and stay out of git; only sha256 is recorded",
                "spec": ["docs/game-design/move-selection/03-ux-spec.md", "docs/game-design/move-selection/04-technical-design.md"],
                "items": []}
    thumbs = []
    for mid, fn in jobs:
        img, meta = fn()
        p = OUT / f"{mid}.png"
        img.save(p, optimize=True)
        g = ImageOps.grayscale(img).convert("RGB")
        pg = OUT / f"{mid}-gray.png"
        g.save(pg, optimize=True)
        manifest["items"].append({"id": mid, "file": str(p.relative_to(ROOT)).replace("\\", "/"), "size": list(img.size),
                                  "sha256": sha(p), "gray": str(pg.relative_to(ROOT)).replace("\\", "/"), "graySha256": sha(pg),
                                  "facts": meta})
        thumbs.append((mid, img, g))
        print(mid, img.size)
    manifest["inputs"] = sorted(USED_INPUTS)
    manifest["inputSha256"] = {rel: sha(ROOT / rel) for rel in sorted(USED_INPUTS)}
    tw = 760
    rows = []
    for mid, img, g in thumbs:
        f = tw / img.width
        a = img.resize((tw, int(img.height * f)), Image.LANCZOS)
        bimg = g.resize((tw, int(img.height * f)), Image.LANCZOS)
        rows.append((mid, a, bimg))
    H = sum(r[1].height + 40 for r in rows)
    cs = Image.new("RGB", (2 * tw + 30, H), (13, 15, 21))
    d = ImageDraw.Draw(cs)
    y = 0
    for mid, a, bimg in rows:
        d.text((10, y + 8), mid, font=ImageFont.truetype(FONT_B, 20), fill=(242, 236, 222))
        cs.paste(a, (0, y + 36))
        cs.paste(bimg, (tw + 30, y + 36))
        y += a.height + 40
    cs.save(OUT / "contact-sheet.png", optimize=True)
    manifest["contactSheet"] = {"file": "scraped-data/derived/move-selection/contact-sheet.png", "sha256": sha(OUT / "contact-sheet.png")}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("ok", OUT)


if __name__ == "__main__":
    main()
