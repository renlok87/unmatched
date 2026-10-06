#!/usr/bin/env python
"""FX-29 procedural extension; the v3 snapshot is read-only and never executed.

Run from any directory: python -B <package>/_tools/build_vortex.py
Only PACKAGE and DERIVED may receive files. No subprocesses, engine or git.
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / 'scraped-data/derived/fx-vortex-codex'
SOURCE = ROOT / 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/joiner/s09-damage-number.jpg'
CELL = 256
SNAPSHOT = PACKAGE/'_tools/draw_icons_v3_snapshot.py'
# Extend the copied generator's literal palette without running its icon exports.
tree = ast.parse(SNAPSHOT.read_text(encoding='utf-8'))
palette = next(ast.literal_eval(n.value) for n in tree.body
               if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TOKENS' for t in n.targets))
TOKENS = {'body': palette['text.secondary'], 'edge_flash': palette['card.cream'], 'keyline': palette['mark.keyline']}
assert list(TOKENS.values()) == ['#B9B2A6','#F9EBDB','#111317']
RGB = [tuple(bytes.fromhex(v[1:])) for v in TOKENS.values()]
NAVY = (6, 22, 35)
WRITES = []
PARAMS = {
    'outer_radius_px': 115.2, 'inner_radius_px': 65.0,
    'body_width_px_at_full_size': [15.36, 10.24],
    'cream_inner_edge_px': 4, 'dark_outer_edge_px': 4,
    'gap_centres_degrees': [[0, 120, 240], [60, 180, 300]],
    'gap_width_degrees': [28, 32],
    'chip_polygon_local_px': [[-17,-6],[9,-8],[17,-2],[12,7],[-11,8]],
    'chip_polygons_local_px': [[[-17,-6],[9,-8],[17,-2],[12,7],[-11,8]], [[-17,-3],[-10,-8],[14,-6],[17,3],[6,8],[-13,6]], [[-17,-7],[6,-8],[17,0],[11,8],[-12,5]]],
    'chip_polygon_indices': [0,1,2,0,1,2],
    'chip_rotation_start_degrees': [5,40,75,110,145,180],
    'chip_spin_degrees_per_frame': [15,15,15,15,15,15],
    'chip_facet_cut_local': {'axis':'x','operator':'<','value_px':-4},
    'chip_scale': 'common ring scale; keyline fixed at 4 px',
    'chip_draw_order': 'shards first, intact rings above',
    'chip_start_angles_degrees': [[105,150,195],[240,285,330]],
    'chip_orbit_radius_px': [75,75], 'chip_radial_drift': 0.15,
    'camera_vertical_scale': 0.82, 'duration_ms': 600,
    'frame_duration_ms': 37.5, 'damage_flash_frame': 12,
    'damage_flash_sector_degrees': 40, 'damage_flash_centre_offset_degrees': 60,
    'damage_flash_absolute_centre_degrees': 300, 'damage_flash_band': 'full outer body R -> G',
    'figure_bbox_xyxy': [795,647,838,702], 'figure_height_px': 55,
    'figure_bbox_includes': 'Medusa silhouette and base disc; excludes HUD 14/16 and board-space outline',
    'ingame_outer_diameter_1080p_px': 77.0, 'ingame_outer_diameter_720p_px': 77.0*2/3,
    'damage_flash_onset_ms': 450, 'damage_flash_midpoint_ms': 468.75,
    'terminal_arc_width_degrees': 24, 'bleed_px_preview_only': 4,
    'board_crop_xyxy': [692,562,948,818],
}


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def allowed(path):
    path = path.resolve()
    if not any(path.is_relative_to(folder.resolve()) for folder in (PACKAGE, DERIVED)):
        raise ValueError(f'Outside allowed folders: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    WRITES.append(relative(path))
    return path


def save_image(im, path):
    im.save(allowed(path))


def save_json(data, path):
    allowed(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def font(size=16):
    return ImageFont.truetype('C:/Windows/Fonts/arial.ttf', size)


def state(i):
    if i <= 4:
        scale, rotation, drift = .4 + .6*i/4, 90*i/4, 0
    elif i <= 10:
        scale, rotation, drift = 1, 90 + 120*(i-4)/6, .15*(i-4)/6
    elif i <= 13:
        scale, rotation, drift = 1 - .4*(i-10)/3, 210 + 15*(i-10), .15
    else:
        scale, rotation, drift = .6, 255, .15
    return scale, rotation, drift


Y, X = np.mgrid[:CELL, :CELL]
DX, DY = X + .5 - CELL/2, Y + .5 - CELL/2
RADIUS = np.hypot(DX, DY)
ANGLE = np.degrees(np.arctan2(DY, DX)) % 360


def angular_distance(a, b):
    return np.abs((a-b+180) % 360-180)


def build_frame(i):
    labels = np.zeros((CELL, CELL), dtype=np.uint8)
    ring_layers = []
    scale, rotation, drift = state(i)
    if i == 15:
        return labels, [labels.copy(), labels.copy()]
    for ring, base in enumerate((115.2,65)):
        rot = rotation if ring == 0 else -rotation
        radius = base * scale
        body_width = PARAMS['body_width_px_at_full_size'][ring] * scale
        thickness = body_width + 8
        centres = np.array(PARAMS['gap_centres_degrees'][ring]) + rot
        distance = np.minimum.reduce([angular_distance(ANGLE, c) for c in centres])
        gap_half = PARAMS['gap_width_degrees'][ring] / 2
        active = distance > gap_half
        end_inset = np.degrees(4 / max(radius-thickness/2, 1))
        if i == 14:
            # Break each surviving sector into two isolated, short 24-degree arcs.
            arc_centres = [c + shift for c in centres for shift in (40,80)]
            arc_dist = np.minimum.reduce([angular_distance(ANGLE,c) for c in arc_centres])
            arc_half = PARAMS['terminal_arc_width_degrees']/2
            active = arc_dist <= arc_half
            colour_active = arc_dist <= max(0,arc_half-end_inset)
        else:
            colour_active = distance > gap_half + end_inset
        full = (RADIUS <= radius) & (RADIUS >= radius-thickness) & active
        layer = np.zeros_like(labels)
        layer[full] = 3
        layer[full & colour_active & (RADIUS <= radius-4)] = 1
        layer[full & colour_active & (RADIUS < radius-4-body_width)] = 2
        labels[full] = layer[full]
        ring_layers.append(layer)
    # Draw chips underneath intact ring masks: no dark chip edge can notch a band.
    chip_labels = np.zeros_like(labels)
    if 1 <= i <= 13:
        count = min(6, math.ceil(6*i/4))
        for k in range(count):
            chip = chip_geometry(i,k)
            chip_labels[chip['mask']] = 3
            chip_labels[chip['fill']] = 1
            chip_labels[chip['facet']] = 2
    occupied = labels > 0
    chip_labels[occupied] = labels[occupied]
    labels = chip_labels
    if i == 12:
        sector = angular_distance(ANGLE,rotation+PARAMS['damage_flash_centre_offset_degrees']) <= 20
        labels[sector & (ring_layers[0] == 1)] = 2
    return labels,ring_layers


def chip_geometry(i,k):
    scale,rotation,drift = state(i)
    group,item = divmod(k,3)
    orbit_angle = math.radians(PARAMS['chip_start_angles_degrees'][group][item]+rotation)
    orbit = PARAMS['chip_orbit_radius_px'][group]*scale*(1+drift)
    cx,cy = 128+orbit*math.cos(orbit_angle),128+orbit*math.sin(orbit_angle)
    spin = math.radians(PARAMS['chip_rotation_start_degrees'][k]+15*i)
    poly = np.array(PARAMS['chip_polygons_local_px'][k%3],float)*scale
    transform = np.array([[math.cos(spin),-math.sin(spin)],[math.sin(spin),math.cos(spin)]])
    points = poly @ transform.T + [cx,cy]
    # Pixel-centre polygon rasterization and Euclidean inward 4px keyline.
    px,py = X+.5,Y+.5
    inside = np.zeros((CELL,CELL),bool)
    distance = np.full((CELL,CELL),np.inf)
    for a,b in zip(points,np.roll(points,-1,axis=0)):
        inside ^= ((a[1]>py)!=(b[1]>py)) & (px < (b[0]-a[0])*(py-a[1])/(b[1]-a[1]+1e-20)+a[0])
        v=b-a
        t=np.clip(((px-a[0])*v[0]+(py-a[1])*v[1])/np.dot(v,v),0,1)
        distance=np.minimum(distance,np.hypot(px-a[0]-t*v[0],py-a[1]-t*v[1]))
    fill=inside & (distance>=4)
    local_x=((px-cx)*math.cos(spin)+(py-cy)*math.sin(spin))/scale
    facet=fill & (local_x < -4)
    return {'mask':inside,'fill':fill,'facet':facet,'points':points.tolist(),'centre':[cx,cy]}



def mask(labels):
    out = np.zeros((CELL,CELL,4),dtype=np.uint8)
    for k in (1,2,3):
        out[:,:,k-1] = (labels == k)*255
    out[:,:,3] = np.max(out[:,:,:3],axis=2)
    return Image.fromarray(out)


def preview(labels):
    out = np.zeros((CELL,CELL,4),dtype=np.uint8)
    for k,colour in enumerate(RGB,1):
        out[labels == k,:3] = colour
    out[:,:,3] = (labels != 0)*255
    occupied = labels != 0
    # Four-pixel Chebyshev bleed; each cell is padded independently, never across tiles.
    original = out[:,:,:3].copy()
    for distance in range(1,5):
        for dy in range(-distance,distance+1):
            for dx in range(-distance,distance+1):
                if max(abs(dx),abs(dy)) != distance:
                    continue
                sy = slice(max(0,-dy), min(CELL,CELL-dy))
                sx = slice(max(0,-dx), min(CELL,CELL-dx))
                ty = slice(max(0,dy), min(CELL,CELL+dy))
                tx = slice(max(0,dx), min(CELL,CELL+dx))
                eligible = occupied[sy,sx] & ~occupied[ty,tx]
                empty = np.all(out[ty,tx,:3] == 0,axis=2)
                dest = out[ty,tx,:3]
                dest[eligible & empty] = original[sy,sx][eligible & empty]
    return Image.fromarray(out)


def atlas(frames):
    im = Image.new('RGBA',(1024,1024))
    for i,frame in enumerate(frames):
        im.paste(frame,((i%4)*256,(i//4)*256))
    return im


def grey(im):
    a = np.asarray(im.convert('RGB')).astype(float)
    v = np.rint(a @ np.array([.2126,.7152,.0722])).astype(np.uint8)
    return Image.fromarray(np.repeat(v[:,:,None],3,axis=2))


def squash(im):
    output = Image.new('RGBA',im.size)
    h = round(im.height*.82)
    output.paste(im.resize((im.width,h),Image.Resampling.NEAREST),(0,(im.height-h)//2))
    return output


def composite(frame, size, board=False, pitch=False):
    fg = squash(frame) if pitch else frame
    if board:
        bg = Image.open(SOURCE).convert('RGB').crop(tuple(PARAMS['board_crop_xyxy'])).convert('RGBA')
    else:
        bg = Image.new('RGBA',(256,256),NAVY+(255,))
    bg.alpha_composite(fg)
    if board and pitch:
        # Restore the supplied figure's small foreground polygon for a static occlusion mockup.
        original = Image.open(SOURCE).convert('RGB').crop(tuple(PARAMS['board_crop_xyxy'])).convert('RGBA')
        cut = Image.new('L',(256,256))
        ImageDraw.Draw(cut).polygon([(110,88),(127,83),(142,95),(145,124),(131,135),(108,128)],fill=255)
        bg.paste(original,(0,0),cut)
    return bg.convert('RGB').resize((size,size),Image.Resampling.NEAREST)


def sheet(frames,size,board=False,pitch=False,grayscale=False):
    magnify = 4 if size in (48,64) else 1
    slot = size*magnify
    sheet = Image.new('RGB',(4*(slot+16)+16,4*(slot+38)+16),NAVY)
    d = ImageDraw.Draw(sheet)
    for i,f in enumerate(frames):
        tile = composite(f,size,board,pitch)
        if grayscale:
            tile = grey(tile)
        tile = tile.resize((slot,slot),Image.Resampling.NEAREST)
        x,y = 16+(i%4)*(slot+16),16+(i//4)*(slot+38)
        sheet.paste(tile,(x,y))
        d.text((x,y+slot+4),f'{i:02d}  {i*37.5:g}-{(i+1)*37.5:g} ms',fill=RGB[1],font=font(14))
    return grey(sheet) if grayscale else sheet


def ingame_effect(mask_cell,height):
    # Cell width includes the original margin. Decode straight mask, then bilinear filter
    # premultiplied coverage channels (equivalent to sampling mask weights on the GPU).
    width=round(height*1.4*256/(2*PARAMS['outer_radius_px']))
    out_height=round(width*.82)
    channels=np.asarray(mask_cell.resize((width,out_height),Image.Resampling.BILINEAR)).astype(float)/255
    coverage=channels[:,:,:3].sum(axis=2)
    rgb=channels[:,:,:3] @ np.array(RGB,float)
    rgb=np.divide(rgb,coverage[:,:,None],out=np.zeros_like(rgb),where=coverage[:,:,None]>0)
    rgba=np.concatenate((np.rint(rgb),np.rint(coverage[:,:,None]*255)),axis=2).clip(0,255).astype(np.uint8)
    return Image.fromarray(rgba),channels


def ingame_tile(mask_cell,resolution,board):
    factor=resolution/1080
    height=PARAMS['figure_height_px']*factor
    effect,_=ingame_effect(mask_cell,height)
    tile_size=round(3*height*1.4)
    cx,cy=round(817*factor),round(691*factor)
    left,top=cx-tile_size//2,cy-tile_size//2
    source=Image.open(SOURCE).convert('RGB')
    if resolution==720:
        source=source.resize((1280,720),Image.Resampling.BILINEAR)
    original=source.crop((left,top,left+tile_size,top+tile_size)).convert('RGBA')
    tile=original.copy() if board else Image.new('RGBA',original.size,NAVY+(255,))
    tile.alpha_composite(effect,((tile_size-effect.width)//2,(tile_size-effect.height)//2))
    if board:
        cut=Image.new('L',source.size)
        # Measured silhouette including base, not the space outline; far half occluded.
        points=[(809,647),(821,647),(827,659),(825,667),(833,678),(838,690),(835,697),(825,702),(807,702),(798,697),(795,688),(800,677),(806,665)]
        ImageDraw.Draw(cut).polygon([(round(x*factor),round(y*factor)) for x,y in points],fill=255)
        tile.paste(original,(0,0),cut.crop((left,top,left+tile_size,top+tile_size)))
    return tile.convert('RGB')


def build_ingame_sheets(mask_atlas):
    for resolution in (1080,720):
        for board in (False,True):
            for zoom in (1,4):
                tile_size=round(3*55*1.4*resolution/1080)*zoom
                out=Image.new('RGB',(4*(tile_size+16)+16,4*(tile_size+38)+16),NAVY)
                draw=ImageDraw.Draw(out)
                for i in range(16):
                    cell=mask_atlas.crop(((i%4)*256,(i//4)*256,(i%4+1)*256,(i//4+1)*256))
                    tile=ingame_tile(cell,resolution,board).resize((tile_size,tile_size),Image.Resampling.NEAREST)
                    x,y=16+i%4*(tile_size+16),16+i//4*(tile_size+38)
                    out.paste(tile,(x,y))
                    draw.text((x,y+tile_size+4),f'{i:02d} {i*37.5:g}-{(i+1)*37.5:g} ms',fill=RGB[1],font=font(12))
                name=f'ingame-{resolution}p-native'+('-nearest4x' if zoom==4 else '')
                folder=(DERIVED if board else PACKAGE)/'comparison'
                save_image(out,folder/(name+'-colour.png'))
                save_image(grey(out),folder/(name+'-gray-rec709.png'))


def run():
    baseline = json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((PACKAGE/'_tools/draw_icons_v3_snapshot.py').read_bytes()).hexdigest() == baseline['inputs']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']
    frames, layers, labels = [],[],[]
    for i in range(16):
        a,b = build_frame(i)
        labels.append(a)
        layers.append(b)
        frames.append(preview(a))
    mask_atlas, colour_atlas = atlas([mask(a) for a in labels]),atlas(frames)
    for path,im in [('vector/T_FX_MedusaVortex_4x4.png',mask_atlas),
                    ('vector/T_FX_MedusaVortex_4x4-preview.png',colour_atlas),
                    ('concepts/procedural-v2-mask-unretouched.png',mask_atlas),
                    ('concepts/procedural-v2-colour-unretouched.png',colour_atlas),
                    ('vector/T_FX_MedusaVortex-poster-frame0.png',frames[0]),
                    ('vector/T_FX_MedusaVortex-reduced-motion-frame6.png',frames[6])]:
        save_image(im,PACKAGE/path)
    for size in (256,64,48):
        for grayscale in (False,True):
            suffix = 'gray-rec709' if grayscale else 'colour'
            scale_suffix = '-nearest4x' if size != 256 else ''
            for pitch in (False,True):
                angle = 'pitch55-scale082' if pitch else 'plan'
                name = f'{angle}-{size}px{scale_suffix}-{suffix}.png'
                save_image(sheet(frames,size,pitch=pitch,grayscale=grayscale),PACKAGE/'comparison'/name)
                save_image(sheet(frames,size,board=True,pitch=pitch,grayscale=grayscale),DERIVED/'comparison'/name)
    strip = Image.new('RGB',(4*256,256))
    for k,i in enumerate((0,6,12,14)):
        strip.paste(composite(frames[i],256),(k*256,0))
    save_image(strip,PACKAGE/'concepts/procedural-v2-four-step-unretouched.png')
    timing = Image.new('RGB',(8*160+16,2*190+16),NAVY)
    td = ImageDraw.Draw(timing)
    for i,f in enumerate(frames):
        x,y = 8+(i%8)*160,8+(i//8)*190
        timing.paste(composite(f,144),(x,y))
        td.text((x,y+148),f'{i:02d} / {i*37.5:g} ms',font=font(14),fill=RGB[1])
        td.text((x,y+165),f'to {(i+1)*37.5:g} ms',font=font(12),fill=RGB[0])
    save_image(timing,PACKAGE/'comparison/timing-strip.png')
    save_image(grey(timing),PACKAGE/'comparison/timing-strip-gray-rec709.png')
    board_timing=timing.copy()
    for i,f in enumerate(frames):
        x,y=8+(i%8)*160,8+(i//8)*190
        board_timing.paste(composite(f,144,board=True,pitch=True),(x,y))
    save_image(board_timing,DERIVED/'comparison/timing-strip.png')
    save_image(grey(board_timing),DERIVED/'comparison/timing-strip-gray-rec709.png')
    for i,name in ((0,'poster-frame0'),(6,'reduced-motion-frame6')):
        save_image(composite(frames[i],256,pitch=True),PACKAGE/f'comparison/{name}-pitch55.png')
    save_json(PARAMS,PACKAGE/'parameters.json')
    records=json.loads((PACKAGE/'generation-records.json').read_text(encoding='utf-8'))
    entry={'prompt_key':'FX-29/procedural/v2',
           'exact_prompt_source':'docs/game-design/visual/06-tasks/prompts/FX-29.fix1.codex.md#Task',
           'exact_prompt_source_sha256':hashlib.sha256((ROOT/'docs/game-design/visual/06-tasks/prompts/FX-29.fix1.codex.md').read_bytes()).hexdigest(),
           'method':'deterministic corrective geometry; zero image generations',
           'script':'_tools/build_vortex.py','parameters':'parameters.json',
           'unretouched':['concepts/procedural-v2-mask-unretouched.png','concepts/procedural-v2-colour-unretouched.png','concepts/procedural-v2-four-step-unretouched.png']}
    records['generations']=[e for e in records['generations'] if e['prompt_key']!='FX-29/procedural/v2']+[entry]
    save_json(records,PACKAGE/'generation-records.json')
    build_ingame_sheets(mask_atlas)
    mask_gray=grey(colour_atlas).convert("RGBA"); mask_gray.putalpha(mask_atlas.getchannel("A"))
    save_image(mask_gray,PACKAGE/"vector/T_FX_MedusaVortex_4x4-gray-rec709.png")
    # Every final/poster and comparison export also has an exact Rec.709 copy.
    for folder in (PACKAGE/'vector',PACKAGE/'comparison',DERIVED/'comparison'):
        for path in list(folder.glob('*.png')):
            if 'gray-rec709' in path.name or path.name.endswith('-colour.png') or path.name=='T_FX_MedusaVortex_4x4.png':
                continue
            im=Image.open(path)
            gray=grey(im)
            if im.mode=='RGBA':
                gray=gray.convert('RGBA'); gray.putalpha(im.getchannel('A'))
            save_image(gray,path.with_name(path.stem+'-gray-rec709.png'))
    # Keep separate clean geometry evidence: 2 rings, without optional chip overlap.
    evidence = []
    for i in range(15):
        for size in (64,48):
            for ring in (0,1):
                alpha = Image.fromarray((layers[i][ring]>0).astype(np.uint8)*255).resize((size,size),Image.Resampling.NEAREST)
                evidence.append({'frame':i,'size':size,'ring':ring,'visible_pixels':int(np.count_nonzero(alpha))})
    save_json({'ring_visibility':evidence},PACKAGE/'geometry-evidence.json')
    changes = []
    for name,info in baseline['inputs'].items():
        p = ROOT/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != info['sha256']:
            changes.append(name)
    hud_now = {relative(p) for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    hud_before = {x for x in baseline['inputs'] if x.startswith('art/imagegen/hud-icons-v3/')}
    save_json({'inputs_unchanged':not changes,'changed_inputs':changes,
               'hud_tree_added':sorted(hud_now-hud_before),'hud_tree_removed':sorted(hud_before-hud_now)},PACKAGE/'source-hashes-after.json')
    save_json({'scope':'all filesystem writes performed by this generator; plus package-only source edits',
               'allowed_roots':[relative(PACKAGE),relative(DERIVED)],'writes':sorted(set(WRITES)),
               'outside_folder':[],'git_invocations':0,'unreal_reads_or_writes':0,
               'note':'No claim of a global disk audit; other sessions may operate concurrently.'},PACKAGE/'write-audit.json')
    print(f'Built 16 frames, {len(WRITES)} files; changed input hashes: {len(changes)}')


if __name__ == '__main__':
    run()
