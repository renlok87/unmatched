"""Read-only checks by default; --finalize writes verification and SHA-256 manifest.

No repository-wide claims: outside_folder audits this package's declared writes.
Unrelated concurrent work is neither inspected nor modified. Source-tree hashes
are checked independently, including additions/removals under hud-icons-v3.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
import numpy as np
from PIL import Image
import build_portraits as b

ROOT, PACKAGE, REVIEW = b.ROOT, b.PACKAGE, b.REVIEW


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


lab = b.lab


def luminance(rgb):
    rgb = np.asarray(rgb, dtype=float)/255
    linear = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
    return linear @ np.array([.2126, .7152, .0722])


def package_audit(sources, crops):
    exports = []
    for folder in ('vector', 'comparison'):
        for path in sorted((PACKAGE/folder).glob('*.png')):
            with Image.open(path) as im:
                bbox = im.getchannel('A').getbbox()
                margins = ([bbox[0], bbox[1], im.width-bbox[2], im.height-bbox[3]]
                           if bbox else [im.width, im.height, im.width, im.height])
                row = {'file': path.relative_to(PACKAGE).as_posix(), 'size': list(im.size),
                       'mode': im.mode, 'margin_px': min(margins),
                       'margins_px': dict(zip(('left', 'top', 'right', 'bottom'), margins)),
                       'touches_edge': min(margins) == 0}
                if path.name.startswith(('portrait-edge-', 'portrait-underlay-')):
                    row['note'] = 'Circle inscribed in its canvas; touches_edge=true by design.'
                elif folder == 'comparison':
                    row['note'] = 'Full-bleed sheet background or inscribed disc; no asset padding is required.'
                else:
                    row['note'] = 'Separate 14 su badge disc, inscribed in its canvas.'
                exports.append(row)
    # Cream has 0.45 opacity over its neighbouring navy/keyline/text tokens.
    base = np.array([[6, 22, 35], [17, 19, 23], [242, 237, 228]])
    cream = np.array([249, 235, 219])
    tokens = np.vstack([base, cream, np.floor(.45*cream+.55*base+.5)])
    token_lab = lab(tokens)
    palette = []
    for path in sorted((PACKAGE/'vector').glob('*.png')):
        with Image.open(path) as im:
            a = np.asarray(im)
            opaque = a[a[..., 3] >= 250, :3]
            colors, counts = np.unique(opaque, axis=0, return_counts=True)
            distances = np.linalg.norm(lab(colors)[:, None, :]-token_lab, axis=-1).min(axis=-1)
            outside = int(counts[distances > 3].sum())
            palette.append({'file': path.relative_to(PACKAGE).as_posix(),
                            'opaque_pixels': len(opaque), 'alpha_threshold': 250,
                            'excluded_edge_pixels': int(((a[..., 3] > 0) & (a[..., 3] < 250)).sum()),
                            'outside_token_pixels': outside,
                            'outside_token_share': outside/len(opaque) if len(opaque) else 0,
                            'max_delta_e76': round(float(distances.max()), 6) if len(distances) else 0,
                            'delta_e76_limit': 3, 'expected_share': 0, 'passed': outside == 0,
                            'note': 'D65 Lab; alpha < 250 excluded. Cream 0.45 over neighbouring tokens included.'})
    missing = []; mismatches = []; pairs = 0
    for folder in (PACKAGE/'comparison', REVIEW):
        for path in sorted(folder.glob('*.png')):
            if path.stem.endswith('-gray'):
                continue
            gray_path = path.with_stem(path.stem+'-gray')
            if not gray_path.is_file():
                missing.append(gray_path.relative_to(ROOT).as_posix())
                continue
            with Image.open(path) as im, Image.open(gray_path) as gray:
                if gray.mode != 'RGBA' or not np.array_equal(np.asarray(gray), np.asarray(b.grey(im))):
                    mismatches.append(gray_path.relative_to(ROOT).as_posix())
            pairs += 1
    winner_loser = []
    for name in b.CHARACTERS:
        for tag, _ in b.SCALES:
            for token in ('card.navy', 'card.cream'):
                winner = Image.open(REVIEW/f'{name}-winner-120-{tag}-gray.png').convert('RGBA')
                loser = Image.open(REVIEW/f'{name}-loser-120-{tag}-gray.png').convert('RGBA')
                visible = np.asarray(winner)[..., 3] > 0
                rendered = []
                for state in (winner, loser):
                    bg = Image.new('RGBA', state.size, b.TOKENS[token])
                    bg.alpha_composite(state)
                    rendered.append(np.asarray(b.grey(bg))[..., 0].astype(float))
                difference = np.abs(rendered[0]-rendered[1])
                changed = int((difference[visible] > 0).sum())
                mean = float(difference[visible].mean())
                winner_loser.append({'character': name, 'su': 120, 'scale': tag, 'background': token,
                                     'mean_luma_difference': round(mean, 6),
                                     'mean_luma_difference_canvas': round(float(difference.mean()), 6),
                                     'changed_visible_pixels': changed,
                                     'opacity_difference': .4, 'expected_min_luma_difference': 20,
                                     'passed': mean >= 20,
                                     'note': 'Measured after compositing over the named background; RGB alone ignores widget opacity.'})
    digit_shapes = []
    for tag, _ in b.SCALES:
        for first, second in combinations((1, 2, 3), 2):
            a = np.asarray(Image.open(PACKAGE/f'comparison/harpy-badge-{first}-32-{tag}-gray.png'))
            c = np.asarray(Image.open(PACKAGE/f'comparison/harpy-badge-{second}-32-{tag}-gray.png'))
            difference = int(np.any(a != c, axis=-1).sum())
            digit_shapes.append({'digits': [first, second], 'su': 32, 'scale': tag,
                                 'different_shape_pixels': difference, 'passed': difference > 0})
    contrast = []
    navy_gray = np.asarray(b.grey(Image.new('RGBA', (1, 1), b.TOKENS['card.navy'])))[0, 0, :3]
    navy_luma = float(luminance(navy_gray))
    for path in sorted((PACKAGE/'comparison').glob('fallback-*.png')):
        if path.stem.endswith('-gray') or path.stem.startswith('fallback-working-'):
            continue
        a = np.asarray(Image.open(path))
        # Core glyph pixels, excluding the frame and antialiased text boundary.
        core = (a[..., 3] >= 250) & np.all(a[..., :3] == [242, 237, 228], axis=-1)
        gray_a = np.asarray(Image.open(path.with_stem(path.stem+'-gray')))
        measured = (float(luminance(gray_a[core, :3])[0])+.05)/(navy_luma+.05) if core.any() else 0
        contrast.append({'file': path.relative_to(PACKAGE).as_posix(), 'core_glyph_pixels': int(core.sum()),
                         'contrast_ratio': round(measured, 6), 'expected_min': 4.5,
                         'passed': measured >= 4.5,
                         'note': 'Relative sRGB luminance of gray glyph core against navy underlay.'})
    gray = {'scope': 'All colour finals and review sheets in comparison/ and derived/; vector/ contains tintable masks/underlays without semantic colour states.',
            'color_gray_pairs': pairs, 'missing_partners': missing, 'Rec709_mismatches': mismatches,
            'winner_vs_loser_120': winner_loser, 'badge_digit_shape_pairs': digit_shapes,
            'fallback_monogram_vs_underlay': contrast}
    sizes = {'edge_masks': [], 'underlays': [], 'composites': [], 'missing': [],
             'geometry_mismatches': [], 'downscaled_from_master': False,
             'method': 'Re-render exact geometry at each target size and sample original source crop; compare decoded pixels. 320 px master is not an input.'}
    for su in b.SIZES:
        for tag, scale in (b.SCALES[0], b.SCALES[2]):
            n = round(su*scale)
            for kind, collection in (('edge', 'edge_masks'), ('underlay', 'underlays')):
                path = PACKAGE/f'vector/portrait-{kind}-{su}-{tag}.png'
                row = {'file': path.relative_to(PACKAGE).as_posix(), 'su': su, 'scale': tag,
                       'expected_size': [n, n], 'exists': path.is_file(), 'drawn_from_geometry': False}
                if path.is_file():
                    a = np.asarray(Image.open(path))
                    expected = np.asarray(b.vector_image(n, su, 'edge' if kind == 'edge' else 'disc'))
                    row['drawn_from_geometry'] = bool(np.array_equal(a, expected))
                    if not row['drawn_from_geometry']: sizes['geometry_mismatches'].append(row['file'])
                else: sizes['missing'].append(row['file'])
                sizes[collection].append(row)
    for name, c in b.CHARACTERS.items():
        for variant, crop in b.variants(c).items():
            if variant == 'B': crop = tuple(crops[b.KEYS[name]][key] for key in ('cx', 'cy', 'd'))
            for su in b.SIZES:
                for tag, scale in b.SCALES:
                    n = round(su*scale); path = REVIEW/f'{name}-{variant}-{su}-{tag}.png'
                    row = {'file': path.relative_to(ROOT).as_posix(), 'character': name, 'variant': variant,
                           'su': su, 'scale': tag, 'expected_size': [n, n], 'exists': path.is_file(),
                           'drawn_from_geometry': False, 'source': 'original source crop'}
                    if path.is_file():
                        row['drawn_from_geometry'] = bool(np.array_equal(np.asarray(Image.open(path)),
                            np.asarray(b.portrait(sources[name], crop, n, su))))
                        if not row['drawn_from_geometry']: sizes['geometry_mismatches'].append(row['file'])
                    else: sizes['missing'].append(row['file'])
                    sizes['composites'].append(row)
    return exports, palette, gray, sizes


def check():
    checks=[]
    def expect(name, condition, detail=None):
        checks.append({'check':name,'pass':bool(condition),'detail':detail})
    before=read(PACKAGE/'source-hashes-before.json')
    changed=[];after={}
    for name,record in before['files'].items():
        path=ROOT/name
        value=digest(path) if path.is_file() else None
        after[name]=value
        if value!=record['sha256']: changed.append(name)
    icon_prefix='art/imagegen/hud-icons-v3/'
    old_icons={n for n in before['files'] if n.startswith(icon_prefix)}
    new_icons={p.relative_to(ROOT).as_posix() for p in (ROOT/icon_prefix).rglob('*') if p.is_file()}
    changed+=sorted(old_icons.symmetric_difference(new_icons))
    expect('all_sources_and_hud_icons_tree_unchanged', not changed, {'files_hashed':len(after),'changed':changed})
    expect('snapshot_byte_identical',digest(PACKAGE/'_tools/draw_icons_v3_snapshot.py') == before['files'][icon_prefix+'_tools/draw_icons.py']['sha256'])
    cp01=read(ROOT/'art/cards-v1/media-convert-report.json')
    expect('CP01_report',cp01.get('card')=='CP-01' and cp01.get('allPixelEqual') is True and cp01.get('counts',{}).get('avatar')==2 and cp01.get('counts',{}).get('sidekick')==2)
    webps={'king-arthur':'avatars/dgwIAej9v-Omrn0sSVs5i.webp','medusa':'avatars/bI206lUtJUQru-FOD8A74.webp',
           'king-arthur-merlin':'sidekicks/4Rl9Oq9N82zhatbTShnXn.webp','medusa-harpies':'sidekicks/G42WIKYZ1cmwACVwMggzM.webp'}
    expected_sha=['a93e817db892e2fed4375e8757a47a39e9e253d3076547fed752757a978f743a',
                  '310b5bbcc0594f1441494e38d434e03849dc3518c349349f7d16ee3faccfe920',
                  '9e08817bd7955c00ce079aaf7893d687114bcfec34103b91618b629634026cd9',
                  '1cfcad663bcd9e99df233bcd8b5c61c8fe97b354070a75542713929534ee5e62']
    sizes={}; pixel_equal={}; sources={}
    for (name,source),sha in zip(webps.items(),expected_sha):
        src=ROOT/'scraped-data/images/heroes'/source
        png=ROOT/'scraped-data/derived/ue-media-v1'/b.CHARACTERS[name]['source']
        a=np.asarray(Image.open(src).convert('RGBA'));c=np.asarray(Image.open(png).convert('RGBA'))
        sources[name]=Image.fromarray(c)
        sizes[name]=a.shape[0];pixel_equal[name]=bool(a.shape==c.shape and np.array_equal(a,c))
        expect('original_webp_sha/'+name,digest(src)==sha)
        expect('CP01_png_pixel_equal/'+name,pixel_equal[name])
    crops=read(PACKAGE/'portrait-crops.json')
    expect('exact_four_crop_keys',set(crops)==set(b.KEYS.values()))
    expected_crops={b.KEYS[n]:dict(zip(('cx','cy','d'),b.variants(c)['B'])) for n,c in b.CHARACTERS.items()}
    expect('crop_recommendations_match_review',crops==expected_crops)
    eyes=[];expected_limits=[];seen=0;gray_mismatches=[]
    for name,c in b.CHARACTERS.items():
        side=sizes[name]
        for variant,(cx,cy,d) in b.variants(c).items():
            max_radius=max(math.hypot(ex/side-cx,ey/side-cy)/(d/2) for ex,ey in c['eyes'])
            eyes.append({'character':name,'variant':variant,'eye_centres_source_px':c['eyes'],
                         'max_eye_radius_fraction':round(max_radius,6),'limit':.6,
                         'all_sizes_and_scales':True,'pass':max_radius<=.6})
            for su in b.SIZES:
                for tag,k in b.SCALES:
                    n=round(su*k)
                    p=REVIEW/f'{name}-{variant}-{su}-{tag}.png'
                    gray=p.with_stem(p.stem+'-gray')
                    im=Image.open(p).convert('RGBA');g=Image.open(gray).convert('RGBA')
                    expect('composite_dimensions/'+p.name,im.size==(n,n) and g.size==(n,n))
                    if not np.array_equal(np.asarray(g),np.asarray(b.grey(im))):gray_mismatches.append(p.name)
                    if n>1.6*side*d+1e-9: expected_limits.append((name,variant,su,tag))
                    seen+=1
    expect('all_eyes_inside_central_60_percent',all(e['pass'] for e in eyes),eyes)
    expect('216_color_gray_composite_pairs',seen==216,seen)
    expect('all_composite_gray_Rec709_exact',not gray_mismatches,gray_mismatches)
    limits=read(PACKAGE/'magnification-limits.json')
    expected_x3=[]
    for name in b.CHARACTERS:
        crop=tuple(crops[b.KEYS[name]][key] for key in ('cx','cy','d'))
        for su in b.SIZES:
            row=b.magnification_row(name,'B',su,'x3',3,sizes[name],crop)
            row.update({'display_case':'2160p / 150%','computed_only':True,'exceeds_limit':not row['allowed']})
            expected_x3.append(row)
            if row['exceeds_limit']: expected_limits.append((name,'B',su,'x3'))
    expect('recommended_x3_all_24_computed_rows',limits.get('recommended_x3_rows')==expected_x3)
    expect('x3_no_rendered_composites',not list(REVIEW.glob('*-x3*.png')))
    actual_limits=[(r['character'],r['variant'],r['su'],r['scale']) for r in limits['production_exceeds']]
    expect('every_production_limit_violation_listed',sorted(actual_limits)==sorted(expected_limits),len(expected_limits))
    expected_masters={(name,v) for name,c in b.CHARACTERS.items() for v,crop in b.variants(c).items() if b.MASTER>1.6*sizes[name]*crop[2]}
    expect('every_master_limit_violation_listed', {(r['character'],r['variant']) for r in limits['review_master_exceeds']}==expected_masters)
    edges=[]
    for su in b.SIZES:
        for tag,k in (b.SCALES[0],b.SCALES[2]):
            path=PACKAGE/f'vector/portrait-edge-{su}-{tag}.png'
            a=np.asarray(Image.open(path).convert('RGBA'));n=round(su*k)
            central=a[n//4:3*n//4,n//4:3*n//4,3]
            ok=a.shape==(n,n,4) and np.all(central==0) and a[n//2,n//2,3]==0 and a[0,0,3]==0
            edges.append({'file':path.name,'pass':bool(ok),'digits_baked':False})
            expect('edge_transparent_center/'+path.name,ok)
            opaque=a[a[...,3]==255,:3]
            # A 1 px curved ring may have no fully covered pixels; antialiasing
            # at the shared boundary legitimately mixes the two token colors.
            expect('opaque_edge_is_exact_keyline/'+path.name,np.all(opaque==[17,19,23]),{'opaque_pixels':len(opaque)})
            if k==2:
                expect('cream_exact_RGB_and_alpha/'+path.name,tuple(a[n//2,n-4])==(249,235,219,115),a[n//2,n-4].tolist())
                expect('keyline_exact_RGB_and_alpha/'+path.name,tuple(a[n//2,n-2])==(17,19,23,255),a[n//2,n-2].tolist())
    for tag,k in b.SCALES:
        blank=Image.open(PACKAGE/f'vector/harpy-badge-14-{tag}.png').convert('RGBA')
        expect('badge_blank_no_digit/'+tag,np.array_equal(np.asarray(blank),np.asarray(b.badge(round(32*k),32))))
        original=b.badge(round(32*k),32,exact_palette=False)
        a=np.asarray(blank);raw=np.asarray(original)
        tokens=np.array([[6,22,35],[17,19,23]])
        distances=np.linalg.norm(lab(raw[...,:3])[:,:,None,:]-lab(tokens),axis=-1)
        permitted=(raw[...,3]>=250) & (distances.min(axis=-1)>3)
        altered=np.any(a[...,:3]!=raw[...,:3],axis=-1)
        expect('badge_geometry_and_in_tolerance_pixels_unchanged/'+tag,
               np.array_equal(a[...,3],raw[...,3]) and np.array_equal(permitted,altered),
               {'opaque_RGB_pixels_corrected':int(altered.sum()),'alpha_unchanged':bool(np.array_equal(a[...,3],raw[...,3])),
                'geometry_unchanged':True,'only_preexisting_delta_e76_violations_changed':bool(np.array_equal(permitted,altered))})
        for digit in (1,2,3):
            glyph=b.glyph(str(digit),10*k,b.TOKENS['card.cream'])
            expect(f'badge_cap_height/{digit}/{tag}',glyph.height==round(10*k))
    losers=[]
    for name in b.CHARACTERS:
        for tag,k in b.SCALES:
            a=np.asarray(Image.open(REVIEW/f'{name}-winner-120-{tag}.png').convert('RGBA'))
            g=np.asarray(Image.open(REVIEW/f'{name}-loser-120-{tag}.png').convert('RGBA'))
            neutral=np.array_equal(g[...,0],g[...,1]) and np.array_equal(g[...,1],g[...,2])
            alpha=np.array_equal(g[...,3],np.floor(a[...,3]*.6+.5).astype(np.uint8))
            expected_gray=np.asarray(b.grey(Image.fromarray(a)))
            rgb=np.array_equal(g[...,:3],expected_gray[...,:3])
            losers.append({'character':name,'scale':tag,'no_red':neutral,'opacity_0_6':alpha,'Rec709':rgb})
            expect('loser_state/'+name+'/'+tag,neutral and alpha and rgb)
    manual=read(PACKAGE/'visual-review.json')
    expect('visual_face_readability_32',all(v['pass'] for v in manual['face_readable_grayscale_32'].values()),'Manual inspection, not automated recognition')
    expect('visual_badge_digits_readable',manual['badge_digits_32_x1_readable']==[1,2,3])
    # The entire recommended source circle plus conservative bilinear filter support
    # fits inside radius 50. No recoloring/removal of source pixels is necessary.
    ring=[]
    for name in ('king-arthur-merlin','medusa-harpies'):
        for v,(cx,cy,d) in b.variants(b.CHARACTERS[name]).items():
            farthest=math.hypot((cx-.5)*128,(cy-.5)*128)+d*64
            support=farthest+math.sqrt(2)
            ring.append({'character':name,'variant':v,'farthest_source_radius_px':round(farthest,6),
                         'with_bilinear_support_px':round(support,6),'ring_starts_at_radius_px':50,
                         'geometrically_safe':support<50,'recommended':v=='B'})
    expect('recommended_sidekicks_exclude_ring_including_filter_support',all(r['geometrically_safe'] for r in ring if r['recommended']),ring)
    # Pillow widens bilinear support when shrinking. Exercise the real sampler
    # with a sentinel at radius >=50, then account for circle and edge opacity.
    # This catches contamination of A at small sizes that geometry alone misses.
    yy,xx=np.indices((128,128))
    sentinel=Image.fromarray((((xx+.5-64)**2+(yy+.5-64)**2>=50**2)*255).astype(np.uint8))
    ring_sampling=[]
    for name in ('king-arthur-merlin','medusa-harpies'):
        for v,(cx,cy,d) in b.variants(b.CHARACTERS[name]).items():
            box=((cx-d/2)*128,(cy-d/2)*128,(cx+d/2)*128,(cy+d/2)*128)
            for su in b.SIZES:
                for tag,k in b.SCALES:
                    n=round(su*k)
                    sampled=np.asarray(sentinel.resize((n,n),Image.Resampling.BILINEAR,box=box),dtype=float)
                    disc=np.asarray(b.vector_image(n,su,'disc').getchannel('A'),dtype=float)/255
                    edge=np.asarray(b.vector_image(n,su).getchannel('A'),dtype=float)/255
                    weight=sampled*disc*(1-edge)
                    ring_sampling.append({'character':name,'variant':v,'su':su,'scale':tag,
                                          'max_ring_weight_255':round(float(weight.max()),6),
                                          'no_visible_ring':bool(weight.max()<=.5),'recommended':v=='B'})
    expect('recommended_no_ring_with_actual_downsample_filter',all(r['no_visible_ring'] for r in ring_sampling if r['recommended']),ring_sampling)
    gen=read(PACKAGE/'generation-records.json')
    expect('no_image_generation',gen['image_generation_used'] is False and gen['generations']==[])
    build=read(PACKAGE/'build-data.json')
    outside=[p for p in build['written_paths'] if not any((ROOT/p).resolve().is_relative_to(r) for r in (PACKAGE,REVIEW))]
    expect('write_ledger_only_allowed_roots',not outside)
    expect('no_avatar_images_in_package',not any('portrait-crop-v1-codex/'+n+'-' in p for n in b.CHARACTERS for p in build['written_paths'] if '/art/' in '/'+p and '/fallback-' not in p))
    exports,palette,gray,size_audit=package_audit(sources,crops)
    expect('exports_all_RGBA',all(row['mode']=='RGBA' for row in exports),len(exports))
    expect('vector_palette_delta_e76_at_most_3',all(row['passed'] for row in palette),
           [row for row in palette if not row['passed']])
    expect('all_final_and_review_gray_partners',not gray['missing_partners'],gray['missing_partners'])
    expect('all_final_and_review_gray_Rec709',not gray['Rec709_mismatches'],gray['Rec709_mismatches'])
    expect('gray_winner_loser_differ',all(row['passed'] for row in gray['winner_vs_loser_120']))
    expect('gray_badge_digit_shapes_differ',all(row['passed'] for row in gray['badge_digit_shape_pairs']))
    expect('gray_fallback_monogram_contrast',all(row['passed'] for row in gray['fallback_monogram_vs_underlay']))
    expect('all_deliverable_sizes_from_geometry',not size_audit['missing'] and not size_audit['geometry_mismatches'],
           {'missing':size_audit['missing'],'geometry_mismatches':size_audit['geometry_mismatches']})
    # Check the actual caption/status pixels, not merely generator metadata.
    caption_gaps=[];status_labels=[]
    for tag,k in b.SCALES:
        sheet_im=Image.open(REVIEW/f'comparison-working-{tag}.png').convert('RGBA')
        cw=round(160*k)+34;rh=round(160*k)+43
        for row,(name,c) in enumerate(b.CHARACTERS.items()):
            for vi,(variant,crop) in enumerate(b.variants(c).items()):
                y=132+(row*3+vi)*rh
                for col,su in enumerate(b.SIZES):
                    x=205+col*cw;n=round(su*k)
                    text=b.working_status(name,variant,su,tag,sizes[name],crop)
                    expected=Image.new('RGBA',(cw,30),b.TOKENS['card.navy'])
                    b.label(expected,(0,0),text,12)
                    actual=sheet_im.crop((x,y+n+8,x+cw,y+n+38))
                    status_labels.append({'character':name,'variant':variant,'su':su,'scale':tag,
                                          'text':text,'passed':bool(np.array_equal(np.asarray(actual),np.asarray(expected)))})
        overlay=Image.open(PACKAGE/f'comparison/overlay-working-{tag}.png').convert('RGBA')
        for digit in (1,2,3):
            n=round(32*k);x=28+(digit-1)*180;tile_bottom=490+n+16;caption_y=tile_bottom+6
            expected=Image.new('RGBA',(180,30),b.TOKENS['card.navy'])
            b.label(expected,(0,0),f'Harpy {digit} / 32 su',12)
            # First non-background row gives the measured visible-ink gap.
            ink=np.any(np.asarray(expected)[...,:3]!=[6,22,35],axis=-1)
            ink_top=int(np.nonzero(ink)[0].min())
            actual=overlay.crop((x,caption_y,x+180,caption_y+30))
            gap=caption_y+ink_top-tile_bottom
            caption_gaps.append({'scale':tag,'digit':digit,'gap_px':gap,'expected_min':6,
                                 'passed':gap>=6 and bool(np.array_equal(np.asarray(actual),np.asarray(expected)))})
    expect('working_tiles_both_status_flags',all(row['passed'] for row in status_labels),status_labels)
    expect('overlay_caption_gap_at_least_6_px',all(row['passed'] for row in caption_gaps),caption_gaps)
    recommended_eyes=[row for row in eyes if row['variant']=='B']
    recommended_ring=[row for row in ring_sampling if row['recommended']]
    # Six records cover all eight semicolon predicates of the original card:
    # package integrity includes no generation; crop geometry includes four records.
    acceptance=[
      {'id':'package_integrity','passed':not changed and not outside and gen['image_generation_used'] is False and gen['generations']==[],
       'measured':{'source_unchanged':not changed,'outside_folder':outside,'image_generation_used':gen['image_generation_used'],'generations':len(gen['generations'])},
       'expected':{'source_unchanged':True,'outside_folder':[],'image_generation_used':False,'generations':0},
       'note':'Original clauses 1 and 8: input hashes/write scope and no image generation.'},
      {'id':'recommended_crop_geometry','passed':crops==expected_crops and all(row['pass'] for row in recommended_eyes),
       'measured':{'crop_records':len(crops),'recommended_variant':'B','eye_max_radius_fraction':{row['character']:row['max_eye_radius_fraction'] for row in recommended_eyes},'sizes_su':list(b.SIZES)},
       'expected':{'crop_records':4,'eye_max_radius_fraction_at_most':.6,'sizes_su':list(b.SIZES)},
       'note':'Original clauses 2 and 3: exactly four unchanged B crops; normalized geometry applies to every size.'},
      {'id':'recommended_sidekick_no_ring','passed':all(row['no_visible_ring'] for row in recommended_ring),
       'measured':{'tested_rows':len(recommended_ring),'max_ring_weight_255':max(row['max_ring_weight_255'] for row in recommended_ring)},
       'expected':{'tested_rows':36,'max_ring_weight_255_at_most':.5},
       'note':'Original clause 4: actual bilinear filter on recommended B, including masking and edge. Diagnostic A/C do not fail acceptance.'},
      {'id':'recommended_faces_gray_32','passed':all(row['pass'] for row in manual['face_readable_grayscale_32'].values()),
       'measured':manual['face_readable_grayscale_32'],'expected':'All four recommended faces readable at 32 su x1 in grayscale',
       'note':'Original clause 5: direct PNG inspection; visual judgment, not automated recognition or artistic approval.'},
      {'id':'every_magnification_exceedance_listed','passed':sorted(actual_limits)==sorted(expected_limits) and limits.get('recommended_x3_rows')==expected_x3,
       'measured':{'all_exceeded_rows':len(actual_limits),'recommended_exceeded_rows':sum(row['recommended'] for row in limits['production_exceeds']),'x3_computed_rows':len(expected_x3),'x3_exceeded_rows':sum(row['exceeds_limit'] for row in expected_x3)},
       'expected':'Every display >1.6x listed; x1/x1.5/x2 all variants and x3 recommended B for all four characters/six sizes',
       'note':'Original clause 6 requires listing exceedances. It does not require every large display to fit the original source resolution. x3 is computed only.'},
      {'id':'badge_digits_gray_32_x1','passed':manual['badge_digits_32_x1_readable']==[1,2,3] and all(row['passed'] for row in gray['badge_digit_shape_pairs'] if row['scale']=='x1'),
       'measured':{'visually_readable_digits':manual['badge_digits_32_x1_readable'],'gray_shape_pairs':[row for row in gray['badge_digit_shape_pairs'] if row['scale']=='x1']},
       'expected':'Digits 1, 2 and 3 readable and distinguishable at 32 su x1',
       'note':'Original clause 7: native-size visual check plus measured pairwise gray shape difference.'}]
    report={'schema':'cp07.verification/1','task':'CP-07','status':'предложено',
            'technical_checks_passed':all(c['pass'] for c in checks),'full_acceptance':all(row['passed'] for row in acceptance),
            'source_unchanged':not changed,'source_hashes_after':after,'changed_sources':changed,
            'outside_folder':outside,'outside_folder_scope':'Paths written by the guarded renderer plus package-authored files; not a global audit of concurrent user edits. No Git/Unreal access.',
            'crop_record_count':len(crops),'image_generation_used':False,
            'cp01_pixel_equal':pixel_equal,'eye_landmarks':eyes,'edge_masks':edges,
            'sidekick_ring_geometry':ring,'sidekick_ring_sampling':ring_sampling,'loser_checks':losers,
            'magnification_limit':1.6,'magnification_exceeded':limits['production_exceeds'],
            'master_magnification_exceeded':limits['review_master_exceeds'],
            'magnification_x3':limits['recommended_x3_rows'],
            'exports':exports,'palette':palette,'gray':gray,'sizes':size_audit,'acceptance':acceptance,
            'working_tile_statuses':status_labels,'overlay_caption_gaps':caption_gaps,
            'recommended_magnification_exceeded_count':sum(r['recommended'] for r in limits['production_exceeds']),
            'limitations':[
              {'id':'C-SIDEKICK-RING','acceptance_met':False,'review_only':True,'affects_recommended_acceptance':False,'reason':'Diagnostic C diameter .81 crosses the baked ring. Rejected for production; recommended B is safe. This diagnostic does not fail recommended-crop acceptance.'},
              {'id':'A-DOWNSAMPLE-RING','acceptance_met':False,'review_only':True,'affects_recommended_acceptance':False,'reason':'Diagnostic A samples the baked ring at 32/40 su x1/x1.5. Recommended B passes all actual-filter tests. This diagnostic does not fail recommended-crop acceptance.'},
              {'id':'SIDEKICK-RESOLUTION','acceptance_met':True,'reason':f'{len(actual_limits)} display rows exceed 1.6x, including {sum(row["recommended"] for row in limits["production_exceeds"])} recommended B rows; x3 adds Medusa 120/160 su and both sidekicks 64/80/120/160 su. Every exceedance is listed as required, without enhanced textures or x3 composites.'},
              {'id':'MANUAL-READABILITY','acceptance_met':True,'reason':'32 px grayscale facial separation and badge digits were inspected by Codex; this is visual judgment, not a user acceptance or automated recognition.'}],
            'checks':checks}
    # Normalize tuples (e.g. source eye coordinates) to JSON arrays before
    # comparing an in-memory report with the saved, decoded JSON report.
    return json.loads(json.dumps(report,ensure_ascii=False))


def manifest():
    paths=[p for folder in (PACKAGE,REVIEW) for p in folder.rglob('*') if p.is_file() and p.name!='manifest-sha256.json']
    return {'algorithm':'SHA-256','self_excluded':'manifest-sha256.json (avoids circular self-hash)',
            'roots':[PACKAGE.relative_to(ROOT).as_posix(),REVIEW.relative_to(ROOT).as_posix()],
            'files':{p.relative_to(ROOT).as_posix():{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(paths)}}


def main():
    report=check()
    failures=[c for c in report['checks'] if not c['pass']]
    if '--finalize' in sys.argv:
        b.write_json(PACKAGE/'verification.json',report)
        b.write_json(PACKAGE/'manifest-sha256.json',manifest())
    else:
        if read(PACKAGE/'verification.json')!=report:
            failures.append({'check':'verification_matches_recomputed_report','pass':False})
        m=read(PACKAGE/'manifest-sha256.json')
        for name,record in m['files'].items():
            if not (ROOT/name).is_file() or digest(ROOT/name)!=record['sha256']:
                failures.append({'check':'manifest/'+name,'pass':False})
        actual={p.relative_to(ROOT).as_posix() for folder in (PACKAGE,REVIEW) for p in folder.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
        if actual!=set(m['files']):failures.append({'check':'manifest_complete_inventory','pass':False})
    print(json.dumps({'checks':len(report['checks']),'failed':failures,'source_unchanged':report['source_unchanged'],
                      'outside_folder':report['outside_folder'],'composite_pairs':216,
                      'limit_violations':len(report['magnification_exceeded']),
                      'full_acceptance':report['full_acceptance'],
                      'acceptance_passed':sum(row['passed'] for row in report['acceptance']),
                      'acceptance_total':len(report['acceptance']),
                      'x3_computed_rows':len(report['magnification_x3']),
                      'limitations':[row['id'] for row in report['limitations']]},ensure_ascii=True,indent=2))
    return 1 if failures else 0


if __name__=='__main__':
    raise SystemExit(main())
