# Этап 7b пилота 3d-model-pipeline: Angel, Ancient Leshen, Achilles — один заход

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Пилот (2026-10-13, дословно): «Сгенерировать модели можно все Но сначала чтобы полностью обкатать скилл и
итерационно его улучшить, можно это сделать на небольшой выборке». Unreal, сборка, тесты и одна упаковка разрешены.
Трат кредитов нет.

## Прочитать целиком
- `.agents/skills/3d-model-pipeline/SKILL.md` §5 (п.6, п.7), §6 «Этап 7» (7b), §8;
- `references/ue-import-package.md` §5–§7, §9; `references/new-character-registration.md` §5 (5.1–5.6);
- `references/animation-vfx-sfx.md` §7 (Contact notify), §9 (SFX), §8 (VFX);
- `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` §0.1, §0.2, §4.7, §8;
- `AGENTS.md`: Unreal GPU load, Iteration speed («One package per change», «No cost optimizations within budget»),
  Board scenes and heroes (только реальные доски, «Look before you report»).

## Состояние (всё закоммичено в fix/admin-panel)
| Герой | Ключ | Модель | Клипы | 7a | Данные для Specs() |
|---|---|---|---|---|---|
| Angel | `Angel` | r1 8.8 | 4/4 pass (r2 LungeAttack/DeathSettle) | `ASSET-ANGEL-001/20261014-h2ld-ue-import-r3`, клипы `20261014-h2anim-r2` | блок `STAGE7A` в `asset-card.yaml` (FigureTop 55.0, BoundsTop 55.909, контакт LungeAttack) |
| Ancient Leshen | `AncientLeshen` | r3 пара 8.1 | 4/4 pass (r2) | `ASSET-ANCIENT-LESHEN-001/20261014-h2ld-ue-import-r5`, клипы `20261014-h2anim-r3` | `STAGE7A`: BudgetUU 55, FigureTopUU 55.003, BoundsTopUU 73.56, Idle 2.3333, контакт f8, MAGIC |
| Achilles | `Achilles` | r3 пара 8.1 | после переимпорта r3 (см. его последний README) | `ASSET-ACHILLES-001/20261014-h2ld-ue-import-r4` (или новее) | `STAGE7A`: FigureTop 55.0, BoundsTop 54.9931, Idle 2.5, контакт f7, BLADE |

Регистрации 7a (CUE-011/013, DirectoriesToAlwaysCook, S08FighterNames, bench-варианты обеих досок) уже есть.
Находки пилота — `docs/art-pipeline/evidence/skill-pilot-2026-10-13/NOTES.md` (особенно F91 дрейф um_masters,
F121 скрытый редактор, F135 сайдкики, F143/F150 кольцо на двухъярусной подставке Ахиллеса — известная проблема).

## Порядок (SKILL.md 7b)
1. Предусловие: ни одного `UnrealEditor.exe` этого движка с Live Coding и GUI-редактора на этом checkout
   (`netstat` 8123, список процессов с командной строкой). Редактор пользователя открыт — гейт §5 п.7: стоп и пакет
   пользователю (текст ue-import-package §1 п.4), сам не закрывать.
2. de010 и de011 для трёх героев: строки регистрации §5.1 (`HEROES`/`CAPTURE_LOOKS`), `de010.py apply --frames
   C:/tmp/<ASSET_ID>-stage7/de010`, `de011.py apply --frames C:/tmp/<ASSET_ID>-stage7/de011` под `ue_lock.py`.
3. C++ §5.2: `Specs()` в `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp` (три строки), тесты
   `S08HeroesV2Tests.cpp` (счётчики, имена, WantMs, WantSeconds), `S08AudioBank.cpp` (CharacterKey/HitType:
   ANGEL/BLADE, ANCIENTLESHEN/MAGIC, ACHILLES/BLADE). Сборка `node tools/s08/build-editor.cjs UnmatchedEditor Win64
   Development -Project=<abs>/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=4` →
   `Result: Succeeded`; затем `node tools/s08/run-ue-tests.cjs "Unmatched.S08" <abs log>` → `EXIT CODE: 0`, нет
   `Result={Fail}`.
4. Одна упаковка `tools/s08/package-client.ps1` (новый `Config/**.json` → touch `Unmatched.Build.cs`, сборка игрового
   target `-MaxParallelActions=4`, затем `-SkipBuild`; ue-import-package §6.1).
5. Кадры `-Bench` каждого героя на обеих реальных досках:
   `python tools/art/render/live_tune.py bench --map marmoreal --fixture S08BenchMarmoreal-<Key>.json --views K1+K2x1.6+K2x2.5 --out <dir> --packaged --extra=-BenchFocusFighter=<Key>`
   и то же `--map sarpedon` с `S08BenchSarpedon-<Key>.json`. Трасса: нет `BENCH FAILED fixture load`; `ARTLOOK … heroes=v2`;
   `ARTPREVIEW heroesV2 fighter=<id> mesh=…/SK_<Key>_H2LD … clips=4/4`; нет `missing=… fallback=legacy`,
   `death … mi=missing`, `death dissolve=missing`, `anim … missing=1`. `render_fingerprint.py check` → код 0 на каждый
   кадр. **Открыть каждый PNG самому** (Read): реальная доска, верный задник (Marmoreal — нарисованный задник;
   Sarpedon — lit3d путь 1), все фигуры v2, новый герой виден и в цветах концепта. Лист K1/K2 в цвете и в сером.
6. Лист клипов AN-18: `clip_review_sheet.py run --packaged --heroes Angel,AncientLeshen,Achilles --fixture
   marmoreal=…,sarpedon=…` и `sheet`; открыть.
7. Один замер стоимости `render_bench.py` на варианте Marmoreal одного героя (ue-import-package §6.5) — записать
   число и идти дальше (без оптимизаций в пределах бюджета).
8. Реестры: `docs/art-pipeline/asset-registry.json` статус «технически импортировано» + `validate_registry.py`
   (ERROR своих ASSET_ID — нет); строки `docs/game-design/visual/03-asset-registry.csv` с `rollback_flag`;
   `docs/art-pipeline/DIRECTORY-MAP.md` при новых каталогах; README evidence этапа 7 у каждого героя.

## Границы
- Писать: перечисленные C++/Config/реестры/evidence, `unreal/Unmatched/Content/PipelineCandidates/{Angel,
  AncientLeshen,Achilles}/**` (через инструменты), `C:/tmp/<ASSET_ID>-stage7/**`. Чужие ассеты и другие герои — нет.
- Инструменты не менять; нужна правка — отчёт с точным местом.
- git — не делать (коммитит оркестратор), но перечислить новые `.uasset` для `git add -f`.
- Свои процессы (UnrealEditor-Cmd, клиенты -Bench, UBT) — проверять и останавливать по PID. Клиенты -Bench — с капом
  FPS по AGENTS.md. Не держать два клиента одновременно.
- Сбой сборки/тестов, падение клиента, `BENCH FAILED` — стоп §5 п.6 с точным логом; не обходить.

## Отчёт (последнее сообщение, ≤ 45 строк)
Результат каждого шага с путями отчётов/логов; сборка и тесты (числа); пакет (stamp commit); кадры (пути, что видно
глазами, отпечатки); лист AN-18; замер стоимости; реестры; список новых `.uasset`; «SKILL FINDINGS».
