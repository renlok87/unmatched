"""Metadata-only 1a repair. Run from the repository root; never edit an existing PNG."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import struct
import subprocess
import sys

PACKAGE = Path('art/imagegen/concept-doctor-strange-codex')
ARCHIVE = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()
EXPECTED = '6a14c00f2c022333e0bcca9a658373edef0451b0e48bab5e54dbdb57c64aff20'
DESIGN = PACKAGE / 'design/doctor-strange-front.png'
CHECKER = 'tools/art/concept/check_concept_views.py'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    assert path.resolve().is_relative_to(PACKAGE.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def unchanged_pngs():
    before = read(ARCHIVE / 'run-before.json')['pngs']
    result = []
    for item in before:
        path = Path(item['path'])
        after = digest(path)
        assert after == item['sha256'], f'Existing PNG changed: {path}'
        assert path.stat().st_size == item['bytes']
        result.append({**item, 'after_sha256': after, 'unchanged': True})
    assert digest(DESIGN) == EXPECTED
    return result


def register():
    unchanged_pngs()
    old = read(ARCHIVE / 'generation-records.json')
    current = read(PACKAGE / 'generation-records.json')
    assert current == old, 'Registration already applied or records changed concurrently'
    attempt = read(ARCHIVE / 'run-before.json')['next_attempt']
    assert len(old) + 1 <= 4
    source = next(record for record in old if record['selected'])
    prompt = source['prompt']
    candidate = PACKAGE / f'concepts/doctor-strange-design-front-g{attempt}.png'
    candidate.parent.mkdir(parents=True, exist_ok=True)
    with candidate.open('xb') as output:
        output.write(DESIGN.read_bytes())
    assert digest(candidate) == EXPECTED
    png_header = DESIGN.read_bytes()[:24]
    assert png_header[:8] == b'\x89PNG\r\n\x1a\n'
    width, height = struct.unpack('>II', png_header[16:24])
    historic = read(ARCHIVE / 'verification.json')['design_source']
    record = {
        'id': f'ASSET-DOCTOR-STRANGE-001-1a-design-front-g{attempt}',
        'card_id': 'ASSET-DOCTOR-STRANGE-001', 'stage': '1a',
        'view': 'design-front', 'side_view': None, 'attempt': attempt,
        'tool': source['tool'] + '; Claude rebg.py historical postprocess; Codex metadata-only registration (0 generation calls)',
        'mode': 'metadata-only registration of existing normalized design; unstability.ai historical source; Claude rebg.py historical background normalization; neither generation nor postprocess executed in this run',
        'references': [], 'prompt_key': f'1a/design-front/g{attempt}',
        'prompt': prompt, 'correction': None,
        'original_path': DESIGN.resolve().as_posix(),
        'saved_path': candidate.as_posix(), 'sha256': EXPECTED,
        'width': width, 'height': height, 'date': now(), 'selected': True,
        'operation': 'metadata-only-registration',
        'generated_in_this_run': False, 'postprocessed_in_this_run': False,
        'generation_calls_in_run': 0, 'image_gen_calls_in_run': 0,
        'prompt_historical': True, 'prompt_executed_in_this_run': False,
        'historical_source_record': source['id'],
        'historical_prompt_key': source['prompt_key'],
        'registration_source': {'path': DESIGN.as_posix(), 'sha256': EXPECTED},
        'historical_postprocess': {
            'by': 'Claude', 'tool': 'C:/tmp/concept-wave/rebg.py',
            'description': historic['post'],
            'evidence': relative(ARCHIVE / 'verification.json') + '#design_source.post',
            'raw_path': (PACKAGE / 'design/doctor-strange-front-raw.png').as_posix(),
            'raw_sha256': digest(PACKAGE / 'design/doctor-strange-front-raw.png'),
            'executed_in_this_run': False,
        },
        'checks': (PACKAGE / f'checks/design-front-g{attempt}/checks-report.json').as_posix(),
    }
    for previous in current:
        previous['selected'] = False
    current.append(record)
    write(PACKAGE / 'generation-records.json', current)
    prompt_path = PACKAGE / 'prompts/concept-prompts.json'
    prompts = read(prompt_path) if prompt_path.exists() else {}
    for entry in current:
        key = entry['prompt_key']
        if key in prompts:
            assert prompts[key] == entry['prompt']
        prompts[key] = entry['prompt']
    write(prompt_path, prompts)
    print(json.dumps({'registered': candidate.as_posix(), 'attempt': attempt,
                      'record_count': len(current), 'image_gen_calls': 0}, indent=2))


def check():
    unchanged_pngs()
    records = read(PACKAGE / 'generation-records.json')
    assert len(records) == 3
    results = []
    temp_root = ARCHIVE / 'temporary-check-sets'
    assert not temp_root.exists()
    assert temp_root.resolve().is_relative_to(PACKAGE.resolve())
    temp_root.mkdir()
    try:
        for record in records:
            attempt = record['attempt']
            source = Path(record['saved_path'])
            temp_set = temp_root / f'design-front-g{attempt}'
            temp_set.mkdir()
            target = temp_set / 'doctor-strange-front.png'
            with target.open('xb') as output:
                output.write(source.read_bytes())
            assert digest(target) == record['sha256'] == digest(source)
            report_dir = PACKAGE / f'checks/design-front-g{attempt}'
            assert not report_dir.exists(), 'Do not overwrite prior checker evidence'
            command = [sys.executable, CHECKER, '--set', relative(temp_set),
                       '--key', 'doctor-strange', '--views', 'front', '--role', 'hero',
                       '--min-top-pct', '4', '--palette', (PACKAGE / 'palette.json').as_posix(),
                       '--out', report_dir.as_posix()]
            process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            results.append({
                'view': 'design-front', 'generation': attempt,
                'record_id': record['id'], 'candidate': source.as_posix(),
                'input_sha256': digest(source), 'temporary_set': relative(temp_set),
                'exit_code': process.returncode,
                'report': (report_dir / 'checks-report.json').as_posix(),
                'final': False, 'historical_candidate': not record['selected'],
                'command': [Path(sys.executable).as_posix(), *command[1:]],
                'stdout': process.stdout, 'stderr': process.stderr, 'date': now(),
            })
            write(ARCHIVE / 'checker-runs.json', results)
            print(f"g{attempt}: exit {process.returncode}\n{process.stdout}", flush=True)
            if process.returncode not in (0, 1):
                print(process.stderr, flush=True)
                return process.returncode
    finally:
        assert temp_root.resolve().is_relative_to(PACKAGE.resolve())
        assert temp_root.resolve().parent == ARCHIVE
        shutil.rmtree(temp_root)
    # This is the last invocation of check_concept_views.py in this corrective run.
    command = [sys.executable, CHECKER, '--set', (PACKAGE / 'design').as_posix(),
               '--key', 'doctor-strange', '--views', 'front', '--role', 'hero',
               '--min-top-pct', '4', '--palette', (PACKAGE / 'palette.json').as_posix()]
    process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    selected = next(record for record in records if record['selected'])
    results.append({
        'view': 'design-front', 'generation': selected['attempt'],
        'record_id': selected['id'], 'candidate': selected['saved_path'],
        'input': DESIGN.as_posix(), 'input_sha256': digest(DESIGN),
        'exit_code': process.returncode,
        'report': (PACKAGE / 'design/checks-report.json').as_posix(), 'final': True,
        'command': [Path(sys.executable).as_posix(), *command[1:]],
        'stdout': process.stdout, 'stderr': process.stderr, 'date': now(),
    })
    write(ARCHIVE / 'checker-runs.json', results)
    unchanged_pngs()
    print(f"final: exit {process.returncode}\n{process.stdout}", flush=True)
    if process.stderr:
        print(process.stderr, flush=True)
    return process.returncode


def finalize():
    preserved_pngs = unchanged_pngs()
    before = read(ARCHIVE / 'run-before.json')
    old_verification = read(ARCHIVE / 'verification.json')
    records = read(PACKAGE / 'generation-records.json')
    selected = next(record for record in records if record['selected'])
    runs = read(ARCHIVE / 'checker-runs.json')
    final_run = runs[-1]
    final = read(Path(final_run['report'])) if Path(final_run['report']).exists() else None
    checker_error = next((run for run in runs if run['exit_code'] not in (0, 1)), None)
    prior_checks = []
    for entry in old_verification.get('checks', []):
        saved = dict(entry)
        saved['report'] = relative(ARCHIVE / 'design/checks-report.json')
        saved['historical'] = True
        saved['current_run'] = False
        prior_checks.append(saved)
    checklist_items = [
        ('single_subject', 'Один персонаж, одна подставка, без коллажа, второго вида, текста, букв, логотипа или водяного знака.'),
        ('strict_front_orthographic', 'Строгий фронтальный ортографический вид, камера на уровне, без перспективы; верх подставки не виден.'),
        ('full_frame_flat_background', 'Персонаж и подставка целиком в кадре, без обрезки; ровный тёмно-серый фон.'),
        ('no_held_object_arm_gaps', 'Без оружия или предмета в руках; обе руки отделены от корпуса; не T-поза и не A-поза.'),
        ('identity_anchors', 'Видны красный плащ с высоким воротником, амулет Eye of Agamotto, жёлтые перчатки, седые виски и эспаньолка.'),
        ('palette_no_team_base_band', 'Есть основные цвета и акцент палитры; нет командного цвета, цветного кольца или полосы на подставке.'),
    ]
    checklist = []
    automated_ids = ['view.border_uniform', 'view.bg_neutral', 'view.bg_dark',
                     'view.top_margin', 'view.frame_top', 'view.bottom_margin', 'view.side_margin']
    framing_ok = bool(final) and all(any(c['id'] == name and c['result'] != 'FAIL'
                                       for c in final['checks']) for name in automated_ids)
    for key, text in checklist_items:
        is_framing = key == 'full_frame_flat_background'
        note = ('Автоматические измерения финального checker: рамка, фон и поля; художественная приёмка не выполнялась.'
                if is_framing else
                'Не переоценивалось визуально: этот запуск допускает изображения только для хешей и checker. passed=null означает не проверено, а не PASS или FAIL.')
        if key == 'single_subject':
            note += ' Историческая заметка Claude: ' + old_verification['design_source']['checklist_note']
        if key == 'palette_no_team_base_band' and final:
            note += ' Доли свотчей измерены в palette.swatches финального отчёта; они не проверяют командные цвета или кольцо.'
        checklist.append({'view': 'design-front', 'item': key, 'requirement': text,
                          'passed': framing_ok if is_framing else None,
                          'assessment': 'automated_only' if is_framing else 'not_reassessed', 'note': note})
    unverified = [entry['item'] for entry in checklist if entry['passed'] is None]
    failed = [entry['item'] for entry in checklist if entry['passed'] is False]
    limits = [{'view': 'design-front', 'failed_items': failed}] if failed else []
    historic_failures = []
    for run in runs:
        report_path = Path(run['report'])
        if not run.get('final') and report_path.exists():
            report = read(report_path)
            historic_failures.append({'generation': run['generation'], 'candidate': run['candidate'],
                                     'exit_code': run['exit_code'],
                                     'failed_checks': [c['id'] for c in report['checks'] if c['result'] == 'FAIL'],
                                     'warnings': [c['id'] for c in report['checks'] if c['result'] == 'WARN']})
    inputs_after = []
    archive_map = {item['source']: item['archive'] for item in before['archived']}
    for item in before['files']:
        path = Path(item['path'])
        after = digest(path)
        preserved = Path(archive_map[item['path']]) if item['path'] in archive_map else path
        inputs_after.append({**item, 'current_sha256': after,
                             'unchanged_in_place': after == item['sha256'],
                             'preserved_input_path': preserved.as_posix(),
                             'preserved_input_sha256': digest(preserved),
                             'preserved_input_unchanged': digest(preserved) == item['sha256']})
    assert all(item['preserved_input_unchanged'] for item in inputs_after)
    assert digest(PACKAGE / 'palette.json') == 'ffd592eafcf164086ff805c726e2b8311cc6053b02d187fd4dcc23344bbe6251'
    verification = dict(old_verification)
    verification.update({
        'status': 'proposed', 'status_ru': 'предложено', 'date': now(),
        'source_unchanged': True,
        'source_unchanged_scope': 'Все исходные PNG и palette.json неизменны на месте; исходные изменяемые метаданные сохранены побайтно в архиве до исправления.',
        'outside_folder': [], 'checks': prior_checks + runs, 'checklist': checklist,
        'generations': {'design-front': 0},
        'generation_records_per_view': {'design-front': len(records)},
        'generation_count_note': 'В этом запуске 0 генераций; 3 записи включают исторический исходник, историческую очистку и регистрацию нормализованного дизайна. Число записей не является числом генераций.',
        'image_gen_calls_in_this_run': 0, 'generation_calls_in_this_run': 0,
        'generations_allowed': 0, 'limit_reached': limits,
        'selected_candidate': selected['saved_path'], 'selected_generation_record': selected['id'],
        'selected_candidate_matches_current_design': digest(Path(selected['saved_path'])) == digest(DESIGN),
        'authoritative_design': {'path': DESIGN.as_posix(), 'sha256': EXPECTED, 'unchanged': True},
        'png_hash_preservation': preserved_pngs,
        'source_hashes_after': inputs_after, 'metadata_archive': relative(ARCHIVE),
        'historical_checker_results': historic_failures,
        'visual_checklist_reassessed': False, 'unverified_checklist_items': unverified,
        'art_acceptance_performed': False,
        'limitations': [
            'Визуальные пункты checklist не переоценивались: изображения разрешены только для хешей и автоматической проверки.',
            'Референс medusa-quality-reference.png находится в другом пакете: не открывался и не хешировался в этом запуске. Исторический сервис text-to-image не использовал его; references=[] сохранён.',
            'Исторические original_path содержат неполный путь загрузки сервиса; старые записи не исправлялись, оригинальный путь новой регистрации — существующий нормализованный дизайн.',
            '1c и художественная приёмка вне области этого запуска; статус предложено.',
        ],
        'blocker': (checker_error['stderr'] or checker_error['stdout'] or 'Checker tool error') if checker_error else None,
    })
    verification['design_source'] = dict(old_verification['design_source'])
    verification['design_source']['registration'] = {
        'run': 'metadata-only', 'source_path': DESIGN.as_posix(),
        'source_sha256': EXPECTED, 'candidate': selected['saved_path'],
        'historical_postprocess_executed_now': False, 'image_gen_calls': 0,
        'historical_prompt_executed_now': False,
    }
    write(PACKAGE / 'verification.json', verification)
    sources = read(PACKAGE / 'source-hashes-before.json')
    sources['corrective_runs'][-1]['after'] = {
        'pngs': preserved_pngs, 'immutable_inputs_unchanged': True,
        'mutable_metadata_originals_preserved_in_archive': True,
        'image_gen_calls': 0, 'outside_folder': [],
    }
    sources['corrective_runs'][-1]['excluded_external_reference'] = {
        'path': 'art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png',
        'declared_sha256': 'e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9',
        'hash_computed_in_this_run': False,
        'reason': 'Не использован в историческом text-to-image и не открыт: запрет открывать другие пакеты.',
    }
    write(PACKAGE / 'source-hashes-before.json', sources)
    prompt_lines = [
        '# Промпты ASSET-DOCTOR-STRANGE-001 — этап 1a', '',
        'Исправление только метаданных. Все приведённые промпты исторические; в этом запуске они не выполнялись. image_gen: 0 вызовов.', '',
    ]
    for record in records:
        prompt_lines += [
            '## ' + record['prompt_key'], '',
            '- Файл: `' + record['saved_path'] + '`.',
            '- Дата записи: ' + record['date'] + '.',
            '- Инструмент: ' + record['tool'] + '.',
            '- Режим: ' + record['mode'] + '.',
            '- referenced_image_paths (порядок исторического вызова): ' + json.dumps([ref['path'] for ref in record['references']], ensure_ascii=False) + '.',
            '- Точный внешний промпт скопирован из исходной записи; не выполнялся сейчас.', '',
            '```text', record['prompt'], '```', '',
        ]
    prompt_lines += [
        '## Проверка и ограничения', '',
        'Проверен только design-front; межвидовое соответствие и этап 1c не оценивались. PNG не изменялись. Новый g3 — побайтная копия текущего дизайна, уже исторически нормализованного Claude через rebg.py. Промпт g3 дословно совпадает с внешним промптом u1c и описывает историческое происхождение, а не новый вызов генератора.', '',
        'Старые кандидаты проверены на временных побайтных копиях внутри пакета; их FAIL остаются историей. Финальный checker запускался последним на design/doctor-strange-front.png без --out. Визуальные пункты checklist не переоценивались. Статус: предложено.', '',
    ]
    (PACKAGE / 'prompts.md').write_text('\n'.join(prompt_lines), encoding='utf-8')
    history_lines = []
    for result in historic_failures:
        failures = ', '.join(result['failed_checks']) or 'нет'
        warnings = ', '.join(result['warnings']) or 'нет'
        history_lines.append(f"- g{result['generation']}: код {result['exit_code']}; FAIL: {failures}; WARN: {warnings}.")
    readme = [
        '# Концепт-пакет ASSET-DOCTOR-STRANGE-001', '',
        'Этап 1a. Статус: **предложено** (`proposed`). Этот запуск исправляет только метаданные; генераций изображений и вызовов image_gen: **0**. Художественная приёмка не выполнялась.', '',
        '## Выбранный кандидат и происхождение', '',
        f"Выбран `{selected['saved_path']}` (запись g{selected['attempt']}, попытка {selected['attempt']}). Это новая неизменяемая побайтная копия уже существовавшего `design/doctor-strange-front.png`, SHA256 `{EXPECTED}`. Авторитетный дизайн не заменялся.", '',
        'Исторический исходник получен из unstability.ai (UltraReal Fine-Tune v4 / Flux.1 D). Запись u1c описывает прежнюю очистку угловых логотипов Claude/PIL; её PNG совпадает с design/doctor-strange-front-raw.png. По прежней verification.json#design_source.post Claude затем исторически нормализовал фон через C:/tmp/concept-wave/rebg.py. Именно этот уже нормализованный дизайн зарегистрирован как g3.', '',
        'Прежняя выбранная запись u1c указывала на ненормализованный кандидат. Исправлено соответствие выбранной записи текущему дизайну: старые записи сохранены целиком, изменены только selected. Новая запись честно отмечает историческую внешнюю обработку и регистрацию без генерации; original_path — абсолютный путь существующего дизайна, а не выдуманный выход ImageGen.', '',
        'Точный внешний промпт взят из исходной записи u1c и скопирован в новый ключ 1a/design-front/g3. Промпты u1, u1c и g3 опубликованы в prompts/concept-prompts.json и prompts.md; ни один не выполнялся сейчас. В историческом text-to-image референсов не было, references=[] сохранён. Другие пакеты не открывались.', '',
        '## Проверки и сохранность', '',
        *history_lines, '',
        f"Финальная проверка текущего дизайна: код {final_run['exit_code']}; отчёт design/checks-report.json. Последний запуск checker выполнен без --out. Отчёты кандидатов находятся в checks/design-front-g1, g2 и g3; входами служили временные побайтные копии doctor-strange-front.png внутри пакета, после проверок они удалены.", '',
        'Исторические FAIL не исправлялись генерацией или обработкой. Все четыре исходных PNG, включая текущий дизайн, raw и оба прежних кандидата, сохранили SHA256 и размер. palette.json не изменялся. Исходные метаданные побайтно архивированы до обновления в `' + relative(ARCHIVE) + '`. Отсутствовавшие файлы промптов, source-hashes-before.json и manifest-sha256.json созданы из существующей истории.', '',
        '## Ограничения', '',
        'Автоматическая проверка не доказывает строгую ортографию, отсутствие текста, предметов или командных колец, позу и идентичность. Визуальные пункты не переоценивались, поскольку изображения этого запуска разрешены только для хешей/checker: passed=null явно означает не проверено. Историческая визуальная заметка Claude сохранена в verification.json. Подтверждённых визуальных FAIL в этом запуске нет; limit_reached=[] не означает художественную приёмку.', '',
        'Записей design-front: 3, что ниже лимита 4; это не три генерации. Исторические неполные original_path оставлены без выдуманного уточнения. Изменения вне пакета: outside_folder=[]. Генерации, постобработка, браузер, git, Unreal, Tripo и SYNTX в этом запуске не выполнялись.', '',
        'Блокер: ' + (verification['blocker'] or 'нет; художественная оценка остаётся отдельным этапом.') + '', '',
    ]
    (PACKAGE / 'README.md').write_text('\n'.join(readme), encoding='utf-8')
    unchanged_pngs()
    # Last package write: include every file, including archived metadata and this script.
    manifest_path = PACKAGE / 'manifest-sha256.json'
    files = [{'path': file.as_posix(), 'sha256': digest(file), 'bytes': file.stat().st_size}
             for file in sorted(PACKAGE.rglob('*')) if file.is_file() and file != manifest_path]
    write(manifest_path, {'schema': 'unmatched.concept-manifest/1', 'generated_at': now(),
                          'package': PACKAGE.as_posix(), 'files': files})
    print(json.dumps({'final_checker_code': final_run['exit_code'], 'record_count': len(records),
                      'manifest_files': len(files), 'pngs_preserved': len(preserved_pngs),
                      'image_gen_calls': 0, 'status': 'proposed', 'blocker': verification['blocker']}, indent=2))


def verify():
    unchanged_pngs()
    manifest = read(PACKAGE / 'manifest-sha256.json')
    actual = {file.as_posix(): file for file in PACKAGE.rglob('*')
              if file.is_file() and file != PACKAGE / 'manifest-sha256.json'}
    declared = {entry['path']: entry for entry in manifest['files']}
    assert set(actual) == set(declared), 'Manifest missing or extra files'
    for path, file in actual.items():
        assert digest(file) == declared[path]['sha256'], f'Manifest hash mismatch: {path}'
        assert file.stat().st_size == declared[path]['bytes']
        if file.suffix in ('.json', '.md'):
            raw = file.read_bytes()
            assert not raw.startswith(b'\xef\xbb\xbf'), f'BOM: {path}'
            text = raw.decode('utf-8')
            assert '\ufffd' not in text and '????' not in text, f'Encoding error: {path}'
    old = read(ARCHIVE / 'generation-records.json')
    records = read(PACKAGE / 'generation-records.json')
    assert len(records) == len(old) + 1 <= 4
    for archived, current in zip(old, records):
        assert {k: v for k, v in archived.items() if k != 'selected'} == {k: v for k, v in current.items() if k != 'selected'}
        assert current['selected'] is False
    selected = [record for record in records if record['selected']]
    assert len(selected) == 1
    selected = selected[0]
    assert selected['attempt'] == max(record['attempt'] for record in old) + 1
    assert selected['original_path'] == DESIGN.resolve().as_posix()
    assert Path(selected['saved_path']).read_bytes() == DESIGN.read_bytes()
    prompts = read(PACKAGE / 'prompts/concept-prompts.json')
    for record in records:
        assert prompts[record['prompt_key']] == record['prompt']
        assert record['prompt'] in (PACKAGE / 'prompts.md').read_text(encoding='utf-8')
        report = read(PACKAGE / f"checks/design-front-g{record['attempt']}/checks-report.json")
        assert report['inputs'][0]['sha256'] == digest(Path(record['saved_path'])) == record['sha256']
        assert report['raw_files_modified'] is False and report['sheet'] is None
    verification = read(PACKAGE / 'verification.json')
    assert verification['status'] == 'proposed' and verification['outside_folder'] == []
    assert verification['image_gen_calls_in_this_run'] == 0
    assert verification['generation_calls_in_this_run'] == 0
    assert verification['generations'] == {'design-front': 0}
    assert verification['art_acceptance_performed'] is False
    runs = read(ARCHIVE / 'checker-runs.json')
    assert len(runs) == len(records) + 1
    assert runs[-1]['final'] and '--out' not in runs[-1]['command']
    final = read(PACKAGE / 'design/checks-report.json')
    assert final['inputs'][0]['sha256'] == EXPECTED
    candidate_report = read(Path(selected['checks']))
    for key in ('checks', 'summary', 'verdict', 'frame', 'measurements', 'palette'):
        assert candidate_report[key] == final[key], f'Selected candidate/final discrepancy: {key}'
    assert not (ARCHIVE / 'temporary-check-sets').exists()
    baseline_pngs = {entry['path'] for entry in read(ARCHIVE / 'run-before.json')['pngs']}
    actual_pngs = {file.as_posix() for file in PACKAGE.rglob('*.png')}
    assert actual_pngs == baseline_pngs | {selected['saved_path']}
    print(json.dumps({'manifest_verified': True, 'manifest_files': len(actual),
                      'prior_pngs_unchanged': len(baseline_pngs), 'selected_candidate': selected['saved_path'],
                      'authoritative_sha256': EXPECTED, 'record_count': len(records),
                      'final_checker_code': runs[-1]['exit_code'], 'image_gen_calls': 0,
                      'utf8_no_bom': True, 'status': 'proposed', 'blocker': verification['blocker']}, indent=2))


if __name__ == '__main__':
    assert ROOT / PACKAGE == PACKAGE.resolve(), 'Run from repository root'
    action = sys.argv[1]
    if action == 'register':
        register()
    elif action == 'check':
        sys.exit(check())
    elif action == 'finalize':
        finalize()
    elif action == 'verify':
        verify()
    else:
        raise SystemExit('Expected register/check/finalize/verify')
