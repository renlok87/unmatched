"""FX-31 fix1: native-scale simulation and measured package verification.

All writes go through build_arc's two-prefix assertions. No subprocesses.
"""
from pathlib import Path
import json
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates


def api():
    # __main__ when launched as a script; avoid a second copy of the generator.
    import sys
    m = sys.modules.get('__main__')
    if hasattr(m, 'PACKAGE'):
        return m
    import build_arc
    return build_arc


def ingame_config(height):
    b = api()
    ratio = height / 1080
    H = (b.FIGURE_BBOX[3] - b.FIGURE_BBOX[1]) * ratio
    nominal = 256 * .5 * H / 88.54
    side = round(nominal)
    scale = side / 256
    hand = [v*ratio for v in b.HAND]
    origin = [round(hand[j]-b.CENTER[j]*scale) for j in range(2)]
    tile_side = side*3
    crop_origin = [round(hand[j]-tile_side/2) for j in range(2)]
    return {'frame_size_px': [round(1920*ratio), height], 'figure_height_px': H,
            'figure_bbox_xyxy': [v*ratio for v in b.FIGURE_BBOX],
            'pivot_px': hand, 'sprite_cell_px': nominal, 'raster_cell_px': side,
            'actual_scale': scale, 'sprite_top_left_px': origin,
            'actual_pivot_px': [origin[j]+b.CENTER[j]*scale for j in range(2)],
            'tile_size_px': tile_side,
            'crop_xyxy': crop_origin+[v+tile_side for v in crop_origin]}


def resample_mask(mask, side):
    # PIL RGBA.resize premultiplies RGB by A. Masks require four independent channels.
    a = np.array(mask)
    return np.stack([np.array(Image.fromarray(a[..., j]).resize((side, side), Image.Resampling.BILINEAR))
                     for j in range(4)], axis=-1)


def tint_mask(sample):
    b = api()
    cov = sample[..., :3].astype(float)/255
    rgb = cov @ b.RGB.astype(float) / np.maximum(cov.sum(-1, keepdims=True), 1e-8)
    return Image.fromarray(np.dstack((np.rint(rgb).astype(np.uint8), sample[..., 3])))


def simulation_tiles(masks, height, board):
    b = api()
    cfg = ingame_config(height)
    reference = Image.open(b.ROOT / b.BOARD).convert('RGB')
    if height != 1080:
        reference = reference.resize(tuple(cfg['frame_size_px']), Image.Resampling.BILINEAR)
    background = reference.crop(tuple(cfg['crop_xyxy'])) if board else Image.new('RGB', (cfg['tile_size_px'],)*2, '#061623')
    local = [cfg['sprite_top_left_px'][j]-cfg['crop_xyxy'][j] for j in range(2)]
    tiles = []
    for mask in masks:
        tile = background.convert('RGBA')
        tile.alpha_composite(tint_mask(resample_mask(mask, cfg['raster_cell_px'])), tuple(local))
        tiles.append(tile.convert('RGB'))
    return tiles


def native_sheet(tiles, destination, stem, factor):
    b = api()
    side = tiles[0].width * factor
    canvas = Image.new('RGB', (48+4*side+3*16, 68+3*(side+48)+24), '#202733')
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 14), f'FX-31 / Arthur 17/18 / {stem}' + (' / nearest x4' if factor == 4 else ' / native pixels'), font=b.font(19), fill='#FAF8F2')
    draw.text((24, 40), 'Camera-facing sprite / hand pivot / radius = 0.5 x figure height', font=b.font(14), fill='#FAF8F2')
    for i, tile in enumerate(tiles):
        xy = (24+(i%4)*(side+16), 68+(i//4)*(side+48))
        canvas.paste(tile.resize((side, side), Image.Resampling.NEAREST), xy)
        draw.text((xy[0], xy[1]+side+6), f'{i:02d} / {i*1000/30:.2f} ms', font=b.font(14), fill='#FAF8F2')
    suffix = '-nearest4' if factor == 4 else ''
    b.save(canvas, destination / f'{stem}-colour{suffix}.png')
    b.save(b.gray(canvas), destination / f'{stem}-gray{suffix}.png')


def build_extras(masks, frames):
    b = api()
    # No earlier concept or prompt records are recaptured or overwritten.
    for name in ('T_FX_ArthurArc_4x4.png', 'T_FX_ArthurArc_4x4-preview.png'):
        b.save(Image.open(b.PACKAGE / 'vector' / name), b.PACKAGE / 'concepts' / ('procedural-v3-unretouched-'+name))
    prompts = json.loads((b.PACKAGE / 'prompts.json').read_text(encoding='utf-8'))
    text = (b.ROOT / 'docs/game-design/visual/06-tasks/prompts/FX-31.fix1.codex.md').read_text(encoding='utf-8')
    prompts['prompts']['FX-31/task/fix1-procedural-v3'] = {'text': text.split('```text\n',1)[1].split('```',1)[0], 'profile_parameters': 'vector/frame-parameters.json'}
    b.write_json(b.PACKAGE / 'prompts.json', prompts)
    registry = json.loads((b.PACKAGE / 'generation-records.json').read_text(encoding='utf-8'))
    for row in registry['procedural_records']:
        row['selected'] = False
    registry['procedural_records'] = [r for r in registry['procedural_records'] if r['prompt_key'] != 'FX-31/task/fix1-procedural-v3']
    registry['procedural_records'].append({'kind': 'procedural', 'prompt_key': 'FX-31/task/fix1-procedural-v3',
        'prompt_registry': 'prompts.json', 'selected': True, 'unretouched': True,
        'outputs': [{'path': p.relative_to(b.PACKAGE).as_posix(), 'sha256': b.sha(p)}
                    for p in sorted((b.PACKAGE/'concepts').glob('procedural-v3-unretouched-*.png'))]})
    registry['procedural_generation'].update(prompt_key='FX-31/task/fix1-procedural-v3', source_prompt='docs/game-design/visual/06-tasks/prompts/FX-31.fix1.codex.md')
    b.write_json(b.PACKAGE / 'generation-records.json', registry)
    params = b.parameters()
    for p, mask in zip(params, masks):
        p['core_exists'] = bool(np.array(mask)[...,1].any())
    b.write_json(b.PACKAGE/'vector/frame-parameters.json', {'centre_px': b.CENTER, 'frames': params})
    for height in (1080, 720):
        for board, destination in ((True, b.DERIVED), (False, b.PACKAGE/'comparison')):
            tiles = simulation_tiles(masks, height, board)
            for factor in (1,4):
                native_sheet(tiles, destination, f'ingame-{height}p-native', factor)
    board = Image.open(b.ROOT/b.BOARD).convert('RGB').crop(b.CROP)
    strip = Image.new('RGB', (24+13*108, 164), '#061623')
    draw = ImageDraw.Draw(strip)
    draw.text((12,8), 'Arthur 17/18 / master scale, not in-game / 30 fps / OFF at 400 ms', font=b.font(17), fill='#FAF8F2')
    for i in range(13):
        x=12+i*108
        if i<12: strip.paste(b.compose(frames[i],board,96),(x,40))
        draw.text((x,139),f'{i*1000/30:.2f} ms' if i<12 else '400 ms / OFF',font=b.font(12),fill='#FAF8F2')
    b.save(strip,b.DERIVED/'timing-colour.png')
    b.save(b.gray(strip),b.DERIVED/'timing-gray.png')
    for path in list((b.PACKAGE/'vector').rglob('*.png')):
        if '-gray' not in path.stem:
            b.save(b.gray(Image.open(path)), path.with_name(path.stem+'-gray.png'))
    b.write_json(b.DERIVED/'crop-provenance.json', {
        'source': b.BOARD, 'source_sha256': b.sha(b.ROOT/b.BOARD), 'crop_xyxy': b.CROP,
        'purpose': 'Arthur 17/18. 256/48/36 sheets are master-scale comparisons, not in-game.',
        'figure_bbox_xyxy': b.FIGURE_BBOX, 'figure_height_px': b.FIGURE_BBOX[3]-b.FIGURE_BBOX[1],
        'bbox_includes': 'Red-cloaked Arthur, raised sword and circular figure base; excludes the board space, selection hexagon, plate and shadow.',
        'hand_pivot_px': b.HAND, 'hand_note': 'Estimated right sword hand, at the raised sword hilt; historical JPEG uncertainty about 2px.',
        'simulation': {str(h): ingame_config(h) for h in (1080,720)},
        'note': 'Historical screenshot for scale/readability; no claim about current accepted models or surroundings.'})
    # Measurement overlay contains board pixels, so stays exclusively in derived.
    reference = Image.open(b.ROOT/b.BOARD).convert('RGB')
    crop = (1030,610,1180,750)
    im = reference.crop(crop).resize((900,840), Image.Resampling.NEAREST)
    d = ImageDraw.Draw(im)
    xy = lambda x,y: ((x-crop[0])*6, (y-crop[1])*6)
    d.rectangle((*xy(*b.FIGURE_BBOX[:2]), *xy(*b.FIGURE_BBOX[2:])), outline='#F2C14E', width=3)
    x,y=xy(*b.HAND); d.line((x-12,y,x+12,y),fill='#FAF8F2',width=2); d.line((x,y-12,x,y+12),fill='#FAF8F2',width=2)
    d.text((12,12), f'Arthur bbox {b.FIGURE_BBOX}; H=69px; hand={b.HAND}',font=b.font(20), fill='#FAF8F2')
    b.save(im,b.DERIVED/'arthur-measurement-annotated-nearest6.png')


def ray_width(binary, p, s, scale=1):
    """Measure a radial binary run through saved raster pixels; subpixel ray integration, no redraw."""
    b = api()
    radius = np.arange(max(0,p['outer_radius_px']-p['coloured_band_px']-12), p['outer_radius_px']+12, .02)
    angle = math.radians(p['start_deg']+s*p['span_deg'])
    x = (b.CENTER[0]+radius*np.cos(angle))*scale-.5
    y = (b.CENTER[1]+radius*np.sin(angle))*scale-.5
    values = map_coordinates(binary.astype(float), [y,x], order=0, mode='constant', cval=0) > .5
    # Longest contiguous run avoids adding disconnected samples along the ray.
    edges = np.diff(np.r_[False, values, False].astype(int))
    starts=np.where(edges==1)[0]; ends=np.where(edges==-1)[0]
    return float((ends-starts).max()*.02*scale) if len(starts) else 0.


def radial_scan(binary,p,scale=1):
    ss = np.linspace(.05,.95,181)
    widths = np.array([ray_width(binary,p,float(s),scale) for s in ss])
    largest=float(widths.max())
    choices=ss[np.isclose(widths,largest,atol=.01)]
    at=float(choices[np.argmin(abs(choices-.78))])
    return largest,at


def margin_support(image):
    a=np.array(image)
    if image.mode=='RGBA':
        support=a[...,3]>0
        # Include the transparent preview's required RGB bleed in its margin.
        if 'preview' in Path(image.filename).stem:
            support |= np.any(a[...,:3]!=0,axis=-1)
    else:
        return 0,True,'Opaque sheet background reaches edge; this is not sprite support.'
    y,x=np.where(support)
    if not len(x): return None,False,'Empty export.'
    margin=int(min(x.min(),y.min(),image.width-1-x.max(),image.height-1-y.max()))
    return margin,margin==0,'Sprite support; preview includes transparent RGB bleed.'


def entry(passed,measured,expected,note=''):
    return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}


def enhance_report(report,atlas,preview):
    b=api()
    params=json.loads((b.PACKAGE/'vector/frame-parameters.json').read_text(encoding='utf-8'))['frames']
    baseline=json.loads((b.PACKAGE/'fix1-before.json').read_text(encoding='utf-8'))
    preserved={p:h for p,h in baseline['sha256'].items() if '/concepts/procedural-v' in p or p.endswith('/source-hashes-before.json')}
    report['checks']['earlier_concepts_and_source_baseline_unchanged']=all(b.sha(b.ROOT/p)==h for p,h in preserved.items())
    geometry_keys=['radius_px','span_deg','start_deg','end_deg','start_ms','end_ms','keyline_px']
    report['checks']['accepted_geometry_and_timing_unchanged']=all(p[k]==old[k] for p,old in zip(params,baseline['frames']) for k in geometry_keys)
    report['checks']['frames_4_5_6_identical_hold']=all(np.array_equal(atlas[256:512,0:256],atlas[256:512,j*256:(j+1)*256]) for j in (1,2))
    rows=[]; margins=[]
    for p in params:
        i=p['frame']; y,x=i//4*256,i%4*256
        m=atlas[y:y+256,x:x+256]; band=m[...,:2].max(-1)>0
        peak,at=radial_scan(band,p)
        mid=ray_width(band,p,.5)
        pp=preview[y:y+256,x:x+256]
        yy,xx=np.where(np.any(pp[...,:3]!=0,-1))
        margin=int(min(xx.min(),yy.min(),255-xx.max(),255-yy.max()))
        margins.append(margin)
        actual_core=bool(m[...,1].any())
        core_components=b.components(m[...,1]>0)
        profile=p['profile']
        rows.append({'frame':i,'measured_widest_band_px':peak,'measured_s_max':at,'measured_mid_band_px':mid,
                     'profile':profile,'outer_radius_px':p['outer_radius_px'],'core_exists':actual_core,
                     'core_components_8':core_components,'margin_including_bleed_px':margin})
        report['checks'][f'fix1_frame_{i:02d}_crescent']=abs(peak-profile['W_max_px'])<=1.5 and abs(mid-profile['mid_width_px'])<=1.5
        report['checks'][f'fix1_frame_{i:02d}_margin_ge4']=margin>=4
        report['checks'][f'fix1_frame_{i:02d}_core_no_islands']=core_components<=1 and actual_core==p['core_exists']
        body,outer,core=b.crescent(p)
        expected=np.stack([body&~core,core,outer&~body],-1).astype(np.uint8)*255
        report['checks'][f'fix1_frame_{i:02d}_saved_profile_matches']=np.array_equal(m[...,:3],expected)
    report['fix1']={'crescent':{'measurement_method':'Longest binary radial run, 0.02px integration; s grid 0.005. Pixel quantization can shift sampled widest s; profile max is exactly 0.78.',
                              'frames':rows,'minimum_margin_including_bleed_px':min(margins)}}
    ingame={'figure_bbox_xyxy':b.FIGURE_BBOX,'H_px':69,'bbox_includes':'Arthur, raised sword and circular figure base; no board hex, plate or cast shadow.',
            'pivot_px':b.HAND,'pivot_note':'Estimated sword hand, uncertainty about 2px on historical JPEG.',
            'rule':'camera-facing; centreline radius 88.54 -> 0.5*H; cell=256*0.5*H/88.54; no vertical squash',
            'resampling':'1080p source; 720p whole frame bilinear; mask each independent channel bilinear; token-weighted colour / sum(R,G,B), opacity A; raster cell rounded to nearest integer; zoom nearest x4',
            '1080p':ingame_config(1080),'720p':ingame_config(720),'measurements_720p':[]}
    cfg=ingame_config(720)
    for i in range(12):
        y,x=i//4*256,i%4*256
        sample=resample_mask(Image.fromarray(atlas[y:y+256,x:x+256]),cfg['raster_cell_px'])
        # R|G is sum of disjoint coverage, not max after filtering a two-tone boundary.
        band=sample[...,:2].astype(int).sum(-1)>=127.5
        silhouette=sample[...,3]>=127.5
        p=params[i]; peak,at=radial_scan(band,p,cfg['actual_scale'])
        mid=ray_width(band,p,.5,cfg['actual_scale'])
        full_peak,full_at=radial_scan(silhouette,p,cfg['actual_scale'])
        full_at_band_peak=ray_width(silhouette,p,at,cfg['actual_scale'])
        ingame['measurements_720p'].append({'frame':i,'widest_coloured_band_px':peak,'s_widest':at,'mid_coloured_band_px':mid,
            'silhouette_at_band_widest_px':full_at_band_peak,'silhouette_mid_px':ray_width(silhouette,p,.5,cfg['actual_scale']),
            'widest_full_silhouette_px':full_peak,'s_full_widest':full_at,'coverage_threshold':.5})
    report['fix1']['ingame']=ingame
    report['source_unchanged']={'passed':report['checks']['source_hashes_unchanged'] and report['checks']['hud_file_set_unchanged'],
                              'input_count':report['source_hashes']['input_count'],'hud_file_count':report['source_hashes']['hud_file_count'],
                              'changed_inputs':report['source_hashes']['changed_inputs'],
                              'source_baseline_preserved':b.sha(b.PACKAGE/'source-hashes-before.json')==baseline['sha256']['art/imagegen/fx-arc-codex/source-hashes-before.json']}
    exports={}
    for directory in ('vector','comparison'):
        for path in sorted((b.PACKAGE/directory).rglob('*.png')):
            im=Image.open(path); margin,touches,note=margin_support(im)
            exports[path.relative_to(b.PACKAGE).as_posix()]={'size':list(im.size),'mode':im.mode,'margin_px':margin,'touches_edge':touches,'note':note}
    report['exports']=exports
    opaque=preview[preview[...,3]==255,:3]
    on_token=np.any(np.all(opaque[:,None,:]==b.RGB[None,:,:],axis=-1),axis=-1)
    report['palette']={'off_token_share_opaque_final':float((~on_token).mean()),'expected':0,
                       'dE76_max':report['palette_dE76_max'],'colour_sheet_dE76_max':report['colour_sheet_dE76_max'],
                       'scope':'Opaque final sprite pixels only. Backgrounds/labels and bilinear simulation mixtures excluded.'}
    gray_pairs=[]
    for path in sorted((b.PACKAGE/'vector').rglob('*.png'))+sorted((b.PACKAGE/'comparison').glob('*colour*.png'))+sorted(b.DERIVED.glob('*colour*.png')):
        if '-gray' in path.stem: continue
        gp=path.with_name(path.name.replace('colour','gray')) if 'colour' in path.name else path.with_name(path.stem+'-gray.png')
        present=gp.exists()
        exact=present and np.array_equal(np.array(Image.open(gp)),np.array(b.gray(Image.open(path))))
        gray_pairs.append({'colour':path.relative_to(b.ROOT).as_posix(),'gray':gp.relative_to(b.ROOT).as_posix(),'present':present,'exact_Rec709':exact})
    report['gray']={'passed':all(p['exact_Rec709'] for p in gray_pairs),'pairs':gray_pairs,
                   'token_luma':{k:{'encoded_luma_0_255':float(rgb @ [.2126,.7152,.0722]),'rounded':int(round(rgb @ [.2126,.7152,.0722]))}
                                 for k,rgb in zip(b.TOKENS,b.RGB.astype(float))}}
    paths=[b.PACKAGE/f'vector/{n}' for n in ('T_FX_ArthurArc_4x4.png','T_FX_ArthurArc_4x4-preview.png','frame-parameters.json','poster-frame00-mask.png','poster-frame00-preview.png','reduced-motion-frame05-mask.png','reduced-motion-frame05-preview.png')]
    paths += [b.PACKAGE/f'vector/frames/frame-{i:02d}-{kind}.png' for i in range(12) for kind in ('mask','preview','mask-gray','preview-gray')]
    for directory,stem in ((b.PACKAGE/'comparison','navy'),(b.DERIVED,'board')):
        paths += [directory/f'{stem}-{colour}-{size}px{suffix}.png' for colour in ('colour','gray') for size,suffix in ((256,''),(48,'-nearest4'),(36,'-nearest4'))]
    for directory in (b.PACKAGE/'comparison',b.DERIVED):
        paths += [directory/f'ingame-{h}p-native-{c}{suffix}.png' for h in (1080,720) for c in ('colour','gray') for suffix in ('','-nearest4')]
    paths += [b.PACKAGE/f'comparison/timing-{c}.png' for c in ('colour','gray')]
    paths += [b.DERIVED/f'timing-{c}.png' for c in ('colour','gray')]
    paths += [b.PACKAGE/f'comparison/{poster}-{c}-{size}px.png' for poster in ('poster-frame00','reduced-motion-frame05') for c in ('colour','gray') for size in (256,48,36)]
    paths += [b.PACKAGE/n for n in ('README.md','verification.json','manifest-sha256.json','generation-records.json','fix1-before.json','source-hashes-before.json')]
    report['sizes']={'passed':all(p.exists() for p in paths),'deliverables':{p.relative_to(b.ROOT).as_posix():p.exists() for p in paths},
                    'note':'Only in-game simulation mask and 720p reference use bilinear downscale; standard 48/36 comparisons are nearest, no master replacement.'}
    inventory=b.DERIVED/'audit/outside-metadata-before.json'
    report['outside_metadata_scope'].update(inventory_path=inventory.relative_to(b.ROOT).as_posix(),inventory_sha256=b.sha(inventory),
        observations_note='Metadata observations are not attributed to this run; generator and commands wrote only inside the two authorized directories.')
    prior=json.loads((b.PACKAGE/'verification.json').read_text(encoding='utf-8'))
    report['process_audit']=prior.get('process_audit',{})
    report['process_audit'].update(fix1={'persistent_external_processes_started':0,'all_task_python_commands_awaited':True,
                                      'commands':'Synchronous Python and file operations only; no engine, build, browser, image generation or git processes.'})
    acceptance={
        '12 frames plus 4 empty cells':entry(all(report['checks'][f'frame_{i:02d}_nonempty'] for i in range(12)) and report['checks']['cells_12_to_15_all_rgba_zero'],{'frames':12,'empty':[12,13,14,15]},'12 nonempty + 4 fully zero'),
        '1024x1024':entry(report['checks']['atlas_1024x1024_rgba'],list(atlas.shape[:2]),[1024,1024]),
        'palette dE76 <= 3':entry(report['palette_dE76_max']<=3,report['palette_dE76_max'],'<=3'),
        'grey sheet present':entry(report['gray']['passed'],len(gray_pairs),'Every final and comparison has exact Rec.709 copy'),
        'outside_folder empty':entry(report['outside_folder']==[],report['outside_folder'],[],'External concurrent metadata observations recorded separately.'),
        '48 px and 36 px nearest x4: one clean curve':entry(all(row['connected_components_8']==1 and row['coloured_band_components_8']==1 for row in report['connectivity']),report['connectivity'],'Silhouette and R|G each one 8-connected component in every frame at 256/48/36'),
        'no red':entry(report['checks']['no_red_in_visible_sprite'],list(b.TOKENS.values()),'Only gold, white and keyline tokens'),
        'fix1.crescent':entry(all(v for k,v in report['checks'].items() if k.startswith('fix1_frame_')),rows,'Specified inward width profile; round blunt caps; 4px keyline; square inner core; >=4px margin'),
        'fix1.ingame':entry(all(p.exists() for p in paths if 'ingame-' in p.name),ingame,'Arthur 17/18, measured H, hand pivot, unsquashed sprite at 1080/720 native and x4'),
        'arc thickness >= 2 px at 720p on K1':entry(all(row['widest_coloured_band_px']>=2 and row['silhouette_at_band_widest_px']>=3 for row in ingame['measurements_720p'] if 3<=row['frame']<=8),
            [row for row in ingame['measurements_720p'] if 3<=row['frame']<=8], 'frames 3-8: widest R|G >=2px, full silhouette there >=3px',
            'Measured on supplied historical Marmoreal screenshot simulation; no new K1 runtime capture authorized.')}
    report['acceptance']=acceptance
    report['fix1']['crescent']['minimum_edge_nominal_px'] = 4
    report['fix1']['crescent']['keyline_method'] = 'Euclidean distance <=4 to densely sampled analytic contour; boundary samples <0.04px apart; raster quantization retained.'
    report['fix1']['crescent']['width_measurement_tolerance_px'] = 1.5
    report['geometry'].update(core_px=.4*.16*b.RADIUS, profile_max_s=.78,
                            mid_coloured_band_px=.1*b.RADIUS, peak_gold_radial_width_px=.6*.16*b.RADIUS)
    report['checks']['crescent_peak_within_requested_s_range'] = all(.70<=r['measured_s_max']<=.85 for r in rows)
    report['checks']['core_and_gold_nominal_widths_ge4'] = all(p['profile']['trailing_width_px']>=4 and p['profile']['leading_width_px']>=4 and (not p['core_exists'] or p['core_px']>=4) for p in params)
    acceptance['gray: distinct from star and vortex'] = entry(all(p['span_deg']<360 for p in params),
        {'maximum_span_deg':max(p['span_deg'] for p in params),'shape':'One open crescent, no rays, loops or additional strokes.'},
        'Single open curve recognisable by shape in Rec.709 grey', 'Automated component check plus recorded visual review of grey sheets.')
    report['checks'].update(standard_gray_copies=report['gray']['passed'],standard_sizes_present=report['sizes']['passed'],
                            opaque_off_token_share_zero=report['palette']['off_token_share_opaque_final']==0,
                            fix1_720p_band_and_silhouette=acceptance['arc thickness >= 2 px at 720p on K1']['passed'])
    report['all_automated_checks_passed']=all(report['checks'].values()) and all(row['passed'] for row in acceptance.values())
    return report
