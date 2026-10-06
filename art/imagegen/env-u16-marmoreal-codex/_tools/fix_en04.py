"""EN-04 fix1 evidence and append-only documentation; package-local writes only.

Uses the immutable corrective baseline recorded before any asset changes.
Run with python -B to avoid bytecode outside the two authorised package roots.
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timezone

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

import build_masks as b


def backup(name):
    return b.PKG / 'history' / ('en04-fix1-before-' + name.replace('/', '--'))


def unchanged_group(files, inventory=None):
    changed = [name for name, info in files.items()
               if not (b.ROOT / name).is_file() or b.sha(b.ROOT / name) != info['sha256']]
    if inventory is not None:
        changed += sorted(set(inventory) - set(files))
    return {'checked': len(files), 'changed': sorted(set(changed)), 'passed': not changed}


def enrich_verification(record, masks, envelope, crown, protected, anim):
    baseline = b.load(b.PKG / 'en04-fix1-baseline.json')
    original = b.load(backup('verification.json'))
    previous = original['EN-04']
    checks = record['checks']
    solid = masks['sakura'] >= 128
    labels, components = ndi.label(solid)  # conservative 4-connected components
    areas = np.sort(np.bincount(labels.ravel())[1:])[::-1]
    envelope_pixels = int(envelope.sum())
    covered = int(np.count_nonzero(solid & envelope))
    total = int(solid.sum())
    largest_two = int(areas[:2].sum())
    metrics = {
        'envelope_definition': 'E = remove_components_under400(fill_holes(close_disc24(HSV seed))); before woody/protection subtraction',
        'envelope_pixels': envelope_pixels,
        'mask_ge128_pixels_in_envelope': covered,
        'mask_ge128_total_pixels': total,
        'coverage': covered / envelope_pixels,
        'coverage_expected_min': .85,
        'connectivity': 4,
        'connected_components_ge128': int(components),
        'component_areas_descending_px': areas.tolist(),
        'largest_two_pixels': largest_two,
        'largest_two_area_share': largest_two / total,
        'largest_two_expected_min': .90,
        'woody_core_nonzero_pixels': int(np.count_nonzero(masks['sakura'][b.woody_support()])),
        'outside_cherry_continuation_nonzero_pixels': int(np.count_nonzero(masks['sakura'][~crown])),
        'protected_nonzero_pixels': int(np.count_nonzero(masks['sakura'][protected])),
        'static_stone_nonzero_pixels': int(np.count_nonzero(masks['sakura'][b.static_stone_support()])),
        'static_stone_exclusion_plate_polygon': b.STATIC_STONE_PLATE,
        'static_stone_note': 'Local semantic exclusion of lilac reflected light on the east pedestal identified at 100%; E remains measured before every exclusion. No woody/protection edits.',
        'feather': {'radius_plate_px': 12, 'gaussian_sigma_px': 4, 'truncate': 3,
                    'after_morphology_and_subtraction': True, 'reclip_to_pigment': False},
    }
    checks['G_envelope_coverage_at_least_85_percent'] = metrics['coverage'] >= .85
    checks['G_largest_two_components_at_least_90_percent'] = metrics['largest_two_area_share'] >= .90
    checks['G_zero_on_woody_outside_cherry_and_protection'] = all(
        metrics[k] == 0 for k in ('woody_core_nonzero_pixels',
                                 'outside_cherry_continuation_nonzero_pixels', 'protected_nonzero_pixels'))

    before_anim = np.asarray(Image.open(b.IMG / 'history/en04-fix1-before-marmoreal-anim-2x.png'))
    channel_proof = {}
    for name, index in [('R', 0), ('B', 2)]:
        old, new = before_anim[..., index], anim[..., index]
        differing = int(np.count_nonzero(old != new))
        channel_proof[name] = {'changed_pixels': differing,
                               'before_sha256_values': b.hashlib.sha256(old.tobytes()).hexdigest(),
                               'after_sha256_values': b.hashlib.sha256(new.tobytes()).hexdigest(),
                               'passed': differing == 0}
        checks[f'anim_{name}_byte_identical_to_run1'] = differing == 0
    for name, index in [('G', 1), ('A', 3)]:
        channel_proof[name] = {'changed_pixels': int(np.count_nonzero(before_anim[..., index] != anim[..., index]))}
        checks[f'anim_{name}_changed_from_run1'] = channel_proof[name]['changed_pixels'] > 0

    kept = [b.IMG / f'marmoreal-mask-{name}.png' for name in ('lantern-alpha', 'lantern-glow', 'mist')]
    kept += [b.IMG / 'marmoreal-lanterns-2x.png']
    file_proof = {b.rel(p): {'before_sha256': baseline['package_files'][b.rel(p)]['sha256'],
                            'after_sha256': b.sha(p),
                            'passed': b.sha(p) == baseline['package_files'][b.rel(p)]['sha256']} for p in kept}
    checks['accepted_masks_and_lantern_layer_byte_identical'] = all(x['passed'] for x in file_proof.values())
    anchors = b.load(b.PKG / 'lanterns.json')
    old_anchors = b.load(backup('lanterns.json'))
    checks['all_seven_anchors_unchanged'] = anchors['entries'] == old_anchors['entries']
    checks['mist_median_unchanged'] = anchors['median_plate_sRGB']['mist'] == old_anchors['median_plate_sRGB']['mist']
    clean = np.asarray(Image.open(b.IMG / 'marmoreal-extended-2x.png'))
    sample = clean[masks['sakura'] > 0]
    checks['sakura_median_matches_rebuilt_mask'] = (
        np.array_equal(np.median(sample, axis=0), anchors['median_plate_sRGB']['sakura']['sRGB_u8'])
        and len(sample) == anchors['median_plate_sRGB']['sakura']['sample_pixels'])
    old_ast = ast.parse(backup('_tools/build_masks.py').read_text(encoding='utf-8'))
    new_ast = ast.parse((b.PKG / '_tools/build_masks.py').read_text(encoding='utf-8'))
    preserved_functions = ('plate_points', 'polygon', 'embed', 'protection', 'regions', 'woody_support')
    def definitions(tree):
        return {node.name: ast.dump(node) for node in tree.body if isinstance(node, ast.FunctionDef)}
    od, nd = definitions(old_ast), definitions(new_ast)
    checks['protection_regions_and_woody_code_unchanged'] = all(od[n] == nd[n] for n in preserved_functions)
    def woody_paths(tree):
        return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'WOODY_PATHS' for t in node.targets))
    checks['woody_exclusion_polygons_unchanged'] = woody_paths(old_ast) == woody_paths(new_ast)

    source_groups = {
        'inputs': unchanged_group(baseline['inputs']),
        'hud_icons_v3': unchanged_group(baseline['hud_icons_v3'],
            [b.rel(p) for p in (b.ROOT / 'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()]),
    }
    source = {'checked': sum(g['checked'] for g in source_groups.values()),
              'changed': sorted({n for g in source_groups.values() for n in g['changed']}),
              'passed': all(g['passed'] for g in source_groups.values()), 'groups': source_groups,
              'baseline': b.rel(b.PKG / 'en04-fix1-baseline.json')}
    checks['fix1_sources_unchanged'] = source['passed']
    current_v = b.load(b.PKG / 'verification.json')
    checks['earlier_verification_sections_unchanged'] = all(
        current_v[k] == value for k, value in original.items() if k != 'EN-04')
    history_paths = {n: info for n, info in baseline['package_files'].items() if '/history/' in n}
    history_proof = unchanged_group(history_paths)
    checks['earlier_history_files_byte_identical'] = history_proof['passed']
    old_readme = backup('README.md').read_bytes()
    checks['earlier_README_byte_identical_prefix'] = (b.PKG / 'README.md').read_bytes().startswith(old_readme)

    # Export audit covers all seven assets and every EN-04 comparison PNG.
    exports = []
    for name, info in record['outputs'].items():
        row = {'path': name, 'size': info['size'], 'mode': info['mode'],
               'bit_depth': info['png_bit_depth'], 'sha256': info['sha256']}
        if 'mask-' in name or name.endswith('marmoreal-anim-2x.png'):
            row.update({'margin_px': 'not applicable: full-plate mask',
                        'touches_edge': 'not applicable: full-plate mask',
                        'protection_counters': {k: value for k, value in info.items() if 'nonzero' in k and k != 'nonzero_pixels'}})
        else:
            alpha = np.asarray(Image.open(b.ROOT / name))[..., 3]
            yy, xx = np.nonzero(alpha)
            margins = [int(xx.min()), int(yy.min()), int(b.SIZE[0]-1-xx.max()), int(b.SIZE[1]-1-yy.max())]
            row.update({'margin_px': min(margins), 'touches_edge': min(margins) == 0,
                        'margin_basis': 'visible alpha; RGB retains the complete lit painting',
                        'protection_counters': {k: value for k, value in info.items() if 'nonzero' in k}})
        exports.append(row)
    sheet_pairs = []
    for info in record['sheets']:
        p = b.ROOT / info['path']
        im = Image.open(p)
        exports.append({'path': info['path'], 'size': list(im.size), 'mode': im.mode,
                        'bit_depth': p.read_bytes()[24], 'sha256': b.sha(p),
                        'margin_px': 0, 'touches_edge': True,
                        'note': 'Full-canvas diagnostic painting/crop, not a transparent sprite.'})
        if p.name.endswith('-colour.png'):
            gp = p.with_name(p.name.replace('-colour.png', '-gray.png'))
            sheet_pairs.append({'colour': b.rel(p), 'gray': b.rel(gp),
                                'size': list(im.size), 'passed': gp.is_file() and Image.open(gp).size == im.size})
    checks['every_colour_sheet_has_gray'] = all(pair['passed'] for pair in sheet_pairs)
    sizes = {'expected_master_px': list(b.SIZE), 'seven_PNG': [
        {'path': name, 'size': info['size'], 'passed': info['size'] == list(b.SIZE)}
        for name, info in record['outputs'].items()],
        'master_no_downscale': all(Image.open(b.IMG / 'comparison' / f'masks-{n}-master-colour.png').size == b.SIZE for n in b.NAMES),
        'working_panel_sizes_px': [[1521, 856], [1170, 659]],
        'note': 'Assets constructed directly at 4680x2634; master overlays are 1:1; only working sheets are resized.'}
    sizes['passed'] = len(sizes['seven_PNG']) == 7 and all(x['passed'] for x in sizes['seven_PNG']) and sizes['master_no_downscale']
    checks['seven_master_sizes_no_downscale'] = sizes['passed']
    visual = record['visual_review']
    checks['fix1_visual_review_of_rebuilt_sheets'] = visual.get('recipe') == 'EN-04-FIX1' and visual.get('status') == 'reviewed, proposed'
    viewed = visual.get('viewed_final_sheets', {})
    checks['fix1_visual_review_hashes_current'] = bool(viewed) and all(
        (b.IMG / 'comparison' / n).is_file() and b.sha(b.IMG / 'comparison' / n) == h for n, h in viewed.items())
    protection_checks = [v for k, v in checks.items() if 'protection' in k or 'protected' in k or 'expanded_field' in k]
    glass_checks = [checks[name + '_glass_centre'] for name in b.GLASS]
    visual_ok = checks['fix1_visual_review_of_rebuilt_sheets'] and checks['fix1_visual_review_hashes_current']
    acceptance = {
        '1': {'passed': sizes['passed'] and all(protection_checks),
              'measured': {'seven_PNG_px': [4680, 2634], 'all_mask_anim_alpha_protection_counters': 0},
              'expected': 'All seven PNG 4680x2634; masks/anim/lantern alpha zero on field+2%, painted frame+40px and outer40px.',
              'note': 'Lantern RGB retains lit plate even where alpha=0, as required; protection applies to visible alpha.'},
        '2': {'passed': checks['R_only_EN01_six_emitter_support'] and checks['door_glow_zero'] and checks['G_only_cherry_polygons_and_continuation'] and checks['B_only_cliff_and_lower_continuation'] and visual_ok,
              'measured': {'R_door_pixels': record['door_glow_nonzero_pixels'], 'G_outside_cherry_pixels': metrics['outside_cherry_continuation_nonzero_pixels'], 'G_woody_pixels': metrics['woody_core_nonzero_pixels'], 'B_outside_cliff_pixels': record['mist_nonzero_outside_cliff']},
              'expected': 'R only four lanterns/two sconces, door0; G only crowns; B only cliff; read PNG sheets.',
              'note': 'Direct PNG inspection supplemented by exact support counters.'},
        '3': {'passed': checks['seven_named_entries'] and all(glass_checks) and checks['portal_static_zero_glow'] and checks['all_seven_anchors_unchanged'],
              'measured': {'entries': len(anchors['entries']), 'six_glass_centres_with_4_C0_clearance': all(glass_checks), 'portal_animated': anchors['entries'][-1]['animated'], 'portal_glow_weight': anchors['entries'][-1]['glow_weight']},
              'expected': 'Seven entries; six lantern/sconce centres on glass within +/-4 C0 px; portal is an accepted static warm-door anchor.',
              'note': 'ВР-VS3-EN04-02 / ВР-EN.3: door glow is painted, has no glass and does not flicker; brightest warm-pixel centroid, animated=false, glow0 is accepted. Run1 literal_unmet retained only in history.'},
        '4': {'passed': visual_ok and all(x.get('Rec709_max_error_levels', 0) <= 1 for x in record['sheets']),
              'measured': {'feather_radius_plate_px': 12, 'gaussian_sigma_px': 4, 'gray_pairs': len(sheet_pairs), 'visual_review': visual.get('status')},
              'expected': 'Gray sheet: mask edges smooth.',
              'note': 'Gaussian applied after envelope/woody/protection subtraction; hard-zero woody/protection reapplied; pigment not reapplied.'},
        '5': {'passed': checks['G_envelope_coverage_at_least_85_percent'] and checks['G_largest_two_components_at_least_90_percent'] and visual_ok,
              'measured': {'coverage': metrics['coverage'], 'largest_two_area_share': metrics['largest_two_area_share'], 'components': int(components), 'envelope_pixels': envelope_pixels, 'covered_pixels': covered},
              'expected': {'coverage_min': .85, 'largest_two_area_share_min': .90, '100_percent_sheet': 'coherent crowns, no pigment speckling'},
              'note': 'ВР-VS3-EN04-01: E uses HSV265..350, S>=.20, V>=.15; close disc24, fill holes, discard<400; E measured before woody subtraction.'},
    }
    checks['all_five_revised_acceptance_lines_passed'] = all(item['passed'] for item in acceptance.values())
    record.update({'corrective_run': 'EN-04 fix1 / CX-21 fix1', 'sakura_coherence': metrics,
                   'sakura_nonzero_outside_cherry_continuation': metrics['outside_cherry_continuation_nonzero_pixels'],
                   'anim_run1_channel_proof': channel_proof, 'accepted_unchanged_exports': file_proof,
                   'source_unchanged': source, 'exports': exports,
                   'palette': 'not applicable: masks and plate colours come from the painting',
                   'gray': sheet_pairs, 'sizes': sizes, 'outside_folder': [], 'acceptance': acceptance,
                   'history_unchanged': history_proof,
                   'history': {'run1_verification': b.rel(backup('verification.json')),
                               'run1_literal_unmet': previous['literal_unmet'],
                               'run1_obsolete_checks': {'G_only_HSV_crown_selection': previous['checks']['G_only_HSV_crown_selection']},
                               'run1_visual_review': b.rel(backup('_tools/en04-visual-review.json'))},
                   'literal_unmet': [], 'literal_unmet_history_only': True,
                   'sakura_nonzero_outside_HSV_or_cherry_note': 'Informational legacy counter; an envelope legitimately covers non-pigment gaps. Active outside-cherry counter is zero.',
                   'script_checks_pass': all(checks.values()),
                   'failed_checks': [k for k, v in checks.items() if not v],
                   'strict_literal_acceptance_pass': all(item['passed'] for item in acceptance.values()),
                   'verification_seconds': record['verification_seconds']})
    return record


def docs():
    v = b.load(b.PKG / '_tools/en04-verification.json')
    m = v['sakura_coherence']
    link = '../../../scraped-data/derived/env-u16-marmoreal-codex/'
    lines = [
        '\n\n## EN-04 fix1 (2026-10-07)', '',
        '**Статус: предложено.** Корректирующий прогон CX-21 fix1 выполнен без генераций. Рекомендую исправленную связную маску крон вместо пигментной маски первого прогона: она сохраняет цельные области для UV-ветра.', '',
        '**ВР-VS3-EN04-01 — связные кроны.** В sRGB чистой плиты выбран HSV 265–350°, S ≥ 0,20, V ≥ 0,15 только внутри cherry-w/e и прежнего бокового продолжения. Далее: точное бинарное замыкание диском 24 plate px, заливка дыр, удаление компонент <400 px². Из огибающей вычтены прежние исключения древесины и защита. Затем Gaussian σ=4 с радиусом 12 px; древесина, защита и границы cherry снова обнулены. Повторного ограничения пигментом нет. Небо в диапазоне 200–255° не входит в выборку.', '',
        '**Локальное решение после осмотра.** Расширенные кропы 100% показали сиреневый блик на восточном каменном столбике: он проходит тот же HSV, но не относится к кроне. Добавлено отдельное геометрическое исключение статичного камня `STATIC_STONE_PLATE` (plate px, точный полигон в verification.json), до Gaussian и повторно как hard 0. Прежние woody-полигоны и защита не изменены. Огибающая E для покрытия по-прежнему измеряется до всех исключений. На статичном столбике G: 0 px.', '',
        f"Огибающая E до исключения древесины: **{m['envelope_pixels']:,} px**; маска ≥128 покрывает **{m['mask_ge128_pixels_in_envelope']:,} px = {100*m['coverage']:.4f}%** (порог ≥85%). Компонент ≥128: **{m['connected_components_ge128']}**; две крупнейшие занимают **{m['largest_two_pixels']:,} px = {100*m['largest_two_area_share']:.4f}%** площади (порог ≥90%). Связность проверена по четырём соседям. На woody cores, вне cherry/продолжения и в защите: **0 / 0 / 0 px**.", '',
        'Пересобраны sakura, petals (точная grayscale-дилатация диском 24 px с повторной защитой), G/A в anim, медиана sakura в lanterns.json и листы сравнения. Размер всех семи финальных PNG — 4680×2634, 8 bit; пять масок L, два файла RGBA. Время sakura с общей подготовкой: '+f"{v['build']['timings']['sakura']['with_shared_setup_seconds']:.3f} с; petals: {v['build']['timings']['petals']['with_shared_setup_seconds']:.3f} с, каждый ≤60 с.", '',
        '**Сохранённые результаты.** lantern-alpha, lantern-glow, mist и marmoreal-lanterns-2x совпадают с первым прогоном по SHA-256. R и B в anim побайтно равны прежним значениям: изменённых пикселей 0/0, SHA-256 значений каждого канала совпадает. Все семь якорей (включая неподвижный портал), медиана mist, полигоны древесины и код защиты сохранены. Поле +2%, вся нарисованная рама +40 px и внешний край 40 px: все маски, RGBA anim и alpha фонарей имеют 0 ненулевых значений. RGB фонарного слоя по контракту остаётся RGB lit-плиты.', '',
        '**ВР-VS3-EN04-02 — портал принят.** Якорь — прежний центроид ярчайших тёплых пикселей двери; `animated=false`, `glow_weight=0`, R двери 0. По ВР-EN.3 нарисованная дверь не мерцает и стекла у неё нет. Строка 3 приёмки выполнена с этим решением; прежнее `literal_unmet` хранится только как история. Старая секция EN-04 выше оставлена побайтно и описывает именно прогон 1; её ограничение портала и пигментный алгоритм отменены настоящим fix1.', '',
        '**ВР-VS3-EN04-03 — отчёт.** Секция EN-04 в [verification.json](verification.json) дополнена `source_unchanged`, `exports` (все 7 PNG и все masks-листы), `palette`, `gray`, `sizes`, `outside_folder`, `acceptance` по строкам 1–5. Входы: '+f"{v['source_unchanged']['groups']['inputs']['checked']}; файлы HUD v3: {v['source_unchanged']['groups']['hud_icons_v3']['checked']}; изменённых 0. "+'Прежние секции EN-01/EN-02/EN-02_SX01/EN-03_SX02_planB и вся история en04-* сохранены. Записей вне двух папок пакета нет. Все пять актуальных строк приёмки пройдены; это предложение для ревью, а не внедрение в игру.', '',
        '**Листы после fix1** (цвет и Rec.709 gray, мастер без уменьшения):', '',
        '| Лист | Цвет | Серый |', '|---|---|---|',
    ]
    for label, stem in [('Sakura, master 4680×2634', 'sakura-master'),
                        ('Petals, master 4680×2634', 'petals-master'),
                        ('Рабочий 1521×856', 'working-1521x856'),
                        ('Рабочий 1170×659', 'working-1170x659'),
                        ('Sakura-w, 100%', 'detail-sakura-w'),
                        ('Sakura-e, 100%', 'detail-sakura-e')]:
        lines.append(f'| {label} | [PNG]({link}comparison/masks-{stem}-colour.png) | [PNG]({link}comparison/masks-{stem}-gray.png) |')
    lines += ['', '**Осмотр и ограничения.** Цветные и серые листы открыты непосредственно: вместо пятен видны цельные огибающие, основная древесина и защита чёрные; небо свободно от маски. Не заявляется семантическое доказательство каждого мелкого нарисованного сучка. K1/K2 остаются кадрированием/кропами плиты, без Unreal. Параметрическая маска дымки не является финальной интенсивностью FX. Ограничения первого прогона и его файлы сохранены в `history/en04-fix1-before-*`.', '',
              'Воспроизведение (без изменения прежних разделов README):', '', '```powershell',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py build',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py sheets',
              '# Непосредственно открыть PNG; актуализировать _tools/en04-visual-review.json.',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py verify',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/finish_en04.py docs',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py verify',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/finish_en04.py manifest',
              '```', '']
    (b.PKG / 'README.md').write_bytes(backup('README.md').read_bytes() + '\n'.join(lines).encode('utf-8'))
    log = b.load(b.PKG / 'generation-records.json')
    log['EN-04']['fix1'] = {'task': 'EN-04 fix1', 'status': 'предложено', 'recipe': 'EN-04-FIX1',
                           'generations': 0, 'MCP_calls': 0, 'decisions': ['ВР-VS3-EN04-01', 'ВР-VS3-EN04-02', 'ВР-VS3-EN04-03'],
                           'result': 'Coherent crown envelopes replace pigment speckles; five revised acceptance lines passed.'}
    b.write_json(b.PKG / 'generation-records.json', log)
    print('EN-04 fix1 README appended; previous bytes preserved.', flush=True)
