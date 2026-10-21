# Бриф 7b-регистратора: волна A мини-пачки 2026-10-20

Исполнитель — один субагент-регистратор оркестратора (`claude-code:8522fd18-3811-4ad8-8aab-07d443cf58fe`). Он один
пишет общие файлы и C++ (ДС-3b).

## Полномочия (дословно)

- Пользователь 2026-10-21: «Хорошо, использую Opus High вместо Z-код для приемщика. Вот, и продолжай без меня, делай
  все сам. Касательно сетов тоже и 3D модели героев.»
- Пользователь через главную сессию: «Просто продолжай работу».
- Главная сессия: регистрация общих файлов — один шаг регистратора после закрытия всех слотов (ДС-3b); одна упаковка
  на волну.
- Трат нет. Пароли не вводить.

## Объём этого прохода

Герои: **BruceLee** (герой, `HERO_SLUG` bruce-lee) и **DrWatson** (помощник Sherlock Holmes, `OWNER_HERO_SLUG`
sherlock-holmes). Шерлок ещё на этапе 3; его строки добавит следующий проход регистратора. **Упаковку не делать.**

Источники строк:
- `art/pipeline-candidates/ASSET-BRUCE-LEE-001/evidence/stage7a-20261021/REGISTRATION-7.md`
- `art/pipeline-candidates/ASSET-DR-WATSON-001/evidence/stage7a-20261021/REGISTRATION-7.md`
- блоки `STAGE7A` обеих заявок.

## Шаги

Шаги — по `.agents/skills/3d-model-pipeline/SKILL.md` §6 «Этап 7» (7a п.4 и 7b п.1–3) и
`references/new-character-registration.md` §5, §9, §10.

1. **Общие файлы 7a п.4** (правки без сборки C++):
   - `cue-table.json` — CUE-011/013, затем `python tools/s08/cue_contract/cue_contract.py validate-table`;
   - `DirectoriesToAlwaysCook` в `unreal/Unmatched/Config/DefaultGame.ini` — включая HP2 витрины Брюса;
   - `S08FighterNames.json`;
   - bench-фикстуры обеих досок:
     - запуск `env_bench_fixtures.cts` внутри контейнера `unmatched-backend`;
     - Брюс: `--variant BruceLee --hero-name "<FIGHTER_NAME>" --hero-slug bruce-lee`;
     - Ватсон: помощник без готового героя — `--hero-name "<FighterName Шерлока>" --hero-slug sherlock-holmes
       --sidekick-name "<FIGHTER_NAME Ватсона>"`;
     - затем `--check`.
   - `anim.csv` уже содержит карточки клипов AN-156…159 и AN-164…167. Строки фигур (AN-51, AN-64) обновить по
     таблице §10.
2. **7b п.1:**
   - базовая линия `validate_registry.py`;
   - `de010.py apply --only BruceLee,DrWatson` и `de011.py apply --only BruceLee,DrWatson`, сначала `--dry-run`;
   - `--frames C:/tmp/wave-a-7b/de010` и `C:/tmp/wave-a-7b/de011`;
   - запуск под `python tools/art/material_library/ue_lock.py --step "…" -- …`;
   - строки `HEROES` / `CAPTURE_LOOKS` из `REGISTRATION-7.md`.
3. **7b п.2 C++:**
   - `Specs()` в `S08HeroesV2.cpp`;
   - `S08HeroesV2Tests.cpp`;
   - `S08AudioBank.cpp`: `CharacterKey` / `HitType`;
   - `UmShowcase::HiPolyPath` для Брюса в `S08/UI/UmHeroShowcase.cpp`; у помощника витрины нет;
   - сборка:
     `node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=<abs>/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=4`,
     в выводе должно быть `Result: Succeeded`. Build.bat отдаёт exit 0 и при ошибке — читать вывод;
   - тесты `node tools/s08/run-ue-tests.cjs "Unmatched.S08" C:/tmp/wave-a-7b/ue-tests.log`: `EXIT CODE: 0`, нет
     `Result={Fail}`.
4. **7b п.3 (без упаковки):**
   - запись `asset-registry.json` «технически импортировано» через `tools/art/registry_writer.py entry --phase 7b-frames`;
   - `python tools/art/registration_check.py --heroes BruceLee,DrWatson` — код 0. Если проверка требует кадров
     пакета, записать, чего не хватает.

## Блокировки и процессы

- Перед сборкой проверить, что нет `UnrealEditor.exe` с `-LiveCoding` (devexec-клиент главной сессии) и нет открытых
  редакторов проекта.
- Если сборку держит Live Coding главной сессии — остановиться. В отчёте написать, что нужна остановка клиента:
  главная сессия обещала его остановить.
- Не открывать GUI-редактор.
- Свои процессы закрыть по PID.
- Blender не нужен.

## Правила

- Код инструментов не править.
- Без git: коммитит оркестратор. Список изменённых файлов — в отчёт.
- Не запускать команд, которым нужен запрос разрешения.
- Писать только в репозиторий и `C:/tmp/wave-a-7b`.
- Перед каждой правкой C++ прочитать соседние строки героев, Beowulf и Achilles, как образец.

## Отчёт

- шаги и коды;
- список изменённых файлов;
- результаты сборки и тестов;
- что не сделано и почему.
