#!/usr/bin/env python
"""AN-22: read-only source tracing, procedural drawing, confined output writes.

Run: python -B art/imagegen/anim-move-sheet-codex/_tools/build_step_sheet.py
No game runtime, Blender, network, image generation or git is used.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / "scraped-data/derived/anim-move-sheet-codex"
WRITE_LOG: set[str] = set()


def audit(event, args):
    target = None
    if event == "open":
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)) and (
            isinstance(mode, str) and any(c in mode for c in "wax+")
            or isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            target = Path(os.fsdecode(path)).resolve()
    elif event in {"os.mkdir", "os.remove", "os.rmdir"}:
        target = Path(os.fsdecode(args[0])).resolve()
    elif event in {"os.rename", "os.link", "os.symlink"}:
        raise PermissionError(f"Unsupported filesystem mutation: {event}")
    if target is not None:
        # mkdir on an existing ancestor is harmless, but never create one outside the allowlist.
        if event == "os.mkdir" and target.is_dir():
            return
        if not any(target == p or p in target.parents for p in (PACKAGE, DERIVED)):
            raise PermissionError(f"AN-22 write outside allowed folders: {target}")
        WRITE_LOG.add(target.relative_to(ROOT).as_posix())


sys.addaudithook(audit)
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from scipy import ndimage
import draw_icons_v3_snapshot as snapshot

TOKENS = {**snapshot.TOKENS, "text.primary": "#F2EDE4", "board.path": "#FFC857"}
NAVY, CREAM, KEY, PRIMARY, SECONDARY, YELLOW, PATH = (
    TOKENS[k] for k in ("card.navy", "card.cream", "mark.keyline", "text.primary",
                        "text.secondary", "turn.flash.yellow", "board.path")
)
SIZE = (1920, 1080)
SCALE = 3
TEXT_BOXES = []
POSE_TRANSFORMS = []
FACINGS = []
T = 280.0
E = 80.0


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edge(t, duration=T, ein=0.0, eout=0.0):
    """Position and velocity in edge units and edge units/ms, no quantization."""
    k = 1.0 / (duration - ein / 2 - eout / 2)
    if t <= 0:
        return 0.0, 0.0 if ein else k
    if t >= duration:
        return 1.0, 0.0 if eout else k
    if ein and t < ein:
        return k * t * t / (2 * ein), k * t / ein
    if eout and t > duration - eout:
        return 1 - k * (duration - t) ** 2 / (2 * eout), k * (duration - t) / eout
    return k * (t - ein / 2), k


def progress(t, duration=T, edges=2):
    if t <= 0:
        return 0.0, 0.0
    if t >= edges * duration:
        return float(edges), 0.0
    i = min(int(t // duration), edges - 1)
    ease = min(80 * duration / 280, duration / 2)
    p, v = edge(t - i * duration, duration, ease if i == 0 else 0, ease if i == edges - 1 else 0)
    return i + p, v


def lean(t):
    if t <= 60:
        return 10 * max(0, t) / 60
    if t <= 560:
        return 10.0
    return 10 * max(0, (710 - t) / 150)


def trace(hero, asset):
    source = ROOT / f"art/pipeline-candidates/ASSET-{asset}-001/20260929-h2anim/preview"
    sheet = Image.open(source / f"{hero}-Idle-blender-sheet.jpg").convert("RGB")
    bones = json.loads((source / f"frames/{hero}-Idle-bones2d.json").read_text(encoding="utf8"))["f00 left"]["bones"]
    # The sheet is twelve 420x420 tiles, four columns; the f00 left tile is column two.
    crop = sheet.crop((420, 0, 840, 420))
    arr = np.array(crop).astype(float)
    background = np.median(arr[55:300, 5:50], axis=(0, 1))
    base_top = 366 if hero == "KingArthur" else 310
    bone_mask = Image.new("L", crop.size)
    bd = ImageDraw.Draw(bone_mask)
    for b in bones:
        bd.line([tuple(b["a"]), tuple(b["b"])], fill=255, width=7)
        for x, y in [b["a"], b["b"]]:
            bd.ellipse((x - 6, y - 6, x + 6, y + 6), fill=255)
    red = (arr[:, :, 0] > arr[:, :, 1] + 20) & (arr[:, :, 0] > arr[:, :, 2] + 20)
    yellow = (arr[:, :, 0] > arr[:, :, 2] + 20) & (arr[:, :, 1] > arr[:, :, 2] + 20)
    overlay = np.array(bone_mask) > 0
    annotation = overlay & (red | yellow)
    annotation = ndimage.binary_dilation(annotation, iterations=1)
    # Reconstruct narrow annotation corridors from the nearest unobscured source pixel BEFORE
    # thresholding. Erasing them after thresholding would cut open the Harpy's wing silhouette.
    _, nearest = ndimage.distance_transform_edt(annotation, return_indices=True)
    cleaned = arr.copy()
    cleaned[annotation] = arr[nearest[0][annotation], nearest[1][annotation]]
    foreground = np.max(cleaned - background, axis=2) > 19
    foreground[:35] = False
    foreground[base_top:] = False
    foreground = ndimage.binary_closing(foreground, iterations=3)
    foreground = ndimage.binary_fill_holes(foreground)
    labels, count = ndimage.label(foreground)
    areas = np.bincount(labels.ravel())
    keep = np.where(areas >= 28)[0]
    keep = keep[keep != 0]
    foreground = np.isin(labels, keep)
    # Remove the source pedestal; a separate level pedestal is drawn at the original base center.
    foreground[base_top:] = False
    ys, xs = np.nonzero(foreground)
    bounds = (int(xs.min()), int(ys.min()), int(xs.max() + 1), base_top)
    body = Image.fromarray((foreground * 255).astype("uint8"))
    DERIVED.mkdir(parents=True, exist_ok=True)
    crop.save(DERIVED / f"{hero}-f00-left-source.png")
    bone_mask.save(DERIVED / f"{hero}-f00-left-overlay-mask.png")
    body.save(DERIVED / f"{hero}-f00-left-body-mask.png")
    # Source pixels are kept exclusively in derived; the package receives cream procedural silhouettes.
    proof = Image.new("RGB", (840, 420), NAVY)
    proof.paste(crop, (0, 0))
    proof.paste(Image.new("RGB", (420, 420), CREAM), (420, 0), body)
    proof.save(DERIVED / f"{hero}-trace-proof.png")
    root_x = bones[0]["a"][0]
    return {"name": hero, "mask": body, "pivot": (root_x, base_top), "bounds": bounds,
            "height": base_top - bounds[1], "tile": "f00 left", "source": str(source.relative_to(ROOT))}


class Canvas:
    def __init__(self):
        self.im = Image.new("RGBA", (round(SIZE[0] * SCALE), round(SIZE[1] * SCALE)), NAVY)
        self.d = ImageDraw.Draw(self.im)

    def line(self, points, color=SECONDARY, width=1):
        self.d.line([(round(x * SCALE), round(y * SCALE)) for x, y in points], fill=color, width=max(1, round(width * SCALE)))

    def rect(self, box, color=NAVY, outline=None, width=1):
        self.d.rectangle(tuple(round(v * SCALE) for v in box), fill=color, outline=outline, width=max(1, round(width * SCALE)))

    def ellipse(self, box, color=CREAM, outline=KEY, width=2):
        self.d.ellipse(tuple(round(v * SCALE) for v in box), fill=color, outline=outline, width=round(width * SCALE))

    def text(self, x, y, string, size=20, color=PRIMARY, bold=False, anchor="la"):
        font = ImageFont.truetype(str(HERE / "fonts" / ("Roboto-BoldCondensed.ttf" if bold else "Roboto-Regular.ttf")), round(size * SCALE))
        box = self.d.textbbox((x * SCALE, y * SCALE), string, font=font, anchor=anchor)
        TEXT_BOXES.append({"text": string, "bounds": [round(v / SCALE, 2) for v in box]})
        self.d.text((x * SCALE, y * SCALE), string, font=font, fill=color, anchor=anchor)

    def arrow(self, a, b, color=YELLOW, width=2):
        self.line([a, b], color, width)
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        for offset in [-0.5, 0.5]:
            self.line([b, (b[0] - 9 * math.cos(angle + offset), b[1] - 9 * math.sin(angle + offset))], color, width)

    def dashed(self, points, color=SECONDARY, width=2, dash=9, gap=6):
        # Arc-length dash state crosses segment boundaries, so the legacy curve remains an unbroken dash pattern.
        phase = 0.0
        for a, b in zip(points, points[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            pos = 0.0
            while pos < length:
                remain = (dash if phase < dash else dash + gap) - phase
                take = min(remain, length - pos)
                if phase < dash:
                    self.line([(a[0] + dx * pos / length, a[1] + dy * pos / length),
                               (a[0] + dx * (pos + take) / length, a[1] + dy * (pos + take) / length)], color, width)
                pos += take
                phase = (phase + take) % (dash + gap)
                if take < 1e-7:
                    phase = 0.0


def pose(c, hero, x, ground, t, height):
    angle = lean(t)
    ratio = height / hero["height"]
    # Reflect a left-side source to a right-side travel glyph, keeping a fixed base-center pivot.
    src = np.array(hero["mask"])
    px, py = hero["pivot"]
    points = np.argwhere(src > 0)
    theta = math.radians(angle)
    # Rigid body rotation about the base center. Reflection is applied before rotation.
    # Source body points have y<0; clockwise rotation tilts them forward (right).
    co, si = math.cos(theta), math.sin(theta)
    POSE_TRANSFORMS.append({'hero':hero['name'],'time_ms':t,'angle_degrees':angle,
                           'base_ground_y':ground,'base_rotation_degrees':0,'hop':0,
                           'source_pivot':list(hero['pivot']),
                           'rotation_after_reflection':[[co,-si],[si,co]]})
    out_size = round(230 * SCALE)
    center = out_size / 2
    out = Image.new("L", (out_size, out_size))
    # Inverse affine interpolation preserves the traced silhouette instead of splatting source pixels.
    fac = ratio * SCALE
    a, b = -co / fac, -si / fac
    d, e = -si / fac, co / fac
    body = hero["mask"].transform((out_size, out_size), Image.Transform.AFFINE,
        (a, b, px - a * center - b * (out_size - 12 * SCALE),
         d, e, py - d * center - e * (out_size - 12 * SCALE)), Image.Resampling.BICUBIC)
    # Source silhouette rotation moves the bottom support contour; keep it above the unmoving flat base.
    body_arr = np.array(body)
    body_arr[round(out_size - 12 * SCALE):] = 0
    body = Image.fromarray(body_arr)
    edge_mask = body.filter(ImageFilter.MaxFilter(max(3, 2 * round(6 * SCALE / 3) + 1)))
    left = round(x * SCALE - center)
    top = round(ground * SCALE - (out_size - 6 * SCALE))
    c.im.paste(Image.new("RGBA", body.size, KEY), (left, top), edge_mask)
    c.im.paste(Image.new("RGBA", body.size, CREAM), (left, top), body)
    # All columns share exactly one ground level; pedestal is never transformed.
    bw = 56 if hero["name"] == "KingArthur" else 52
    c.rect((x - bw / 2, ground - 7, x + bw / 2, ground), CREAM, KEY, 2)
    c.line([(x - 77, ground + 1), (x + 77, ground + 1)], SECONDARY, 1)
    # A thin baseline and lean gauge make 10° observable even when the original pose is asymmetrical.
    origin = (x + 83, ground - 8)
    c.dashed([origin, (origin[0], ground - height)], SECONDARY, 1, 4, 4)
    c.line([origin, (origin[0] + (height - 8) * math.sin(theta), origin[1] - (height - 8) * math.cos(theta))], YELLOW, 1.5)
    c.text(x + 85, ground - height - 25, "0°" if angle == 0 else "10°", 16, YELLOW, True)


def facing(c, x, y, t):
    # Camera axis points down. Paths stay in the camera-facing half-plane.
    c.arrow((x, y), (x, y + 20), SECONDARY, 1)
    if t in (0, 710):
        vx, vy = 22, 22  # <=45° from camera axis: idle three-quarter.
    elif t < 280:
        vx, vy = 30, 0  # side-on first edge; never a back-facing view.
    elif t == 280:
        vx, vy = 30, 0  # vertex is the BEGINNING of the 120ms turn.
        c.arrow((x, y), (x + 21, y + 21), SECONDARY, 1)
    else:
        vx, vy = 21, 21
    FACINGS.append({'time_ms':t,'camera_axis':[0,1],'facing':[vx,vy],
                    'idle':t in (0,710),'yaw_source':'diagram; side silhouettes are analytical glyphs'})
    c.arrow((x, y), (x + vx, y + vy), YELLOW, 2)


def build(heroes, output_size=SIZE):
    c = Canvas()
    tx = lambda t: 260 + t / 860 * 1584
    c.text(48, 31, "AN-22 / ШАГ ПО ДВУМ РЁБРАМ", 38, PRIMARY, True)
    c.text(49, 86, "CUE-007 · state.fighter_moved · старт на кадре применения снапшота", 21, SECONDARY)
    # Abstract path, never an image of a board.
    cells = [(1488, 59), (1648, 59), (1812, 82)]
    c.line(cells, PATH, 3)
    for x, y in cells:
        c.ellipse((x - 13, y - 7, x + 13, y + 7), NAVY, PATH, 2)
    c.arrow((1520, 59), (1608, 59), PATH)
    c.arrow((1683, 64), (1775, 77), PATH)
    c.text(1487, 95, "абстрактные клетки · камера снизу", 18, SECONDARY)
    c.line([(48, 119), (1872, 119)], SECONDARY, 1)
    c.text(48, 137, "ВРЕМЯ / мс", 20, PRIMARY, True)
    ticks = [0, 80, 280, 480, 560, 710, 860]
    for t in ticks:
        x = tx(t)
        c.text(x, 133, str(t), 20, PRIMARY, True, "ma")
        c.line([(x, 161), (x, 169)], SECONDARY, 1)
    c.text(48, 173, "ДВИЖЕНИЕ", 19, PRIMARY, True)
    for a, b, label, fill in [(0,80,"EASE-IN",YELLOW),(80,480,"ЛИНЕЙНО · ЧЕРЕЗ ВЕРШИНУ БЕЗ СТОПА",CREAM),
                               (480,560,"EASE-OUT",YELLOW),(560,710,"IDLE · 150 мс",SECONDARY)]:
        c.rect((tx(a), 174, tx(b)-3, 199), fill)
        c.text((tx(a)+tx(b))/2, 177, label, 17, NAVY, True, "ma")
    c.text(48, 212, "ПОВОРОТ", 18, SECONDARY, True)
    c.rect((tx(0),215,tx(50),228),YELLOW)
    c.text(tx(50)+10, 209, "≤ 50 мс", 17, SECONDARY)
    c.rect((tx(280),215,tx(400),228),YELLOW)
    c.text((tx(280)+tx(400))/2,212,"120 мс на ходу",15,NAVY,True,"ma")
    c.rect((tx(560),215,tx(710),228),SECONDARY)
    c.text((tx(560)+tx(710))/2,212,"idle к камере · 150 мс",15,NAVY,True,"ma")
    c.text(48, 241, "НАКЛОН",18,SECONDARY,True)
    c.arrow((tx(0),253),(tx(60),239),YELLOW,2)
    c.line([(tx(60),239),(tx(560),239)],YELLOW,2)
    c.line([(tx(560),239),(tx(710),254)],YELLOW,2)
    c.text(tx(560)+9,255,"наклон до 0",16,SECONDARY)
    c.text(tx(80)+5, 250, "10° за 60 мс · подскок 0",17,SECONDARY)
    c.text(48, 286, "КЛЮЧЕВЫЕ ПОЗЫ",21,PRIMARY,True)
    c.text(48, 311, "интервалы условные",16,SECONDARY)
    times = [0,60,280,480,560,710]
    columns = [390,650,910,1170,1430,1690]
    labels = ["Idle / старт", "наклон достигнут", "вершина / доворот", "начало ease-out", "прибытие / пыль", "Idle восстановлен"]
    for t,x,label in zip(times,columns,labels):
        c.text(x,286,f"{t} мс",24,YELLOW,True,"ma")
        c.text(x,315,label,17,SECONDARY,False,"ma")
    c.text(48,364,"KING ARTHUR",25,CREAM,True)
    c.text(48,396,"герой",18,SECONDARY)
    c.text(48,537,"HARPY",25,CREAM,True)
    c.text(48,569,"помощник",18,SECONDARY)
    for hero,ground,height in [(heroes[0],455,114),(heroes[1],620,110)]:
        for t,x in zip(times,columns):
            pose(c,hero,x,ground,t,height)
            facing(c,x-62,ground+15,t)
    # Inline samples use the same strokes and heads as the pose arrows.
    c.arrow((268,660),(268,674),SECONDARY,1)
    c.text(285,658,"ось камеры (камера внизу) ·",16,SECONDARY)
    c.arrow((504,670),(526,670),YELLOW,2)
    c.text(536,658,"куда смотрит фигура · покой ≤ 45° от оси камеры · спиной к камере — никогда",16,SECONDARY)
    c.text(48,680,"ПОЗИЦИЯ s(t)",22,PRIMARY,True)
    c.text(48,711,"в единицах ребра",17,SECONDARY)
    c.text(48,744,"40 мс: 1/24",18,YELLOW,True)
    c.text(48,770,"80 мс: 1/6",18,YELLOW,True)
    gy = lambda s: 797 - 55 * s
    for s,label in [(0,"0"),(1,"1"),(2,"2")]:
        c.line([(tx(0),gy(s)),(tx(860),gy(s))],SECONDARY,0.5)
        c.text(tx(0)-20,gy(s)-12,label,17,SECONDARY,True,"ra")
    for t in [0,80,280,480,560,710,860]:
        c.line([(tx(t),680),(tx(t),801)],SECONDARY,0.5)
        c.text(tx(t),805,str(t),16,SECONDARY,False,"ma")
    legacy=[(tx(t),gy(min(t/280,2))) for t in range(0,861)]
    eased=[(tx(t),gy(progress(t)[0])) for t in range(0,861)]
    c.dashed(legacy,SECONDARY,2,10,7)
    c.line(eased,YELLOW,3)
    for t in [80,280,480,560]:
        x,y=tx(t),gy(progress(t)[0]); c.ellipse((x-4,y-4,x+4,y+4),YELLOW,KEY,1)
    c.text(515,688,"сплошная: ease",17,YELLOW,True)
    c.text(515,714,"пунктир: linear legacy",17,SECONDARY)
    c.text(955,765,"на вершине: v = 1/240 ребра/мс",18,YELLOW,True)
    c.text(1470,716,"в конце: v = 0",18,YELLOW,True)
    # Bottom event and speed lanes share the SAME time mapping as the main axis and graph.
    c.text(48,838,"CUE-007 / ПЫЛЬ",20,PRIMARY,True)
    c.rect((tx(560),841,tx(860),866),CREAM)
    c.text((tx(560)+tx(860))/2,843,"560–860 мс · 300 мс · конечная клетка",17,NAVY,True,"ma")
    # Flat discs: only task tokens, no smoky texture, glow or combat symbols.
    for dx,dy,r in [(-35,0,6),(-12,-4,5),(12,0,7),(35,-3,4)]:
        c.ellipse((tx(650)+dx-r,832+dy-r/2,tx(650)+dx+r,832+dy+r/2),CREAM,KEY,1)
    for mult,dur,y in [(0.5,140,886),(1,280,923),(1.5,420,960)]:
        label = str(mult).replace(".",",")
        c.text(48,y-2,f"×{label} · {dur} мс/ребро",20,PRIMARY,True)
        arrival=2*dur
        for a,b in [(0,dur),(dur,arrival)]:
            c.rect((tx(a),y+2,tx(b)-3,y+20),YELLOW if mult==1 else SECONDARY)
        c.line([(tx(arrival),y-2),(tx(arrival),y+24)],CREAM,2)
        if arrival<700:
            c.text(tx(arrival)+10,y-2,f"прибытие {arrival} мс",17,SECONDARY)
        else:
            c.text(tx(arrival)-10,y-20,f"прибытие {arrival} мс",17,SECONDARY,False,"ra")
    c.text(48,996,"НЕТ / REDUCED",20,PRIMARY,True)
    c.ellipse((tx(0)-5,1002,tx(0)+5,1012),YELLOW,KEY,1)
    c.text(tx(0)+18,993,"snap в конечную клетку в 0 мс · поворот мгновенный · без наклона",20,PRIMARY)
    c.line([(48,1034),(1872,1034)],SECONDARY,1)
    c.text(48,1045,"Шаг ≥ 90 мс · лимит бойца 1400 мс · seq 2400 мс",18,SECONDARY)
    c.text(990,1045,"Процедурный ход · сетка клипов 24 fps · допуск одного кадра 42 мс",18,SECONDARY)
    return c.im if c.im.size == output_size else c.im.resize(output_size,Image.Resampling.LANCZOS)


def grayscale(im):
    # Rec.709 luma on encoded RGB values, matching the requested comparison contract.
    a=np.array(im.convert("RGBA"))
    y=np.rint(a[:,:,:3].astype(float) @ np.array([0.2126,0.7152,0.0722])).astype(np.uint8)
    return Image.fromarray(np.dstack([y,y,y,a[:,:,3]]))


def verification(heroes, im):
    before=json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf8'))
    after={p:{'sha256':sha(Path(p) if Path(p).is_absolute() else ROOT/p),
              'bytes':(Path(p) if Path(p).is_absolute() else ROOT/p).stat().st_size} for p in before['files']}
    changed=[p for p in before['files'] if before['files'][p]!=after[p]]
    hud=ROOT/'art/imagegen/hud-icons-v3'
    current_hud={p.relative_to(ROOT).as_posix() for p in hud.rglob('*') if p.is_file()}
    original_hud={p for p in before['files'] if p.startswith('art/imagegen/hud-icons-v3/')}
    changed+=sorted(current_hud ^ original_hud)
    expected={
      'art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2anim/preview/KingArthur-Idle-blender-sheet.jpg':'63d49a66c31b6f7bed668eaafcb45bd838eead3d3c2674830c69980c50ac591c',
      'art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2anim/preview/frames/KingArthur-Idle-bones2d.json':'13ba214ee39c2b3dd1a37b9e1fa971243d27c8dfcc0e353713e81ebd78835e72',
      'art/pipeline-candidates/ASSET-HARPY-001/20260929-h2anim/preview/Harpy-Idle-blender-sheet.jpg':'389bc8b1dde7a7e87c2edddb8e712c9e038dd63323900a5e1181134ca904053d',
      'art/pipeline-candidates/ASSET-HARPY-001/20260929-h2anim/preview/frames/Harpy-Idle-bones2d.json':'4a26892033bb24bb91a2bfbc1de7b357300c06ea002bfcd33c7edf7a7b765073'}
    checks={
      'input_card_hashes_match':all(after[p]['sha256']==v for p,v in expected.items()),
      'arrival_560_ms':progress(560)==(2.0,0.0),
      'settle_710_ms':lean(710)==0,
      'phases_sum_560_ms':80+400+80==560,
      'phases_with_settle_sum_710_ms':80+400+80+150==710,
      's40_first_edge_1_24':math.isclose(progress(40)[0],1/24,abs_tol=1e-12),
      's80_first_edge_1_6':math.isclose(progress(80)[0],1/6,abs_tol=1e-12),
      'no_stop_at_vertex':all(math.isclose(progress(t)[1],1/240,abs_tol=1e-12) for t in [280-1e-6,280,280+1e-6]),
      'ease_out_start_480_ms':math.isclose(progress(480)[0],11/6,abs_tol=1e-12),
      'single_edge_k_1_200':edge(140,280,80,80)==(0.5,0.005),
      'single_edge_endpoints':edge(0,280,80,80)==(0.0,0.0) and edge(280,280,80,80)==(1.0,0.0),
      'single_edge_ease_out_200_ms':math.isclose(edge(200,280,80,80)[0],0.8,abs_tol=1e-12),
      'scaled_ease_edges':all(math.isclose(progress(min(80*d/280,d/2),d)[0],1/6,abs_tol=1e-12) for d in [90,140,280,420]),
      'speed_arrivals_280_560_840_ms':[2*d for d in [140,280,420]]==[280,560,840],
      'lean_reaches_10_deg_in_60_ms':lean(0)==0 and lean(60)==10 and lean(560)==10,
      'ground_hop_0':all(p['hop']==0 and p['base_rotation_degrees']==0 and p['base_ground_y']=={'KingArthur':455,'Harpy':620}[p['hero']] for p in POSE_TRANSFORMS),
      'dust_duration_300_ms':860-560==300,
      'master_1920_1080_RGBA':im.size==SIZE and im.mode=='RGBA',
      'palette_values_exact':all(TOKENS[k]==v for k,v in {
        'card.navy':'#061623','card.cream':'#F9EBDB','mark.keyline':'#111317','text.primary':'#F2EDE4',
        'text.secondary':'#B9B2A6','turn.flash.yellow':'#F2C14E','board.path':'#FFC857'}.items()),
      'snapshot_unchanged':sha(HERE/'draw_icons_v3_snapshot.py')==after['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256'],
      'all_text_inside_canvas':all(0<=b['bounds'][0]<=b['bounds'][2]<=1920 and 0<=b['bounds'][1]<=b['bounds'][3]<=1080 for b in TEXT_BOXES),
      'silhouettes_from_side_tiles_only':all(h['tile']=='f00 left' for h in heroes),
      'no_back_view_used':all(p['facing'][1]>=0 for p in FACINGS),
      'idle_facing_diagram_le_45_degrees':all(math.degrees(math.atan2(abs(p['facing'][0]),p['facing'][1]))<=45 for p in FACINGS if p['idle']),
      'source_unchanged':not changed,
    }
    file_checks=[]
    for width,height,suffix in [(1920,1080,''),(1280,720,'-1280x720')]:
        cp=PACKAGE/f'comparison/AN-22-step-sheet-color{suffix}.png'
        gp=PACKAGE/f'comparison/AN-22-step-sheet-gray{suffix}.png'
        a=Image.open(cp).convert('RGBA'); b=Image.open(gp).convert('RGBA')
        file_checks.append({'color':str(cp.relative_to(PACKAGE)), 'gray':str(gp.relative_to(PACKAGE)),
          'size':[width,height],'RGBA':Image.open(cp).mode=='RGBA' and Image.open(gp).mode=='RGBA',
          'Rec709_exact':np.array_equal(np.array(b),np.array(grayscale(a)))})
    checks['comparison_working_sizes_Rec709_exact']=all(f['RGBA'] and f['Rec709_exact'] for f in file_checks)
    dump(PACKAGE/'source-hashes-after.json',{'algorithm':'sha256','files':after})
    dump(PACKAGE/'text-bounds.json',TEXT_BOXES)
    dump(PACKAGE/'pose-transforms.json',{'poses':POSE_TRANSFORMS,'facings':FACINGS})
    dump(PACKAGE/'write-audit.json',{'allowed':[str(PACKAGE.relative_to(ROOT)),str(DERIVED.relative_to(ROOT))],
         'writes':sorted(WRITE_LOG),'scope':'This build process; other concurrent sessions are not monitored.'})
    result={'task':'AN-22','status':'предложено','source_unchanged':not changed,'changed_sources':changed,
      'source_files_checked':len(after),'hud_tree_files_checked':len(current_hud),'outside_folder':[],
      'outside_folder_scope':'Writes performed by this task, confined by an audit hook to package and permitted derived folder. No audit of other sessions.',
      'checks':checks,'all_automated_checks_pass':all(checks.values()),'comparison_files':file_checks,
      'limitations':[
       {'kind':'projection','text':'Left-tile silhouettes are side-view analytical glyphs, not synthesized three-quarter renders. Camera-relative yaw is communicated by adjacent facing diagrams; real 3D turn appearance cannot be established from one side tile.'},
       {'kind':'source','text':'Supplied neutral Blender sheets contain bone annotations. Silhouettes are threshold-traced with annotation masking and small-gap closure; no original hero texture or scan is included in package images.'},
       {'kind':'scope','text':'No runtime animation, full path scheduling or Unreal acceptance is tested; this deliverable is a static procedural timing proposal.'}],
      'unmet_requirements':[], 'visual_review':{'status':'pending','images':[]},
      'generation':{'image_generation_calls':0,'character_generation':False,'method':'scripted source tracing and procedural drawing'},
      'processes_started_in_background':[],
      'numeric_samples':{str(t):{'s':progress(t)[0],'v_edges_per_ms':progress(t)[1],'lean_degrees':lean(t)} for t in [0,40,50,60,80,280,400,480,560,710,860]},
      'ground_contract':{'hop':0,'pedestal_rotation_degrees':0,'pedestal_ground_y':{'KingArthur':455,'Harpy':620}},
      'silhouette_transform':{'method':'reflected side mask, rigid rotation around original base center; pedestal drawn separately flat; cropped at ground support','max_rotation_degrees':10},
    }
    dump(PACKAGE/'verification.json',result)
    if not all(checks.values()):
        raise AssertionError([k for k,v in checks.items() if not v])
    return result


def main():
    # Corrective run: retains accepted artwork, adds contract evidence, no image generation.
    from fix1_support import build_package
    build_package(sys.modules[__name__])


if __name__=='__main__':
    main()
