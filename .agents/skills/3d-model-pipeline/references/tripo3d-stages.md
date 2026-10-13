# Tripo3D: этап 2 (генерация H2) и маршрут «Черновик» шага 1b

Справочник для двух мест карты этапов скилла (SKILL.md, этапы 0–7):

- **шаг 1b этапа 1** — маршрут «Черновик»: дешёвая модель по утверждённому дизайн-front, из неё ортопроекции для
  перерисовки видов (`references/concept-sheet.md`);
- **этап 2** — генерация героя H2 (или пропа) по принятым видам этапа 1. Результат — GLB-исходники, source-spec и
  отчёт прогона. Это вход этапа 3 (сборка в Blender).

**Норма производства — хендбук** `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (дальше HANDBOOK): §3.2 «Генерация в
Tripo Studio», §3.3 «Source spec», §7.1 «Входы и Tripo». Числа хендбука здесь не копируются. Этот файл добавляет
полное покрытие инструментов Tripo (требование №2), протокол траты кредитов, проверку дублей, чек-листы и справочник
API.

**Достоверность.** Без пометки — факт из файлов репозитория (путь указан). «Живая проверка 2026-10-09» — осмотр
Tripo Studio оркестратором переписывания скилла без генераций (0 кредитов): баланс 21 540, левая панель из 12
инструментов, форма генерации. Пометка «(API, не вызывался)» — факт из документации developers.tripo3d.ai, снятый
2026-10-09 по указанному URL. В проекте API ни разу не вызывался.

## 1. Что делать до первой платной операции

| № | Предусловие | Как проверить | Если нет |
|---|---|---|---|
| 1 | Заявка этапа 0 `ASSET_DIR/asset-card.yaml` заполнена: `ASSET_ID`, `CONTENT_KEY`, `ROLE`, `ANATOMY`, `WEAPON_HAND`, `SIDE_VIEW`, `POLY_BUDGET`, `CREDITS`, `VISUAL_CARD_ID` | прочитать файл | вернуться к этапу 0 (SKILL.md) |
| 2 | `ANATOMY` = `humanoid`, `winged-biped` или `prop` | поле заявки | не-гуманоид — стоп ещё на этапе 0 (гейт стопа SKILL.md §5 п.1: нужен rig-contract/3). Генерация Tripo для него не запускается |
| 3 | Есть карточка задачи в `docs/game-design/visual/06-tasks/anim.csv` (area `hero`; шаблон `T-TRIPO-PART`, `docs/game-design/visual/07-prompt-templates.md` §0.1, §3.2) | `ledger.py add` без карточки отказывает: `--task … is not a card in 06-tasks` (`tools/art/visual/ledger.py:409`) | дописать строку карточки на этапе 0 (SKILL.md §6, этап 0 п.3; её id — поле `VISUAL_CARD_ID` заявки, `<VISUAL_CARD_ID>` ниже) |
| 4 | В журнале есть строка условий Tripo (ВР-05) | на 2026-10-09 её нет: предпроверка п. 5 даёт ERROR `pre-flight Tripo: no providerTerms row for Tripo`, а `ledger.py check` после траты без неё — ERROR `no providerTerms row for Tripo …` (`ledger.py:261`; предпроверка — `:331-334`) | записать **до** первой траты: `python tools/art/visual/ledger.py terms --service Tripo --model "Tripo Studio H3.1" --url https://www.tripo3d.ai/terms` |
| 5 | Остаток лимита ВР-04 и свежий баланс ≥ цены цепочки (§3) | `python tools/art/visual/ledger.py check --service tripo --next-cost <цена цепочки> [--balance <баланс Studio>] --model "Tripo Studio H3.1"` → код 0 (строка `info` печатает цену, остаток ВР-04 из 3000 до 2026-10-28, остаток после операции и баланс) | код 1 — стоп, гейт стопа SKILL.md §5 п.3: пакет пользователю |
| 6 | Исполнитель Studio определён (§2) | — | гейт стопа SKILL.md §5 п.2 |
| 7 | Входы не генерировались раньше (§6, шаг 3) | скрипт проверки дублей | стоп: исходник уже есть, 0 кредитов (HANDBOOK §3.2, первая строка) |

Правила журнала трат:

- Единственный действующий журнал — `docs/game-design/visual/credits-ledger.json`. Его пишет только
  `tools/art/visual/ledger.py add`: одна строка сразу после каждой операции, до следующей (07 §4.1–4.2). Лимит
  Tripo ВР-04 — значение `limits.tripo.credits` журнала, окно до 2026-10-28, покупок нет
  (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`, строка ВР-04). Было 3000; 2026-10-13
  пользователь снял потолок («На триппо нет лимита», `docs/game-design/decisions/2026-10-13-tripo-no-limit.md`,
  в журнале 1 000 000). Числа «3000» ниже — история; реальная граница — свежий баланс Studio (`--balance`).
- Предпроверка Tripo — только с `--service tripo` (`tools/art/visual/ledger.py`, `_tripo_preflight`): ERROR, если
  `tripo_spent + N` больше 3000 (ВР-04), если сегодня позже 2026-10-28, если свежий баланс `--balance` меньше цены
  (покупок нет), если нет строки `providerTerms` Tripo или `--model` ею не покрыт (ВР-05); WARN, если баланс ниже
  остатка ВР-04, но цену покрывает. Лимиты SYNTX (visual cap 54, stop balance, окно SYNTX) к Tripo не применяются.
  Без `--service` команда — прежняя предпроверка SYNTX (`--balance` и `--next-cost` обязательны парой): цену Tripo в
  неё не подавать, она упадёт на visual cap 54. Ошибки аргументов (`--service tripo` без `--next-cost`, `--next-kind`
  с Tripo, `--model` без Tripo) — код 2.
- `ledger.py check` после траты Tripo пишет `WARN … roster after MVP is out of scope (ВР-18)`. Это ожидаемо. Запрос
  пользователя на нового героя — основание для запуска (SKILL.md).
- Старый журнал `docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json` — история до 2026-10-05.
  В него не писать. Его `tripo.window.remaining` (−1090) — историческое поле по `limitNote`, остаток по нему не
  считается. `tools/art/syntx_video_refs/ledger_append.py` пишет только этот старый журнал; HANDBOOK §3.2 п.5 и 07 §4.1
  ведут новые траты через `ledger.py add`.

**Лицензия.** Условия Tripo не проверены. Позиция проекта — ВР-05: сборка личная и локальная (LAN), коммерческих
прав не заявляем, условия провайдера записываются в журнал до первой траты (п. 4 таблицы). Вывода «план подходит»
скилл не делает.

## 2. Кто нажимает кнопки Studio

| Вариант | Когда | Правила |
|---|---|---|
| Запускающий агент, Claude in Chrome, своя вкладка | всегда первым (запуск скилла заявкой пользователя = разрешение трат в лимите ВР-04, SKILL.md §1), если права сессии пропускают клики | одна своя вкладка на ассет. Чужие вкладки не трогать. Параллельных вкладок Studio нет. Цену читать с кнопки **до** клика. Баланс — до и после |
| Запускающий агент, Windows-MCP в Chrome пользователя | расширение Claude in Chrome не подключено, а Studio уже открыта и залогинена в Chrome пользователя (пилот 2026-10-13: 3 героя, 12 операций, 0 сбоев) | клики по координатам экрана; кадры снимать `System.Drawing.CopyFromScreen` по области панели (снимок всего стола уменьшен в 4 раза и нечитаем). Загрузка вида — клик по слоту → в системном диалоге путь в поле имени файла + Enter. uuid задачи — §5.2 п. 5а. Вкладка — та же, где Studio уже открыта; другие вкладки пользователя не трогать |
| Пользователь по чек-листу §8 | клики заблокированы классификатором прав (живая проверка 2026-10-09: клик по вкладке «Умная сетка» остановлен категорией Real-World Transactions) или пользователь так решил | агент готовит всё до клика (§6, шаги 1–4), отдаёт чек-лист, затем сам проверяет файлы и пишет журнал по присланным ценам и балансам |

**Разрешение трат (одно правило, решение скилла).** Заявка пользователя на новую фигуру, по которой запущен скилл, —
это разрешение тратить кредиты Tripo и SYNTX в лимите ВР-04 (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`)
с записью каждой операции в журнал (`ledger.py`). Отдельно «разрешаете траты?» не спрашивать: такого гейта нет
(SKILL.md §5). Если клик блокирует классификатор прав сессии или пользователь, — это гейт SKILL.md §5 п.2: чек-лист
§8 пользователю, агент проверяет результат.

Вызов Studio-операций через API, tripo-mcp или Blender MCP (`generate_tripo_model`) нормой не является. Это другие
кредиты (`api-credits`), ключа в репозитории нет (`TRIPO_API_KEY` не найден grep-ом), см. §10.

## 3. Цены и итог на ассет

| Цепочка | Операции Studio | Цена, studio-credits | Источник |
|---|---|---|---|
| Герой H2 (этап 2) | по частям 60 → текстура 8K 30 → PBR 5 | **95** | `art/pipeline-candidates/ASSET-{KING-ARTHUR,MERLIN,HARPY}-001/20260929-h2-tripo/reports/tripo-run.json` (`this_hero_total_observed` 95); Harpy H3 `source-specs/tripo-bca735a3-h3.json` — тоже 60/30/5 |
| То же при неизрасходованной пробе 8K | 60 → 0 → 5 | 65 | только Medusa (`ASSET-MEDUSA-001/20260929-h2-tripo/reports/tripo-run.json`: «пробная версия ×1»). Проба ×1 на аккаунт израсходована 2026-09-29. Считать 95, пока кнопка текстуры не покажет `0` |
| Черновик (шаг 1b) | одна генерация по одному изображению | ≈ 30, точно — с кнопки | живая проверка 2026-10-09: форма по умолчанию (H3.1, без 8K) показала 30; с 8K — 65. Не списывалось |
| Проп | multi-view → (Smart UV / ремеш по необходимости) → текстура 2K 10 → PBR 5 | 60–130 | бочка `ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json`: 45 + Smart UV 0 (проба) + 10 + 5; фонарь `tripo-26bb832e.json`: 55 + 40 + 20 + 10 + 5 |

План на героя (решение скилла): черновик ≈ 30 + H2 95 = **≈ 125**. Одна перегенерация (`return_to_stage_2`) — ещё
60–95. Порог остановки — §1 п. 5 и правило «две неудачные генерации подряд — стоп» (гейт стопа SKILL.md §5 п.3, HANDBOOK §0.3
п. 1; как считать — §5.4).

## 4. Все инструменты Tripo Studio: что применяем и почему

Левая панель Studio — 12 инструментов (живая проверка 2026-10-09). Цена Studio — с кнопки или из журнала прогона.
Публичные цены API (§10) для Studio не подставлять: авторитетна форма в момент запуска
(`docs/game-design/evidence/ART-004/tripo-production-20260927/README.md`, последний абзац «Проверенная карта
функций Studio»; дальше — ART-004 README).

| Инструмент (UI) | Цена Studio | Применяем? | Где | Почему нет / оговорка |
|---|---|---|---|---|
| **Изображение** (новый, генерация картинок) | не снималась | нет | — | концепт делает Codex по строгим правилам листа (требование №1, `references/concept-sheet.md`). Картинка Tripo обходит сетку и автопроверки этапа 1 |
| **Модель → «HD модель»**, H3.1 «Макс. кач.» | по частям без текстуры 60 (H2); multi-view с текстурой 4K 55 (h31); одно изображение по умолчанию 30 | **да** | этап 2 (герой, проп), шаг 1b (черновик) | — |
| Модель → H3.0 «Баланс», H2.5 Legacy | не снималась | нет | — | все принятые фигуры сделаны на H3.1 (`model_version_note` в tripo-run H2). Более слабая модель даёт расхождение с эталоном качества |
| Модель → **«Умная сетка»** (Smart Mesh, низкополигональные квады и части) | не снималась (клик заблокирован 2026-10-09) | нет | — | H2-сборке нужен high-poly ~2M для запекания high→low; ретопологию делает Blender по частям с приоритетами (HANDBOOK §4.2, ключ `retopo`). На наших фигурах не испытывалась (ART-004 README, строка «Model / Smart Mesh») |
| Опции формы: «Геометрия и текстура», «по частям», «Текстура 8K», «Приватность» | 8K в форме генерации: 30 → 65 | по маршруту | §5 | для H2 текстура в форме **выключена**: генерация по частям несовместима с текстурой (API: `generate_parts` требует `texture=false`, `pbr=false`). 8K делается отдельным шагом текстуры. «Приватность» всегда включена |
| **Делить** (Segment: Simple 3–6, Balanced 6–15, Detailed 15+) | 40 (h31); проба 0 (Medusa) | нет | — | генерация «по частям» уже даёт 12–21 часть (tripo-run H2). Segment не принимает Quad-модели («Quad модели не поддерживают сегментацию», ART-004 README). Историческое применение — маршрут h31 |
| **Докомпл** (Fill Parts: Quick Cap / AI Completion) | не снималась на нашем аккаунте | нет | — | работает только после сегментации (ART-004 README). Срезы и стыки закрывает этап 3: ключ `closure` профиля h2_bake (HANDBOOK §4.2) |
| **Ремеш** (Retopology: Quad/Triangle, Smart Mesh P1.0, цель 500–10 000) | 40 | нет для героя; для пропа — только по решению §5.3 | проп | для героя ретопология в Blender (HANDBOOK §4.2). Studio перебирает цель в 1,9–2,2 раза (6800 → 13 011–13 893 tris, h31 tripo-run Harpy), а Quad после этого блокирует Segment |
| **Smart UV** | 20; пробы 0 | нет для героя; для пропа — только по решению §5.3 | проп | удаляет текстуру (после — ретекстура). Отказывает на многочастных моделях. Лимит 80k tris / 40k quads (ART-004 README). UV героя — charts в h2_bake (HANDBOOK §4.2, ключ `uv`) |
| **Текстура** (Texture Gen: 2K/4K/8K, «Удалить освещение», по изображениям/модели/тексту) | 2K 10 (списано, h31); 4K 30 — цена с кнопки, не списывалась (h31 tripo-run Harpy, Arthur, Merlin: `note` операции `texture` «4K стоил бы 30»); 8K 30 (списано у Arthur, Merlin, Harpy H2; проба ×1 = 0 израсходована) | **да** | герой: 8K + «Удалить освещение»; проп: 2K | «8K» даёт набор карт по частям (крупнейшая 4096²), это вход запекания (tripo-run H2, `findings`) |
| **Правка** (Magic Brush: маска на поверхности + запрос) | предпросмотр 5 (ART-004 README) | нет | — | цвет и детали правятся в look-dev и этапе 5 профилем (HANDBOOK §4.4). Ручная кисть в Studio невоспроизводима и меняет исходник после регистрации |
| **Увелич** (Texture Upscale 4K/8K) | 20; 8K — проба `0` (ART-004 README) | нет | — | после «Текстура 8K» увеличивать нечего; рантайм 2K (HANDBOOK §4.2, ключ `uv`: `runtime_px`) |
| **PBR** (PBR Generator) | 5 | **да** | герой после 8K; проп после 2K | добавляет карту RM, BC/N не меняет (h31 tripo-run: те же sha256) |
| **Риг** (Auto-rig: «Гуманоид»/«Другое», пресеты ActorCore, Mixamo, UE5 Mannequin, VRM 1.0, Unity Humanoid) | 20 за запуск | **нет** | — | HANDBOOK §3.2 «Tripo-авториг не использовать». P1.6 на Medusa: 5/7 и 7/7 проб в неверной зоне, подставка на бедре, L/R перепутаны (`art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/README.md`). Риг — Blender, `UM_HUMANOID_17_v2` (этап 3) |
| **Анимация** (пресеты, Text-to-motion, «Многоэтапное движение»; «видео → движение» — «Скоро») | Text-to-motion 20; пресет — не подтверждена | **нет** | — | требует риг Tripo. Пресеты не равны клипам D-11 с длительностями и неподвижным root. «стоя_отдых» прошёл валидатор, но визуально сломан (P1.6 README). Клипы — этап 6 (`references/animation-vfx-sfx.md`) |
| **Экспорт**: GLB, FBX (Blender/Mixamo/3dsmax), USD, OBJ, STL, 3MF; разрешение текстур; Compact UV | 0 | **GLB — да**; прочее нет | все маршруты | FBX пишет сам этап 3 по пресету UM_FBX_v1 (HANDBOOK §2.2). OBJ/STL/3MF не несут скелет. Compact UV не проверен: ссылка не скачалась (ART-004 README) |
| **Send To / DCC Bridge** (Blender, UE) | 0 | нет | — | обходит source-spec и проверки; масштаб и материалы не доказывает (ART-004 README, `docs/game-design/evidence/ART-001/TRIPO-DCC-BRIDGE.md`) |
| «Сохранить как новую модель» (клон) | 0 | нет (H2) | — | нужен был только ветке h31 для Smart UV |
| «Бесплатный повтор (×3)» | 0 | да, при явном браке — только если форма показывает его с ценой `0` | §5.4 | в репозитории кнопка записана только у шага Smart UV и не нажималась (`art/pipeline-candidates/ASSET-HARPY-001/20260928-tripo-h31/reports/tripo-run.json:186`, у Merlin так же). Есть ли она после генерации модели — не проверено: смотреть форму. Результат повтора проверяется так же, как платный |

## 5. Маршруты

### 5.1 Герой H2 — этап 2

Порядок и настройки — **HANDBOOK §3.2 п. 3**. Коротко:

1. **Модель → «HD модель», из нескольких видов**, H3.1, «Приватность» вкл., «по частям» Баланс, ультра-сетка 2M,
   треугольники, **без текстуры**. 60.
2. **Текстура** на этой же задаче: 8K, «Удалить освещение». 30 (0, если кнопка показывает пробу).
3. **PBR**. 5.
4. **Экспорт GLB** двух состояний одной задачи: после шага 1 (части без текстуры) и после шага 3 (текстура + PBR).
   Этапу 3 нужны оба файла с одинаковой геометрией по частям (HANDBOOK §4.2, ключ `sources`; проверку делает стадия
   `prepare` h2_bake).

Ретопологии, Segment, Smart UV, клонов, Upscale, рига и анимаций Tripo в маршруте нет (§4).

Как это выглядит в Studio (пилот 2026-10-13, Achilles `b467cd91`, Angel `b2c2b9dc`, Ancient Leshen `fd1d4e21`):

- После генерации по частям задача открывается по адресу `/workspace/segmentation/<uuid>` со списком
  `tripo_part_N`; GLB шага 1 экспортируется отсюда («Экспорт» → GLB → «Экспорт»).
- «Текстура» на открытой задаче (`/texture-edit/<uuid>`) уже содержит виды этой задачи; «Удалить освещение» и 8K
  форма помнит с прошлого запуска — проверить глазами, цена 30. «PBR» — `/texture-pbr/<uuid>`, цена 5.
- Текстура и PBR идут на той же плитке «Ассетов» («Gerando Textura…», «Генерация PBR…»). Самая новая плитка — самая
  новая **задача**, а не операция.
- После PBR кнопка «Создать PBR 5» снова активна: повторный клик спишет ещё раз. Экспорт делать кнопкой «Экспорт»
  внизу (разрешение текстуры 8k).
- Имя файла экспорта — подпись Studio («ancient warrior 3d model.glb»), не задача: переименовать при переносе в
  `source/` по §7.
- Генерацию следующего героя можно запускать, пока у предыдущего идёт текстура: Studio ставит задачи в очередь
  («В очереди»). Время: генерация ≈ 2 мин, текстура 8K ≈ 3–4 мин, PBR ≈ 1–2 мин.
- Тонкое оружие приходит несколькими частями (копьё Achilles — 2, меч Angel — 2: клинок с гардой и рукоять).

### 5.2 «Черновик» — шаг 1b этапа 1

Нужен, чтобы перерисовать виды поверх ортопроекций одной модели. Иначе front/side/back расходятся по силуэту, и
Tripo строит фантомы (HANDBOOK §3.1, шаг 1).

Имена и каталоги черновика задаёт `references/concept-sheet.md` (раздел 3 «каталоги», раздел 7 «шаг 1b»); ниже они
повторены дословно. При расхождении действует concept-sheet.

1. Вход — один файл: утверждённый дизайн-front шага 1a
   `art/imagegen/concept-<CONTENT_KEY>-codex/design/<CONTENT_KEY>-front.png`.
2. Лимит и условия — §1, пункты 3–5 (§6 шаг 1).
3. CLI-учёт входов в `<ASSET_DIR>/<YYYYMMDD>-draft-tripo/generation-request/` — те же шаги §6, что у героя, с отличиями
   черновика (все обязательны, иначе §7 и §9 не сходятся):
   - §6 шаг 2: `init --primary-source tripo-pending --primary-role draft-glb`;
   - §6 шаг 3: проверка дублей с одним аргументом `front=<путь дизайн-front>`;
   - §6 шаг 4: `prepare-generation --dry-run --mode single-image --view front=<путь дизайн-front>`.
4. **Модель → «HD модель»**, одно изображение, H3.1, «Приватность» вкл., «по частям» **выкл.**, «Текстура 8K»
   **выкл.**, остальное по умолчанию формы. Цену читать с кнопки (ожидается ≈ 30).
5. Строка журнала сразу после операции (§6 шаг 6) с `--note "этап 1b: черновик"`.
   5а. **uuid задачи.** Адрес вкладки после «Создать» не меняется, пока открыта прежняя модель (пилот 2026-10-13: 12
   черновиков). uuid новой задачи — клик по самой новой плитке «Ассетов» (первая после «Загрузить 3D-модель»), затем
   адрес вкладки `…/workspace/<generate|segmentation>/<uuid>`.
6. Экспорт GLB → `<ASSET_DIR>/<YYYYMMDD>-draft-tripo/source/<CONTENT_KEY>-draft-tripo-<task8>.glb`, проверка
   контейнера (§6 шаг 7).
7. Source-spec `source-specs/tripo-<task8>-draft.json` с обязательными полями §6 шага 8 (`source_id` =
   `tripo-<task8>-draft`, `generation.mode` = `single-image`, одна роль файла `draft-glb`) и `register-source` в
   `generation-request/` черновика (§6 шаг 8). `register-source` проверяет, что файлы из `evidence` spec существуют:
   до него положить заготовку `reports/tripo-run.json` (`{}`), иначе отказ «evidence file missing»; полный отчёт —
   п. 8 (пилот 2026-10-13). То же у героя (§6 шаги 8, 10).
8. Отчёт `<YYYYMMDD>-draft-tripo/reports/tripo-run.json` (§6 шаг 10: настройки формы, цена, баланс до и после,
   `findings`), затем вернуть настройки Studio (§6 шаг 11). Превью §6 шага 9 у черновика заменяют ортопроекции п. 9.
9. Ортопроекции — команда concept-sheet раздела 7 п. 2 (аспект — его раздел 4.2):

   ```bash
   python tools/art/concept/draft_orthos.py \
       --glb art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/source/<CONTENT_KEY>-draft-tripo-<task8>.glb \
       --out art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-draft-tripo/orthos \
       --views front,left,back,right --aspect 3:4
   # winged-biped: --aspect 4:3; → orthos/ortho_<view>.png + orthos/ortho-framing.json; код 0/1
   ```

   Осмотр орто, выбор `SIDE_VIEW` и числа рамки для 1c — concept-sheet раздел 7 пп. 3–5.
10. Черновик — не исходник героя. Он не идёт в этап 3, его GLB в git не коммитится (как сырые GLB, §7). Каталог
   `orthos/` идёт в git (concept-sheet раздел 3).

Проп с осевой симметрией может пропустить 1b (виды — перерисовка front; `references/concept-sheet.md`).

### 5.3 Проп — этап 2

HANDBOOK §3.2 п. 4 и §5. Режим — **multi-view**, не одно изображение:

- осесимметричный проп (бочка): `front` + `left` (side в LEFT) — `ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json`;
- асимметричный (фонарь с дверцей): `front` + `back` — `tripo-26bb832e.json`.

Настройки: H3.1, «Геометрия и текстура», текстура 2K, PBR, треугольники, «Приватность»; 8K и «по частям» выкл.
Полигоны в форме — по `POLY_BUDGET` заявки (бочка: 4000, генерация 45 вместо 55). Smart UV или ремеш — только если
первый прогон `static_prop_candidate.py` (HANDBOOK §5 п. 2) упирается в UV или сетку исходника; решение записать в
`reports/tripo-run.json`.

### 5.4 Брак генерации и повтор

**Правило счёта (одно, решение скилла по гейту SKILL.md §5 п.3 и HANDBOOK §0.3 п. 1).** Генерация — любой результат
модели: платная генерация, «Бесплатный повтор», генерация с исправленным слотом. Отклонённых подряд может быть не
больше одной: **вторая отклонённая подряд → стоп** (гейт SKILL.md §5 п.3), новая платная генерация — только после ответа
пользователя. Принятая генерация обнуляет счёт. Так один брак стоит не больше одной лишней генерации.

1. Явный брак виден на превью шага 9 §6: второе оружие, двуликая голова, лишняя рука, нет части, двоение крыла.
   Брак записывается в `reports/tripo-run.json` (`findings`). Строка журнала за списанную операцию уже есть
   (§6 шаг 6) и не удаляется. Счёт отклонённых = 1.
2. Единственная следующая попытка выбирается так:
   - ошибка слота (§5.5) → исправить слот и сделать платную генерацию в **новом** run-каталоге (на ту же дату —
     суффикс `-2`, решение скилла);
   - слоты верны и форма показывает «Бесплатный повтор» с ценой `0` → повтор (строка журнала с `--quoted 0`,
     `--note "этап 2: бесплатный повтор"`; `--service-task-id` — uuid задачи повтора, а если Studio оставила прежний
     uuid — суффикс `#retry`, решение скилла: поле уникально, §6 шаг 6);
   - слоты верны, бесплатного повтора нет → платная генерация в новом run-каталоге.
3. Результат этой попытки отклонён → стоп, гейт стопа SKILL.md §5 п.3. Пользователю — пакет: оба превью, `findings`, цена
   следующей попытки и остаток ВР-04.
4. Дефект, который виден только после сборки, решает приёмка этапа 4 вердиктом `return_to_stage_2`
   (`references/acceptance-and-blender.md`). Тогда этап 2 повторяется новым run-каталогом; счёт отклонённых
   начинается с 1 (отклонена генерация, на которой собиралась модель).

Черновик шага 1b считает так же (concept-sheet раздел 7 п. 3: «Две неудачные генерации подряд → стоп»).

### 5.5 Слоты видов: одно правило

Конвенция проекта: `left` — собственный **левый** бок персонажа к камере, лицо смотрит **влево по кадру**; `right` —
наоборот (`docs/art-pipeline/imagegen-inputs/CONSISTENCY-REVIEW.md`, абзац «Соглашение о сторонах»).

**Правило.** Слот Tripo = бок, который реально нарисован. Side этапа 1 рисуется поверх `ortho_<SIDE_VIEW>`. При
дефолте `SIDE_VIEW: left`: `FRONT` = front, `LEFT` = side, `BACK` = back, `RIGHT` пусто (HANDBOOK §3.2 п. 3). Перед
загрузкой проверить по картинке side: лицо смотрит влево по кадру; при `WEAPON_HAND: left` оружие у ближней к камере
руки, при `right` — за корпусом или поверх груди. При `SIDE_VIEW: right` (лицо вправо по кадру) side идёт в `RIGHT`,
а `LEFT` пуст. Если бок на картинке не совпал с `SIDE_VIEW` карточки — это брак вида этапа 1: не загружать, вернуть
вид на этап 1 (кредиты Tripo ещё не потрачены). Подавать левый вид в `RIGHT` (или правый в `LEFT`) запрещено. Это зеркалит вид и даёт фантомы (HANDBOOK §7.1).

Доказательства:

| Прогон | Что нарисовано | Слот | Итог |
|---|---|---|---|
| Medusa H2 `40c4d1cd` | левый вид | LEFT | согласовано |
| Merlin H2 `de0654b5` | правый вид `art/imagegen/hero-quality-v1/merlin/merlin-side.png` (поверх `ortho_right`) | RIGHT | согласовано (`source-specs/tripo-de0654b5-h2.json` `generation.views.right`) |
| Merlin h31 `d9ff4260` | правый вид `art/imagegen/mvp-v1/characters/ref-merlin-v3-right.png` | RIGHT | согласовано (`source-specs/tripo-d9ff4260.json`) |
| Arthur H2 `c24eeff0` | левый вид | RIGHT | расхождение (tripo-run, `slot_consistency`) |
| Harpy H2 `330872a3` | левый вид | RIGHT | двуликая голова; исправлено H3 `bca735a3` с side в LEFT (`source-specs/tripo-bca735a3-h3.json`, `slot_note`) |

`SIDE_VIEW` окончательно фиксируется на шаге 1b: запускающий агент выбирает бок глазами по `ortho_left.png` и пишет
его в карточку (`references/concept-sheet.md` раздел 4.1 «Выбор SIDE_VIEW», раздел 7 п. 4). Дефолт — `left`; `right`
только при `WEAPON_HAND: right` и закрытой корпусом кисти с оружием на `ortho_left` (прецедент Merlin). На этапе 2
слот side = значение `SIDE_VIEW` карточки, а картинка side проверяется по правилу выше.

## 6. Протокол этапа 2 (команды)

Из корня репозитория; в Git Bash сначала `export MSYS_NO_PATHCONV=1`.

```bash
T="python tools/tripo-pipeline/tripo_pipeline.py"
A=art/pipeline-candidates/<ASSET_ID>
RUN=$A/<YYYYMMDD>-h2-tripo                 # проп: <YYYYMMDD>-prop-tripo; черновик: <YYYYMMDD>-draft-tripo (решение скилла)
C=art/imagegen/concept-<CONTENT_KEY>-codex # принятые виды этапа 1
```

1. **Лимит и условия** — §1, пункты 3–5.

2. **CLI-пакет запроса.** Каталог `generation-request/` — CLI run для учёта входов. `init` идёт **раньше**
   `prepare-generation`; без него `prepare-generation` завершается кодом 2 «run is not initialised»
   (`tripo_pipeline.py:530-531`). `--primary-source tripo-pending` — источника ещё нет (прецедент
   `art/pipeline-candidates/ASSET-TABLE-BASE-001/20260928-table-base-tripo-h31/generation-request/manifest.json`).
   Тот же порядок — HANDBOOK §3.2 п. 2.

   ```bash
   $T init --run-dir $RUN/generation-request --asset-id <ASSET_ID> \
       --primary-source tripo-pending --primary-role h2-parts-glb   # проп: source-glb; черновик: draft-glb
   ```

3. **Проверка дублей по всем прогонам.** `prepare-generation` ищет дубль только среди источников, уже
   зарегистрированных в **этом** run-каталоге (`tripo_pipeline.py:3796-3805`). В новом каталоге он дубля не увидит.
   Поэтому до клика сверить sha256 входов со всеми source-spec репозитория:

   ```bash
   python - front=$C/<CONTENT_KEY>-front.png <SIDE_VIEW>=$C/<CONTENT_KEY>-side.png back=$C/<CONTENT_KEY>-back.png <<'EOF'
   import glob, hashlib, json, sys
   mine = {s: hashlib.sha256(open(p, "rb").read()).hexdigest() for s, p in (a.split("=", 1) for a in sys.argv[1:])}
   hits = 0
   for spec in sorted(glob.glob("art/pipeline-candidates/*/source-specs/*.json")):
       gen = json.load(open(spec, encoding="utf-8")).get("generation") or {}
       reg = {s: (v or {}).get("sha256") for s, v in (gen.get("views") or {}).items() if v}
       if set(mine.values()) & set(reg.values()):
           hits += 1
           print("SAME-SLOTS" if reg == mine else "SHARED-INPUTS", spec, gen.get("mode"), sorted(reg))
   print("matches:", hits)
   sys.exit(1 if hits else 0)
   EOF
   ```

   Аргументы — те же слоты и файлы, что пойдут в шаг 4: `<SIDE_VIEW>` = `left` или `right` из карточки (§5.5). Проп —
   его слоты (§5.3): `front` + `left` (осесимметричный) или `front` + `back` (асимметричный), без лишних аргументов.
   Черновик — один аргумент `front=…/design/<CONTENT_KEY>-front.png`.

   Код 0 — продолжать. `SAME-SLOTS` — стоп: такая генерация уже оплачена (HANDBOOK §0.3 п. 2). `SHARED-INPUTS`
   (тот же файл в другом слоте или наборе) — продолжать только с причиной в `reports/tripo-run.json`. Прецедент:
   Harpy H3 повторила входы H2 со сменой слота RIGHT → LEFT.

4. **Пакет входов** (в сеть не ходит, ничего не платит):

   ```bash
   $T prepare-generation --run-dir $RUN/generation-request --dry-run --service tripo-studio --mode multi-view \
       --model-label "H3.1" --view front=$C/<CONTENT_KEY>-front.png \
       --view <SIDE_VIEW>=$C/<CONTENT_KEY>-side.png --view back=$C/<CONTENT_KEY>-back.png
   # код 0 — пакет generation-requests/<key16>.json; 1 — проблема входа (формат, > 20 МБ);
   # 3 — дубль внутри run; обход только --allow-duplicate --duplicate-reason "почему"
   ```

   Имена файлов видов — по `references/concept-sheet.md` (`<CONTENT_KEY>-<view>.png`). `<SIDE_VIEW>` — `left` или
   `right` из карточки (§5.5). Проп — `--mode multi-view` с его двумя слотами (§5.3); черновик —
   `--mode single-image --view front=…/design/<CONTENT_KEY>-front.png`.

5. **Перед каждой операцией Studio:** записать в `reports/tripo-run.json` настройки формы до изменений
   (`studio_settings_before`; при нескольких героях подряд — один раз на героя, если форма уже стоит на настройках
   §5.1 от предыдущего); снять баланс; прочитать цену с кнопки; предпроверка
   `python tools/art/visual/ledger.py check --service tripo --next-cost <цена с кнопки> --balance <баланс> --model "Tripo Studio H3.1"`
   → код 0. Код 1 → стоп (гейт SKILL.md §5 п.3).

6. **Операция → строка журнала сразу после неё:**

   ```bash
   python tools/art/visual/ledger.py add --task <VISUAL_CARD_ID> --template T-TRIPO-PART --service Tripo \
       --model "Tripo Studio H3.1" --units "multi-view, по частям (Баланс), Ultra 2M, без текстуры" \
       --quoted 60 --before <баланс до> --after <баланс после> --service-task-id <task uuid> \
       --result $RUN/source/ --note "этап 2: generate"
   ```

   `--service-task-id` в журнале уникален (`ledger.py:422`). Текстура и PBR идут на той же задаче, поэтому у их
   строк суффикс: `<task uuid>#texture-8k`, `<task uuid>#pbr` (решение скилла). Черновик — `--note "этап 1b:
   черновик"`. Неудачная операция тоже пишется (`--status failed` или `refunded`). Расхождение цены и списания
   больше 0,5 инструмент сам дописывает в `note`. Команда проверена на копии журнала 2026-10-09.

7. **Экспорт GLB.** Одна загрузка за раз. Chrome оставляет `C:/Users/ren/Downloads/<guid>.tmp`; свой диалог
   сохранения закрыть до передачи браузера (HANDBOOK §3.2 п. 6). Переложить в `$RUN/source/` под именами §7 и
   проверить контейнер и структуру:

   ```bash
   python - $RUN/source/*.glb <<'EOF'
   import struct, sys
   from pathlib import Path
   sys.path.insert(0, "tools/tripo-pipeline")
   from tripo_pipeline import inspect_glb, sha256_file
   for p in map(Path, sys.argv[1:]):
       b = p.read_bytes()
       magic, ver, length = struct.unpack_from("<4sII", b, 0)
       off = 12
       while off + 8 <= len(b):
           off += 8 + struct.unpack_from("<I", b, off)[0]
       g = inspect_glb(p)
       ok = magic == b"glTF" and ver == 2 and length == len(b) and off == len(b)
       print(p.name, "container", "OK" if ok else "FAIL", "bytes", len(b), "sha256", sha256_file(p),
             "meshes", g["mesh_count"], "tris", g["triangles"], "materials", g["materials"],
             "images", g["images"], "skins", g["skins"])
   EOF
   ```

   Ожидание для H2: оба файла `container OK`. `meshes` и `tris` у `-parts<N>` и `-tex8k-pbr` равны. У parts —
   `materials 1`, `images 0`. Число частей N = `meshes`. `skins 0` везде. Проверено на Harpy H3: 19/19 мешей,
   1 930 656 tris.

8. **Source-spec** `$A/source-specs/tripo-<task8>-h2.json` по схеме `unmatched.tripo-pipeline.source-spec/1`
   (HANDBOOK §3.3). Собирать **по образцу** `ASSET-MEDUSA-001/source-specs/tripo-40c4d1cd-h2.json`, не по списку.
   Что проверяет `validate_spec` (`tripo_pipeline.py:835-868`; нарушение → код 2 «source spec invalid»):

   | Поле | Значение |
   |---|---|
   | `schema` | `unmatched.tripo-pipeline.source-spec/1` |
   | `source_id` | `tripo-<task8>-h2` (это же значение — `--primary-source` этапа 7; черновик `tripo-<task8>-draft`) |
   | `asset_id`, `task_id` | `<ASSET_ID>`; полный uuid задачи |
   | `service` | `tripo-studio` (API — `tripo-api`) |
   | `generation.mode` | `multi-view` (≥ 2 непустых слота) или `single-image` (1 слот) |
   | `operations[]` | у каждой `op` (`generate`, `texture`, `pbr`); цены и балансы — в `operations[].credits`: `unit: "studio-credits"`, `quoted`, `observed_debit`, `balance_before`, `balance_after` |
   | `files[]` | роли уникальны и непусты: `h2-parts-glb`, `h2-tex8k-pbr-glb` |

   По образцу, без проверки валидатором, но нужны этапу 3 и аудиту: `task_url`, `generation.views` (слот → `path` +
   `sha256`, пустой слот `null`), `generation.slot_note` и `generation.settings` (внутри `generation`, не на верхнем
   уровне), у `files[]` — `path`, `expected_sha256`, `expected_bytes`, `produced_by`, `in_git: false`;
   `expectations` из шага 7. Проверка spec против файлов:

   ```bash
   $T register-source --run-dir $RUN/generation-request --spec $A/source-specs/tripo-<task8>-h2.json
   # "registered tripo-<task8>-h2 (2 files, …; this command spent 0)", код 0
   ```

   После регистрации повтор шага 4 с теми же входами вернёт код 3: дубль защищён внутри этого run.

9. **Превью и осмотр:**

   ```bash
   python tools/art/concept/draft_orthos.py --glb $RUN/source/<CONTENT_KEY>-h2-tripo-<task8>-tex8k-pbr.glb \
       --out $RUN/preview --views front,left,back,right --aspect 3:4   # winged-biped: --aspect 4:3
   ```

   Открыть все `ortho_*.png` и виды концепта инструментом Read и сравнить глазами. Нужно: одна фигура, одна
   подставка, оружие на стороне `WEAPON_HAND` во всех видах, нет второго оружия, лишней руки или второго лица; у
   крылатых ровно два крыла. Число частей и роли (тело, лицо, кисти, оружие, подставка) записать в
   `reports/tripo-run.json` — их возьмёт профиль этапа 3 (HANDBOOK §4.2, ключ `parts`). Брак → §5.4.
   Габариты частей считать по буферу вершин, не по `accessor.min/max`: Tripo пишет `min[1] = 2.2e-308` (DBL_MIN),
   и у всех частей выходит «низ = 0» (пилот 2026-10-13, все три героя). Оси glTF: Y вверх, фронт фигуры +Z,
   правая сторона фигуры — −X (слева по кадру front).

10. **Отчёт** `$RUN/reports/tripo-run.json` по схеме `unmatched.tripo-pipeline.studio-run-evidence/1` (образец —
    `ASSET-MEDUSA-001/20260929-h2-tripo/reports/tripo-run.json`): `performed_by` (агент или пользователь),
    `generation` со `slot_mapping` и `slot_consistency`, `operations[]`, `exports[]` (sha256, bytes, итог шага 7),
    `credits` (`this_hero_total_observed`, ссылка на журнал `docs/game-design/visual/credits-ledger.json`), `findings`.
    И `claims`: `art_accepted: false`, `game_ready: false`, `budgets_declared: false`.

11. **Вернуть настройки Studio** из `studio_settings_before`: они сохраняются на аккаунт (HANDBOOK §3.2 п. 7).
    Закрыть свою вкладку. При нескольких героях подряд — после последнего героя пачки; вкладку пользователя, в которой
    Studio была открыта до прогона, не закрывать.

## 7. Каталоги и имена

```
art/pipeline-candidates/<ASSET_ID>/
  .gitignore                                   # этап 0; строки для сырых GLB — ниже
  source-specs/tripo-<task8>-h2.json           # герой; черновик: tripo-<task8>-draft.json; проп: tripo-<task8>.json
  <YYYYMMDD>-draft-tripo/                      # шаг 1b (имена — references/concept-sheet.md раздел 3)
    generation-request/                        # CLI run черновика (§6 шаги 2–4)
    source/<CONTENT_KEY>-draft-tripo-<task8>.glb
    orthos/ortho_{front,left,back,right}.png, orthos/ortho-framing.json   # выход draft_orthos.py, в git
    reports/tripo-run.json
  <YYYYMMDD>-h2-tripo/                         # этап 2 героя
    generation-request/                        # CLI run: manifest.json, journal.jsonl, generation-requests/
    source/<CONTENT_KEY>-h2-tripo-<task8>-parts<N>.glb
    source/<CONTENT_KEY>-h2-tripo-<task8>-tex8k-pbr.glb
    preview/ortho_{front,left,back,right}.png, ortho-framing.json
    reports/tripo-run.json
  <YYYYMMDD>-prop-tripo/                       # этап 2 пропа: generation-request/, source/, reports/ так же
    source/<CONTENT_KEY>-tripo-<task8>-<состояние>.glb   # по образцу бочки: -source, -smartuv-tex2k-pbr
```

- Имена файлов — по фактическим прогонам H2 и H3 (`medusa-h2-tripo-40c4d1cd-parts17.glb`,
  `harpy-h3-tripo-bca735a3-tex8k-pbr.glb`), так же в HANDBOOK §3.2 п. 6. Роль файла задаёт source-spec. `<task8>` —
  первые 8 символов uuid задачи.
- `source/` лежит рядом с `generation-request/`, а не внутри CLI run. `register-source` отказывает, если оригинал
  внутри run-каталога (HANDBOOK §3.3).
- Сырые GLB (45–79 МБ) в git не идут. В `.gitignore` ассета строка `*-tripo/source/*.glb` (шаблон `references/intake-and-evidence.md` §3)
  ловит `-h2-tripo`, `-draft-tripo` и `-prop-tripo`. Проверка:
  `git check-ignore -v <файл>`. Файлы закреплены sha256 и bytes в source-spec. В чистом checkout их нет; это
  известно (HANDBOOK §3.3).
- Новый прогон — всегда новый каталог (HANDBOOK §4.1).

## 8. Чек-лист пользователю (если Studio выполняет он)

Агент заполняет угловые скобки и отдаёт список целиком. Пользователь присылает цены, балансы, uuid задачи и пути
скачанных GLB.

1. Открыть studio.tripo3d.ai в одной вкладке. Записать баланс.
2. «Модель» → «HD модель» → «Из нескольких видов». Загрузить: FRONT ← `<путь front>`, `<LEFT|RIGHT>` ← `<путь
   side>`, BACK ← `<путь back>`. Свободный боковой слот оставить пустым.
3. H3.1 «Макс. кач.»; «по частям» — Баланс; ультра-сетка 2M; треугольники; «Геометрия и текстура» — выкл.;
   «Текстура 8K» — выкл.; «Приватность» — вкл. Сообщить цену на кнопке (ожидается 60). Нажать, записать баланс и
   uuid из адреса задачи.
4. Скачать GLB (частей без текстуры).
5. «Текстура» на этой задаче: 8K, «Удалить освещение». Сообщить цену (30, или 0 при пробе). Нажать, записать баланс.
6. «PBR». Сообщить цену (5). Нажать, записать баланс. Скачать GLB.
7. Вернуть настройки формы, как было до шага 2. Закрыть вкладку.

Не нажимать: «Делить», «Ремеш», «Smart UV», «Увелич», «Правка», «Риг», «Анимация», «Send To».

## 9. Чек-лист выхода этапа 2

- [ ] Каждая операция: цена с кнопки до клика и `ledger.py check --service tripo --next-cost <цена> --balance <баланс>`
      код 0; строка `ledger.py add` сразу после; `ledger.py check` — `check OK`.
- [ ] Строка `providerTerms` Tripo (ВР-05) есть; карточка `<VISUAL_CARD_ID>` есть в 06-tasks.
- [ ] Проверка дублей §6 шаг 3 — 0 совпадений `SAME-SLOTS`. Пакет `prepare-generation` — код 0.
- [ ] Слот side по §5.5 записан в `slot_note` и `slot_mapping`.
- [ ] Оба GLB: `container OK`, геометрия parts = tex8k-pbr, `skins 0`; sha256 и bytes в source-spec и
      `exports[]`.
- [ ] `register-source` — код 0.
- [ ] Превью `ortho_*` открыты и осмотрены глазами против концепта. Брака §5.4 нет. Роли частей записаны.
- [ ] Сырые GLB игнорируются git (`git check-ignore`).
- [ ] `claims` все `false`. Художественный статус ставит только приёмка этапа 4: при `pass` — «художественно
      принято, по делегированию» (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`).
      Статус без этой пометки ставит только пользователь.
- [ ] Настройки Studio возвращены, вкладка закрыта.

Дальше — этап 3: профиль `<content-key>-h2-bake-h2.json`, ключ `sources` берёт source-spec и оба GLB
(`references/acceptance-and-blender.md`, HANDBOOK §4.2).

## 10. API v3 (не вызывался; справочник покрытия)

Нормой не является (§2). Нужен только если пользователь даст API-ключ. Тогда кредиты — `api-credits`, отдельно от
Studio (`tripo_pipeline.py:312` `SERVICES`), строка журнала та же, модель — `"Tripo API <model>"`.

- База: `https://openapi.tripo3d.ai/v3` (зеркало `openapi.tripo3d.com/v3`); заголовок `Authorization: Bearer <key>`.
  Ключ создаётся в консоли developers.tripo3d.ai (migration-гайд:
  https://developers.tripo3d.com/assets/developer/tripo-v2-to-v3-migration/SKILL.md). Переменной ключа в репо нет.
- Задачи асинхронные: POST → `task_id` → `GET /v3/tasks/{task_id}`, статусы `queued | running | success | failed |
  cancelled` (`banned`/`expired` стали `failed` + `error_code`). Результат — `output.model_url`. Пачкой —
  `POST /v3/tasks/list` (≤ 100). Вебхуки `task.completed`/`task.failed`. 429: код 1007 — квота создания в минуту,
  2000 — лимит параллельных задач; повтор с паузой.
- Поле модели генерации **обязательно**, умолчания нет: `"model"` (или старое имя `model_version`) —
  `v3.1-20260211` | `v3.0-20250812` | `v2.5-20250123` | `P1-20260311`.

| Эндпоинт (POST, `/v3/…`) | Аналог Studio | Цена API, кредиты | Применяем | Ключевые параметры |
|---|---|---|---|---|
| `generation/image-to-model` | Модель, одно изображение | 20 без текстуры / 30 с текстурой | нет (§2) | `input`: file_token \| URL \| task_id |
| `generation/multiview-to-model` | Модель, из нескольких видов | 20 / 30; +HD-текстура 10, +8K 20, +HD-геометрия 20, +Quad 5, +Smart Low-poly 10, +Parts 20 | нет | `inputs`: массив объектов, по одному ключу `front`/`left`/`back`/`right` в каждом; front обязателен, минимум 2 |
| `generation/text-to-model` | — | 10 / 20 | нет | `prompt` |
| `generation/text-to-image`, `image-to-image` | Изображение | 5–20 на базовом качестве (seedream 5; banana 5; banana2, chat_image 10–15; banana_pro 15–20); 20–50 с уровнями `high`/`xhigh`/`max` у chat_image | нет | концепт — Codex |
| `generation/image-to-multiview`, `edit-multiview` | — | 10; 5 за изображение | нет | виды — Codex по сетке |
| `generation/image-to-splat` | — | не опубликована | нет | сплаты не идут в пайплайн |
| `models/texture` | Текстура | fast/standard 10, HD 20, 8K 30 | нет | `input`, `model` (версия текстуры), `texture_prompt`, `pbr`, `texture_quality`, `bake`, `delight`, `part_names` |
| `models/refine` | — | не опубликована | нет | принимает только черновики text_to_model |
| `models/stylize` | — | не опубликована | нет | lego, voxel, voronoi, minecraft и др. |
| `models/convert` | Экспорт | basic 5 / advanced 10 | нет | `format`, `fbx_preset`, `texture_size`, `pack_uv` |
| `models/import` | — | не опубликована | нет | своя модель ≤ 150 МБ |
| `mesh/segment` | Делить | 40 | нет | `input`; `model` `v1.0-20250506` (по умолчанию, геометрическая) \| `v2.0-20260430` (Beta, семантическая); v2: `segmentation_granularity`, `split_by_connectivity`, `ref_image` |
| `mesh/smartsegment` | — | 55 по модели / 85 по изображению | нет | интерактивная сегментация |
| `mesh/complete` | Докомпл | 50 / quick_cap 30 | нет | `completion_mode`, `part_names` |
| `mesh/decimate` | Ремеш | v2.0 30 / v1.0 10 | нет | `input`, `model`, `face_limit`, `quad`, `bake`, `part_names` (не для v1.0) |
| `animations/rig-check` | — | 0 | нет | проверка годности |
| `animations/rig` | Риг | 25 (в примере ответа — 30) | **нет** (HANDBOOK §3.2) | `input`; `model` `v1.0-20240301` (бипед) \| `v2.5-20260210` (не-гуманоиды); `rig_type`; `spec` tripo\|mixamo; `out_format` |
| `animations/retarget` | Анимация | 10 за анимацию | нет | пресеты на заригованную модель |
| `files`, `files/presign`, `files/upload-credentials`; GET `account/balance`, `account/usage` | — | 0 | — | баланс — дробное число |

Источники цен и параметров: https://developers.tripo3d.ai/en/pricing (1 кредит = $0,01; цены P-серии, сплатов,
stylize, refine, import не опубликованы), https://developers.tripo3d.com/en/docs/generation-multiview-to-model/standard.md,
https://developers.tripo3d.ai/en/docs/models-texture.md, https://developers.tripo3d.ai/en/docs/mesh-segment.md,
https://developers.tripo3d.ai/en/docs/mesh-decimate.md, https://developers.tripo3d.ai/en/docs/animations-rig.md,
migration-гайд выше (список эндпоинтов). Всё снято 2026-10-09.

Ловушки параметров (те же доки):

- `delight` читает **только** текстурная модель `v3.5-20260815`. По умолчанию для геометрии v3.x текстура —
  `v3.0-20250812`, и `delight: true` молча игнорируется: запечённый свет остаётся в BC. На генерации ставить
  `"texture_version": "v3.5-20260815"`, на `models/texture` — `"model": "v3.5-20260815"`.
- `generate_parts` требует `texture: false` и `pbr: false`. Без явных значений запрос отклоняется кодом 1004.
  С `quad` части приходят треугольниками; `smart_low_poly` отменяет части.
- `quad: true` форсирует FBX. `export_orientation` не ставить, если модель пойдёт в постобработку.
- Ретопология, сегментация и completion выполняются до рига: риг — только на финальной топологии
  (`docs/research/2026-09-27-animation-audit/services.md`).

Пример — эквивалент маршрута H2 (не вызывался):

```bash
curl -s https://openapi.tripo3d.ai/v3/generation/multiview-to-model \
  -H "Authorization: Bearer $TRIPO_API_KEY" -H "Content-Type: application/json" \
  -d '{"inputs": [{"front": "<file_token>"}, {"left": "<file_token>"}, {"back": "<file_token>"}],
       "model": "v3.1-20260211", "geometry_quality": "detailed", "face_limit": 2000000,
       "generate_parts": true, "texture": false, "pbr": false}'

curl -s https://openapi.tripo3d.ai/v3/models/texture \
  -H "Authorization: Bearer $TRIPO_API_KEY" -H "Content-Type: application/json" \
  -d '{"input": "<task_id генерации>", "model": "v3.5-20260815", "texture_quality": "extreme",
       "delight": true, "pbr": true}'
```

```python
# опрос задачи до конечного статуса (не вызывался)
import json, time, urllib.request

def poll(task_id, key, every_s=5):
    while True:
        req = urllib.request.Request(f"https://openapi.tripo3d.ai/v3/tasks/{task_id}",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req) as r:
            data = json.load(r)["data"]
        if data["status"] in ("success", "failed", "cancelled"):
            if data["status"] != "success":
                print("task", task_id, data["status"], data.get("error_code"))
            return data                      # success -> data["output"]["model_url"]
        time.sleep(every_s)
```

## 11. Типовые ошибки

| Признак | Причина | Действие |
|---|---|---|
| Второй меч, рука или лицо; двуликая голова | вид в чужом слоте | §5.5; перегенерация с правильным слотом (HANDBOOK §7.1) |
| `prepare-generation` код 2 «run is not initialised» | не было `init` | §6 шаг 2 |
| `prepare-generation` код 3 | те же входы, mode и service уже зарегистрированы в этом run | не повторять. Обход — `--allow-duplicate --duplicate-reason` с причиной |
| `ledger.py add` код 2 «is not a card in 06-tasks» | нет карточки | §1 п. 3 |
| `ledger.py add` код 2 «service_task_id … already in the ledger» | вторая операция на той же задаче | суффикс `#texture-8k` / `#pbr` |
| `ledger.py check` ERROR `no providerTerms row for Tripo` | трата до записи условий | `ledger.py terms …` (§1 п. 4); строку траты не удалять |
| `ledger.py check --next-cost` ERROR про visual cap 54 | цена Tripo подана в предпроверку SYNTX (без `--service`) | `check --service tripo --next-cost …` (§1) |
| GLB `container FAIL` | Chrome не дописал загрузку | скачать заново, одна загрузка за раз |
| `tris` у parts и tex8k-pbr различаются | файлы от разных задач или версий | скачать оба из одной задачи; иначе этап 3 откажет на `prepare` |
| Серый камень обрезан по краю | серый на сером фоне | отметить до генерации (HANDBOOK §7.1) |
| Металл выглядит пластиком | PBR Tripo даёт metallic 0,07–0,095 | металл-маска на этапе 3 (HANDBOOK §7.1) |
| Smart UV: «не поддерживает модели из нескольких частей» | многочастная модель | в маршрутах H2 и пропа Smart UV по умолчанию нет (§4) |

## 12. История, не образец

Маршрут h31 (multi-view 4K → Segment → Quad-ремеш → клон → Smart UV → 2K → PBR, 190–210 кредитов, профиль
`skeletal-candidate`) и раскладка `blender/ASSET-MEDUSA-001/tripo-source/` — история поколения до H2. Для новых
ассетов не использовать (HANDBOOK §1 «Не использовать как образец»; входы mvp-v1 — HANDBOOK §3.1).
Цифры h31 в §4 — только замеры цен инструментов.

## Источники

- `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` §0.3, §1, §3.1–3.3, §4.1–4.2, §5, §7.1
- `art/pipeline-candidates/ASSET-{MEDUSA,KING-ARTHUR,MERLIN,HARPY}-001/20260929-h2-tripo/reports/tripo-run.json`;
  `ASSET-HARPY-001/source-specs/tripo-bca735a3-h3.json`; `ASSET-*-001/20260928-tripo-h31/reports/tripo-run.json`
  (цены инструментов); `ASSET-DECOR-KIT-001/source-specs/tripo-{3f7a258f,26bb832e}.json` (проп)
- `docs/game-design/evidence/ART-004/tripo-production-20260927/README.md` — карта функций Studio
- `art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/README.md` — авториг, анимация, форматы экспорта
- `docs/art-pipeline/imagegen-inputs/CONSISTENCY-REVIEW.md` — конвенция сторон
- `tools/tripo-pipeline/tripo_pipeline.py` — `init`, `prepare-generation`, `register-source`, `inspect_glb`, коды
  выхода
- `tools/art/visual/ledger.py`, `docs/game-design/visual/credits-ledger.json`,
  `docs/game-design/visual/07-prompt-templates.md` §0.1, §3, §4 — журнал, лимиты, шаблон `T-TRIPO-PART`
- `docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md` — ВР-04, ВР-05, ВР-18
- Инструменты скилла: `tools/art/concept/draft_orthos.py` (CLI зафиксирован контрактом скилла)
