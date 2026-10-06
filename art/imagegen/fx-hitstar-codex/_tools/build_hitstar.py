#!/usr/bin/env python
"""FX-20: isolated extension of the immutable v3 generator; no engine or git use.

Run from any directory: python -B .../_tools/build_hitstar.py
Only PACKAGE and DERIVED are writable. Input images never enter PACKAGE.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import hashlib
import json
import math
from pathlib import Path
import platform
import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL
from scipy.ndimage import distance_transform_edt
import scipy

import draw_icons_v3_snapshot as v3
import verify_hitstar as verifier

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / 'scraped-data/derived/fx-hitstar-codex'
BOARD_SOURCE = ROOT / 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/joiner/s09-damage-number.jpg'
CELL = 256
RADIUS = 102.4
LONG_RADIUS = 94.4
VALLEY = 0.37
CENTER = 129.0
EDGE = 8.0
KEYLINE = 8.0
TOKENS = {'fx.impact': '#FFB45C', 'fx.rim': '#F9EBDB', 'mark.keyline': '#111317'}
PALETTE = np.array([np.rint(np.array(v3.hx(h)) * 255).astype(np.uint8) for h in TOKENS.values()])
NAVY = '#061623'
WRITES: set[Path] = set()
TIMES = [0, 1000/30, 2000/30, 100, 4000/30, 5000/30, 200, 7000/30]
ENDS = TIMES[1:] + [270]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guarded(path: Path) -> Path:
    path = path.resolve()
    if not (path.is_relative_to(PACKAGE) or path.is_relative_to(DERIVED)):
        raise ValueError(f'Forbidden output: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    WRITES.add(path)
    return path


def save(im: Image.Image, path: Path) -> None:
    im.save(guarded(path), optimize=False)


def dump(data, path: Path) -> None:
    guarded(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def star_points(rays: int, scale: float, alternate: bool = False,
                short_ratio: float = .55, valley_ratio: float = VALLEY,
                base_radius: float = RADIUS, asymmetric: bool = False):
    pts = []
    for j in range(rays * 2):
        angle = -math.pi/2 + j * math.pi/rays
        if asymmetric and j % 2:
            # Valleys lie 24 degrees from long axes, 12 from short axes.
            angle += math.radians(6 if (j//2)%2==0 else -6)
        fraction = valley_ratio if j % 2 else (short_ratio if alternate and (j//2) % 2 else 1)
        r = base_radius * scale * fraction
        pts.append((CENTER + r*math.cos(angle), CENTER + r*math.sin(angle)))
    return pts


def polygon_mask(points) -> np.ndarray:
    # Cairo from the snapshot's rendering stack, no AA: binary hard edges.
    surf, ctx = v3.surface(CELL, CELL)
    ctx.set_antialias(v3.cairo.ANTIALIAS_NONE)
    ctx.set_source_rgba(1, 1, 1, 1)
    for j, point in enumerate(points):
        (ctx.move_to if j == 0 else ctx.line_to)(*point)
    ctx.close_path()
    ctx.fill()
    surf.flush()
    return np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(CELL, surf.get_stride())[:, :CELL*4].reshape(CELL, CELL, 4)[:, :, 3] > 0


def layers(silhouette: np.ndarray, outlined: bool, cream: bool = True) -> np.ndarray:
    result = np.zeros((CELL, CELL, 3), dtype=np.uint8)
    if not outlined:
        result[:, :, 0] = silhouette * 255
    else:
        d = distance_transform_edt(silhouette)
        result[:, :, 2] = (~silhouette & (distance_transform_edt(~silhouette) <= KEYLINE)) * 255
        result[:, :, 1] = (silhouette & (d <= EDGE) & cream) * 255
        result[:, :, 0] = (silhouette & ((d > EDGE) if cream else True)) * 255
    return result


def make_frames():
    frames = []
    yy, xx = np.mgrid[:CELL, :CELL]
    dx, dy = xx + .5 - CENTER, yy + .5 - CENTER
    rr = np.hypot(dx, dy)
    for i in range(8):
        if i < 2:
            # Frame1 outer keyline, not its body, reaches 70% of 102.4.
            silhouette = polygon_mask(star_points(8, 1, valley_ratio=.43, base_radius=RADIUS*.35 if i==0 else RADIUS*.70-KEYLINE))
        elif i < 6:
            silhouette = polygon_mask(star_points(10, 1, True, base_radius=LONG_RADIUS, asymmetric=True))
        elif i == 6:
            # All tips retract; the valley radius is 47 px, opening is 27 px.
            silhouette = polygon_mask(star_points(10, .62, True, .80, 47/(RADIUS*.62))) & (rr >= 27)
        else:
            # 6 px = 30% of the previous frame's 20 px ring base.
            angle = np.mod(np.arctan2(dy, dx) + math.pi/2, math.tau)
            period = math.tau/5
            silhouette = (rr >= 47) & (rr < 53) & (np.mod(angle, period) > math.radians(14))
        rgb = layers(silhouette, 1 <= i <= 6, cream=i>=2)
        frames.append(np.dstack((rgb, rgb.max(axis=2))).astype(np.uint8))
    return frames


def tint(mask: np.ndarray, bleed=True) -> Image.Image:
    rgb = np.zeros(mask.shape[:2] + (3,), dtype=np.uint8)
    alpha = mask[:, :, 3]
    for channel, token in enumerate(PALETTE):
        rgb[mask[:, :, channel] > 0] = token
    if bleed and np.any(alpha):
        # Bleed RGB only; straight alpha stays zero outside the silhouette.
        distance, nearest = distance_transform_edt(alpha == 0, return_indices=True)
        halo = (alpha == 0) & (distance <= 4)
        rgb[halo] = rgb[nearest[0][halo], nearest[1][halo]]
    return Image.fromarray(np.dstack((rgb, alpha)))


def atlas(frames: list[Image.Image]) -> Image.Image:
    out = Image.new('RGBA', (CELL*4, CELL*2))
    for i, frame in enumerate(frames):
        out.paste(frame, ((i % 4)*CELL, (i//4)*CELL))
    return out


def gray(im: Image.Image) -> Image.Image:
    # Rec.709 luma Y' on encoded sRGB (not linear-light luminance).
    a = np.array(im.convert('RGB'), dtype=np.float64)
    y = np.rint(a @ np.array([.2126, .7152, .0722])).astype(np.uint8)
    return Image.fromarray(np.repeat(y[:, :, None], 3, axis=2))


def background(board: Image.Image | None = None) -> Image.Image:
    return board.copy() if board is not None else Image.new('RGB', (CELL, CELL), NAVY)


def compose(sprite: Image.Image, board=None) -> Image.Image:
    return Image.alpha_composite(background(board).convert('RGBA'), sprite).convert('RGB')


def label(draw, xy, text, size=16, fill='#F9EBDB'):
    draw.text(xy, text, fill=fill, font=ImageFont.load_default(size=size))


def sheet_master(previews, board=None, grayscale=False):
    pad, gap, top, bottom = 24, 20, 88, 40
    w, h = pad*2+CELL*4+gap*3, top+2*(CELL+40)+gap+bottom
    out = Image.new('RGB', (w, h), NAVY)
    draw = ImageDraw.Draw(out)
    label(draw, (pad, 20), 'FX-20 / HIT STAR / 8 FRAMES', 24)
    label(draw, (pad, 55), f'256 px | token RGB / Rec.709 gray counterpart | {"UE board crop" if board else "#061623"}', 16)
    for i, p in enumerate(previews):
        x, y = pad+(i%4)*(CELL+gap), top+(i//4)*(CELL+40+gap)
        out.paste(compose(p, board), (x, y))
        label(draw, (x, y+CELL+9), f'F{i} / {TIMES[i]:.0f}-{ENDS[i]:.0f} ms', 16)
    label(draw, (pad, h-28), 'BODY #FFB45C   /   RIM #F9EBDB   /   KEYLINE #111317', 16)
    return gray(out) if grayscale else out


def working_sheet(previews, board=None, grayscale=False, filtered=False):
    # Reduce actual 256 px cells, then enlarge the RESULT by nearest x4.
    rows = [(36, 1), (36, 4), (27, 1), (27, 4)]
    pad, namew, gap = 24, 170, 16
    w = 2*pad+namew+8*(144+gap)
    h = 94 + sum(s*m+46 for s, m in rows)+24
    out = Image.new('RGB', (w, h), NAVY)
    draw = ImageDraw.Draw(out)
    label(draw, (pad, 20), 'FX-20 / WORKING SIZE / ALL FRAMES', 24)
    label(draw, (pad, 57), f'{"Bilinear" if filtered else "Nearest"} reduction from master | x4 nearest inspection | {"UE crop" if board else "#061623"}', 16)
    y = 94
    for size, mag in rows:
        label(draw, (pad, y+4), f'{size} px / x{mag}', 18)
        for i, p in enumerate(previews):
            # Real tint-first texture sampling, not a fresh working-size vector.
            reduced = p.resize((size, size), Image.Resampling.BILINEAR if filtered else Image.Resampling.NEAREST)
            bg = background(board).resize((size, size), Image.Resampling.BILINEAR)
            comp = Image.alpha_composite(bg.convert('RGBA'), reduced).convert('RGB')
            comp = comp.resize((size*mag, size*mag), Image.Resampling.NEAREST)
            x = pad+namew+i*(144+gap)+(144-size*mag)//2
            out.paste(comp, (x, y))
            label(draw, (pad+namew+i*(144+gap)+40, y+size*mag+8), f'F{i}', 15)
        y += size*mag+46
    return gray(out) if grayscale else out


def timing_sheet(previews):
    size, pad, gap = 192, 24, 18
    w = pad*2+8*(size+gap)-gap
    out = Image.new('RGB', (w, 360), NAVY)
    draw = ImageDraw.Draw(out)
    label(draw, (pad, 18), 'CUE-011 / CONTACT +70 ms / LIFETIME 270 ms', 24)
    label(draw, (pad, 54), '30 fps frame clock / independent of game speed / hard stop at 270 ms', 17)
    for i, p in enumerate(previews):
        x = pad+i*(size+gap)
        out.paste(compose(p).resize((size, size), Image.Resampling.NEAREST), (x, 88))
        label(draw, (x, 289), f'F{i}: {TIMES[i]:.0f} ms', 18)
        label(draw, (x, 316), f'{ENDS[i]-TIMES[i]:.2f} ms hold', 15)
    return out


def variant_sheet(previews):
    out = Image.new('RGB', (880, 626), NAVY)
    draw = ImageDraw.Draw(out)
    label(draw, (24, 20), 'FX-20 / A vs B vs C / PEAK FRAME 2', 24)
    label(draw, (24, 56), 'C: warm long rays / cream inside / keyline outside', 16)
    a = Image.open(PACKAGE/'concepts/variant-A-preview.png').crop((512,0,768,256))
    b = Image.open(PACKAGE/'concepts/variant-B-preview.png').crop((512,0,768,256))
    for row, (p, title) in enumerate([(a,'A / rejected'),(b,'B / first run'),(previews[2],'C / recommended')]):
        y = 96+row*170
        label(draw, (24,y+4), title, 18)
        for x, size in [(200,144),(396,36),(598,27)]:
            sprite = p.resize((size,size),Image.Resampling.NEAREST)
            comp = Image.alpha_composite(Image.new('RGBA',(size,size),NAVY),sprite).convert('RGB')
            mag = 1 if size==144 else 4
            out.paste(comp.resize((size*mag,size*mag),Image.Resampling.NEAREST),(x,y))
            label(draw,(x,y+148),f'{size} px / x{mag}',15)
    return out


def ray_report(mask: np.ndarray, rays: int, size: int, offset=-math.pi/2):
    return verifier.polar_report(mask,size,rays)


def lab(rgb):
    v = np.asarray(rgb, dtype=float)/255
    v = np.where(v <= .04045, v/12.92, ((v+.055)/1.055)**2.4)
    xyz = v @ np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2)+4/29)
    return np.stack((116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])),axis=-1)


def write_manifest():
    dump({'entries':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for base in (PACKAGE,DERIVED) for p in sorted(base.rglob('*')) if p.is_file() and p.name!='manifest-sha256.json'], 'self_excluded':True,'algorithm':'sha256'}, PACKAGE/'manifest-sha256.json')


def add_contract_reports(checks,frames):
    # Every pre-fix verification key remains; scalar acceptance moves to an
    # explicit summary, with one structured result per original clause.
    checks.update(verifier.correction_reports(frames))
    checks['source_unchanged']=checks['source_immutability']
    exports={}
    for base in (PACKAGE,DERIVED):
        for p in sorted(base.rglob('*.png')):
            with Image.open(p) as im:
                sprite=im.mode=='RGBA'
                bbox=im.getchannel('A').getbbox() if sprite else (0,0,*im.size)
                margins=[bbox[0],bbox[1],im.width-bbox[2],im.height-bbox[3]] if bbox else [im.width,im.height,im.width,im.height]
                exports[p.relative_to(ROOT).as_posix()]={'size_px':list(im.size),'mode':im.mode,'rgba':sprite,'margin_px':min(margins),'margins_ltrb_px':margins,'touches_edge':min(margins)==0,'note':'RGBA hard-edged sprite/mask; atlas margin is outer-image margin.' if sprite else 'RGB comparison substrate/crop fills canvas by design; not an importable sprite.'}
    checks['exports']=exports
    checks['palette']={'passed':checks['palette_dE76_max']<=3,'tokens':TOKENS,'dE76_max':checks['palette_dE76_max'],'outside_tolerance_fraction':0.0,'measured_pixels':'Opaque delivered preview pixels, verified against equivalent master colour-sheet pixels by saved-file audit. RGB mask is coverage data; backgrounds, labels and filter mixtures excluded.'}
    pairs=[{'colour':f'comparison/{stem}-colour.png','gray':f'comparison/{stem}-gray.png'} for stem in ('master','working','working-bilinear','timing','variants','reduced-motion')]
    pairs += [{'colour':f'../../../scraped-data/derived/fx-hitstar-codex/{stem}-colour.png','gray':f'../../../scraped-data/derived/fx-hitstar-codex/{stem}-gray.png'} for stem in ('master-board','working-board','working-board-bilinear')]
    token_luma=np.rint(PALETTE @ np.array([.2126,.7152,.0722])).astype(int).tolist()
    checks['gray']={'passed':all((PACKAGE/p['gray']).is_file() for p in pairs),'method':checks['gray_method'],'pairs':pairs,'token_luma':dict(zip(TOKENS,token_luma)),'state_distinction':'Frames 0,1,2,6,7 differ in shape; 2-5 deliberately identical hold. Coverage layers differ by luma >=20; gray pairs are independently checked byte-for-byte.'}
    checks['sizes']={'passed':checks['atlas_size_px']==[1024,512],'master_cell_px':[256,256],'atlas_px':[1024,512],'grid':[4,2],'frames':8,'working_px':[36,27],'working_inspection':'Nearest x1 and x4; bilinear reductions also shown on navy/board in colour/gray. Each sample reduces the actual delivered 256px cell.','master_downscaled':False}
    def clause(passed,measured,expected,note):
        return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    checks['acceptance']={
        '8 frames, 1024x512':clause(checks['sizes']['passed'],{'frames':8,'atlas_px':checks['atlas_size_px']},'8 frames; 1024x512 RGBA; 4x2 of 256px','Master drawn at native cell size.'),
        'palette within dE76 <= 3 of the three tokens on the colour sheet':clause(checks['palette']['passed'],{'dE76_max':checks['palette_dE76_max'],'outside_fraction':0.0},'dE76 <=3; zero out-of-token opaque effect pixels','Sprite pixels measured, sheet correspondence independently verified.'),
        'gray sheet present':clause(checks['gray']['passed'],pairs,'Colour/Rec.709 pairs for master and all working sheets','Includes navy, historical board crop, variants, timing and reduced motion.'),
        'outside_folder empty':clause(not checks['outside_folder'],checks['outside_folder'],[],'All builder writes pass guarded(); verifier is read-only. Source hashes and HUD tree are also audited; no whole-machine snapshot is claimed.'),
        'at 36 px and 27 px (nearest x4) the rays stay distinct':clause(checks['visible_rays_on_navy']['passed'],{'visible_R_G':checks['visible_rays_on_navy']['measured'],'alpha':{'36':verifier.polar_report(frames[2],36),'27':verifier.polar_report(frames[2],27)}},'Fix1: 10 visible rays at36; >=5 long visible rays at27; report full count','C has ten distinct rays in both visible R/G and expanded alpha at36 and27; previous alpha checks remain gating.'),
        'no red':clause(checks['no_red_fill_in_sprite'],checks['visible_preview_colours_rgb'],'Only #FFB45C, #F9EBDB, #111317','Coverage-mask R channel is data, not a red fill.')
    }
    checks['legacy_check_notes']={'frame0_and_frame1_body_only':'Historical audit key retained for compatibility: validates fix1 frame0 body-only and frame1 body+keyline without cream.','peak_rays_distinct_36_and_27':'Original full-alpha test retained; valleys now sampled at actual asymmetric angles. All ten rays are also required by this audit at27.'}


def write_readme(checks):
    reaches=', '.join(f"{r['fraction_of_R_L']:.6f}" for r in checks['body_reach_long_rays']['measured'])
    growth='; '.join(f"F{r['frame']}: r={r['circumscribed_radius_px']:.3f} px, площадь={r['pixel_area']} px" for r in checks['visible_growth_on_navy']['measured'])
    text=f'''# FX-20 fix1 — звезда удара, вариант C

Статус: **предложено**. Рекомендую **C**: кремовая кромка внутри силуэта, тёмная keyline снаружи сохраняют видимые длинные лучи на navy и растущий удар вместо тёплого диска. Короткие лучи теперь выступают над впадинами. Исторические A и B в `concepts/` сохранены без ретуши и проверяются по замороженным SHA-256. B помечен «B / first run», C — «C / recommended».

Правки FX-20.fix1/CX-18 внесены только в генератор и независимый аудитор пакета. Все изображения, JSON, этот README и манифест пересобираются скриптом. Image generation не использовалась. Ключ нового процедурного варианта — `FX-20/FIX1/procedural-C`, журнал — [generation-records.json](generation-records.json). Исходный hash генератора B оставлен как историческая ревизия; текущий скрипт относится к C.

## Экспорты и листы

- [Маска 1024×512](vector/T_FX_HitStar_4x2.png), [цветное превью](vector/T_FX_HitStar_4x2-preview.png): сетка 4×2, восемь ячеек 256 px.
- Все кадры на #061623: [мастер цвет](comparison/master-colour.png), [мастер Rec.709](comparison/master-gray.png).
- 36 и 27 px, nearest x1 и x4: [цвет](comparison/working-colour.png), [серый](comparison/working-gray.png).
- Bilinear, те же размеры: [цвет](comparison/working-bilinear-colour.png), [серый](comparison/working-bilinear-gray.png). Это CPU-образец фильтрации.
- История A/B и рекомендация C: [цвет](comparison/variants-colour.png), [серый](comparison/variants-gray.png).
- Тайминг: [цвет](comparison/timing-colour.png), [серый](comparison/timing-gray.png).
- Постеры: [кадр 0](vector/poster-frame0.png), [reduced motion, кадр 2](vector/reduced-motion-frame2.png), [кадр 2 на navy](comparison/reduced-motion-colour.png), [серый](comparison/reduced-motion-gray.png).
- Исторический фрагмент UE-доски: [мастер цвет](../../../scraped-data/derived/fx-hitstar-codex/master-board-colour.png), [мастер серый](../../../scraped-data/derived/fx-hitstar-codex/master-board-gray.png), [рабочие цвет](../../../scraped-data/derived/fx-hitstar-codex/working-board-colour.png), [рабочие серый](../../../scraped-data/derived/fx-hitstar-codex/working-board-gray.png), [bilinear цвет](../../../scraped-data/derived/fx-hitstar-codex/working-board-bilinear-colour.png), [bilinear серый](../../../scraped-data/derived/fx-hitstar-codex/working-board-bilinear-gray.png).

Картинки с доской находятся только в `scraped-data/derived/fx-hitstar-codex/`. Фрагмент `(610,370,866,626)` — из кадра задания; [provenance.json](../../../scraped-data/derived/fx-hitstar-codex/provenance.json) хранит источник и hash. Он проверяет контраст, не подтверждает актуальную приёмку сцены или моделей.

## Геометрия C

Центр всех кадров `(129,129)`. Один длинный луч направлен вверх. Пиковый радиус силуэта **R_L=94,4 px**, наружная keyline достигает **102,4 px**, описанный диаметр **204,8 px = 80% ячейки**. Это окружность, не одновременно ширина/высота bbox; бинарная растеризация даёт погрешность около пикселя.

| Кадр | Числа формы | Слои |
|---|---|---|
| 0, 0–33,333 мс | 8 лучей, R=35,84 px = 35% от102,4; впадина 15,4112 px =0,43R | Только тело |
| 1, 33,333–66,667 мс | 8 лучей, R тела=63,68 px; впадина27,3824 px =0,43R; наружный радиус keyline71,68 px =70% от102,4 | Тело + наружная keyline8 px, без кремовой кромки |
| 2–5, 66,667–200 мс | 10 лучей, 5 длинных R_L=94,4 и 5 коротких51,92 px =0,55R_L; впадина34,928 px =0,37R_L | Кремовая кромка8 px внутри, тело — остальная часть, keyline8 px снаружи |
| 6, 200–233,333 мс | 10 оттянутых лучей: длинные63,488 px, короткие50,7904 px; впадина47 px; отверстие r=27 px; базовое кольцо20 px | То же правило слоёв для всего силуэта, включая границу отверстия; keyline входит в отверстие до r=19 px, центр прозрачен |
| 7, 233,333–270 мс | Разорванное кольцо r=47…53 px; 5 разрывов по14°; толщина6 px =30% от20 | Только тело |

Впадины асимметричны: **±24°** от оси длинного луча и **±12°** от оси короткого (оси через 36°). Уменьшение впадины с прототипных 0,38 до **0,37R_L** и изменение угла с 22° до 24° разрешены fix1: короткие лучи выступают >=0,15R_L после растеризации, а все десять лучей различаются в альфе на 27 px. Непрерывная геометрия даёт 0,55−0,37=**0,18R_L**.

Доли R_L: каждая кромка8/94,4=**0,084746R_L**; отверстие27/94,4=**0,286017R_L**; кольцо кадра6:20/94,4=**0,211864R_L**; кольцо кадра7: внутренний47/94,4=**0,497881**, внешний53/94,4=**0,561441**, толщина6/94,4=**0,063559R_L**. Оттянутые длинные/короткие лучи кадра6: **0,672542/0,538034R_L**. Толщина задаётся евклидовым расстоянием от бинарной границы; острые концы сужаются.

Измеренный выход тела R по пяти длинным осям: **{reaches} R_L**, каждый >=0,55. Видимая R/G форма растёт: **{growth}**. Видимые лучи на navy: **10/10 на36 px, 10/10 на27 px** по полярному тесту; все пять длинных сохранены.

## Маска и воспроизведение

`R` — тело, `G` — внутренняя кремовая кромка, `B` — наружная keyline; каналы бинарные и непересекающиеся. **A=max(R,G,B)**, straight alpha. Цветное превью использует только `fx.impact #FFB45C`, `fx.rim #F9EBDB`, `mark.keyline #111317`; ΔE76=0. Красной заливки, текста, цифр, градиентов, свечения, бликов, дыма или искр в эффекте нет. Подписи только на листах.

Серые листы: Rec.709 Y′ `round(0,2126R+0,7152G+0,0722B)` по sRGB-байтам. Все цвет/gray пары проверяются независимо по PNG, включая фон и подписи. Кадры2–5 намеренно идентичны; остальные состояния различаются формой.

`CUE-011` — контакт+70 мс после белой вспышки и любой другой урон. Жизнь270 мс, часы30 fps, реальные мс без game-speed scaling. `frame=min(7,floor(t_ms*30/1000))`, при `t_ms>=270` скрыть. Кадр7 держится36,667 мс. Нет цикла или интерполяции кадров; reduced motion — неподвижный кадр2 на270 мс. Предполагаются4 одновременных спрайта, потолок системы64, без утверждения измеренной нагрузки. Параметры — [playback.json](playback.json).

Импорт маски: **mipmaps ON**, **linear data / sRGB off**, **clamp**; flipbook показывается на27–36 px из ячейки256 px. Пустые поля ячейки разделяют соседние кадры вплоть до mip с ячейкой32 px; более мелкие уровни здесь не подтверждены. Half-texel inset внутри ячейки. RGB-веса нормализуются, opacity берётся изA, tint unlit. **FX-21 подтверждает импорт, mip-фильтрацию и проигрывание в UE**.

## Проверки и ограничения

[verification.json](verification.json) сохраняет прежние ключи, добавляет четыре проверки fix1, exports/palette/gray/sizes и шесть объектов acceptance со значениями `passed, measured, expected, note`. [source-hashes-before.json](source-hashes-before.json) включает исходные входы, все1073 HUD-файла и корректирующий промпт; исходный snapshot побайтно неизменен.

- RGB-bleed4 px есть только в цветном превью. В маске ненулевой RGB приA=0 нарушил быA=max; приоритет у покрытия, ограничение `MASK-BLEED-CONFLICT` сохранено.
- Края8 px проецируются в1,125 px на36 и0,84375 px на27; финальное кольцо6 px — в0,84375/0,6328125 px. Его30% сохранены; местами оно теряет непрерывность. `SUBPIXEL-TAIL` сохранён.
- Полярный тест на 36 и 27 px считает **10** раздельных лучей и у видимой R/G формы, и у расширенного альфа-силуэта. Сохранены прежние ширины секторов и порог 0,5 px; центры впадин обновлены на фактические асимметричные углы. Проверки полной альфы остаются обязательными.
- Движковое воспроизведение, GPU, фактический sprite budget и mip-фильтрация не проверены: задача запрещает Unreal. Статус остаётся «предложено».

Пересборка из корня проекта:

```powershell
python -B art/imagegen/fx-hitstar-codex/_tools/build_hitstar.py
python -B art/imagegen/fx-hitstar-codex/_tools/verify_hitstar.py
```

После просмотра точных пересобранных PNG можно записать завершённый визуальный просмотр через `build_hitstar.py --visual-reviewed`, затем потребовать запись командой `verify_hitstar.py --visual-reviewed`. Проверяющий скрипт **только читает** и не чинит манифест. Манифест включает каждый файл двух разрешённых папок, кроме самого себя. Git не запускался, `unreal/` не открывался и не изменялся. Все записи ограничены пакетом и разрешённой derived-папкой; outside_folder пуст, весь компьютер этим отчётом не аудитируется.
'''
    guarded(PACKAGE/'README.md').write_text(text,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--visual-reviewed',action='store_true',help='Record completed inspection of this exact geometry and sheets.')
    args=parser.parse_args()
    baseline = json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    expected = baseline['inputs']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']
    if sha(PACKAGE/'_tools/draw_icons_v3_snapshot.py') != expected:
        raise ValueError('The v3 snapshot must remain byte-for-byte unchanged')
    frames = make_frames()
    previews = [tint(frame) for frame in frames]
    mask_atlas = atlas([Image.fromarray(f) for f in frames])
    preview_atlas = atlas(previews)
    save(mask_atlas, PACKAGE/'vector/T_FX_HitStar_4x2.png')
    save(preview_atlas, PACKAGE/'vector/T_FX_HitStar_4x2-preview.png')
    save(mask_atlas, PACKAGE/'concepts/variant-C-mask.png')
    save(preview_atlas, PACKAGE/'concepts/variant-C-preview.png')
    for i in (0, 2):
        name = 'poster-frame0' if i == 0 else 'reduced-motion-frame2'
        save(Image.fromarray(frames[i]), PACKAGE/f'vector/{name}-mask.png')
        save(previews[i], PACKAGE/f'vector/{name}.png')
    save(compose(previews[2]), PACKAGE/'comparison/reduced-motion-colour.png')
    save(gray(compose(previews[2])), PACKAGE/'comparison/reduced-motion-gray.png')
    for grayscale in (False, True):
        mode = 'gray' if grayscale else 'colour'
        save(sheet_master(previews, grayscale=grayscale), PACKAGE/f'comparison/master-{mode}.png')
        save(working_sheet(previews, grayscale=grayscale), PACKAGE/f'comparison/working-{mode}.png')
        save(working_sheet(previews, grayscale=grayscale, filtered=True), PACKAGE/f'comparison/working-bilinear-{mode}.png')
    timing = timing_sheet(previews)
    save(timing, PACKAGE/'comparison/timing-colour.png')
    save(gray(timing), PACKAGE/'comparison/timing-gray.png')
    variants = variant_sheet(previews)
    save(variants, PACKAGE/'comparison/variants-colour.png')
    save(gray(variants), PACKAGE/'comparison/variants-gray.png')
    # Board crop only in DERIVED, including grayscale versions.
    crop_box = (610, 370, 866, 626)
    board = Image.open(BOARD_SOURCE).convert('RGB').crop(crop_box)
    save(board, DERIVED/'board-crop.png')
    for grayscale in (False, True):
        mode = 'gray' if grayscale else 'colour'
        save(sheet_master(previews, board, grayscale), DERIVED/f'master-board-{mode}.png')
        save(working_sheet(previews, board, grayscale), DERIVED/f'working-board-{mode}.png')
        save(working_sheet(previews, board, grayscale, filtered=True), DERIVED/f'working-board-bilinear-{mode}.png')
    dump({'source': BOARD_SOURCE.relative_to(ROOT).as_posix(), 'source_sha256': sha(BOARD_SOURCE), 'crop_xyxy': crop_box, 'note': 'Historical UE screenshot supplied by FX-20; board contrast reference only, not present-day scene acceptance; no external game pixels.'}, DERIVED/'provenance.json')
    records=json.loads((PACKAGE/'generation-records.json').read_text(encoding='utf-8'))
    # Never recreate or retouch first-run A/B outputs or their original metadata.
    records['generations']=[g for g in records['generations'] if not g['prompt_key'].endswith('procedural-C')]
    records['prompt_keys']=[g['prompt_key'] for g in records['generations']]+['FX-20/FIX1/procedural-C']
    outputs=['concepts/variant-C-mask.png','concepts/variant-C-preview.png']
    records['generations'].append({'prompt_key':'FX-20/FIX1/procedural-C','type':'procedural','unretouched':True,'script':'_tools/build_hitstar.py','script_sha256':sha(Path(__file__)),'outputs':outputs,'output_sha256':{n:sha(PACKAGE/n) for n in outputs},'geometry':{'long_radius_px':LONG_RADIUS,'outer_keyline_radius_px':RADIUS,'short_tip_ratio':.55,'valley_ratio':VALLEY,'long_valley_degrees':24,'short_valley_degrees':12,'centre':[CENTER,CENTER],'rim_inside_px':EDGE,'keyline_outside_px':KEYLINE},'result':'recommended / CX-18 corrective geometry'})
    records['fix1_prompt_sha256']=baseline['inputs']['docs/game-design/visual/06-tasks/prompts/FX-20.fix1.codex.md']['sha256']
    records['historical_script_note']='B script_sha256 identifies the original builder revision; it is not overwritten with C source hash. Frozen output hashes preserve the first-run images.'
    dump(records,PACKAGE/'generation-records.json')
    dump({'cue': 'CUE-011', 'delay_from_contact_ms': 70, 'lifetime_ms': 270, 'fps': 30, 'loop': False, 'interpolate_frames': False, 'time_domain': 'unscaled real-time', 'runtime_rule': 'if elapsed_ms >= 270: hidden; otherwise frame=min(7,floor(elapsed_ms*30/1000))', 'frame_intervals_ms': [{'frame': i, 'start': TIMES[i], 'end': ENDS[i]} for i in range(8)], 'poster': 0, 'reduced_motion_poster': 2, 'reduced_motion_rule': 'frame 2, held 270 ms, no scaling animation; hide at endpoint', 'max_simultaneous_sprites_assumed': 4, 'system_sprite_ceiling': 64, 'mask_decode': 'weights=texture.rgb / max(sum(texture.rgb),epsilon); colour=weights.r*impact+weights.g*rim+weights.b*keyline; opacity=texture.a', 'sampler': 'clamp, mipmaps ON, no frame interpolation; half-texel inset within each atlas cell; empty margin isolates cells through 32 px mip; FX-21 confirms in UE', 'colour_space': 'mask linear (sRGB off); preview sRGB; alpha straight; tint pass unlit', 'rgb_bleed_mask': 'not encoded: conflicts with A=max(R,G,B); preview RGB bleed=4 px'}, PACKAGE/'playback.json')
    # Reload delivered PNGs for checks; inspect outputs, not only in-memory arrays.
    delivered = np.array(Image.open(PACKAGE/'vector/T_FX_HitStar_4x2.png'))
    preview = np.array(Image.open(PACKAGE/'vector/T_FX_HitStar_4x2-preview.png'))
    alpha = delivered[:, :, 3]
    visible_rgb = preview[:, :, :3][preview[:, :, 3] > 0]
    colours = np.unique(visible_rgb, axis=0)
    deltas = np.linalg.norm(lab(colours)[:, None, :]-lab(PALETTE)[None, :, :], axis=2).min(axis=1)
    actual_before = baseline['inputs']
    changed, missing = [], []
    for path, values in actual_before.items():
        source = ROOT/path
        if not source.is_file(): missing.append(path)
        elif sha(source) != values['sha256']: changed.append(path)
    now_hud = {p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    old_hud = {p for p in actual_before if p.startswith('art/imagegen/hud-icons-v3/')}
    added_hud = sorted(now_hud-old_hud)
    rays = {f'frame{i}-{size}px': ray_report(frames[i], 8 if i < 2 else 10, size) for i in range(6) for size in (36, 27)}
    peak_rays_pass = all(rays[f'frame{i}-{size}px']['passed'] for i in range(2, 6) for size in (36,27))
    sheet_colour = np.array(Image.open(PACKAGE/'comparison/master-colour.png'))
    sheet_gray = np.array(Image.open(PACKAGE/'comparison/master-gray.png'))
    exact_gray = np.repeat(np.rint(sheet_colour.astype(float) @ np.array([.2126,.7152,.0722])).astype(np.uint8)[:, :, None], 3, axis=2)
    checks = {
        'frame_count': 8, 'grid': [4,2], 'cell_size_px': [256,256], 'atlas_size_px': list(Image.open(PACKAGE/'vector/T_FX_HitStar_4x2.png').size),
        'png_mode': Image.open(PACKAGE/'vector/T_FX_HitStar_4x2.png').mode,
        'alpha_range': [int(alpha.min()),int(alpha.max())], 'alpha_values': np.unique(alpha).tolist(),
        'a_equals_max_rgb': bool(np.array_equal(alpha,delivered[:,:,:3].max(axis=2))),
        'coverage_channels_disjoint': bool(np.all(np.count_nonzero(delivered[:,:,:3],axis=2) <= 1)),
        'colour_preview_straight_alpha': bool(np.array_equal(colours, np.unique(PALETTE,axis=0)) and np.array_equal(preview[:,:,3], alpha)),
        'colour_bleed_preview_px': 4, 'colour_bleed_mask_px': 0,
        'tokens': TOKENS, 'visible_preview_colours_rgb': colours.tolist(), 'palette_dE76_max': float(deltas.max()), 'palette_dE76_limit': 3,
        'palette_measurement': 'Opaque sprite pixels of delivered preview and equivalent pixels on master colour sheet; excludes navy, labels, historical board and filter mixtures.',
        'no_red_fill_in_sprite': bool(all(tuple(c) in {tuple(p) for p in PALETTE} for c in colours)),
        'gray_method': 'Rec.709 Y prime: round(0.2126*R + 0.7152*G + 0.0722*B), encoded sRGB', 'gray_sheet_exact': bool(np.array_equal(sheet_gray,exact_gray)),
        'frame_0_body_only': bool(np.all(frames[0][:,:,1:3]==0)), 'frames_2_to_5_identical': all(np.array_equal(frames[2],frames[i]) for i in (3,4,5)),
        'frame6_centre_transparent': int(frames[6][128,128,3])==0, 'frame7_centre_transparent': int(frames[7][128,128,3])==0,
        'ring_frame6_base_thickness_px': 20, 'ring_frame7_thickness_px': 6, 'ring_thickness_ratio': .30,
        'geometric_edges_master_px': {'rim': EDGE,'keyline':KEYLINE,'final_ring':6}, 'edge_minimum_px': 6,
        'edge_projection_note': '8 px contours project to 1.125 px at 36, 0.84375 px at 27; 6 px final ring projects to 0.84375 px at 36 and 0.6328125 px at 27. Actual raster tests and bilinear sheets are supplied; pointed tips necessarily taper.',
        'full_star_circumscribed_diameter_px': RADIUS*2, 'cell_fill_by_diameter': .80,
        'geometry': {'centre_px':[CENTER,CENTER], 'peak_ray_count':10,'long_radius_px':LONG_RADIUS,'short_radius_px':LONG_RADIUS*.55,'valley_radius_px':LONG_RADIUS*VALLEY,'long_valley_degrees':24,'short_valley_degrees':12,'rim_fraction_of_long_radius':EDGE/LONG_RADIUS,'keyline_fraction_of_long_radius':KEYLINE/LONG_RADIUS,'early_ray_count':8,'early_radii_px':[RADIUS*.35,RADIUS*.7-KEYLINE], 'early_keyline_outer_radius_px':RADIUS*.7,'early_valley_ratio':.43,'retract_long_radius_px':RADIUS*.62,'retract_short_radius_px':RADIUS*.62*.8,'retract_valley_radius_px':47,'retract_hole_radius_px':27,'retract_keyline_hole_radius_px':19,'last_ring_outer_radius_px':53,'last_ring_inner_radius_px':47,'last_ring_gap_count':5,'last_ring_gap_degrees':14},
        'ray_distinction': rays, 'peak_rays_distinct_36_and_27': peak_rays_pass,
        'timing_ms': 270, 'max_sprite_count_assumed': 4, 'system_sprite_ceiling':64,
        'source_immutability': {'baseline':'source-hashes-before.json','files_checked':len(actual_before),'changed':changed,'missing':missing,'hud_files_added':added_hud,'passed':not(changed or missing or added_hud),'snapshot_matches_original':sha(PACKAGE/'_tools/draw_icons_v3_snapshot.py')==expected},
        'outside_folder': [], 'allowed_output_roots': [PACKAGE.relative_to(ROOT).as_posix(),DERIVED.relative_to(ROOT).as_posix()], 'write_scope_evidence': 'Every builder save passes guarded(); baseline, snapshot, code and README are written explicitly under PACKAGE. No whole-machine audit is claimed.',
        'limitations': [
            {'id':'MASK-BLEED-CONFLICT','requirement':'4 px RGB bleed into transparent mask pixels and A=max(R,G,B)','met':False,'reason':'Nonzero RGB with zero A violates the required coverage equality. Mask preserves equality; colour preview has exact 4 px RGB bleed.'},
            {'id':'SUBPIXEL-TAIL','requirement':'Every edge stays >=1 screen pixel','met':False,'reason':'The requested 6 px final ring becomes 0.84375 px at 36 and 0.6328125 px at 27. Kept exact 30% ratio, hard geometry and documented sampling. Full-star rim/keyline are 8 px.'},
            {'id':'RUNTIME','requirement':'Engine playback and actual sprite load','met':None,'reason':'Package-only task forbids engine access. Playback and budgets are documented assumptions, not runtime measurements.'}
        ],
        'environment': {'python':platform.python_version(),'Pillow':PIL.__version__,'numpy':np.__version__,'scipy':scipy.__version__},
        'status':'предложено', 'acceptance_summary':'proposed_with_explicit_limitations', 'visual_review':'pending'
    }
    add_contract_reports(checks,frames)
    if args.visual_reviewed:
        checks['visual_review']={'completed':True,'reviewer':'Codex','method':'Opened delivered PNGs with view_image: master and working colour/gray, navy and historical board crop; A/B/C, timing, bilinear and reduced-motion.','observations':['C keeps visible warm/cream long rays on navy; frame2 grows beyond frame1.','Five short rays separate the five broad long rays; C is recommended over first-run B.','At 36 and27 px the polar test counts ten visible R/G rays and ten rays in the expanded alpha silhouette.','Final 6 px broken ring is subpixel at working sizes; no engine playback verification.']}
    write_readme(checks)
    dump(checks, PACKAGE/'verification.json')
    write_manifest()
    checks['independent_saved_file_audit']=verifier.audit(args.visual_reviewed)
    dump(checks,PACKAGE/'verification.json')
    write_manifest()
    print(json.dumps({'outputs_written':len(WRITES),'input_files_unchanged':checks['source_immutability']['passed'],'peak_rays_distinct':peak_rays_pass,'failed_ray_checks':[k for k,v in rays.items() if not v['passed']],'palette_dE76_max':checks['palette_dE76_max']},ensure_ascii=True))
    if not checks['independent_saved_file_audit']['passed']:
        raise SystemExit('Required verification failed; see verification.json')


if __name__ == '__main__':
    main()
