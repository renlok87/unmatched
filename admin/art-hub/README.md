# Арт-хаб (admin/art-hub)

Страница админки `/art-hub` — живое отражение файлов арт-пайплайна: модели, UE-слои,
look-dev, риг, скелетные клипы, видео-референсы, конвейер «видео → скелет», звуки и
кредиты по каждому персонажу (Medusa, King Arthur, Merlin, Harpy ×3) и по
пропсам/окружению, плюс обзорные разделы: «Состояние пайплайна», «План и задачи»,
«Look-dev и концепты», «Библиотека материалов», «Решения».
Только чтение: хаб ничего не пишет в данные пайплайна и не повышает статусы.

## Разделы (меню «Обзор»)

| Раздел (`?item=`) | Источник | Что показывает |
| --- | --- | --- |
| Состояние пайплайна (`health`) | реестр, прогоны, clip-manifest, журнал кредитов | счётчики; дата среза **из файла** (`snapshotDate`), время изменения реестра и дата самого свежего слоя (метка «срез старше слоёв», если слои новее); матрица «герой × UE-слой» |
| План и задачи (`plan`) | `docs/art-pipeline/plan-status.json` (`unmatched-plan-status/v1`, пишет трек plan) | волны, задачи с фильтрами по треку/статусу, арт-статус, доказательства (раскрываются в таблицу файлов), следующий шаг/блокер. Пока файла нет — заглушка. Проверки: арт-статус вне словаря, «художественно принято» без акта `docs/game-design/evidence/(ART\|GD)-…/*.md`, отсутствующие файлы доказательств. Пути вне репо (`C:/tmp/…`) — только текст |
| Look-dev и концепты (`lookdev`) | `art/imagegen/hero-quality-v1/<герой>/`, `docs/art-pipeline/<герой>-lookdev*.md`, `art/pipeline-candidates/<ASSET>/<run>/review/<итерация>/*-lookdev-sheet-*`, `…/preview/{ld_sheet_*,compare-ld-*,ld_concept_zones_*}`, листы `docs/art-pipeline/evidence/<…герой…>/*sheet*` | концепт (front/side/back + prompts.md), отчёты look-dev (заголовок, строка «Дата/Статус», разделы), листы «концепт \| UE» по прогонам и итерациям, свежие первыми |
| Библиотека материалов (`materials`) | `docs/art-pipeline/material-library/{*.md,um-material-presets-v1.json,sources.json,evidence/}`, `art/material-library/v1/{tiles,preview/tiles-sheet.png}` | классы и расширения (образец цвета из `typicalLinear`, metallic/roughness/shading), CC0-наборы с лицензиями (не-CC0 → предупреждение), процедурные классы, тайлы, кадры доказательств |
| Решения (`decisions`) | `docs/game-design/decisions/*.md` | заголовок, дата из имени файла, разделы `##`, абзац «Происхождение» |

На странице персонажа добавлены вкладки **«UE-слои»** и **«Look-dev и концепт»**. Статус в
навигации и в шапке — статус **самого свежего слоя** записи (дата из имени слоя/путей: run id
`20260929-…` или ISO-дата; при равенстве — более поздний в `layers[]`); статус самой записи
реестра показан рядом («запись: …») и не меняется.

UE-слои: папка героя `/Game/PipelineCandidates/<Folder>/` берётся из путей реестра (иначе из
`ue.target_path` clip-manifest, иначе из имени). Для H2 / H2LD / H3LD / Rig / H2Anim и других
папок героя показываются: наличие папки в `unreal/Unmatched/Content` и число `.uasset`
(только `stat`/`readdir`, файлы не отдаются), слои реестра, где упомянут путь (статус как есть),
статусы `ue.status` клипов clip-manifest, прогоны и документы-упоминания (md в
`docs/art-pipeline/**`, журналы решений, корневые json/md прогонов, `reports/*.json`,
`build-profiles/*.json`). Статус слою, которого нет в реестре/clip-manifest, не присваивается.

## Как открыть

```bash
cd admin
npm run dev            # http://localhost:5480/art-hub  (логин в бэкенд не нужен)
```

Страница вне `ProtectedRoute`: она не ходит в GraphQL и не использует токены, данные
отдаёт dev-плагин Vite. Лейаут в `publicMode` не запрашивает identity. В production-сборке
плагина нет — страница показывает заглушку.

Снимок без сервера:

```bash
npm run art-hub:snapshot                    # → docs/art-pipeline/art-hub-snapshot.json
npm run art-hub:snapshot -- --summary       # только сводка в консоль
npm run art-hub:snapshot -- --out <файл>
```

## Устройство

| Файл | Что делает |
| --- | --- |
| `aggregate.ts` | Агрегатор (Node, без БД): собирает `ArtHubData` из файлов репо. Кэш по mtime/size: JSON разбирается заново только при изменении файла, результат целиком переиспользуется, пока отпечаток отслеживаемых файлов не изменился (в отпечаток входит и дерево `unreal/Unmatched/Content/PipelineCandidates/*/*` — mtime каталогов двух уровней) |
| `overview.ts` | Обзорные разделы: план, look-dev и концепты, библиотека материалов, решения, UE-слои героя, свежий слой. Упоминания UE-путей ищутся одним проходом; результат по каждому файлу кэшируется по mtime (`FileCache.derive`) |
| `types.ts` | Модель данных, общая для агрегатора и страницы (без Node-импортов) |
| `fs-utils.ts` | Обход каталогов (без symlink), кэши JSON/текста/sha256, CSV, разбор markdown (акты, таблицы) |
| `path-guard.ts` | Белый список путей, защита от traversal, MIME, разбор `Range` |
| `vite-plugin.ts` | Dev-плагин (`apply: 'serve'`): `/__art-hub/data`, `/__art-hub/file`, `/__art-hub/texture` |
| `cli.ts` | CLI снимка (`npm run art-hub:snapshot`) |
| `__tests__/` | vitest: агрегатор на фикстуре (создаётся во временном каталоге) и на реальном репо; path-guard и эндпоинты через настоящий HTTP-сервер |
| `../src/pages/art-hub/` | Страница (antd): навигация, вкладки, 3D-просмотр (three.js, лениво), видео, галереи |

### Эндпоинты (только dev-сервер)

- `GET /__art-hub/data` — свежая агрегация (`Cache-Control: no-store`).
- `GET|HEAD /__art-hub/file?path=<путь от корня репо>[&download=1]` — файл из белого списка;
  `Range` (206/416) для перемотки видео, `ETag`/304, `nosniff`, CSP `sandbox`; HTML отдаётся как текст.
- `GET /__art-hub/texture?model=<путь модели>&name=<имя текстуры>` — текстура рядом с FBX
  (тот же каталог, `<model>.fbm/`, `textures/`, `../textures/`); если нет — серая заглушка 1×1
  с заголовком `X-Art-Hub-Missing: 1`.

### Белый список `/__art-hub/file`

`art/`, `docs/art-pipeline/`, `docs/game-design/evidence/`,
`docs/game-design/decisions/*.md` (только markdown — прочие файлы там 403),
`blender/<ASSET>/{preview,export,textures,variants,tripo-source}/`.
Концепты (`art/imagegen/…`), библиотека материалов и `plan-status.json` уже внутри `art/` и
`docs/art-pipeline/` — отдельного расширения не требуют. Прочие файлы `docs/game-design/`
(13-sprint-plan.md, 14-sprint-backlog.csv, 06/05…) не отдаются: на странице — только путь.
`tripo-source` добавлен к списку из задания: там лежат исходные Tripo GLB Medusa, их нужно
смотреть в 3D. Отказ: пустой путь, NUL, абсолютные пути (POSIX, `C:`, UNC), любой сегмент
`..`, скрытые сегменты (`.git`, `.env`), `:` (ADS), пути вне списка (403) и
symlink/junction, чей реальный путь выходит из списка или из репо (403).
Каталог `unreal/` не отдаётся.

## Источники данных

| Источник | Что берётся |
| --- | --- |
| `docs/art-pipeline/asset-registry.json` | словари статусов/стадий, записи (персонажи = `hero`/`sidekick` без родителя, потомки — оружие/аксессуары; всё остальное — «Пропсы и окружение»), слои, решения, next step/blocker, акты, пути с `sha256` |
| `docs/art-pipeline/animation-refs/*.json`, `art/animation-refs/<ASSET>/manifest.json` | манифесты видео-референсов: статус, пригодность, оценка, бюджет. Записи персонажа собираются из трёх мест: верхний уровень (`assetId` + плоские `clips[]` = take1), `assets[]` (по `assetId`: `clips[].takes[]`, `selectedTake`, `budget`) и `retakes[]` (по CUE: `takes[]`, `selectedTake`). Пригодность клипа = оценка выбранного дубля (`selectedTake` / `takes[].selected`), у каждого дубля — своя; `budgetAll` — итог по манифесту |
| `art/animation-refs/<ASSET>/<CUE>/[takeN/]` | mp4, контакт-листы, `keyframes/`, `prompt.txt`, `analysis.json` (только `summary`) |
| `docs/art-pipeline/animation-library/clip-manifest.json` (+ `.schema.json`) | слоты клипов, статусы (русские подписи из описания схемы), источник, валидация, UE |
| `docs/art-pipeline/animation-library/validation/*.json` | проверки `validate_clip.py`, `summary.json` |
| `docs/art-pipeline/animation-library/VIDEO-TO-MOTION.md` | §5 рекомендация, §6 таблица зависимостей, строка про Harpy |
| `docs/art-pipeline/rig/rig-contract.json` | скелет, кости, сокеты, расширения, оси, карты ретаргета |
| `docs/art-pipeline/evidence/*/credits-ledger.json` (самый свежий) | траты Tripo (Studio-кредиты) и SYNTX (токены), без суммирования единиц |
| `art/pipeline-candidates/<ASSET>/<run>/` | `manifest.json` / `pipeline/manifest.json` / `run.json` / `reports/tripo-run.json`, `export/`, `source/`, `preview/` (включая `preview/deform/*-deform.json` + `*-sheet.png`), `reports/`, `textures/` |
| `docs/art-pipeline/*report*.{md,json}` | отчёты; к ассету — по ссылке из реестра или по имени файла |
| `docs/game-design/evidence/ART-*` | акты (строка `**Решение…**`), свежие кадры — если id бэклога однозначно принадлежит ассету |
| `blender/<ASSET>/{preview,export,textures,variants,tripo-source}` | превью, FBX/GLB, текстуры |
| `docs/game-design/07-animation-vfx-audio.csv` | запланированные звуковые CUE (по CUE слотов клипа и по упоминанию персонажа) |
| `docs/art-pipeline/plan-status.json` | раздел «План и задачи» (см. выше) |
| `docs/game-design/decisions/*.md` | раздел «Решения» (отслеживаются в отпечатке кэша) |
| `unreal/Unmatched/Content/PipelineCandidates/<Folder>/<Layer>/` | только наличие папки и число `.uasset` для вкладки «UE-слои» |
| `art/`, `public/`, `src/`, `scraped-data/`, `unreal/Unmatched/Content`, `docs/art-pipeline` | поиск аудиофайлов персонажа (wav/mp3/ogg/flac/m4a/aac/opus; SoundWave-uasset в папках audio/sound/sfx) |

Правила отнесения файлов к странице: каталог `blender/<ID>`, `art/pipeline-candidates/<ID>`,
`art/animation-refs/<ID>` персонажа → его страница; прогоны пропсов — по ссылкам реестра
внутрь каталога прогона, затем по суффиксу id (`.BARREL` → `…-barrel`). Новый персонаж, у
которого есть `art/animation-refs/<ID>/` или слоты в clip-manifest, но нет записи реестра,
появляется как страница «нет в реестре». Прогоны на диске, которых нет в реестре, выводятся
заметкой в «Сводке».

Статусы копируются как есть. «Художественно принято» без `acceptanceEvidence` помечается
ошибкой; статус вне словаря показывается пунктиром. Незаконченный (дописываемый) JSON
становится предупреждением, а не падением.

## Как добавить новый тип данных

1. Опишите поле в `types.ts` (например, `AssetPage.vfx?: VfxSection`).
2. В `aggregate.ts` добавьте константу пути в `SOURCES`, прочитайте файл через
   `readJson(ctx, rel)` / `ctx.cache.readText(...)` (кэш по mtime уже есть), сделайте
   `buildVfx(ctx, b)` и вызовите его в цикле по страницам `build()`. Ссылки на файлы
   делайте через `makeRef(ctx, path, { role })` — он сам проверит наличие, размер, sha256 и
   белый список. Если данные лежат вне отслеживаемых корней (`walkWatched`), добавьте корень
   туда, иначе кэш не заметит изменений.
3. Если файлы должны открываться в браузере — расширьте `ALLOWED_PREFIXES` /
   `ALLOWED_BLENDER_SUBDIRS` в `path-guard.ts` (и тест в `__tests__/path-guard.test.ts`).
4. Нарисуйте секцию в `src/pages/art-hub/sections/` и добавьте вкладку в `AssetView`
   (`ArtHubPage.tsx`). Общие компоненты: `FileTable`, `Gallery`, `StatusTag`, `ClipStatusTag`,
   `FileActions` (3D/текст/открыть/скачать).
5. Тест на фикстуре: дополните `__tests__/fixture-repo.ts` и `aggregate.test.ts`
   (обзорные разделы — `addOverviewFixtures()` и `overview.test.ts`).

## Проверки

```bash
npm test                     # vitest (art-hub + существующие тесты src)
npx vitest run art-hub       # только тесты арт-хаба (агрегатор, обзор, path-guard, эндпоинты)
npm run typecheck:art-hub    # tsc для Node-части (агрегатор, плагин, vite.config.ts)
npx tsc -b                   # tsc для страницы
```
