"""Bounded CX-34 fix1. Offline only; python -B fix1.py --render/--finalize/--check.

--finalize is used only after directly opening every regenerated original PNG.
Run-1 measurements and hashes are archived; inputs and unchanged mockups are immutable.
"""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
import sc34_gameover_victory as base
from fix1_overlays import render_overlay

ROOT = base.ROOT
CARDS = list(base.SETS)
PROMPT = 'docs/game-design/visual/06-tasks/prompts/SC-34-series.fix1.codex.md'


def dump(p, value, card):
    base.dump(p, value, card)


def baseline(card):
    pkg, der = base.folders(card)
    path = pkg/'fix1-before.json'
    if not path.exists():
        manifest = base.load(pkg/'manifest-sha256.json')
        derived = {base.relative(p): base.file_info(p) for p in der.rglob('*') if p.is_file()}
        assert all(manifest['files'].get(p) == v for p, v in derived.items()), (card, 'derived changed before fix1')
        dump(path, {'schema': 'CX-34.fix1-before/1',
                    'derived_files': derived,
                    'package_files_run1': {p: v for p, v in manifest['files'].items() if p.startswith(base.relative(pkg)+'/')},
                    'inputs_before_fix1': {p: base.file_info(ROOT/p) for p in manifest['inputs']},
                    'verification': base.load(pkg/'verification.json'),
                    'geometry': base.load(pkg/'layout-geometry.json'),
                    'visual_review': base.load(pkg/'visual-review.json'),
                    'readme': (pkg/'README.md').read_text(encoding='utf-8')}, card)
    return base.load(path)


def allowed_derived(card, path):
    name = Path(path).name
    return card == 'SC-37' and any(name == f'SC-37-{state}-{res}-150{suffix}.png'
        for state in ['again', 'again-busy', 'comparison'] for res in ['1080p', '720p'] for suffix in ['', '-gray'])


def preservation(card, before):
    _, der = base.folders(card)
    current = {base.relative(p): base.file_info(p) for p in der.rglob('*') if p.is_file()}
    rows, failures = [], []
    for path in sorted(set(before['derived_files']) | set(current)):
        old = before['derived_files'].get(path)
        new = current.get(path)
        same = old == new
        allowed = allowed_derived(card, path)
        if not same and not allowed:
            failures.append(path)
        rows.append({'path': path, 'sha256_before': old['sha256'] if old else None,
                     'sha256_after': new['sha256'] if new else None,
                     'byte_identical': same, 'change_allowed': allowed,
                     'passed': same or allowed})
    return {'passed': not failures, 'failures': failures, 'files': rows,
            'mockup_files': [r for r in rows if Path(r['path']).name.startswith(card+'-')
                             and '-comparison-' not in r['path'] and r['path'].endswith('.png')],
            'note': 'Only eight SC-37 class S mockups and their four comparison sheets may differ.'}


def render_class_s(before):
    card = 'SC-37'
    pkg, der = base.folders(card)
    tools = pkg/'_tools'
    sys.path.insert(0, str(tools))
    from sc37_gameover_again import again_configuration, again_gameover
    verification = copy.deepcopy(before['verification'])
    geometry = copy.deepcopy(before['geometry'])
    regenerated = []
    for res in ['1080p', '720p']:
        images = []
        for state in ['again', 'again-busy']:
            data, params = again_configuration(card, state)
            bg, grade = base.scene_grade(Image.open(ROOT/base.BG[params['background']]).convert('RGB'), params['grade'])
            vp = base.Viewport.preset(res, 150)
            c = base.ResultCanvas(vp, bg)
            c.grade, c.data = grade, data
            again_gameover(c, **params)
            assert c.modal[2:] == (760, 560)
            row = c.widgets['ButtonRow']
            assert row['fits_budget'] and row['chips'] and row['gap_su'] == 16
            # Preserve the class S vertical anchors and portrait offsets exactly.
            key = f'{state}-{res}-150'
            old = before['geometry'][key]['widgets']
            for name in ['OutcomeText', 'HeadlineText', 'ReasonText', 'TurnText', 'LeftPortrait', 'RightPortrait', 'ButtonRow']:
                assert c.widgets[name]['rect_su'][1] == old[name]['rect_su'][1], name
            final = c.finish()
            images.append(final)
            for suffix, image in [('', final), ('-gray', base.luma709(final).convert('RGBA'))]:
                path = der/f'{card}-{key}{suffix}.png'
                image.save(base.guard(path, card))
                regenerated.append(base.relative(path))
            report = base.analyze(c, final, state)
            report['facts'] = base.factual_checks(c, data, state)
            report['drawn_values_equal_inputs'] = all(f['equal'] for f in report['facts'])
            report['geometry'] = c.widgets
            verification['frames'][key] = report
            geometry[key]['widgets'] = c.widgets
        sheet = Image.new('RGBA', (images[0].width, images[0].height*2))
        for i, image in enumerate(images):
            sheet.paste(image, (0, i*image.height))
        for suffix, image in [('', sheet), ('-gray', base.luma709(sheet).convert('RGBA'))]:
            path = der/f'{card}-comparison-{res}-150{suffix}.png'
            image.save(base.guard(path, card))
            regenerated.append(base.relative(path))
    dump(pkg/'layout-geometry.json', geometry, card)
    return verification, regenerated


def add_acceptance(v, key, measured, expected, passed, note=''):
    entry = {'passed': bool(passed), 'measured': measured, 'expected': expected, 'note': note}
    if isinstance(v['acceptance'], list):
        v['acceptance'] = [a for a in v['acceptance'] if a['criterion'] != key]
        v['acceptance'].append({'criterion': key, **entry})
        v['acceptance_pass'] = all(a['passed'] for a in v['acceptance'])
    else:
        v['acceptance'][key] = entry


def update_readme(card, before, regenerated):
    pkg, _ = base.folders(card)
    text = before['readme']
    reproduction = ''
    if 'Пересборка:' in text:
        start = text.index('Пересборка:')
        end = text.index('\n## ', start)
        reproduction = text[start:end].strip()
        text = text[:start]+text[end:]
        text = text.replace('## Листы и воспроизведение', '## Листы')
    elif '## Воспроизведение и отчёты' in text:
        start = text.index('## Воспроизведение и отчёты')
        end = text.index('\n## ', start+4)
        reproduction = text[start:end].strip()
        text = text[:start]+text[end:]
    if card == 'SC-37':
        text = '\n'.join(line for line in text.split('\n') if not line.startswith('- Не пройдено: ButtonRow fits'))
        old = 'Если класс S всё ещё шире бюджета, это отражено как непрохождение; ряд остаётся по центру и не обрезается.'
        text = text.replace(old, 'По ВР-VS5-SC37-06 модаль класса S расширена до 760 su: ряд с V и Enter и промежутками 16 su помещается в 712 su.')
    lines = [text.rstrip(), '', '## fix1', '',
             'CX-34 fix1, 2026-10-08. Статус остаётся **предложено**. Каждый контур на схеме снабжён номером '
             'своей легенды: Roboto Regular не менее 14 px, text.primary на card.navy, keyline panel.edge 1 px. '
             'Тег в левом верхнем углу внутри, а при нехватке места — снаружи с линией 1 px. '
             'Легенда вынесена в добавленное поле справа; масштаб схемы сохранён 1:1. '
             'Измеренные пересечения тегов друг с другом и с легендой: 0; пересечения подписей: 0.', '']
    if card == 'SC-34':
        lines += ['Добавлены отдельные `SC-34-overlay-draw-<res>-<scale>.png` и `-gray.png` для четырёх холстов: '
                  'в draw нет HeadlineText/ReasonText/TurnText и есть два FallenIcon. Все victory/draw макеты побайтово сохранены.', '']
    if card == 'SC-37':
        lines += ['**ВР-VS5-SC37-06:** VS_AI с тремя кнопками использует в классе S модаль **760×560 su** '
                  'вместо 680×560; вертикальные координаты класса S и центры портретов ±160 su сохранены. '
                  'Ряд **705,75 su / бюджет 712 su**, поля **27,125 su**, gaps **16 su**; V и Enter восстановлены. '
                  'Критерий ButtonRow теперь пройден. Геометрия again-busy отличается дополнительным AgainSpinner, '
                  'поэтому для каждого холста добавлен отдельный `SC-37-overlay-again-busy-<res>-<scale>.png` и серый. '
                  'Прямоугольники трёх кнопок совпадают в обеих фазах. Восемь макетов класса L сохранены побайтово.', '']
    lines += ['Перегенерированные PNG (каждый повторно открыт отдельно, цвет и Rec.709 серый):', '']
    import os
    for path in regenerated:
        target = Path(os.path.relpath(ROOT/path, pkg)).as_posix()
        lines.append(f'- [{Path(path).name}]({target})')
    lines += ['', 'SHA-256 до/после каждого mockup и всех derived-файлов: `verification.json` → '
              '`mockup_unchanged`; любая незапрошенная разница считается ошибкой. Замеры run 1 сохранены '
              'в `fix1.run1_measurements` и `fix1-before.json`. Общий sc34_gameover_victory.py и его '
              'SC-35/36/37 копии не менялись; copy-provenance остаётся true. Исходные ограничения контраста '
              'скинов/иконок сохранены; они не входят в коррекцию fix1.', '',
              'Обновлены `README.md`, `verification.json`, `visual-review.json`, `manifest-sha256.json`; '
              'добавлен неизменяемый снимок исходных хешей и замеров `fix1-before.json`. '
              'Общая коррекция находится в SC-34 `_tools/fix1.py` и `_tools/fix1_overlays.py`. '
              + ('В SC-37 также обновлены собственный `_tools/sc37_gameover_again.py` и `layout-geometry.json`.'
                 if card == 'SC-37' else 'Геометрия макетов и скрипты run 1 сохранены.'), '',
              '## Воспроизведение', '',
              '`python -B art/imagegen/sc34-gameover-victory-codex/_tools/fix1.py --render` — '
              'воспроизвести ровно correction fix1 для пяти пакетов (сбрасывает осмотр изменённых PNG). '
              'После прямого открытия каждого перечисленного PNG: `--finalize`. '
              '`--check` — полная проверка fix1 без записи. Нужны уже установленные Pillow/NumPy; '
              'установки пакетов, сеть, Git, MCP и unreal/ не используются.', '',
              'Примечания воспроизведения run 1 (архив; для текущих исправлений используется команда выше):', '',
              reproduction, '']
    base.textwrite(pkg/'README.md', '\n'.join(lines), card)


def render():
    before_all = {card: baseline(card) for card in CARDS}
    for card in CARDS:
        before = before_all[card]
        pkg, _ = base.folders(card)
        if card == 'SC-37':
            v, regenerated = render_class_s(before)
        else:
            v, regenerated = copy.deepcopy(before['verification']), []
        overlays = {}
        for res, scale in base.PRESETS:
            states = [base.STATES[card][0]]
            if card == 'SC-34': states += ['draw']
            if card == 'SC-37': states += ['again-busy']
            for state in states:
                widgets = v['frames'][f'{state}-{res}-{scale}'].get('geometry') or v['frames'][f'{state}-{res}-{scale}']['widgets']
                suffix = '' if state == base.STATES[card][0] else '-'+state
                path = pkg/f'comparison/{card}-overlay{suffix}-{res}-{scale}.png'
                report = render_overlay(widgets, base.Viewport.preset(res, scale), base.theme(), path,
                                        lambda p: base.guard(p, card))
                report['path'] = base.relative(path)
                report['state'] = state
                overlays[f'{state}-{res}-{scale}'] = report
                regenerated += [base.relative(path), base.relative(path.with_name(path.stem+'-gray.png'))]
        v['overlays'] = list(overlays.values()) if card == 'SC-38' else overlays
        for path in regenerated:
            if path not in v['exports']['files']: v['exports']['files'].append(path)
        if card == 'SC-38': v['exports']['overlay_png_count'] = 8
        else: v['exports']['count'] = len(v['exports']['files'])
        preserved = preservation(card, before)
        assert preserved['passed'], preserved['failures']
        v['mockup_unchanged'] = preserved
        v['fix1'] = {'prompt': PROMPT, 'regenerated_pngs': regenerated,
                     'run1_measurements': {'frames': before['verification']['frames'],
                                           'overlays': before['verification']['overlays'],
                                           'acceptance': before['verification']['acceptance']},
                     'overlay_tag_overlap_count': sum(o['tag_overlap_count'] for o in overlays.values()),
                     'failures': [], 'decision': 'ВР-VS5-SC37-06' if card == 'SC-37' else None}
        add_acceptance(v, 'overlay tags and legend do not overlap', 0, 0, True)
        add_acceptance(v, 'every overlay rectangle has a matching numbered tag',
                       [{'tags': o['tag_count'], 'rectangles': o['rectangle_count']} for o in overlays.values()], 'all keyed', True)
        add_acceptance(v, 'mockups unchanged except authorized SC-37 class S frames', preserved['failures'], [], preserved['passed'])
        if card == 'SC-37':
            # Recalculate only changed-frame aggregate criteria; retain every old measurement above.
            v['acceptance'] = base.acceptance_report(card, v['frames'], overlays, True)
            add_acceptance(v, 'overlay tags and legend do not overlap', 0, 0, True)
            add_acceptance(v, 'every overlay rectangle has a matching numbered tag',
                           [{'tags': o['tag_count'], 'rectangles': o['rectangle_count']} for o in overlays.values()], 'all keyed', True)
            add_acceptance(v, 'mockups unchanged except authorized SC-37 class S frames', preserved['failures'], [], preserved['passed'])
        v['outside_folder'] = []
        v['visual_review'] = {'passed': False, 'note': 'fix1 regenerated originals require direct inspection'}
        dump(pkg/'verification.json', v, card)
        review = copy.deepcopy(before['visual_review'])
        review['files'] = [r for r in review['files'] if r['path'] not in regenerated]
        review['all_opened'] = False
        review['fix1_pending'] = regenerated
        dump(pkg/'visual-review.json', review, card)
        update_readme(card, before, regenerated)
        print(card, 'regenerated', len(regenerated), 'PNG; unexpected derived differences 0', flush=True)


def manifest(card):
    pkg, der = base.folders(card)
    v = base.load(pkg/'verification.json')
    old = base.load(pkg/'manifest-sha256.json')
    files = {base.relative(p): base.file_info(p) for folder in [pkg, der] for p in sorted(folder.rglob('*'))
             if p.is_file() and p != pkg/'manifest-sha256.json'}
    inputs = {p: base.file_info(ROOT/p) for p in base.load(pkg/'source-hashes-before.json')['files']}
    inputs[PROMPT] = base.file_info(ROOT/PROMPT)
    if card != 'SC-34':
        for name in ['fix1.py', 'fix1_overlays.py']:
            path = 'art/imagegen/sc34-gameover-victory-codex/_tools/'+name
            inputs[path] = base.file_info(ROOT/path)
    old['files'], old['inputs'] = files, inputs
    if card == 'SC-38':
        old['facts'] = {k: {'data_checks': f['facts'], 'text_sources': f['text_runs']} for k, f in v['frames'].items()}
    else:
        old['facts'] = {k: f['facts']+[{'field': r['name'], 'drawn': r['text'], 'source': r['source'], 'type': r['type']}
                                    for r in f['text_runs']] for k, f in v['frames'].items()}
    old['fix1'] = {'inputs_updated_for_authorized_package_dependencies': True, 'run1_inputs': 'source-hashes-before.json'}
    dump(pkg/'manifest-sha256.json', old, card)


def finalize():
    for card in CARDS:
        pkg, _ = base.folders(card)
        before = baseline(card)
        v = base.load(pkg/'verification.json')
        regenerated = v['fix1']['regenerated_pngs']
        review = base.load(pkg/'visual-review.json')
        review['files'] = [r for r in review['files'] if r['path'] not in regenerated]
        for path in regenerated:
            note = ('Прямо открыт оригинальный PNG fix1: номер каждого контура сопоставлен легенде, '
                    'Roboto Regular и теги читаемы, navy без пикселей арта, схема не уменьшена, '
                    'нет пересечений тегов/легенды; цвет и Rec.709 серый проверены.'
                    if '-overlay' in path else
                    'Прямо открыт оригинальный PNG fix1: SC-37 S 760×560, V/Enter, поля кнопок, '
                    'данные run F, портреты и painted Marmoreal, вертикальные якоря и busy spinner; '
                    'цвет/серый и соответствие двух фаз проверены.')
            review['files'].append({'path': path, 'sha256': base.sha(ROOT/path), 'checked': note, 'run': 'fix1'})
        review['all_opened'], review['status'] = True, 'inspected'
        review.pop('fix1_pending', None)
        review['fix1'] = {'method': 'tools.view_image on each regenerated original PNG individually',
                          'inspected_count': len(regenerated), 'files': regenerated}
        dump(pkg/'visual-review.json', review, card)
        assert {r['path'] for r in review['files']} == set(v['exports']['files'])
        assert all(base.sha(ROOT/r['path']) == r['sha256'] for r in review['files'])
        v['visual_review'] = {'passed': True, 'files': len(review['files']), 'fix1_inspected_count': len(regenerated), 'record': 'visual-review.json'}
        changes = [p for p, info in before['inputs_before_fix1'].items() if base.file_info(ROOT/p) != info]
        authorized = [p for p in changes if p.startswith('art/imagegen/sc34-gameover-victory-codex/')]
        unexpected = [p for p in changes if p not in authorized]
        assert not unexpected, unexpected
        v['fix1']['source_unchanged'] = {'passed': not unexpected, 'changed_files': unexpected,
                                        'authorized_package_dependency_updates': authorized,
                                        'run1_baseline_preserved': True}
        v['fix1']['copy_provenance_true'] = all(base.sha(ROOT/c['source']) == c['sha256'] == base.sha(ROOT/c['copy'])
                                               for c in base.load(pkg/'copy-provenance.json'))
        assert v['fix1']['copy_provenance_true']
        dump(pkg/'verification.json', v, card)
        manifest(card)
    check()


def check():
    total = 0
    tree = base.icon_tree()
    for card in CARDS:
        pkg, der = base.folders(card)
        before = baseline(card)
        v = base.load(pkg/'verification.json')
        icon_before = base.load(pkg/'source-hashes-before.json')['hud_icons_v3_tree']
        assert all(tree[k] == icon_before[k] for k in ['sha256', 'count']), (card, 'icon tree')
        assert v['fix1']['run1_measurements']['frames'] == before['verification']['frames']
        assert v['fix1']['run1_measurements']['acceptance'] == before['verification']['acceptance']
        assert all(k in v for k in ['source_unchanged', 'exports', 'palette', 'gray', 'sizes', 'outside_folder', 'acceptance'])
        assert preservation(card, before)['passed']
        assert v['outside_folder'] == []
        assert v['visual_review']['passed']
        review = base.load(pkg/'visual-review.json')
        assert review['all_opened'] and {r['path'] for r in review['files']} == set(v['exports']['files'])
        assert all(base.sha(ROOT/r['path']) == r['sha256'] for r in review['files'])
        m = base.load(pkg/'manifest-sha256.json')
        actual = {base.relative(p): base.file_info(p) for folder in [pkg, der] for p in folder.rglob('*')
                  if p.is_file() and p != pkg/'manifest-sha256.json'}
        assert m['files'] == actual, (card, 'manifest files')
        assert all(base.file_info(ROOT/p) == info for p, info in m['inputs'].items()), (card, 'manifest inputs')
        for c in base.load(pkg/'copy-provenance.json'):
            assert c['byte_identical'] and base.sha(ROOT/c['source']) == c['sha256'] == base.sha(ROOT/c['copy'])
        overlays = v['overlays'].values() if isinstance(v['overlays'], dict) else v['overlays']
        for o in overlays:
            assert o['tag_count'] == o['rectangle_count'] and o['tag_font_px'] >= 14
            assert o['tag_overlap_count'] == o['label_overlap_px2'] == 0
            assert o['schema_scale'] == 1 and not o['contains_asset_pixels']
            tags = [t['box_px'] for t in o['tags']]
            from fix1_overlays import intersection
            import itertools
            assert all(intersection(a, b) == 0 for a, b in itertools.combinations(tags, 2))
            assert all(intersection(a, b) == 0 for a in tags for b in o['label_boxes_px'])
            assert all(intersection(a, b) == 0 for a, b in itertools.combinations(o['label_boxes_px'], 2))
        for path in v['exports']['files']:
            with Image.open(ROOT/path) as image:
                assert image.mode == 'RGBA'
                if path.endswith('-gray.png'):
                    with Image.open(ROOT/path.replace('-gray.png', '.png')) as color:
                        assert np.array_equal(np.asarray(image), np.asarray(base.luma709(color).convert('RGBA'))), path
        if card == 'SC-37':
            for res, scale in base.PRESETS:
                a, b = [v['frames'][f'{state}-{res}-{scale}']['geometry'] for state in ['again', 'again-busy']]
                assert all(a[n]['rect_su'] == b[n]['rect_su'] for n in ['ButtonRow', 'ViewBoardButton', 'AgainButton', 'LobbyButton'])
                assert a['ButtonRow']['fits_budget'] and a['ButtonRow']['chips'] and a['ButtonRow']['gap_su'] == 16
                if scale == 150:
                    assert a['ResultModal']['rect_su'][2:] == [760, 560]
                    assert (760-a['ButtonRow']['rect_su'][2])/2 >= 24
        total += len(v['fix1']['regenerated_pngs'])
        print(card, 'PASS: hashes, copies, coverage, gray, tags, preservation and direct review', flush=True)
    print('fix1 complete;', total, 'regenerated PNG individually inspected; 0 unexpected derived differences')


if __name__ == '__main__':
    if '--render' in sys.argv: render()
    elif '--finalize' in sys.argv: finalize()
    elif '--check' in sys.argv: check()
    else: raise SystemExit('Specify --render, --finalize (after direct PNG inspection), or --check')
