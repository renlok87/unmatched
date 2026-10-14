"""Register an existing normalized design; never generate or encode an image."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import struct
import subprocess
import sys

PACKAGE = Path('art/imagegen/concept-bullseye-codex')
STATE = PACKAGE / 'metadata-repair-run.json'
DESIGN = PACKAGE / 'design/bullseye-front.png'
EXPECTED = 'bea7253991b97489a90cf0ff78b3facd7a49f6acdc02d7c2b4dba5367d9f42e1'
CHECKER = Path('tools/art/concept/check_concept_views.py')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(path):
    return {'path': path.as_posix(), 'sha256': digest(path), 'bytes': path.stat().st_size}


def byte_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(source.read_bytes())
    assert digest(source) == digest(destination)


def preserved(state):
    rows = []
    for before in state['pngs_before']:
        path = Path(before['path'])
        after = snapshot(path)
        row = dict(before, sha256_after=after['sha256'], bytes_after=after['bytes'],
                   unchanged=(before['sha256'] == after['sha256'] and before['bytes'] == after['bytes']))
        rows.append(row)
    assert all(row['unchanged'] for row in rows), 'An existing PNG changed'
    assert digest(DESIGN) == EXPECTED
    assert digest(PACKAGE / 'palette.json') == state['palette_sha256']
    return rows


def prepare():
    assert not STATE.exists(), 'Repair already prepared; do not register twice'
    assert digest(DESIGN) == EXPECTED, 'Authoritative design hash mismatch'
    records = read(PACKAGE / 'generation-records.json')
    assert isinstance(records, list) and records and len(records) + 1 <= 4
    selected = [row for row in records if row.get('selected') and row.get('view') == 'design-front']
    assert len(selected) == 1
    old = selected[0]
    prompt = old['prompt']
    number = max(row['attempt'] for row in records if row['view'] == 'design-front') + 1
    candidate = PACKAGE / f'concepts/bullseye-design-front-g{number}.png'
    assert not candidate.exists()
    registered_paths = {row['saved_path'] for row in records}
    concept_paths = {f.as_posix() for f in (PACKAGE / 'concepts').glob('*.png')}
    assert concept_paths <= registered_paths, 'Unrecorded historical candidate needs investigation'
    now = dt.datetime.now(dt.timezone.utc)
    run_id = 'metadata-only-' + now.strftime('%Y%m%dT%H%M%S%fZ')
    archive = PACKAGE / 'archive' / run_id
    archive.mkdir(parents=True, exist_ok=False)
    original_files = sorted(f for f in PACKAGE.rglob('*') if f.is_file()
                            and 'scripts' not in f.relative_to(PACKAGE).parts)
    inputs = [snapshot(f) for f in original_files]
    mutable = [f for f in original_files if f.suffix in ('.json', '.md') and f.name != 'palette.json']
    archives = []
    for source in mutable:
        target = archive / source.relative_to(PACKAGE)
        byte_copy(source, target)
        archives.append(dict(snapshot(source), archive=target.as_posix(), archive_sha256=digest(target)))
    missing = [name for name in ('prompts/concept-prompts.json', 'prompts.md',
                                'manifest-sha256.json', 'source-hashes-before.json')
               if not (PACKAGE / name).exists()]
    state = {'schema': 'unmatched.metadata-only-concept-repair/1', 'run_id': run_id,
             'date': now.isoformat(timespec='seconds'), 'stage': '1a', 'status': 'proposed',
             'image_gen_calls_in_this_run': 0, 'all_generation_calls_in_this_run': 0,
             'generations_allowed': 0, 'outside_folder': [], 'archive': archive.as_posix(),
             'metadata_archives': archives, 'inputs_before': inputs, 'initially_absent': missing,
             'pngs_before': [row for row in inputs if row['path'].endswith('.png')],
             'palette_sha256': digest(PACKAGE / 'palette.json'), 'old_records': json.loads(json.dumps(records)),
             'selected_candidate': candidate.as_posix(), 'selected_attempt': number,
             'selected_prompt_key': f'1a/design-front/g{number}', 'historical_prompt_key': old['prompt_key'],
             'source_prompt_sha256_utf8': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
             'checker_runs': [], 'checks_completed': False, 'blockers': []}
    before_path = PACKAGE / 'source-hashes-before.json'
    before = read(before_path) if before_path.exists() else {'schema': 'unmatched.source-hashes-before/1'}
    block = {'run_id': run_id, 'date': state['date'], 'mode': 'metadata-only registration',
             'image_gen_calls': 0, 'inputs': inputs, 'initially_absent': missing,
             'note': 'Хеши сняты до изменения метаданных. Все существовавшие PNG и palette.json неизменяемы; исходные изменяемые метаданные сохранены побайтно в архиве.'}
    if isinstance(before, list):
        before.append(block)
    else:
        before.setdefault('corrective_runs', []).append(block)
    write(before_path, before)
    write(STATE, state)
    byte_copy(DESIGN, candidate)
    header = DESIGN.read_bytes()[:24]
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR'
    width, height = struct.unpack('>II', header[16:24])
    for row in records:
        row['selected'] = False
    entry = {'id': f'ASSET-BULLSEYE-001-1a-design-front-g{number}',
             'card_id': 'ASSET-BULLSEYE-001', 'stage': '1a', 'view': 'design-front',
             'side_view': None, 'attempt': number,
             'tool': 'unstability.ai source (historical); Claude rebg.py historical postprocess; Python metadata-only registration',
             'mode': 'historical external postprocessing; metadata-only byte-copy registration; zero generation calls',
             'references': [], 'prompt_key': state['selected_prompt_key'], 'correction': None,
             'original_path': DESIGN.resolve().as_posix(), 'saved_path': candidate.as_posix(),
             'sha256': EXPECTED, 'width': width, 'height': height,
             'date': state['date'], 'selected': True, 'generation_calls_in_this_run': 0,
             'prompt_executed_in_this_run': False,
             'prompt_origin': {'record_id': old['id'], 'prompt_key': old['prompt_key'],
                               'historical': True, 'exact_copy': True},
             'historical_postprocessing': {'by': 'Claude', 'script': 'C:/tmp/concept-wave/rebg.py',
                 'description': read(PACKAGE / 'verification.json')['design_source']['post'],
                 'executed_in_this_run': False, 'reproduced_in_this_run': False,
                 'raw_path': (PACKAGE / 'design/bullseye-front-raw.png').as_posix(),
                 'raw_sha256': digest(PACKAGE / 'design/bullseye-front-raw.png'),
                 'note': 'Историческая обработка документирована прежним verification.json#design_source.post. Байтовая связь старого кандидата и raw не устанавливалась; их хеши различаются.'},
             'registration': {'source_path': DESIGN.as_posix(), 'source_sha256': EXPECTED,
                 'byte_identical': True, 'new_image_generated': False,
                 'note': 'Источник — уже существовавший нормализованный дизайн, не результат ImageGen этого запуска. references=[]: вызова генератора и его входных изображений в этом запуске нет.'},
             'checks': [(PACKAGE / f'checks/design-front-g{number}/checks-report.json').as_posix(),
                        (PACKAGE / 'design/checks-report.json').as_posix()]}
    records.append(entry)
    for original, current in zip(state['old_records'], records):
        assert {k: v for k, v in original.items() if k != 'selected'} == {k: v for k, v in current.items() if k != 'selected'}
    write(PACKAGE / 'generation-records.json', records)
    prompts_path = PACKAGE / 'prompts/concept-prompts.json'
    prompts = read(prompts_path) if prompts_path.exists() else {}
    if old['prompt_key'] in prompts:
        assert prompts[old['prompt_key']] == prompt
    else:
        prompts[old['prompt_key']] = prompt
    assert state['selected_prompt_key'] not in prompts
    prompts[state['selected_prompt_key']] = prompt
    write(prompts_path, prompts)
    preserved(state)
    print(f"Prepared {candidate.as_posix()}; records={len(records)}; generations=0")


def check():
    state = read(STATE)
    assert not state['checker_runs'], 'Checker history already exists'
    preserved(state)
    runs = [(row['saved_path'], f"design-front-g{row['attempt']}", row['attempt'], True)
            for row in state['old_records']]
    raw = PACKAGE / 'design/bullseye-front-raw.png'
    if raw.exists():
        runs.append((raw.as_posix(), 'historical-raw', 'historical-raw', True))
    runs.append((state['selected_candidate'], f"design-front-g{state['selected_attempt']}",
                 state['selected_attempt'], False))
    temporary = PACKAGE / 'checks' / ('.temporary-' + state['run_id'])
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')

    def invoke(set_path, report_dir, generation, source, historical, final=False):
        command = [sys.executable, '-B', CHECKER.as_posix(), '--set', set_path.as_posix(),
                   '--key', 'bullseye', '--views', 'front', '--role', 'hero', '--min-top-pct', '4',
                   '--palette', (PACKAGE / 'palette.json').as_posix()]
        if not final:
            command.extend(['--out', report_dir.as_posix()])
        result = subprocess.run(command, env=env, capture_output=True, text=True, encoding='utf-8')
        report_dir.mkdir(parents=True, exist_ok=True)
        log = report_dir / ('metadata-repair-checker-output.txt' if final else 'checker-output.txt')
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
        row = {'view': 'design-front', 'generation': generation, 'exit_code': result.returncode,
               'report': (report_dir / 'checks-report.json').as_posix(), 'source_path': source,
               'source_sha256': digest(Path(source)), 'historical': historical, 'final': final,
               'run_id': state['run_id'], 'command': command[2:], 'output_log': log.as_posix()}
        if Path(row['report']).exists():
            report = read(Path(row['report']))
            row['failed_checks'] = [r['id'] for r in report['checks'] if r['result'] == 'FAIL']
            row['verdict'] = report['verdict']
            assert report['inputs'][0]['sha256'] == row['source_sha256']
        if not final:
            row['temporary_set'] = set_path.as_posix()
            row['byte_copy_sha256'] = digest(set_path / 'bullseye-front.png')
            assert row['byte_copy_sha256'] == row['source_sha256']
        state['checker_runs'].append(row)
        if result.returncode not in (0, 1):
            state['blockers'].append({'kind': 'checker_tool_error', 'exit_code': result.returncode,
                                      'output': result.stdout + result.stderr, 'source': source})
        write(STATE, state)
        print(result.stdout + result.stderr, end='')
        print(f'Checker exit={result.returncode}, source={source}', flush=True)
        return result.returncode

    for source, folder, generation, historical in runs:
        target = PACKAGE / 'checks' / folder
        assert not target.exists(), f'Refusing to overwrite historical checker output: {target}'
        set_path = temporary / folder
        byte_copy(Path(source), set_path / 'bullseye-front.png')
        try:
            code = invoke(set_path, target, generation, source, historical)
        finally:
            copy = set_path / 'bullseye-front.png'
            assert digest(copy) == digest(Path(source))
            copy.unlink()
            set_path.rmdir()
            state['checker_runs'][-1]['temporary_set_removed'] = True
            write(STATE, state)
        if code not in (0, 1):
            temporary.rmdir()
            return
    temporary.rmdir()
    final_code = invoke(PACKAGE / 'design', PACKAGE / 'design', state['selected_attempt'],
                        DESIGN.as_posix(), False, final=True)
    state['final_checker_exit_code'] = final_code
    state['checks_completed'] = final_code in (0, 1)
    state['png_preservation'] = preserved(state)
    write(STATE, state)


def finalize():
    state = read(STATE)
    archive = Path(state['archive'])
    records = read(PACKAGE / 'generation-records.json')
    selected = next(row for row in records if row['selected'])
    pngs = preserved(state)
    prompt = read(PACKAGE / 'prompts/concept-prompts.json')[state['selected_prompt_key']]
    assert prompt == state['old_records'][0]['prompt']
    for row in state['metadata_archives']:
        assert digest(Path(row['archive'])) == row['sha256']
    verification = read(archive / 'verification.json')
    prior_checks = []
    for old in verification.get('checks', []):
        row = dict(old)
        original_report = Path(row['report'])
        archived_report = archive / original_report.relative_to(PACKAGE)
        row.update(historical=True, final=False, previous_report_path=row['report'],
                   report=archived_report.as_posix(), note='Проверка предыдущего запуска; исходный отчёт сохранён в архиве.')
        prior_checks.append(row)
    report = read(PACKAGE / 'design/checks-report.json') if state['checks_completed'] else None
    checks = {row['id']: row['result'] for row in report['checks']} if report else {}
    framing_ids = ('view.border_uniform', 'view.bg_neutral', 'view.bg_dark', 'view.top_margin',
                   'view.bottom_margin', 'view.side_margin')
    framing_passed = all(checks.get(cid) == 'PASS' for cid in framing_ids)
    items = [
        ('single_subject_no_text', 'Один субъект и пьедестал; без коллажа, второго вида, текста, букв, логотипа и водяного знака', False,
         'Историческая заметка Claude подтверждает одного субъекта, пьедестал и отсутствие текста/логотипа. Полный пункт заново визуально не проверен: изображения разрешены только для хеширования и checker. passed=false означает неподтверждённый пункт, не обнаруженный дефект.'),
        ('strict_front_orthographic', 'Строгий фронтальный ортографический вид; камера горизонтальна; верх пьедестала не виден', False,
         'Историческая заметка говорит front view, но не доказывает ортографию, уровень камеры и отсутствие верхней поверхности. Автопроверка этого не измеряет; визуальная переоценка не выполнена.'),
        ('whole_subject_flat_background', 'Фигура и пьедестал целиком; без обрезки; ровный тёмно-серый фон', framing_passed,
         'Основание: текущий checker проверяет поля и рамку фона; историческая заметка Claude подтверждает full body и пьедестал, design_source.post документирует нормализацию фона. Нового визуального заключения нет.'),
        ('right_hand_and_arm_gaps', 'Ножи в собственной ПРАВОЙ руке (слева для зрителя); обе руки отделены от тела; не T/A-поза', False,
         'Сторона хвата и промежутки у рук не проверяются этим checker. Исторический промпт не является доказательством результата; пункт не подтверждён.'),
        ('identity_anchors', 'Видны все признаки: ножи в ПРАВОЙ руке, чёрно-синий костюм и белая мишень', False,
         'Признаки заданы историческим промптом, но не подтверждены новым осмотром. Доли цветов в отчёте не доказывают сторону хвата и символ.'),
        ('palette_and_plain_base', 'Основные цвета и стальной акцент; без командного цвета, цветного кольца и полосы на базе', False,
         'Палитра присутствует в измерениях checker; отсутствие командного цвета, кольца и полосы требует визуальной проверки, которая в этом запуске не разрешена.')]
    checklist = [{'view': 'design-front', 'id': cid, 'item': item, 'passed': passed,
                  'note': note, 'visual_checked_in_this_run': False,
                  'assessment': 'supported_by_automatic_and_historical_evidence' if passed else 'not_confirmed'}
                 for cid, item, passed, note in items]
    failed_items = [row['id'] for row in checklist if not row['passed']]
    metadata_changes = []
    archived = {row['path']: row for row in state['metadata_archives']}
    for before in state['inputs_before']:
        path = Path(before['path'])
        after = snapshot(path)
        row = dict(before, sha256_after=after['sha256'], unchanged=before['sha256'] == after['sha256'])
        if row['path'] in archived:
            row.pop('sha256_after')
            row.update(mutable_metadata=True, archive=archived[row['path']]['archive'],
                       unchanged=False, original_bytes_preserved_in_archive=True,
                       final_sha256_location='manifest-sha256.json#files',
                       note='Метаданные намеренно обновлены. Исходный хеш проверен по архиву; окончательный хеш текущего файла находится в manifest, чтобы не включать самохеш verification.json.')
        else:
            row['mutable_metadata'] = False
            assert row['unchanged']
        metadata_changes.append(row)
    limitations = [
        {'id': 'visual_checklist_not_reassessed', 'note': 'Изображения использовались только для хешей и checker. Неподтверждённые визуальные пункты не объявлены успешными; исторические сведения явно отделены от этого запуска.'},
        {'id': 'aspect_ratio', 'actual': f"{selected['width']}x{selected['height']} (4:5)", 'requested': '3:4',
         'note': 'Авторитетный исходный PNG сохранён без изменения размера. Checker не проверяет требуемый абсолютный аспект одного вида.'},
        {'id': 'historical_prompt_differs_from_core', 'note': 'Скопирован точный внешний промпт из исторической записи unstability.ai, а не CORE ImageGen. Промпт сейчас не выполнялся; image references не использовались.'},
        {'id': 'historical_raw_chain_not_reproduced', 'note': 'Хеши u1, raw и нормализованного дизайна различаются. Обработка Claude rebg.py документирована исторически, но её воспроизведение и пиксельная связь u1/raw не проверялись.'}]
    verification.update(status='proposed', status_ru='предложено', source_unchanged=True,
        source_unchanged_scope='Все существовавшие PNG и palette.json; исходные изменяемые метаданные сохранены побайтно в архиве.',
        outside_folder=[], checks=prior_checks + state['checker_runs'], checklist=checklist,
        generations={'design-front': 1}, generations_in_this_run={'design-front': 0},
        registrations_in_this_run={'design-front': 1}, image_gen_calls_in_this_run=0,
        all_generation_calls_in_this_run=0, generations_allowed=0, record_count=len(records),
        final_checker_exit_code=state.get('final_checker_exit_code'),
        limit_reached=[{'view': 'design-front', 'failed_items': failed_items,
                       'reason': 'Лимит генераций этого запуска равен 0. Пункты не подтверждены, а не признаны визуальными дефектами.'}] if failed_items else [],
        png_preservation=pngs, input_hashes=metadata_changes, metadata_archives=state['metadata_archives'],
        limitations=limitations, blockers=state['blockers'], art_acceptance_claimed=False,
        selected_registration={'attempt': selected['attempt'], 'candidate': selected['saved_path'],
            'sha256': EXPECTED, 'original_path': selected['original_path'], 'byte_identical_to_current_design': True,
            'prompt_key': selected['prompt_key'], 'historical_prompt_executed_now': False,
            'prompt_sha256_utf8': state['source_prompt_sha256_utf8']},
        repair_run={'run_id': state['run_id'], 'date': state['date'], 'mode': selected['mode'],
                    'initially_absent': state['initially_absent'], 'new_image_generated': False})
    verification['design_source']['metadata_only_registration'] = {
        'candidate': selected['saved_path'], 'sha256': EXPECTED, 'run_id': state['run_id'],
        'historical_postprocess_executed_now': False, 'generation_calls': 0}
    write(PACKAGE / 'verification.json', verification)
    prompt_sections = [f"# Исторические промпты ASSET-BULLSEYE-001 — этап 1a\n\nДата исправления метаданных: {state['date']}.\n\nВ этом запуске генераций: **0**. Ни один промпт не выполнялся.\n"]
    for row in records:
        exact = read(PACKAGE / 'prompts/concept-prompts.json')[row['prompt_key']]
        registration = row['attempt'] == selected['attempt']
        purpose = 'Регистрация существующего нормализованного дизайна; точная копия исторического внешнего промпта.' if registration else 'Историческая внешняя генерация; эта запись в текущем запуске не выполнялась.'
        prompt_sections.append(f"\n## {row['prompt_key']}\n\nФайл: `{row['saved_path']}`.\n\nДата записи: {row['date']}.\n\nИнструмент: {row['tool']}.\n\n{purpose}\n\nreferenced_image_paths (в порядке вызова): `[]` — исторический text-to-image без image-reference; в текущем запуске вызова нет.\n\nТочный исторический промпт:\n\n```text\n{exact}\n```\n")
    prompt_sections.append('\n## Проверка и ограничения\n\nВ пакете только design-front; сравнения между видами нет. Новый кандидат совпадает побайтно с существовавшим нормализованным дизайном. Исторический u1 и raw не заменялись. Нормализация Claude rebg.py — историческое действие, не действие этого запуска. Полный CORE ImageGen историческим внешним промптом не подменяется. Аспект исходного PNG 4:5 вместо 3:4. Визуальные пункты заново не оценивались: permitted inputs использованы только для хешей и checker. Статус — предложено; художественная приёмка не заявляется.\n')
    (PACKAGE / 'prompts.md').write_text(''.join(prompt_sections), encoding='utf-8')
    history_lines = []
    for run in state['checker_runs']:
        label = 'финальная проверка текущего дизайна' if run['final'] else 'исторический raw (не отдельная генерация)' if run['generation'] == 'historical-raw' else f"кандидат g{run['generation']}"
        history_lines.append(f"- {label}: код `{run['exit_code']}`, отчёт `{run['report']}`; FAIL: {', '.join(run.get('failed_checks', [])) or 'нет'}.\n")
    readme = f"""# Концепт-пакет ASSET-BULLSEYE-001

Этап 1a, статус: **предложено** (`proposed`). Художественная приёмка не выполнялась и не заявляется.

## Исправление происхождения без генераций

Дата: {state['date']}. Все вызовы генераторов в этом запуске: **0**, в том числе ImageGen: **0**. Генерации и ретраи запрещены. Браузер, git, Unreal, Tripo и SYNTX не запускались.

Авторитетный источник этой волны — уже существовавший `design/bullseye-front.png`, SHA256 `{EXPECTED}`. Исторический `verification.json#design_source.post` документирует нормализацию фона Claude через `C:/tmp/concept-wave/rebg.py`. Этот скрипт сейчас не открывался и не выполнялся. Исторические сведения о внешней генерации unstability.ai и прежних отказах сервисов сохранены в архиве; они не относятся к вызовам этого запуска.

Выбран новый неизменяемый кандидат **g{selected['attempt']}**: `{selected['saved_path']}`. Он зарегистрирован простым побайтным копированием текущего нормализованного дизайна. `original_path` указывает на этот существовавший дизайн, а не на вымышленный выход ImageGen. Нормализованный PNG выбран по прямому указанию пользователя, а не по новой визуальной оценке. Записей в реестре: **{len(records)}** — одна историческая внешняя генерация и одна регистрация без генерации.

Исторический кандидат `concepts/bullseye-design-front-u1.png` и `design/bullseye-front-raw.png` имеют другие хеши и сохранены без изменений. Побайтная или пиксельная цепочка между u1 и raw не восстанавливалась; происхождение нормализации основано на архивном документе, а регистрация — на проверяемом SHA256 текущего дизайна. Все прежние поля записей сохранены; изменены только флаги `selected`.

## Проверки

{''.join(history_lines)}
Для каждого кандидата использован временный набор внутри пакета с побайтной копией под именем `bullseye-front.png`. Временные копии после проверки удалены; их совпадение с источниками записано в verification.json. Авторитетный дизайн не подменялся. Последний вызов checker проверил именно `design/bullseye-front.png` без `--out` и обновил `design/checks-report.json`. Исторические FAIL сохранены как история, без перегенераций.

## Ограничения и малые решения

- Полный визуальный чек-лист сейчас не переоценён: изображения разрешены только для хеширования и checker. Неподтверждённые пункты имеют `passed=false` с явной пометкой «не подтверждено», а не утверждением об обнаруженном дефекте; они перечислены в `limit_reached` при бюджете 0.
- Аспект существующего PNG: 1280×1600, 4:5 вместо требуемого 3:4. PNG не менялся. Автопроверка одного вида это отклонение не оценивает.
- Точный внешний промпт взят из прежней записи unstability.ai и скопирован в новый ключ `{selected['prompt_key']}`. Это исторический промпт, не CORE ImageGen; он не выполнялся сейчас. Image-reference исторически отсутствовал; другие пакеты не открывались.
- Raw проверен дополнительно как исторический промежуточный файл, без добавления отдельной записи генерации. Для u1 папка checker названа g1 по его неизменённому `attempt=1`.
- Изменяемые исходные метаданные сохранены побайтно в `{state['archive']}` до обновления. Отсутствовавшие prompts.md, prompts/concept-prompts.json, source-hashes-before.json и manifest-sha256.json созданы заново. Палитра неизменна.

Все три существовавших PNG сохранили SHA256 и размеры файлов; новый g{selected['attempt']} совпадает с текущим дизайном. `outside_folder=[]`. Manifest записывается последним и содержит хеши и размеры каждого файла пакета, кроме самого себя.
"""
    (PACKAGE / 'README.md').write_text(readme, encoding='utf-8')
    state.update(png_preservation=pngs, record_count=len(records), metadata_finalized=True,
                 art_acceptance_claimed=False, source_prompt_exact_copy=True)
    write(STATE, state)
    preserved(state)
    manifest = {'schema': 'unmatched.package-manifest-sha256/1',
                'files': [snapshot(f) for f in sorted(PACKAGE.rglob('*'))
                          if f.is_file() and f != PACKAGE / 'manifest-sha256.json']}
    write(PACKAGE / 'manifest-sha256.json', manifest)
    print(f"Finalized: records={len(records)}, final_checker={state.get('final_checker_exit_code')}, generations=0")


def verify():
    state = read(STATE)
    verification = read(PACKAGE / 'verification.json')
    preserved(state)
    records = read(PACKAGE / 'generation-records.json')
    assert len(records) == len(state['old_records']) + 1 <= 4
    for original, current in zip(state['old_records'], records):
        assert {k: v for k, v in original.items() if k != 'selected'} == {k: v for k, v in current.items() if k != 'selected'}
    selected = [row for row in records if row['selected']]
    assert len(selected) == 1 and selected[0]['saved_path'] == state['selected_candidate']
    assert digest(Path(state['selected_candidate'])) == digest(DESIGN) == EXPECTED
    assert selected[0]['original_path'] == DESIGN.resolve().as_posix()
    prompts = read(PACKAGE / 'prompts/concept-prompts.json')
    assert prompts[state['selected_prompt_key']] == prompts[state['historical_prompt_key']] == state['old_records'][0]['prompt']
    assert verification['status'] == 'proposed' and not verification['art_acceptance_claimed']
    assert verification['image_gen_calls_in_this_run'] == verification['all_generation_calls_in_this_run'] == 0
    assert verification['outside_folder'] == []
    assert state['checker_runs'][-1]['final'] and '--out' not in state['checker_runs'][-1]['command']
    for row in state['metadata_archives']:
        assert digest(Path(row['archive'])) == row['sha256']
    manifest_path = PACKAGE / 'manifest-sha256.json'
    manifest = read(manifest_path)
    paths = {f.as_posix() for f in PACKAGE.rglob('*') if f.is_file() and f != manifest_path}
    assert paths == {row['path'] for row in manifest['files']}
    for row in manifest['files']:
        assert snapshot(Path(row['path'])) == row
        if Path(row['path']).suffix in ('.json', '.md', '.txt', '.py'):
            data = Path(row['path']).read_bytes()
            assert not data.startswith(b'\xef\xbb\xbf'), row['path']
            data.decode('utf-8')
    report = read(PACKAGE / 'design/checks-report.json')
    assert report['inputs'][0]['path'] == DESIGN.as_posix()
    assert report['inputs'][0]['sha256'] == EXPECTED
    assert (0 if report['summary']['FAIL'] == 0 else 1) == verification['final_checker_exit_code']
    print(json.dumps({'selected_candidate': selected[0]['saved_path'], 'image_generations': 0,
        'existing_pngs_preserved': len(state['pngs_before']), 'design_sha256': EXPECTED,
        'final_checker_exit_code': verification['final_checker_exit_code'], 'record_count': len(records),
        'manifest_verified': True, 'manifest_files': len(manifest['files']), 'blockers': state['blockers'],
        'visual_checklist_not_reassessed': True, 'status': 'proposed'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    {'prepare': prepare, 'check': check, 'finalize': finalize, 'verify': verify}[sys.argv[1]]()
