# Tripo3D — все стадии генерации (этап 2 пайплайна 3D-моделей)

Справочник этапа 2: генерация и обработка модели в Tripo3D до передачи в Blender. Вход — концепт-лист
этапа 1 (Codex), выход — GLB-исходники, зарегистрированные в source-spec. Приёмка — этап 3 (модель-приёмщик,
порог 8.0), доработка — этап 4 (Blender).

**Достоверность.** Всё без пометки подтверждено файлами репозитория (список в конце). Пометка **(не проверено)** —
внешние данные API-доков developers.tripo3d.ai, снятые 2026-10-09: API в этом проекте ни разу не вызывался.
Единственный реальный путь — Tripo Studio вручную в браузере (прогоны 2026-09-27…29).

## 1. Сервис и доступ

| Способ | Что это | Как используем |
|---|---|---|
| Tripo Studio (`studio.tripo3d.ai`) | веб-UI, план «Max», единица `studio-credits` | текущий путь: вручную, «Claude in Chrome, своя вкладка», одна вкладка на ассет, одна загрузка за раз. Исполнитель браузерной работы — запускающий агент через браузерную автоматизацию своей среды (прецедент прогонов — Claude in Chrome) либо руки пользователя; скилл конкретный инструмент автоматизации не фиксирует. Нет ни того, ни другого — эскалация пользователю до первой платной операции |
| API v3 (`https://openapi.tripo3d.ai/v3`) **(не проверено)** | REST, асинхронные задачи | не используется; справочные данные ниже |
| `tools/tripo-pipeline/tripo_pipeline.py` (v 0.8.0, `tripo_pipeline.py:81`) | локальные стадии ПОСЛЕ Tripo (preflight → import → verify → atlas → build → ue-import) | сетевых вызовов нет: preflight проверяет отсутствие сетевых импортов (`tripo_pipeline.py:1262-1263`); генерация — только dry-run пакет `prepare-generation` (без `--dry-run` отказывает) |
| TRIPO-DCC-BRIDGE (`docs/game-design/evidence/ART-001/TRIPO-DCC-BRIDGE.md`) | мост Studio↔Blender/UE, тип Editor | в пайплайне кандидатов не используется; импорт из Tripo не считается готовым игровым ассетом |

Переменные окружения репозитория — все внутренние, НЕ креденшелы Tripo (проверено grep по `tripo_pipeline.py`):
`TRIPO_PIPELINE_BACKEND`, `TRIPO_PIPELINE_BLENDER`, `TRIPO_PIPELINE_BLENDER_CMD`,
`TRIPO_PIPELINE_BLENDER_MCP_CMD`, `TRIPO_PIPELINE_UNREAL_MCP_CMD`, `TRIPO_PIPELINE_CONSOLE_GRACE_S`
(`tripo_pipeline.py:507-518, 782`), `TRIPO_PIPELINE_UE_ROOT` (`tripo_pipeline.py:1232`).

## 2. Аутентификация

- **Studio:** ключ не нужен — доступ руками в браузере. Правила: одна своя вкладка Chrome, параллельные вкладки
  запрещены (правило писателя журнала кредитов, `docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json`).
- **API (не проверено):** заголовок `Authorization: Bearer {api_key}` на каждом запросе; ключ создаётся в консоли
  `platform.tripo3d.ai` → страница API Keys, показывается один раз; доки рекомендуют имя переменной `TRIPO_API_KEY`.
  **В репозитории переменной ключа Tripo НЕТ** (repo-wide grep по `*.py/*.md/*.json` нашёл только `TRIPO_PIPELINE_*`).
  Путь со своим ключом — официальный tripo-mcp (`docs/research/2026-10-03-blender-agent-skills/README.md` §3.1);
  имя env-переменной ключа в репо не зафиксировано.
- **Лицензия (не проверено):** коммерческое использование Outputs — только платные планы (Terms §5.2.1/§5.2.2);
  у платных пользователей все права на Inputs/Outputs пользователю и Outputs не идут в обучение Tripo. Наш план Max
  подходит. Публичная модель даёт Tripo royalty-free лицензию на показ.

## 3. Полный список стадий

### 3.1 Асинхронная модель (API, не проверено)

POST создаёт задачу → `task_id` → `GET /v3/tasks/{task_id}` (статусы `queued/running/success/failed/cancelled`,
progress 0–100); результат — `output.model_url` (GLB на cdn.tripo3d.ai) + `output.rendered_image_url`. Есть
`POST /v3/tasks/list` и вебхуки. Кредиты: заморозка при создании, списание при success, возврат при fail/cancel.
Превышение лимитов — HTTP 429 (code 1007 на ключ, code 2000 на категорию конкурентности).

### 3.2 Генерация 3D (API, не проверено)

| Эндпоинт | Назначение | Ключевые параметры (дефолты для игровых персонажей) | Выход |
|---|---|---|---|
| `POST /v3/generation/image-to-model` | 1 ортогональный концепт → модель | input: `file_token`/URL/`task_id` (PNG/JPEG/WebP ≤20 МБ, ≥256²); `model` `v3.1-20260211` (последняя, лучшее качество; вероятный аналог Studio-подписи «H3.1» — совпадает линейка V3.1 и Ultra-лимит 2M tri, официальной таблицы маппинга нет) / `v3.0-20250812` (стабильная) / `v2.5-20250123`; `face_limit` до 1.5M (v3.1 standard) / 2M (Ultra=`geometry_quality:detailed`) / 1M (v3.0) / 500k (v2.5) — для игры 50–100k; `quad:true` → ≤150k и форсирует FBX; `texture`+`pbr` default true; `texture_quality` `fast|standard|detailed|extreme` (для игры `detailed`); `texture_version` пинует модель текстуры; `delight` default true (удаление запечённого света, только v3.5); `model_seed`/`texture_seed` (воспроизводимость); `smart_low_poly` 500–20000 tri; `generate_parts` только при texture=false и pbr=false; `export_uv` default true; `export_orientation` не ставить при пост-обработке | GLB |
| `POST /v3/generation/multiview-to-model` | ≥2 ортогональных вида → модель (наш основной режим) | `inputs` с ключами `front/left/back/right` (front обязателен, минимум 2; сервер канонизирует порядок [front, left, back, right]); legacy-формат — ровно 4 строки, пустая пропускает вид. Остальные параметры = image-to-model. Наш прогон 3 вида (front+left+back, right пустой) — валидный кейс | GLB |
| `POST /v3/generation/text-to-model` | промпт → модель | `prompt` ≤1024 симв. (материал/стиль/масштаб), `negative_prompt` ≤255, `image_seed` внутренней text-to-image стадии; остальные = image-to-model | GLB |
| P-серия (те же эндпоинты, `model`=`P1-20260311`\|`P2-20260801`) | low-poly сразу | P2: quad:true, triangle 48–50000; P1 без quad/smart_low_poly. Алиасы: `tripo-p1` «Game pipelines / UGC» | GLB |
| `POST /v3/generation/image-to-gaussian-splat` | сплаты | параметры не подтверждены (не проверено) | сплат |

### 3.3 Препайплайн изображений (API, не проверено)

| Эндпоинт | Назначение | Примечание |
|---|---|---|
| `POST /v3/generation/text-to-image` | промпт → картинка (5 кредитов) | у нас концепты делает Codex (этап 1), не Tripo |
| `POST /v3/generation/image-to-image` | стилизация/перекрас картинки по референсам | |
| `POST /v3/generation/image-to-multiview` | один вид → 4 вида (front/left/back/right), 10 кредитов | готовый input для multiview-to-model |
| `POST /v3/generation/edit-multiview` | правка отдельных видов multiview-сета промптом | |

### 3.4 Обработка моделей (API, не проверено)

| Эндпоинт | Назначение | Ключевые параметры | Когда применять |
|---|---|---|---|
| `POST /v3/models/texture` | (пере)текстурирование | input: `task_id`\|`file_token`\|URL (GLB/GLTF/FBX/OBJ/STL ≤150 МБ); model текстуры `v3.5-20260815` (нужна для fast/delight) \| `v3.0-20250812` (default) \| `v2.5`; `texture_prompt` text\|image\|images (ровно 4 референса front/left/back/right); `pbr` default true; `texture_quality` fast\|standard\|detailed\|extreme (8K); `bake` default true; `delight` (v3.5); `part_names` — только указанные части; `texture_seed` | после ретопологии/ремеша, когда UV новые |
| `POST /v3/models/stylize` | 3D-стилизация | заявлен в migration-гайде; страницы параметров нет — параметры и цена не подтверждены (не проверено) | — |
| `POST /v3/models/convert` | конвертация формата | `format` `GLTF|FBX|USDZ|OBJ|STL|3MF`; `fbx_preset` `blender`(default)\|`3dsmax`\|`mixamo`\|`bake_scale`; `texture_size` 4096; `bake` default true; `pack_uv`; `with_animation` default true; `export_orientation` | когда нужен FBX/quad-меш из API |
| `POST /v3/models/import` | своя модель (file_token/URL ≤150 МБ) для пост-обработки | те же форматы | текстура/риг/конвертация чужой геометрии |
| `POST /v3/models/refine` | уточнение | упомянут в rate-limits; параметры не подтверждены (не проверено) | — |

### 3.5 Меш-операции (API, не проверено)

| Эндпоинт | Назначение | Ключевые параметры | Наш аналог Studio |
|---|---|---|---|
| `POST /v3/mesh/segment` | сегментация на части | `model` `v1.0-20260506` (геометрическая, default) \| `v2.0-20260430` Beta (семантическая); v2: `segmentation_granularity` `simple|balanced|detailed`, `split_by_connectivity` default true, `ref_image` (маска; при наличии игнорирует granularity) | «ИИ сегментация», Balanced = 6–15 частей |
| `POST /v3/mesh/complete` | достройка частей (заполнение срезов) | input = task_id сегментации; `completion_mode` `ai_completion`(default)\|`quick_cap`; `part_names` | «ИИ-дополнение» (выкл. в наших прогонах) |
| `POST /v3/mesh/decimate` («Retopology») | ремеш/ретопология high→low | `model` `v2.0` (default, smart, чистая топология) \| `v1.0` (базовая децимация); `face_limit` — целевой поликаунт; `quad` default false; `bake` default true (запекание текстур на лоуполи; не для v1.0); `part_names` (не для v1.0) | «Ретопология Quad + smart mesh P1.0, цель N» ≈ model=v2.0, quad=true, face_limit≈N, bake=true |

### 3.6 Риг и анимация (API, не проверено)

| Эндпоинт | Назначение | Ключевые параметры |
|---|---|---|
| `POST /v3/animations/rig-check` | бесплатная проверка риггерности | input GLB ≤150 МБ; 0 кредитов; ответ: `riggable` + рекомендуемый `rig_type` |
| `POST /v3/animations/rig` | авто-риг | `model` `v1.0-20240301` (только бипед, 90+ пресетов) \| `v2.5-20260210` (не-гуманоиды); `rig_type` `biped|quadruped|hexapod|octopod|avian|serpentine|aquatic`; `spec` `tripo`\|`mixamo`; `out_format` `glb`\|`fbx`; ~25 кредитов |
| `POST /v3/animations/retarget` | анимационные пресеты на заригованную модель | input = task_id заригованной; `animation`\|`animations` (взаимоисключающие); пресеты: idle, walk, run, jump, slash, shoot, hurt, fall + `<type>:walk/march`; `out_format`; `bake_animation` default true; `animate_in_place` default false; 10 кредитов за анимацию |

**Порядок обязателен: ремеш/квад, smart low poly, сегментация и completion срезают риг/анимацию** — риг и retarget
только ПОСЛЕ финальной топологии (предупреждение v2-доков, подтверждено аудитом
`docs/research/2026-09-27-animation-audit/services.md`). **В нашем проекте риг делается в Blender**
(UM_HUMANOID_17_v2 + цепочки крыльев по RIG-CONTRACT; v1 закрыта для новых клипов — `rig-contract.json`
`skeletons.UM_HUMANOID_17_v1.status`); Tripo-авториг не запускался ни в одном прогоне.
Крыльевых (avian) пресетов анимации нет — крылья Harpy анимируются вручную.

### 3.7 Служебные (API, не проверено)

`POST /v3/files` (multipart → `file_token`; изображения ≤20 МБ, модели ≤150 МБ; >60 МБ — `/v3/files/upload-credentials`),
`GET /v3/account/balance` (balance + frozen), `GET /v3/account/usage`.

## 4. Стадии Tripo Studio — наблюдённые (измерено)

Источник: `reports/tripo-run.json` прогонов `20260928-tripo-h31` (Harpy/King Arthur/Merlin) и `20260929-h2-tripo` (Medusa).

| Операция (UI) | Цена, studio-credits | Результат / оговорка |
|---|---|---|
| Генерация «Из нескольких видов в модель» (H3.1, 4K, Ultra 2M tri, PBR, удалить освещение, Приватный) | 55 | Harpy: 1 918 262 tri, 1 меш; Merlin/Arthur так же |
| Генерация multi-view **по частям** (Баланс, Ultra 2M, без текстуры) | 60 | Medusa H2: 17 частей, 1 856 473 tri |
| «ИИ сегментация» Balanced (6–15 частей) | 40 | Harpy 9 частей; исторически у Medusa b6253e58 списание 0 |
| «Сохранить (части)» | 0 | записи в истории нет |
| Ретопология (Quad, smart mesh P1.0, цель 6800/10000) | 40 | факт ≈ ×1.9–2.2 от цели: 6800 → 13 011–13 893 tri |
| Smart UV («Развернуть UV») | 20 | **отказывает на многочастных моделях** (0 при отказе); удаляет текстуру; проба ×1 на аккаунт (израсходована на Arthur) |
| Генератор текстур 2K (remove lighting) | 10 | 4K = 30; 8K — проба ×1 бесплатно |
| Генератор PBR | 5 | добавляет карту RM; BC/N не меняются |
| Клон «Сохранить как новую модель» | 0 | ветка для одночастных операций |
| «Бесплатный повтор (×3)» после генерации | 0 | не использовался |

Экспорт из Studio — **только GLB**. Загрузка падает в `C:/Users/ren/Downloads`; проверять длину заголовка GLB =
размер файла и обходить чанки; свой Save-диалог закрыть до передачи браузера (инцидент P1.5).

## 5. Рекомендуемые маршруты

### A. Герой (маршрут h31 — проверен на Arthur/Merlin/Harpy, 190–210 кредитов)

1. **Виды:** multi-view front+left+back (right пустой). Конвенция: role name == имя слота Studio
   front/left/right/back (`docs/art-pipeline/imagegen-inputs/manifest.json`, `tripoSlotConvention`).
2. **Настройки генерации:** Приватный; геометрия и текстура; H3.1; текстура **2K** — норма для новых прогонов
   (`ADDING-AN-ASSET.md` §2 п. 2; 2K = 10 кредитов против 30 за 4K); Ultra mesh, Triangle 2 000 000; PBR;
   «удалить освещение»; 8K и «по частям» выкл. Базлайн h31 генерировал 4K и понижал до 2K позже на клоне —
   исторический факт прогона, не норма: при расхождении действует инструкция для новых прогонов.
3. **Сегментация Balanced** → «Сохранить (части)» (0). Части `tripo_part_N` нужны сборке (weapon, anatomy, atlas).
4. **Ретопология Quad + smart mesh** на сегментированном состоянии; цель ≈ половина бюджета (факт ×1.9–2.2).
   Бюджет берётся ТОЛЬКО из POLY_BUDGET заявки этапа 0 (SKILL.md §6): герой 15–25k tris, потолок 45k
   («Предложение 04» HANDBOOK — решение за GD-058); 8–15k — бюджет помощника (Merlin, Harpy). Цель 6800 —
   факт прогона Harpy (помощник), не «бюджет героя».
5. **Одночастная ветка для чистых UV:** клон версии генерации «Сохранить как новую модель» (0) → ретопология
   (40) → Smart UV (20) → текстура 2K (10) → PBR (5). Smart UV на многочастной отказывает — поэтому клон.
6. **Экспорт GLB** всех состояний (см. §7), SHA-256, source-spec, журнал кредитов сразу после каждой операции.
7. Дальше — CLI: import/verify/atlas/build берут `segmented-retopo-glb` (в git); риг — Blender, не Tripo.

### B. Проработка героя high-poly (маршрут H2 — Medusa 20260929, 65 кредитов)

multi-view **по частям** (Баланс, Ultra 2M, без текстуры) → текстура 8K (проба ×1, 0; фактически набор карт
на часть, крупнейшая 4096²) → PBR (5). Без клонов и ретопологии; high-poly ~2M tri остаётся для запекания
high→low в Blender. Группа H2 целиком: 350 кредитов (`20260929-h2-tripo/reports/tripo-run.json`).

### C. Существо / не-гуманоид

Маршрут A. Авториг не используется (Harpy: риг по контракту UM_HUMANOID_17_v2, крылья = цепочки рук;
исторический прогон Harpy шёл по v1 — для новых клипов v1 закрыта; avian-пресетов
нет). Если когда-нибудь нужен Tripo-авториг — сначала `rig-check`, и только после финальной топологии.

### D. Проп

Одно изображение → GLB → профиль `static-candidate` (образец — бочка: `ASSET-DECOR-KIT-001/20260928-p15-barrel`;
`docs/art-pipeline/PIPELINE.md`, профиль static-candidate).

## 6. Экспорт: что выбираем и почему

- **Наш выбор — GLB напрямую из Studio в Blender** (стадия import CLI). Конвертация не нужна: свой FBX пишем
  сами из Blender-этапа по пресету **UM_FBX_v1** (поворот +90° по Z, данные ×100, `FBX_SCALE_UNITS`,
  `UnitScaleFactor` = 1.0, −Y вперёд) — Studio FBX не отдаёт, а API-FBX в проекте не проверялся.
- **API (не проверено):** нативный результат всех генераций — GLB; FBX/USDZ/OBJ/STL/3MF через `models/convert`
  (`fbx_preset=blender` — default); `quad:true` форсирует FBX; полного USD нет, USDZ — Apple AR (для Blender
  не нужен). OBJ/STL/3MF не поддерживают ригованные модели.
- **Текстуры:** отдельные файлы `*_basecolor.jpg` / `*_normal.png` / `*_rm.png`; в glTF RM = G-roughness /
  B-metallic, R=1.0 (не AO — измерено, `texture_measurements` в tripo-run.json). В атласе проекта ORM:
  R = запечённый AO (стадия atlas), G = roughness, B = metallic. В GLB может лежать `baseColorFactor` 0.8 —
  решать в Blender-этапе (запечь в BC или сбросить в 1.0).

## 7. Структура папок прогона (по образцу репозитория)

```
art/pipeline-candidates/<ASSET-ID>/                 # ASSET-HARPY-001
  source-specs/tripo-<task8>.json                   # схема unmatched.tripo-pipeline.source-spec/1:
                                                    #   service, task_id/parent_task_id, model_version,
                                                    #   generation (views+sha256, settings), operations[],
                                                    #   files[] c expected_sha256/bytes, expectations, evidence[]
  build-profiles/<name>-um-fbx-v1*.json             # профили сборки (этапы 4/6; новой версии — новый файл)
  <дата>-tripo-<вер>/                               # 20260928-tripo-h31, 20260929-h2-tripo — прогон Tripo
    reports/tripo-run.json                          # схема unmatched.tripo-pipeline.studio-run-evidence/1
    source/                                         # GLB Studio; только читаются; ВНЕ CLI run-каталога
      <asset>-tripo-h31-<task8>-source.glb          # сырой исходник 62-65 МБ; локально вне git (de252a25)
      <asset>-tripo-<task8>-segmented-<N>.glb       # после сегментации
      <asset>-tripo-<task8>-segmented-retopo.glb    # В GIT; главный вход import/atlas/build
      <asset>-tripo-<clone8>-retopo-<target>.glb    # одночастный клон после ретопологии
      <asset>-tripo-<clone8>-smartuv-tex2k.glb      # Smart UV + текстура 2K
      <asset>-tripo-<clone8>-smartuv-tex2k-pbr.glb  # + PBR (карта RM)
      textures/*_basecolor.jpg|*_normal.png|*_rm.png
    preview/                                        # h31_*.png, segretopo_*.png, pbr_*.png (ортокамера Blender)
    pipeline/                                       # CLI-прогон: manifest.json (run/1), journal.jsonl, reports/
    export/  textures/  work/                       # выходы CLI-стадий; work/ и logs/ не в git
```

- **Правило размещения сырых GLB (единое для нового прогона):** исходники Studio кладутся в `source/`
  каталога ПРОГОНА Tripo (`<дата>-tripo-<вер>/source/`), а CLI-прогон живёт в `<дата>-tripo-<вер>/pipeline/`
  (или в отдельном `<дата>-cli-<вер>/`) — каталоги не вложены друг в друга, потому что `register-source`
  отказывает, если оригинал находится внутри CLI run-каталога (docs/art-pipeline/PIPELINE.md). Раскладка
  Medusa (`blender/ASSET-MEDUSA-001/tripo-source/<task8>/`) — историческая, для новых прогонов не образец.
- `<task8>` = первые 8 символов task id (d500fc84, c756522c…); роли файлов в `exports[]`/`files[]`:
  `source-glb`, `segmented-N`, `segmented-retopo`, `retopo-<N>`, `smartuv-tex2k`, `smartuv-tex2k-pbr`.
- Новый прогон — всегда новый `<run-id>`; повторная генерация тех же входов запрещена: `prepare-generation`
  отказывает (код 3) при тех же хешах входов + mode + service при любой подписи модели; обход — только
  `--allow-duplicate --duplicate-reason "..."` (`docs/art-pipeline/PIPELINE.md`, «Команды»).
- В чистом checkout preflight `source_files_present` героев не пройдёт (сырые исходники вне git);
  сборка их не читает — import/atlas/build берут `segmented-retopo-glb` (в git).

## 8. Кредиты и бюджет

Цены Studio — измерено 2026-09-28/29 (§4). Цены API — **(не проверено)**, `developers.tripo3d.ai/en/pricing`,
2026-10-09; 1 кредит API = $0.01, pay-as-you-go. Studio-кредиты и API-кредиты учитываются раздельно
(`credits.unit` в spec: `studio-credits` / `api-credits`, USD не смешивается).

| Операция | API, кредиты (не проверено) | Studio, наблюдено |
|---|---|---|
| image/multiview-to-model | 20 без текстуры / 30 standard; аддоны: HD Texture +10, 8K +20, HD Geometry +20, Quad +5, Smart Low-poly +10, Generate Parts +20 | multi-view HD 55; по частям 60 |
| text-to-model | 10 / 20 | — |
| P-серия | P2: 100 / 110 / 120 / 130; P1 не подтверждена (не проверено) | — |
| texture | fast/standard 10, detailed 20, extreme 30 | 2K 10; 4K 30 |
| retopology | v2.0 = 30, v1.0 = 10 | Quad 40 |
| segment | 40; Smart Segmentation 55 (модель) / 85 (изображение) | Balanced 40 |
| mesh complete | ai_completion 50 / quick_cap 30 | — (не включали) |
| rig-check / rig / retarget | 0 / 25 / 10 за анимацию | не запускались |
| convert | basic 5 / advanced 10 | — (нативный GLB) |
| image-to-multiview | 10 | — |

**Бюджет:** потолок на одного героя ~400 studio-кредитов (задание Harpy); окно автономии этапа 3 — 300
studio-кредитов на всё окно, покупки кредитов запрещены (`credits-ledger.json` `windowLimits`). Окно 300 —
решение пользователя от 2026-09-28 **только на то окно** (`windowLimits.source`): на новый прогон оно
автоматически не продлевается. Перед первой платной операцией запускающий читает остаток в журнале
(`docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json`, раздел `tripo.window`:
`spent`/`remaining`), а если старое окно закрыто или новый прогон им не покрывается —
останавливается и подтверждает лимит у пользователя. Списания Tripo дописываются в `tripo.window.entries`
**вручную, готового инструмента нет**: по `writer.rule` журнала («один писатель; каждое новое списание
дописывается той задачей, которая его сделала, со временем истории Studio, balance_before/after и ссылкой
на run-файл; параллельные вкладки запрещены») — формат полей существующих записей: `historyTime`,
`observedAt`, `op`, `taskId`, `delta`, `quoted`, `balanceBefore/After`, `ref`, `owner`.
`tools/art/syntx_video_refs/ledger_append.py` для Tripo НЕ подходит — он только для SYNTX-генераций
(читает `quote.json`/`balance_before/after.json` SYNTX-прогона и пишет `syntx.window.entries` с
`op='image2video (SYNTX)'`). Факт по героям:
Arthur 190, Merlin 210, Harpy 210 (вторая ретопология 40 — осознанная, для одночастной ветки Smart UV);
Medusa H2 — 65. Баланс плана Max на 2026-09-28: 24 545 → 24 335 за окно Harpy. Правило остановки 1: цена с
кнопки выше остатка лимита ассета или окна — стоп; две неудачные генерации подряд — стоп (`ADDING-AN-ASSET.md` §0).

## 9. Примеры вызовов

CLI (проверено; из корня репозитория, Git Bash: `export MSYS_NO_PATHCONV=1`):

```bash
T="python tools/tripo-pipeline/tripo_pipeline.py"

# пакет входов БЕЗ отправки (ничего не платит, в сеть не ходит)
$T prepare-generation --run-dir art/pipeline-candidates/ASSET-NEW-001/<run> --dry-run \
    --service tripo-studio --mode multi-view \
    --model-label "H3.1 - Макс.кач. Ожидание дольше" \
    --view front=art/imagegen/mvp-v1/characters/ref-<hero>-v5-front.png \
    --view left=art/imagegen/mvp-v1/characters/ref-<hero>-v5-left.png \
    --view back=art/imagegen/mvp-v1/characters/ref-<hero>-v5-back.png
# код 3 = такие входы уже генерировались; обход: --allow-duplicate --duplicate-reason "почему"

# регистрация уже оплаченной задачи и локальные стадии
$T init --run-dir <R> --asset-id ASSET-NEW-001 --primary-source tripo-<task8> \
    --primary-role segmented-retopo-glb --profile skeletal-candidate --build-profile <профиль>
$T register-source --run-dir <R> --spec art/pipeline-candidates/ASSET-NEW-001/source-specs/tripo-<task8>.json
$T run --run-dir <R>
```

API (не проверено; имена полей входа сверьте в /en/docs — в этом репозитории API не вызывался):

```bash
export TRIPO_API_KEY="..."   # ключ из platform.tripo3d.ai → API Keys

# image-to-3D, игровые дефолты (вход: file_token | URL | task_id)
curl -s https://openapi.tripo3d.ai/v3/generation/image-to-model \
  -H "Authorization: Bearer $TRIPO_API_KEY" -H "Content-Type: application/json" \
  -d '{"file": "<URL референса front>", "model": "v3.1-20260211", "face_limit": 100000,
       "texture": true, "pbr": true, "texture_quality": "detailed", "delight": true}'

# multiview: 3 вида, right пустой (наш кейс)
curl -s https://openapi.tripo3d.ai/v3/generation/multiview-to-model \
  -H "Authorization: Bearer $TRIPO_API_KEY" -H "Content-Type: application/json" \
  -d '{"inputs": [{"front": "<url>", "left": "<url>", "back": "<url>"}],
       "model": "v3.1-20260211", "face_limit": 100000, "texture": true, "pbr": true}'

# опрос задачи -> output.model_url (GLB)
curl -s https://openapi.tripo3d.ai/v3/tasks/<task_id> -H "Authorization: Bearer $TRIPO_API_KEY"

# ретопология (= наш Quad-прогон), текстура, баланс
curl -s https://openapi.tripo3d.ai/v3/mesh/decimate -H "Authorization: Bearer $TRIPO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "<task_id генерации>", "model": "v2.0", "face_limit": 6800, "quad": true, "bake": true}'
curl -s https://openapi.tripo3d.ai/v3/models/texture -H "Authorization: Bearer $TRIPO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "<task_id>", "texture_quality": "detailed", "pbr": true, "bake": true}'
curl -s https://openapi.tripo3d.ai/v3/account/balance -H "Authorization: Bearer $TRIPO_API_KEY"
```

```python
#_poll задач (не проверено): от POST до output.model_url
import time, urllib.request
def poll(task_id, key):
    while True:
        req = urllib.request.Request(f"https://openapi.tripo3d.ai/v3/tasks/{task_id}",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req) as r:
            data = json.load(r)["data"]
        if data["status"] in ("success", "failed", "cancelled"):
            return data                       # success -> data["output"]["model_url"]
        time.sleep(10)
```

## 10. Типовые ошибки и признаки

| Ошибка | Признак | Что делать |
|---|---|---|
| Smart UV на многочастной модели | отказ Studio «Smart UV пока не поддерживает модели из нескольких частей», списания нет | клон «Сохранить как новую модель» (0) → ретопология → Smart UV в одночастной ветке |
| Ретопология перебирает поликаунт | цель 6800 → факт 13 011–13 893 tri (×1.9–2.2); 6500 → 12.2k/14.1k | ставить цель ≈ 0.5× от бюджета верхнего предела |
| Вывернутый winding частей | при backface culling «пропадает» лицо/нога; доля граней наружу 0.278–0.284 против 0.70–0.81 у нормальных частей (Harpy `tripo_part_2`, `tripo_part_6`) | чинить в Blender: build `orientation.expected_inside_out_parts` / `per_face_reference`; невылеченная часть запекает AO чёрной |
| Кривой масштаб | Tripo нормирует метры ~1 м по наибольшему габариту (у Harpy — размах крыльев, не высота); низ на Z=0; сжатый по Y вход даёт сплющенную модель | сверять отношение высота/ширина модели с референсом (у Harpy 2.06 против 1.99–2.00); игровой масштаб — `figure_height_m` профиля сборки, не Tripo |
| Развалившиеся/сдвоенные детали | два крыла вместо одного, «двоение» перьев | вид сверху (h31_wide_top): Harpy — ровно два тонких крыла V-образно; явный брак → бесплатный повтор ×3, не использованный — не тратить |
| Запечённый свет в текстуре | тени/блики концепта в BC | «удалить освещение» при генерации текстур (API `delight`, только v3.5 — не проверено) |
| Экспорт Studio | Chrome оставляет `C:/Users/ren/Downloads/<guid>.tmp`, незавершённый Save-As дописывает чужая сессия | длина заголовка GLB = размер файла, обход чанков; одна загрузка за раз; свой диалог закрыть |
| Повторная генерация | `prepare-generation` код 3 (те же хеши входов + mode + service) | не повторять без решения; обход — `--allow-duplicate --duplicate-reason` |
| Чистый checkout | preflight `source_files_present` падает: сырые `*-source.glb` вне git | файлы локальные по решению de252a25; сборке хватает `segmented-retopo-glb` из git |
| Формат потерял риг | OBJ/STL/3MF не несут скелет; remesh/segment/complete срезают риг | риг/анимация — только после финальной топологии; у нас риг в Blender |
| Лимиты API (не проверено) | HTTP 429: code 1007 (ключ), code 2000 (категория конкурентности) | ждать `X-RateLimit-Reset`; категории независимы |

## 11. Чек-лист приёмки прогона Tripo (выход этапа 2)

- [ ] Каждая платная операция: цена считана с кнопки ДО клика; `quoted`, `observed_debit`, баланс до/после записаны
- [ ] Журнал кредитов `docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json` дополнен сразу после каждой операции
- [ ] Каждый GLB: длина заголовка = размер файла, обход чанков пройден; файл переименован `<asset>-tripo-<task8>-<role>.glb`
- [ ] SHA-256 и байты каждого файла в `reports/tripo-run.json` (`exports[]`)
- [ ] Превью 6+ видов (front/left/back/right/3-4/top + крупные планы головы/лап/оружия) просмотрены глазами
- [ ] Нет двоения деталей; все части на месте; подставка ровная; ориентация Z вверх, лицо −Y, своё левое +X
- [ ] Winding частей проверен (backface culling); вывернутые перечислены в отчёте
- [ ] Метры Tripo измерены (`measured_bounds_blender_m`), соотношения с референсом сверены
- [ ] Настройки Studio возвращены (4K / 2 000 000 / Приватный), вкладка закрыта
- [ ] `source-specs/tripo-<task8>.json` по схеме `unmatched.tripo-pipeline.source-spec/1`; хеши файлов совпадают
- [ ] `claims`: `art_accepted: false`, `game_ready: false`, `budgets_declared: false` — приёмку ставит только арт-трек (порог 8.0, этап 3)
- [ ] Идемпотентность: повторная генерация не делалась (или оформлена `--allow-duplicate --duplicate-reason`)

## Источники (репозиторий)

- `art/pipeline-candidates/ASSET-{HARPY,KING-ARTHUR,MERLIN}-001/20260928-tripo-h31/reports/tripo-run.json` — операции, цены, экспорты, измерения
- `art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-tripo/reports/tripo-run.json` — маршрут H2
- `art/pipeline-candidates/ASSET-*/source-specs/tripo-*.json` — схема source-spec/1
- `tools/tripo-pipeline/tripo_pipeline.py` — версии, env-переменные, dry-run, коды выхода
- `docs/art-pipeline/PIPELINE.md`, `docs/art-pipeline/ADDING-AN-ASSET.md` — CLI, правила остановки, статусы, ловушки
- `docs/art-pipeline/imagegen-inputs/manifest.json` — конвенция слотов; `docs/art-pipeline/art-hub-snapshot.json`, `asset-registry.json` — статусы/реестр
- `docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json` — окно лимитов
- `docs/research/2026-09-27-animation-audit/services.md`, `docs/game-design/evidence/ART-001/TRIPO-DCC-BRIDGE.md`, `docs/research/2026-10-03-blender-agent-skills/README.md`
