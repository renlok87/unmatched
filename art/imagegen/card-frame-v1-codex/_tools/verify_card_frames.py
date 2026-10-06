#!/usr/bin/env python
"""Independent file/pixel verification of CP-13. No rendering, git or Unreal."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / 'scraped-data/derived/card-frame-v1-codex'
WRITES = set()


def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            p = Path(os.fsdecode(args[0])).resolve()
            if not p.is_relative_to(PACKAGE):
                raise PermissionError(f'Verifier cannot write here: {p}')
            WRITES.add(p.relative_to(ROOT).as_posix())
    elif event in ('subprocess.Popen', 'os.system'):
        raise PermissionError('Verifier cannot start processes')


sys.addaudithook(guard)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify():
    start = time.monotonic()
    before = read(PACKAGE / 'source-hashes-before.json')['files']
    changed = [rel for rel, info in before.items() if not (ROOT / rel).is_file() or sha(ROOT / rel) != info['sha256']]
    added = []
    for subtree in ('art/imagegen/hud-icons-v3', 'scraped-data/images/decks'):
        added.extend(p.relative_to(ROOT).as_posix() for p in (ROOT / subtree).rglob('*')
                     if p.is_file() and p.relative_to(ROOT).as_posix() not in before)
    snapshot_source = 'art/imagegen/hud-icons-v3/_tools/draw_icons.py'
    snapshot_same = sha(PACKAGE / '_tools/draw_icons_v3_snapshot.py') == before[snapshot_source]['sha256']
    contract, review = read(PACKAGE / 'asset-contract.json'), read(PACKAGE / 'review-index.json')
    checks, failures = {}, []

    def check(name, ok, detail=None):
        checks[name] = {'passed': bool(ok), 'detail': detail}
        if not ok:
            failures.append(name)

    check('source_unchanged', not changed and not added, {'changed': changed, 'added': added, 'files': len(before)})
    check('generator_snapshot_byte_identical', snapshot_same)
    palette = {(6, 22, 35), (249, 235, 219), (13, 122, 137), (232, 129, 44), (250, 248, 242), (17, 19, 23)}
    asset_results, palette_bad = {}, 0
    for rel, meta in contract['assets'].items():
        with Image.open(PACKAGE / rel) as im:
            arr = np.asarray(im.convert('RGBA'))
        assert [arr.shape[1], arr.shape[0]] == meta['size_px'], rel
        # Exact palette is stronger than dE76 <=3. Only alpha<255 is excluded.
        opaque = arr[:, :, 3] == 255
        valid = np.zeros(opaque.shape, bool)
        for rgb in palette:
            valid |= np.all(arr[:, :, :3] == rgb, axis=2)
        bad = int(np.count_nonzero(opaque & ~valid))
        palette_bad += bad
        if meta['layer'] == 'frame':
            x, y, w, h = meta['window_px']
            assert not np.any(arr[y:y+h, x:x+w, 3]), f'Window opacity: {rel}'
            corner = (meta['radius_su'] + meta['edge_su'] + 1) * meta['density'] + 1
            assert meta['nine_slice_px'] == [corner] * 4, rel
            # Straight centre edge must match the requested token, width and alpha.
            tokens = {'idle': (249, 235, 219), 'hover': (249, 235, 219),
                      'selected': (13, 122, 137), 'warning': (232, 129, 44),
                      'flash': (250, 248, 242), 'mini-idle': (249, 235, 219)}
            k = meta['density']; edge = meta['edge_su']
            assert tuple(arr[0, arr.shape[1] // 2, :3]) == (17, 19, 23), rel
            stripe = arr[k:(1+edge)*k, arr.shape[1] // 2]
            assert np.all(stripe[:, :3] == tokens[meta['state']]), rel
            assert np.all(stripe[:, 3] == round(255 * meta['edge_alpha'])), rel
        elif meta['layer'] == 'focus-only':
            k = meta['density']; w, h = meta['logical_frame_su']
            # Independent overlap test using actual base texture alpha.
            base_path = rel.replace('focus', 'selected')
            with Image.open(PACKAGE / base_path) as im:
                base = np.asarray(im.convert('RGBA'))[:, :, 3]
            padded = np.zeros(arr.shape[:2], dtype=np.uint8)
            padded[4*k:(4+h)*k, 4*k:(4+w)*k] = base
            assert not np.any((padded > 0) & (arr[:, :, 3] > 0)), rel
            middle = arr[:, arr.shape[1] // 2, 3]
            assert np.all(middle[:2*k] == 255) and not np.any(middle[2*k:4*k]), rel
            assert meta['nine_slice_px'] == [(meta['radius_su'] + 4) * k + 1] * 4, rel
        asset_results[rel] = {'nine_slice_px': meta['nine_slice_px'], 'size_px': meta['size_px'],
                              'opaque_pixels_outside_palette': bad}
    check('palette', palette_bad == 0, {'opaque_pixels_outside_dE76_3': palette_bad,
          'method': 'Every opaque pixel equals an exact token; this implies dE76=0. Only alpha<255 excluded.'})
    check('transparent_windows_and_state_geometry', True, {'assets_measured': len(asset_results)})
    check('focus_ring_gap_and_no_overlap', True, {'gap_su': 2, 'ring_su': 2, 'all_sizes_and_densities': True})

    states = {'idle', 'hover', 'selected', 'warning', 'flash', 'focus', 'mini-idle', 'playable', 'not-playable', 'new'}
    displays = {'hand', 'hover', 'combat', 'source-slot', 'inspector-ru', 'inspector-en',
                'class-s-hand', 'opponent-back', 'deck-chip', 'discard-chip'}
    expected_names = {f'{s}-{d}-x{k}.png' for s in states for d in displays for k in (1, 2)}
    check('all_states_displays_densities', set(review['sheets']) == expected_names,
          {'colour_sheets': len(review['sheets']), 'gray_sheets': len(review['sheets'])})
    reuse = read(ROOT / 'art/imagegen/mvp-v1/reused-cardart.json')
    allowed = {c['stableContentKey']: c for c in reuse['cards']}
    expected_keys = {'medusa:gaze-of-stone', 'medusa:hiss-and-slither', 'medusa:snipe', 'medusa:winged-frenzy',
                     'king-arthur:excalibur', 'king-arthur:the-holy-grail', 'king-arthur:skirmish', 'king-arthur:prophecy'}
    for source in review['source_assets']:
        if source['kind'] == 'scan':
            assert source['key'] in expected_keys
            assert source['path'] == allowed[source['key']][source['language']]['path']
            assert source['sha256'] == allowed[source['key']][source['language']]['sha256']
    for lang in ('ru', 'en'):
        for hero in ('medusa', 'king-arthur'):
            selected = [s for s in review['source_assets'] if s['language'] == lang and s['key'].startswith(hero + ':')]
            assert len(selected) == 4
            assert {s['type'] for s in selected} == {'attack', 'defense', 'versatile', 'scheme'}
    check('real_card_provenance_and_four_types_each_hero_ru_en', True,
          {'cards': sorted(expected_keys), 'scan_files': 16, 'original_back_files': 2})
    gray_bad, provenance_bad, real_pixel_bad, sampled_pixels = 0, [], 0, 0
    source_images, expected_crops = {}, {}
    for source in review['source_assets']:
        with Image.open(ROOT / source['path']) as im:
            source_images[(source['key'], source['language'])] = im.convert('RGBA')
    for i, (name, info) in enumerate(sorted(review['sheets'].items())):
        lang = info['display'].split('-')[-1] if info['display'].startswith('inspector-') else None
        expect = {(s['key'], s['language']) for s in review['source_assets'] if lang is None or s['language'] in (lang, 'shared')}
        actual = {(s['source_key'], s['language']) for s in info['entries']}
        if actual != expect:
            provenance_bad.append(name)
        with Image.open(DERIVED / name) as color, Image.open(DERIVED / info['gray']) as gr:
            assert color.size == tuple(info['size_px']) == gr.size
            # Bounded row chunks avoid several giant arrays for x2 inspector sheets.
            for y in range(0, color.height, 128):
                box = (0, y, color.width, min(color.height, y + 128))
                a = np.asarray(color.crop(box).convert('RGBA'))
                b = np.asarray(gr.crop(box).convert('RGBA'))
                luma = np.floor(np.einsum('ijk,k->ij', a[:, :, :3].astype(np.float32),
                       np.array([.2126, .7152, .0722], np.float32)) + .5).astype('uint8')
                gray_bad += int(np.count_nonzero(np.any(b[:, :, :3] != luma[:, :, None], axis=2)))
                assert np.array_equal(a[:, :, 3], b[:, :, 3]), name
            for entry in info['entries']:
                w, h = contract['displays'][info['display']][:2]
                k = info['density']
                fit = review['fitting'][f"{entry['source_key']}|{entry['language']}|{w}x{h}|x{k}"]
                fx, fy, iw, ih = fit['draw_rect_px']
                cache_key = (entry['source_key'], entry['language'], w, h, k, info['state'] == 'not-playable')
                if cache_key not in expected_crops:
                    original = source_images[(entry['source_key'], entry['language'])]
                    if entry['language'] == 'shared':
                        crop = round(fit['back_side_crop_fraction_total'] * original.width / 2)
                        original = original.crop((crop, 0, original.width-crop, original.height))
                    resized = original.resize((iw, ih), Image.Resampling.LANCZOS)
                    if info['state'] == 'not-playable':
                        pixels = np.asarray(resized).copy()
                        lum = np.einsum('ijk,k->ij', pixels[:, :, :3].astype(np.float32), np.array([.2126, .7152, .0722]))
                        pixels[:, :, :3] = np.floor(.4 * pixels[:, :, :3] + .6 * lum[:, :, None] + .5).astype('uint8')
                        pixels[:, :, 3] = np.floor(pixels[:, :, 3] * .7 + .5).astype('uint8')
                        resized = Image.fromarray(pixels)
                    expected = Image.new('RGBA', (iw, ih), (6, 22, 35, 255))
                    expected.alpha_composite(resized)
                    expected_crops[cache_key] = np.asarray(expected)[::max(1, ih//31), ::max(1, iw//31)].copy()
                ex, ey = entry['composite_rect_px'][:2]
                padding_px = (entry['composite_rect_px'][2] - w*k) // 2
                bx, by = ex + padding_px + fx, ey + padding_px + fy
                actual = np.asarray(color.crop((bx, by, bx+iw, by+ih)).convert('RGBA'))[::max(1, ih//31), ::max(1, iw//31)]
                expected = expected_crops[cache_key]
                real_pixel_bad += int(np.count_nonzero(np.any(actual != expected, axis=2)))
                sampled_pixels += actual.shape[0] * actual.shape[1]
        if i % 20 == 0:
            print(f'verified review sheets {i+1}/200', flush=True)
    extra_color_files = [PACKAGE / f'comparison/overlay-{size}-x{k}.png'
                         for size in ('master', 'working') for k in (1, 2)] + [
                         DERIVED / f'lift-comparison-x{k}.png' for k in (1, 2)]
    for color_path in extra_color_files:
        with Image.open(color_path) as color, Image.open(color_path.with_name(color_path.stem + '-gray.png')) as gr:
            assert color.size == gr.size
            for y in range(0, color.height, 128):
                box = (0, y, color.width, min(color.height, y + 128))
                a = np.asarray(color.crop(box).convert('RGBA'))
                b = np.asarray(gr.crop(box).convert('RGBA'))
                luma = np.floor(np.einsum('ijk,k->ij', a[:, :, :3].astype(np.float32),
                       np.array([.2126, .7152, .0722], np.float32)) + .5).astype('uint8')
                gray_bad += int(np.count_nonzero(np.any(b[:, :, :3] != luma[:, :, None], axis=2)))
                assert np.array_equal(a[:, :, 3], b[:, :, 3])
    check('every_sheet_has_all_real_cards_and_both_backs', not provenance_bad, provenance_bad)
    check('real_scan_and_back_pixels_match_sources', real_pixel_bad == 0,
          {'mismatched_sample_pixels': real_pixel_bad, 'sampled_pixels': sampled_pixels,
           'method': 'Deterministic >=31x31 pixel lattice per source in every colour sheet, independently resized from originals; includes preview saturation and opacity.'})
    check('rec709_grayscale', gray_bad == 0, {'wrong_pixels': gray_bad, 'formula': 'round(0.2126R + 0.7152G + 0.0722B)'})
    fits = list(review['fitting'].values())
    scan_fits = [f for f in fits if f['language'] in ('ru', 'en')]
    back_fits = [f for f in fits if f['language'] == 'shared']
    check('scan_contain_no_crop_aspect_within_one_px', all(f['scan_crop_px'] == 0 and f['scan_aspect_error_px_at_x1'] <= 1 for f in scan_fits),
          {'max_aspect_error_px': max(f['scan_aspect_error_px_at_x1'] for f in scan_fits)})
    ru_regular = [f for f in scan_fits if f['language'] == 'ru' and f['viewport_su'][0] < 400]
    inspectors = [f for f in scan_fits if f['viewport_su'][0] >= 400]
    check('ru_no_enlargement_1080p_100pct_outside_inspector', all(f['logical_scale'] <= 1 for f in ru_regular),
          {'max_scale': max(f['logical_scale'] for f in ru_regular), 'x2': 'texture density, su unchanged'})
    check('inspector_at_most_1_6', all(f['logical_scale'] <= 1.6 + 1e-9 for f in inspectors),
          {'max_logical_scale': max(f['logical_scale'] for f in inspectors)})
    check('back_crop_at_most_1_4pct', all(f['back_side_crop_fraction_total'] <= .014 for f in back_fits),
          {'max_total_crop': max(f['back_side_crop_fraction_total'] for f in back_fits)})
    # The following contradictory task constraints are explicitly failed, never silently waived.
    viewport_errors = [{'key': f['source_key'], 'language': f['language'], 'viewport_su': f['viewport_su'],
                        'aspect_width_error_px': abs(f['viewport_su'][0] - f['viewport_su'][1] * f['source_size_px'][0] / f['source_size_px'][1])}
                       for f in scan_fits]
    check('nominal_frame_window_matches_scan_aspect_within_one_px', all(f['aspect_width_error_px'] <= 1 for f in viewport_errors),
          {'max_error_px': max(f['aspect_width_error_px'] for f in viewport_errors),
           'reason': 'Exact prescribed viewports differ from RU/EN source aspects. Actual fitted scans pass their separate aspect check.'})
    check('contain_gap_at_most_one_su_per_side', all(max(f['gap_per_side_su']) <= 1 for f in scan_fits),
          {'max_gap_su': max(max(f['gap_per_side_su']) for f in scan_fits), 'reason': 'Prescribed viewports plus contain produce larger letterboxing.'})
    check('backs_strict_cover_by_height', all(f['strict_cover_required_crop_fraction'] <= .014 for f in back_fits),
          {'required_total_crop_range': [min(f['strict_cover_required_crop_fraction'] for f in back_fits), max(f['strict_cover_required_crop_fraction'] for f in back_fits)],
           'reason': 'Strict height cover conflicts with the 1.4% crop budget. Centred budget-limited crop then contain preserves logos.'})
    check('all_display_aspects_exactly_0_721', all(abs(v[0] / v[1] - .721) < 1e-9 for v in contract['displays'].values()),
          {'aspects': {k: v[0] / v[1] for k, v in contract['displays'].items()}, 'reason': 'Exact prescribed integer dimensions take precedence.'})
    widths = {'idle': 1, 'selected': 3, 'warning': 2, 'flash': 2}
    check('four_grayscale_states_differ_by_edge_width_alone', len(set(widths.values())) == 4,
          {'widths_su': widths, 'reason': 'Warning and flash both explicitly require 2 su; grayscale luminance differentiates them instead.'})
    check('mini_selected_warning_flash_keep_full_edge_width', False,
          {'available_edge_su': 1, 'requested_edge_su': {'selected': 3, 'warning': 2, 'flash': 2},
           'reason': '2 su band includes 1 su keyline. Full state edges would overlap scan. Mini previews use 1 su; distinct widths exist at regular sizes.'})
    gray_signatures = {}
    for state in ('idle', 'selected', 'warning', 'flash'):
        with Image.open(PACKAGE / f'vector/sizes/hand/card-frame-{state}-x1.png') as im:
            a = np.asarray(im.convert('RGBA'))[:4, 75].astype(np.float64)
        lum = a[:, :3] @ np.array([.2126, .7152, .0722])
        alpha = a[:, 3] / 255
        gray_signatures[state] = np.round(lum * alpha + (np.array([6, 22, 35]) @ np.array([.2126, .7152, .0722])) * (1 - alpha), 3).tolist()
    check('four_grayscale_states_visually_distinct', len({tuple(v) for v in gray_signatures.values()}) == 4, gray_signatures)
    check('no_image_generation', read(PACKAGE / 'generation-records.json')['image_generation_used'] is False)
    # Package cannot contain scans: derive a complete listing of scan-bearing files and enforce its root.
    package_png = {p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*.png')}
    expected_package_png = set(contract['assets']) | {
        f'comparison/overlay-{size}-x{k}{suffix}.png'
        for size in ('master', 'working') for k in (1, 2) for suffix in ('', '-gray')}
    derived_png = {p.name for p in DERIVED.glob('*.png')}
    expected_derived_png = expected_names | {n.replace('.png', '-gray.png') for n in expected_names} | {
        f'lift-comparison-x{k}{suffix}.png' for k in (1, 2) for suffix in ('', '-gray')}
    check('scan_bearing_outputs_in_derived_only', package_png == expected_package_png and derived_png == expected_derived_png,
          {'package_png': len(package_png), 'derived_png': len(derived_png),
           'unexpected_package_png': sorted(package_png - expected_package_png),
           'unexpected_derived_png': sorted(derived_png - expected_derived_png),
           'proof': 'Every package frame is independently measured as exact procedural tokens with transparent aperture; remaining package images are the eight declared scan-free overlays. Real source entries exist exclusively in derived sheets.'})
    allowed_roots = ('art/imagegen/card-frame-v1-codex/', 'scraped-data/derived/card-frame-v1-codex/')
    audit = read(PACKAGE / 'write-audit.json')
    outside = [p for p in audit['observed_writes'] if not p.startswith(allowed_roots)]
    check('outside_folder', not outside, {'guarded_generator': True, 'guarded_verifier': True,
          'scope': 'Operations of this task; concurrent sessions are outside the audit scope.'})
    result = {'task': 'CP-13', 'status': 'предложено', 'source_unchanged': not changed and not added,
              'outside_folder': outside, 'all_acceptance_met': not failures,
              'implementation_checks_passed': all(v['passed'] for k, v in checks.items() if k not in {
                  'nominal_frame_window_matches_scan_aspect_within_one_px', 'contain_gap_at_most_one_su_per_side',
                  'backs_strict_cover_by_height', 'all_display_aspects_exactly_0_721',
                  'four_grayscale_states_differ_by_edge_width_alone', 'mini_selected_warning_flash_keep_full_edge_width'}),
              'failed_or_conflicting_requirements': failures, 'checks': checks, 'assets': asset_results,
              'verification_duration_seconds': round(time.monotonic() - start, 2),
              'runtime_animation_verified': False,
              'runtime_note': 'Static procedural package only. No Unreal opened. 500 ms cue and lift offsets specified, not tested in engine.'}
    dump(PACKAGE / 'verification.json', result)
    audit['verifier_writes'] = sorted(WRITES | {'art/imagegen/card-frame-v1-codex/manifest-sha256.json',
                                             'art/imagegen/card-frame-v1-codex/write-audit.json'})
    audit['authored_files'] = [p.relative_to(ROOT).as_posix() for p in PACKAGE.rglob('*') if p.is_file() and p.suffix in ('.py', '.md')]
    dump(PACKAGE / 'write-audit.json', audit)
    files = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
             for base in (PACKAGE, DERIVED) for p in sorted(base.rglob('*'))
             if p.is_file() and p.name != 'manifest-sha256.json'}
    dump(PACKAGE / 'manifest-sha256.json', {'algorithm': 'sha256', 'self_excluded': True, 'files': files})
    print(json.dumps({'implementation_checks_passed': result['implementation_checks_passed'],
                      'source_unchanged': result['source_unchanged'], 'outside_folder': outside,
                      'reported_conflicts': failures, 'hashed_outputs': len(files)}, ensure_ascii=False), flush=True)
    if not result['implementation_checks_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    verify()
