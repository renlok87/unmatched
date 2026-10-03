#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Эталонный рендер движения значков v3 по контракту icon-motion.json (как его сыграет UE).

    python art/imagegen/hud-icons-v3/_tools/motion.py            # всё: листы, GIF, ролик MP4, index.html
    python art/imagegen/hud-icons-v3/_tools/motion.py --only state-sent,action-attack

Как в UE: каждый слой — текстура точного размера (sizes/, layers/), поза из icon_motion.Animator, аффинное
преобразование «слой → корень» с билинейной выборкой, непрозрачность корня × слоя. Сценарий — demo из контракта
(тот же играет галерея UE -S08IconGallery). Всё — функция t; повторный запуск даёт те же кадры.

Выход в sheets/motion/:
  frames-<id>.png        12 кадров сценария (96 px и 32 px ×3), строка reduced motion под обычной;
  <id>.gif               сценарий целиком, 50 к/с, 96 / 48 / 32 px на панели;
  <id>-reduced.gif       то же при reduced motion;
  reel.mp4, reel-reduced.mp4   все 23 значка сеткой, 60 к/с (нужен ffmpeg);
  index.html             страница просмотра: GIF всех значков и ролики.
"""
from __future__ import annotations

import io
import math
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import draw_icons as D  # noqa: E402
import icon_motion as M  # noqa: E402

OUT = os.path.join(D.ROOT, "sheets", "motion")
TEAM_DEMO = D.C["team1"]
PANEL = D.PANEL


# ------------------------------------------------------------------------------------------------ текстуры
_cache = {}


def texture(src, frame, size):
    name = src
    if src.endswith("#"):
        name = f"{src[:-1]}_f{int(frame):02d}"
    key = (name, size)
    if key not in _cache:
        sub = "layers" if "_" in name else "sizes"
        path = os.path.join(D.ROOT, sub, f"{name}-{size}.png")
        _cache[key] = Image.open(path).convert("RGBA")
    return _cache[key]


def affine(pose, pivot_u, px_per_u):
    """3×3: p → pivot + R(θ)·diag(s·sx, s·sy)·(p − pivot) + t (в px)."""
    s = pose["scale"]
    sx, sy = s * pose["scale_x"], s * pose["scale_y"]
    th = math.radians(pose["rotate"])
    c, si = math.cos(th), math.sin(th)
    px, py = pivot_u[0] * px_per_u, pivot_u[1] * px_per_u
    tx, ty = pose["tx"] * px_per_u, pose["ty"] * px_per_u
    a, b = c * sx, -si * sy
    d, e = si * sx, c * sy
    return np.array([[a, b, px + tx - (a * px + b * py)],
                     [d, e, py + ty - (d * px + e * py)],
                     [0, 0, 1.0]])


def compose(anim, pp, size):
    """Кадр значка (RGBA) размера size по позе pp."""
    cw, ch = anim.d["canvas_u"]
    k = size / 32.0
    pad = round(0.25 * size)                  # как в UE: трансформ рисует за границей виджета (клип выключен)
    W, H = round(size * cw / 32) + 2 * pad, round(size * ch / 32) + 2 * pad
    pose, pivots = pp["pose"], pp["pivot"]
    shift = np.array([[1, 0, pad], [0, 1, pad], [0, 0, 1.0]])
    A_all = shift @ affine(pose["all"], anim.pivot_of("all", pivots), k)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for l in anim.d["layers"]:
        lp = pose[l["id"]]
        op = pose["all"]["opacity"] * lp["opacity"]
        if op <= 1e-4:
            continue
        tex = texture(l["src"], lp["frame"], size)
        if l.get("tint") == "team":
            arr = np.asarray(tex).astype(np.float32)
            arr[..., :3] *= np.array(TEAM_DEMO, dtype=np.float32)
            tex = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")
        Mx = A_all @ affine(lp, anim.pivot_of(l["id"], pivots), k)
        if abs(np.linalg.det(Mx[:2, :2])) < 1e-6:      # масштаб 0 — слоя не видно (так же в UE)
            continue
        inv = np.linalg.inv(Mx)
        im = tex.transform((W, H), Image.AFFINE, data=tuple(inv[:2].ravel()), resample=Image.BILINEAR)
        if op < 1.0:
            im.putalpha(im.getchannel("A").point(lambda v, o=op: int(v * o + 0.5)))
        out.alpha_composite(im)
    return out


def frames_for(icon, reduced, times, sizes):
    c = M.load_contract()
    rows, total = M.run_demo(c, icon, reduced, times)
    res = []
    for t, (pp, visible), anim in rows:
        res.append((t, {s: (compose(anim, pp, s) if visible else None) for s in sizes}))
    return res, total


def on_panel(im, w, h):
    bg = Image.new("RGBA", (w, h), PANEL)
    if im is not None:
        bg.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return bg


# ------------------------------------------------------------------------------------------------ листы и GIF
def key_times(c, icon, reduced, total, n=12):
    """12 моментов сценария, привязанных к командам (а не равномерно): у каждой анимации — доли её длительности,
    у цикла — четверти периода; так на листе видны и события, и удар цикла."""
    base = c["icons"][c.get("variants", {}).get(icon, icon)]
    sched, _ = M.demo_schedule(c, icon, reduced)

    def dur(name):
        a = base["anims"][name]
        br = a.get("reduced") if reduced else None
        return float((br or a)["duration_ms"])

    want = []
    for t0, op in sched:
        d = dur(op)
        if op == "appear":
            want += [t0, t0 + 0.35 * d, t0 + d]
            if "cycle" in base["anims"]:
                cd = dur("cycle")
                if cd > 0:
                    want += [t0 + d + f * cd for f in (0.2, 0.4, 0.55, 0.7, 0.85)]
        elif op == "leave":
            want += [t0 + 0.5 * d]
        else:
            want += [t0 + 0.3 * d, t0 + 0.7 * d] if d > 0 else [t0]
    want = sorted({round(min(max(w, 0.0), total * 0.995)) for w in want})
    if len(want) > n:
        idx = [round(i * (len(want) - 1) / (n - 1)) for i in range(n)]
        want = [want[i] for i in idx]
    while len(want) < n:
        gaps = [(b - a, i) for i, (a, b) in enumerate(zip(want, want[1:]))] or [(total, 0)]
        g, i = max(gaps)
        want.insert(i + 1, round(want[i] + g / 2) if len(want) > 1 else round(total / 2))
    return want


def padded(s, wide):
    """Размер кадра compose() для стороны s: холст значка + поле 0,25 s с каждой стороны."""
    p = round(0.25 * s)
    return (2 * s if wide else s) + 2 * p, s + 2 * p


def frame_sheet(icon, c):
    _, total = M.demo_schedule(c, icon, False)
    _, total_r = M.demo_schedule(c, icon, True)
    wide = c["icons"][c.get("variants", {}).get(icon, icon)]["canvas_u"][0] > 32
    big, small = 96, 32
    bw, bh = padded(big, wide)
    sw, sh = padded(small, wide)
    cw = bw + 16 + sw * 3 + 16
    ch = max(bh, sh * 3) + 8
    n = 12
    W = 20 + n * cw
    H = 60 + 2 * (ch + 36)
    sheet = Image.new("RGBA", (W, H), D.SHEET_BG)
    sched = ", ".join(f"{int(t)} {op}" for t, op in M.demo_schedule(c, icon, False)[0])
    D.paste(sheet, D.label(W, 36, f"{icon}: сценарий {int(total)} мс ({sched}); 96 px и 32 px ×3; низ — reduced motion", 15), 0, 8)
    for row, (red, tot) in enumerate(((False, total), (True, total_r))):
        times = key_times(c, icon, red, tot, n)
        frames, _ = frames_for(icon, red, times, (big, small))
        y = 60 + row * (ch + 36)
        for i, (t, ims) in enumerate(frames):
            x = 20 + i * cw
            panel = Image.new("RGBA", (cw - 8, ch), PANEL)
            if ims[big] is not None:
                D.paste(panel, ims[big], 4, (ch - bh) // 2)
                D.paste(panel, D.xN(ims[small], 3), bw + 12, (ch - sh * 3) // 2)
            D.paste(sheet, panel, x, y)
            D.paste(sheet, D.label(cw - 8, 20, f"t = {t} мс" + ("  reduced" if red else ""), 12), x, y + ch + 6)
    p = os.path.join(OUT, f"frames-{icon}.png")
    sheet.convert("RGB").save(p, optimize=True)
    return p


def gif(icon, c, reduced=False, step=20, sizes=(96, 48, 32)):
    _, total = M.demo_schedule(c, icon, reduced)
    total += 300
    times = list(range(0, int(total), step))
    frames, _ = frames_for(icon, reduced, times, sizes)
    wide = c["icons"][c.get("variants", {}).get(icon, icon)]["canvas_u"][0] > 32
    gap = 8
    W = sum(padded(s, wide)[0] for s in sizes) + gap * (len(sizes) + 1)
    H = padded(max(sizes), wide)[1] + 2 * gap
    pal_frames = []
    for t, ims in frames:
        bg = Image.new("RGBA", (W, H), PANEL)
        x = gap
        for s in sizes:
            w, h = padded(s, wide)
            if ims[s] is not None:
                bg.alpha_composite(ims[s], (x, (H - h) // 2))
            x += w + gap
        pal_frames.append(bg.convert("RGB"))
    # общая палитра на весь GIF — без мерцания цветов между кадрами
    strip = Image.new("RGB", (W, H * min(len(pal_frames), 24)))
    for i in range(min(len(pal_frames), 24)):
        strip.paste(pal_frames[i * len(pal_frames) // min(len(pal_frames), 24)], (0, i * H))
    pal = strip.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in pal_frames]
    p = os.path.join(OUT, f"{icon}{'-reduced' if reduced else ''}.gif")
    q[0].save(p, save_all=True, append_images=q[1:], duration=step, loop=0, disposal=1, optimize=False)
    return p


# ------------------------------------------------------------------------------------------------ ролик
def reel(c, reduced=False, fps=60, size=96, cols=6):
    ff = shutil.which("ffmpeg") or os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe")
    if not os.path.exists(ff):
        print("ffmpeg не найден — ролик пропущен")
        return None
    icons = c["order"]
    totals = {i: M.demo_schedule(c, i, reduced)[1] + 400 for i in icons}
    length = max(totals.values())
    n = int(length / 1000 * fps)
    pw, ph = padded(size, True)
    cell_w, cell_h = pw + 8, ph + 32
    rows = math.ceil(len(icons) / cols)
    W, H = cols * cell_w + 24, rows * cell_h + 24
    W += W % 2
    H += H % 2
    labels = {i: D.label(cell_w - 8, 22, i, 13) for i in icons}
    anims = {}
    scheds = {}
    for i in icons:
        scheds[i] = M.demo_schedule(c, i, reduced)[0]
        anims[i] = None
    tmp = os.path.join(OUT, "_reel_tmp")
    os.makedirs(tmp, exist_ok=True)
    for f in range(n):
        t_global = f * 1000.0 / fps
        frame = Image.new("RGBA", (W, H), D.SHEET_BG)
        for idx, icon in enumerate(icons):
            t = t_global % totals[icon]
            if anims[icon] is None or t < anims[icon][1]:
                anims[icon] = [M.Animator(c, icon, reduced), t, 0]
            a, _, si = anims[icon]
            sched = scheds[icon]
            while si < len(sched) and sched[si][0] <= t:
                a.play(sched[si][1], sched[si][0])
                si += 1
            anims[icon][1], anims[icon][2] = t, si
            pp, vis = a.pose(t)
            x = 12 + (idx % cols) * cell_w
            y = 12 + (idx // cols) * cell_h
            cell = Image.new("RGBA", (cell_w - 8, ph), PANEL)
            if vis:
                im = compose(a, pp, size)
                cell.alpha_composite(im, ((cell.width - im.width) // 2, (ph - im.height) // 2))
            frame.alpha_composite(cell, (x, y))
            frame.alpha_composite(labels[icon], (x, y + ph + 4))
        frame.convert("RGB").save(os.path.join(tmp, f"{f:05d}.png"))
    out = os.path.join(OUT, f"reel{'-reduced' if reduced else ''}.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def index_html(c):
    rows = []
    for icon in c["order"]:
        d = c["icons"][icon]
        names = ", ".join(d["anims"].keys())
        rows.append(f'<figure><figcaption><b>{icon}</b><br><small>{names}</small></figcaption>'
                    f'<img src="{icon}.gif" alt="{icon}"><img class="r" src="{icon}-reduced.gif" alt="{icon} reduced"></figure>')
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Движение значков v3</title><style>
:root{{--bg:#1e2028;--panel:#161a28;--fg:#ece6dc;--mut:#9a958c}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;padding:16px}}
h1{{font-size:20px;margin:0 0 4px}} p{{color:var(--mut);margin:0 0 16px;max-width:900px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}}
figure{{margin:0;background:var(--panel);border-radius:8px;padding:10px}} img{{display:block;max-width:100%;margin-top:6px}}
img.r{{opacity:.85}} small{{color:var(--mut)}} video{{max-width:100%;border-radius:8px;margin:8px 0 20px}}
</style></head><body>
<h1>Движение значков HUD v3</h1>
<p>Эталон по контракту <code>docs/unreal/contracts/hud/icon-motion.json</code>: так же сыграет UE. В каждой карточке верхний GIF — обычное
движение (96 / 48 / 32 px), нижний — reduced motion. Сценарий значка — поле <code>demo</code> контракта.</p>
<video src="reel.mp4" controls loop muted autoplay playsinline></video>
<div class="grid">{''.join(rows)}</div>
<h1 style="margin-top:20px">Reduced motion</h1><video src="reel-reduced.mp4" controls loop muted playsinline></video>
</body></html>"""
    p = os.path.join(OUT, "index.html")
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return p


def build(only=None):
    os.makedirs(OUT, exist_ok=True)
    c = M.load_contract()
    icons = only or c["order"]
    for icon in icons:
        print(frame_sheet(icon, c))
        print(gif(icon, c, False))
        print(gif(icon, c, True))
    if not only:
        for stale in os.listdir(OUT):
            if stale.startswith("frames-transitions") or stale.endswith(".gif") and stale[:-4].replace("-reduced", "") not in c["order"]:
                os.remove(os.path.join(OUT, stale))
        print(reel(c, False))
        print(reel(c, True))
        print(index_html(c))


if __name__ == "__main__":
    args = sys.argv[1:]
    only = args[args.index("--only") + 1].split(",") if "--only" in args else None
    build(only)
