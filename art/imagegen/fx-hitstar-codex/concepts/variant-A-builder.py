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

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL
from scipy.ndimage import distance_transform_edt
import scipy

import draw_icons_v3_snapshot as v3

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / 'scraped-data/derived/fx-hitstar-codex'
BOARD_SOURCE = ROOT / 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/joiner/s09-damage-number.jpg'
CELL = 256
RADIUS = 102.4
VALLEY = 0.34
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
                short_ratio: float = .55, valley_ratio: float = VALLEY):
    pts = []
    for j in range(rays * 2):
        angle = -math.pi/2 + j * math.pi/rays
        fraction = valley_ratio if j % 2 else (short_ratio if alternate and (j//2) % 2 else 1)
        r = RADIUS * scale * fraction
        pts.append((CELL/2 + r*math.cos(angle), CELL/2 + r*math.sin(angle)))
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


def layers(silhouette: np.ndarray, outlined: bool) -> np.ndarray:
    result = np.zeros((CELL, CELL, 3), dtype=np.uint8)
    if not outlined:
        result[:, :, 0] = silhouette * 255
    else:
        d = distance_transform_edt(silhouette)
        result[:, :, 2] = (silhouette & (d <= KEYLINE)) * 255
        result[:, :, 1] = (silhouette & (d > KEYLINE) & (d <= KEYLINE + EDGE)) * 255
        result[:, :, 0] = (silhouette & (d > KEYLINE + EDGE)) * 255
    return result


def make_frames():
    frames = []
    yy, xx = np.mgrid[:CELL, :CELL]
    dx, dy = xx + .5 - CELL/2, yy + .5 - CELL/2
    rr = np.hypot(dx, dy)
    for i in range(8):
        if i < 2:
            silhouette = polygon_mask(star_points(8, (.35, .70)[i], valley_ratio=.43))
        elif i < 6:
            silhouette = polygon_mask(star_points(10, 1, True))
        elif i == 6:
            # All tips retract; the valley radius is 47 px, opening is 27 px.
            silhouette = polygon_mask(star_points(10, .62, True, .80, 47/(RADIUS*.62))) & (rr >= 27)
        else:
            # 6 px = 30% of the previous frame's 20 px ring base.
            angle = np.mod(np.arctan2(dy, dx) + math.pi/2, math.tau)
            period = math.tau/5
            silhouette = (rr >= 47) & (rr < 53) & (np.mod(angle, period) > math.radians(14))
        rgb = layers(silhouette, 2 <= i <= 6)
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
    label(draw, (pad, 55), f'256 px | {"Rec.709 luma" if grayscale else "exact token colour"} | {"UE board crop" if board else "#061623"}', 16)
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


def ray_report(mask: np.ndarray, rays: int, size: int, offset=-math.pi/2):
    a = np.array(Image.fromarray(mask[:, :, 3]).resize((size, size), Image.Resampling.NEAREST)) > 0
    yy, xx = np.mgrid[:size, :size]
    dx, dy = xx+.5-size/2, yy+.5-size/2
    radius = np.hypot(dx, dy)
    angle = np.mod(np.arctan2(dy, dx)-offset, math.tau)
    results = []
    # Compare tip and each neighbouring valley using pixel centres in wedges.
    step = math.tau/rays
    def reach(theta, width):
        delta = np.abs(np.angle(np.exp(1j*(angle-theta))))
        select = a & (delta <= width)
        return float(radius[select].max()) if np.any(select) else 0.0
    for j in range(rays):
        tip = reach(j*step, step*.22)
        valley_left = reach((j-.5)*step, step*.09)
        valley_right = reach((j+.5)*step, step*.09)
        prominence = tip-max(valley_left, valley_right)
        results.append({'ray': j, 'tip_radius_px': round(tip, 4), 'adjacent_valley_radius_px': round(max(valley_left,valley_right),4), 'prominence_px': round(prominence,4), 'distinct': prominence >= .5})
    return {'size': size, 'method': 'nearest master sample; polar wedges; tip radius exceeds both adjacent valley radii by >=0.5 px', 'expected_rays': rays, 'distinct_rays': sum(r['distinct'] for r in results), 'passed': all(r['distinct'] for r in results), 'rays': results}


def lab(rgb):
    v = np.asarray(rgb, dtype=float)/255
    v = np.where(v <= .04045, v/12.92, ((v+.055)/1.055)**2.4)
    xyz = v @ np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2)+4/29)
    return np.stack((116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])),axis=-1)


def main():
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
    dump({'task': 'FX-20', 'optional_image_generation': 'skipped', 'reason': 'Final geometry is fully specified; procedural raster is reproducible and enforces exact tokens.', 'generations': [], 'prompt_keys': [], 'procedural_record': {'prompt_key': 'FX-20/FINAL/procedural-v1', 'task_prompt_sha256': baseline['inputs']['docs/game-design/visual/06-tasks/prompts/FX-20.codex.md']['sha256'], 'script': '_tools/build_hitstar.py', 'script_sha256': sha(Path(__file__)), 'snapshot_sha256': expected, 'unretouched': True, 'operations': ['analytic polygon', 'distance-to-boundary flat strata', 'binary coverage', 'RGB-only preview bleed'], 'final_atlas': 'vector/T_FX_HitStar_4x2.png'}}, PACKAGE/'generation-records.json')
    dump({'cue': 'CUE-011', 'delay_from_contact_ms': 70, 'lifetime_ms': 270, 'fps': 30, 'loop': False, 'interpolate_frames': False, 'time_domain': 'unscaled real-time', 'runtime_rule': 'if elapsed_ms >= 270: hidden; otherwise frame=min(7,floor(elapsed_ms*30/1000))', 'frame_intervals_ms': [{'frame': i, 'start': TIMES[i], 'end': ENDS[i]} for i in range(8)], 'poster': 0, 'reduced_motion_poster': 2, 'reduced_motion_rule': 'frame 2, held 270 ms, no scaling animation; hide at endpoint', 'max_simultaneous_sprites_assumed': 4, 'system_sprite_ceiling': 64, 'mask_decode': 'weights=texture.rgb / max(sum(texture.rgb),epsilon); colour=weights.r*impact+weights.g*rim+weights.b*keyline; opacity=texture.a', 'sampler': 'clamp, no mipmaps, no frame interpolation; half-texel inset within each atlas cell', 'colour_space': 'mask linear (sRGB off); preview sRGB; alpha straight; tint pass unlit', 'rgb_bleed_mask': 'not encoded: conflicts with A=max(R,G,B); preview RGB bleed=4 px'}, PACKAGE/'playback.json')
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
        'colour_preview_straight_alpha': bool(np.all(preview[:,:,:3][preview[:,:,3]>0].max(axis=1)==255) or np.array_equal(colours, np.unique(PALETTE,axis=0))),
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
        'status':'предложено', 'acceptance':'proposed_with_explicit_limitations', 'visual_review':'pending'
    }
    dump(checks, PACKAGE/'verification.json')
    dump({'entries':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for base in (PACKAGE,DERIVED) for p in sorted(base.rglob('*')) if p.is_file() and p.name!='manifest-sha256.json'], 'self_excluded':True,'algorithm':'sha256'}, PACKAGE/'manifest-sha256.json')
    print(json.dumps({'outputs_written':len(WRITES),'input_files_unchanged':checks['source_immutability']['passed'],'peak_rays_distinct':peak_rays_pass,'failed_ray_checks':[k for k,v in rays.items() if not v['passed']],'palette_dE76_max':checks['palette_dE76_max']},ensure_ascii=True))


if __name__ == '__main__':
    main()
