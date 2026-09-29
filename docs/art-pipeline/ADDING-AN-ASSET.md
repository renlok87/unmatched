# Как добавить следующий ассет (Tripo → CLI → Blender → UE → сцена → доказательства)

Срез: 2026-09-28, этап 3, T3.1 (исправления ревью 2026-09-29: посадка декора — §6, сквозные дыры подставки — §4.2 п. 4
и §6). Инструмент: `tools/tripo-pipeline/tripo_pipeline.py` 0.5.0 (логика UE-стадии
`ue-candidate/6`). Подробности каждой стадии — в [PIPELINE.md](PIPELINE.md); этот документ — порядок действий и правила
остановки. Проверен сухим повтором на бочке (раздел 11): каждое отступление исполнителя от текста считалось дефектом
инструкции и правилось здесь.

Статусы только такие: **предложено / измерено / технически импортировано / художественно принято**. Инструкция доводит
ассет максимум до «технически импортировано»; «художественно принято» ставит только арт-трек актом. Числа из отчётов —
измерения, а не бюджеты (бюджеты 04 §1 / 17 §4.5 остаются предложением до GD-058).

## 0. Прежде чем начать

**Окружение** (Git Bash, из корня главного checkout `C:/Users/ren/WebstormProjects/unmached/unmached`):

```bash
export MSYS_NO_PATHCONV=1      # иначе /Game/... превращается в C:/Program Files/Git/Game/... (стадия откажет, код 2)
export PYTHONIOENCODING=utf-8  # отчёты и профили содержат ≤, ≈, кириллицу; cp1251-консоль падает на print
T="python tools/tripo-pipeline/tripo_pipeline.py"
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
git -c core.longpaths=true status --short   # длинные пути art/animation-refs, *.fbm — всегда с core.longpaths
```

**Живые приложения** — только уже запущенные и выданные задаче:

- UnrealEditor главного checkout с MCP `127.0.0.1:8123` (проверка: `netstat -ano | grep ':8123 .*LISTEN'`). Если порт
  молчит — редактор не запущен; запуск по памяти `unreal-mcp-setup`: `UnrealEditor.exe <Unmatched.uproject>
  -ModelContextProtocolPort=8123 "-ExecCmds=ModelContextProtocol.StartServer 8123" -log`, записать PID.
  **UnrealEditor-Cmd на главном проекте запрещён**, пока открыт GUI-редактор.
- Blender :9876 / :9877 (`C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py`, `BLENDER_MCP_PORT`) — только для
  просмотра; без `read_factory_settings`, `SystemExit`, `sys.exit`, `os._exit` (завершат живой Blender). Всё, что должно
  дать байты (FBX, атлас), делается headless: `"$B" -b --factory-startup --python-exit-code 1 --python ...`.

**Чужое не трогать:** `/Game/ART004`, `/Game/ArtPreview`, `blender/ASSET-MEDUSA-001/`, сцены пользователя в Blender.
UE-ассеты кандидата живут только в `/Game/PipelineCandidates/<Hero>/<run>` (CLI отказывает вне этой папки).

**Правила остановки** (остановиться, записать причину в отчёт/акт и не обходить):

1. Цена операции Tripo (надпись на кнопке) выше остатка лимита ассета или окна (журнал кредитов
   `docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json`); две неудачные генерации подряд.
2. `prepare-generation --dry-run` вернул код 3 (такие входы уже генерировались) — не повторять без решения.
3. Любая проверка CLI не прошла (код 1), конфликт (код 3), нужен `resume` (код 5): сначала разобрать причину. Правка
   профиля — только новым файлом, если по старому уже был прогон.
4. Несоответствие контракту рига (`rig-contract.json`: 17 костей, кость 0 = объект арматуры, ≤ 4 влияний, масштаб 1).
5. В папке UE есть чужие ассеты, `Name_1`-дубли, в `/Game/ART004` или `/Game/ArtPreview` что-то изменилось
   (снимок до/после, раздел 5).
6. Редактор упал или ушёл в модальный диалог: не повторять ту же операцию; прочитать `unreal/Unmatched/Saved/Crashes/*/
   Unmatched.log`, перезапустить редактор той же командой, записать инцидент.

## 1. Реестр и входы

1. Запись ассета в [asset-registry.json](asset-registry.json) (`id`, `contentKey`, `manifest06Row`, `sourceImages`,
   `status: предложено`). Проверка: `python tools/tripo-pipeline/validate_registry.py` → `RESULT PASS`.
2. Пункты 3–4 — только если планируется **новая** генерация Tripo. Ассет с уже оплаченными задачами (и сухой повтор)
   их пропускает и идёт в раздел 3.
3. Виды для multi-view — только прошедшие `tools/tripo-pipeline/check_inputs.py` (T2). WARN — решение художника.
4. Пакет входов без отправки: `$T prepare-generation --run-dir <run> --dry-run --service tripo-studio --mode multi-view
   --model-label "H3.1" --view front=<png> --view left=<png> --view back=<png>`. Код 3 = дубль → правило остановки 2.

## 2. Tripo Studio (только при выделенном лимите кредитов)

Сухой повтор и любой ассет с уже оплаченными задачами этот раздел **пропускают**: 0 кредитов, Tripo не открывается,
исходники берутся из закоммиченного `source-spec` (раздел 3).

1. Одна своя вкладка Chrome («perosnal chrome», Claude in Chrome). Одна загрузка за раз.
2. Перед генерацией: «Приватный»; multi-view (не batch); H3.1; текстура 2K; PBR; Triangle; 8K и «по частям» выключены.
   Цена — с кнопки **до клика**; сравнить с лимитом (правило 1).
3. После каждой операции — баланс и строка истории (время, списание) в `evidence/<asset>-<дата>/tripo-run.json` и в
   журнал кредитов (`tools/art/syntx_video_refs/ledger_append.py` — формат журнала: отступ 2, CRLF). Чужие списания того
   же окна разнести по времени истории.
4. **Загрузка GLB («Экспорт»)**: Chrome оставляет файл как `C:/Users/ren/Downloads/<guid>.tmp` и не завершает Save-As.
   Перед копированием проверить длину из заголовка GLB = размер файла и пройти все чанки; скопировать в
   `art/pipeline-candidates/<ASSET-ID>/<run>/source/` под именем `<asset>-tripo-<task8>-<role>.glb`, посчитать SHA-256.
   **Свой Save-диалог завершить или отменить до передачи браузера** (иначе чужая сессия допишет файл в чужой каталог —
   инцидент P1.5, prop-barrel-report §3).
5. После работы вернуть настройки Studio (они сохраняются на аккаунт; было 4K / 2 000 000 полигонов) и закрыть вкладку.

## 3. Source spec и исходники

1. Оригиналы — вне run-каталога CLI: `art/pipeline-candidates/<ASSET-ID>/<date>-<name>/source/` (CLI не принимает
   оригинал внутри run-каталога).
2. `art/pipeline-candidates/<ASSET-ID>/source-specs/tripo-<task8>.json` по схеме `unmatched.tripo-pipeline.source-spec/1`
   (PIPELINE.md, «Source spec»): задача, модель, режим, операции с наблюдёнными списаниями, файлы с `expected_sha256`.
   Встроенные текстуры GLB, если их копии не коммитятся, восстанавливает скрипт рядом со spec — у бочки
   `python art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/restore_embedded_textures.py` (**до** любой команды
   CLI: preflight проверяет наличие каждого файла spec).
3. Сырые исходники героев `*-h31-*-source.glb` (62–65 МБ) хранятся локально (коммит de252a25): в чистом checkout
   preflight их прогонов не пройдёт — решение (коммит/LFS/отметка «локально») за владельцем.

## 4. Профили: что делает CLI для каждого вида ассета

| Вид | Профиль CLI | Стадии | Кто строит FBX |
|---|---|---|---|
| статический пропс (бочка, фонарь, ящик) | `static-candidate` (+ `passthrough` для проверки) | preflight → adopt → ue-import | `tools/tripo-pipeline/blender/static_prop_candidate.py` (headless), CLI фиксирует байты |
| персонаж (Medusa, Arthur, Merlin, Harpy) | `skeletal-candidate`, build-профиль `/2` | preflight → import → verify → atlas → build → ue-import | стадия build CLI по профилю (`build.flow`) |
| оружие | часть skeletal-профиля героя (`meshes.weapon`) | те же | build CLI: меш оружия 100 % на кости `weapon` |

Каталоги одного ассета: `art/pipeline-candidates/<ASSET-ID>/{source-specs,build-profiles,<date>-<name>/}`. Новый прогон
— всегда **новый** run-каталог; закоммиченные run-каталоги не переиспользуются под другой конфиг (init откажет, код 3).

### 4.1 Статический пропс (профиль static-candidate)

Имена ниже — для нового прогона `<R>` ассета `<ASSET-ID>` (у бочки `R=art/pipeline-candidates/ASSET-DECOR-KIT-001/<run>`).
`<ASSET-ID>.<PART>` — id записи реестра (у бочки `ASSET-DECOR-KIT-001.BARREL`). Роль основного GLB (`--primary-role`) —
роль в source-spec того файла, который стоит в `source_glb` params кандидата:

```bash
python -c "import json,sys; s=json.load(open(sys.argv[1],encoding='utf-8')); [print(f['role'], f['path']) for f in s['files']]" <source-spec>
```

1. **Проверочный passthrough** (сырой Tripo в UM_FBX_v1, не игровой ассет):

   ```bash
   $T init --run-dir $R/ue-passthrough --asset-id <ASSET-ID>.<PART> --primary-source tripo-<task8> \
       --primary-role <role основного GLB> --export-basename <SM_Name>_TripoPassthrough --run-id <run>-ue-passthrough
   $T register-source --run-dir $R/ue-passthrough --spec <source-spec>     # повтор = no-op
   $T run --run-dir $R/ue-passthrough                                       # headless: preflight, import, verify, export
   ```

2. **Кандидат**: скопировать params предыдущего кандидата этого вида (`<прежний run>/reports/candidate-params.json`) в
   `$R/reports/candidate-params.json`, поменять `out_dir` на `$R` (и имена/`geometry_repair` для нового ассета;
   `geometry_repair: null`, если ремонтировать нечего). Затем:

   ```bash
   mkdir -p $R/reports
   python -c "import json,sys,pathlib; p=json.load(open(sys.argv[1],encoding='utf-8')); p['out_dir']=sys.argv[3]; pathlib.Path(sys.argv[2]).write_bytes((json.dumps(p,indent=2,ensure_ascii=False)+chr(10)).encode('utf-8'))" <прежний run>/reports/candidate-params.json $R/reports/candidate-params.json $R
   "$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/static_prop_candidate.py -- $R/reports/candidate-params.json
   "$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/check_static_prop_fbx.py -- $R/export/<SM_Name>.fbx $R/reports/fbx-readback.json 0.5
   ```

   Проверить `reports/candidate-report.json`: все `checks` истинны (среди них `um_fbx_v1_conforms`), `checks_passed: true`:

   ```bash
   python -c "import json,sys; r=json.load(open(sys.argv[1],encoding='utf-8')); print([k for k,v in r['checks'].items() if v is not True], r['checks_passed'])" $R/reports/candidate-report.json
   # ожидается: [] True
   ```

   Превью (`preview/*.png`) просмотреть глазами — это наблюдение, не приёмка.
3. **Build-профиль** `<ASSET-ID>/build-profiles/<name>-static-um-fbx-v1[-<run>].json`: копия профиля того же вида,
   `candidate.dir` = `$R`, свой `profile_id`, имена UE (`static_asset`, `material`, `instance`, текстуры BC sRGB/TC_Default,
   N linear/TC_Normalmap/`flip_green: false` (DirectX), ORM linear/TC_Masks), `collision: none`, `two_sided: false`.
   Для того же контракта (новый прогон того же пропса) меняются только `profile_id` и `candidate.dir`:

   ```bash
   python -c "import json,sys,pathlib; p=json.load(open(sys.argv[1],encoding='utf-8')); p['profile_id']=sys.argv[3]; p['candidate']['dir']=sys.argv[4]; pathlib.Path(sys.argv[2]).write_bytes((json.dumps(p,indent=1,ensure_ascii=False)+chr(10)).encode('utf-8'))" <профиль-образец> <новый профиль> <новый profile_id> $R
   ```
4. **Прогон CLI**:

   ```bash
   $T init --run-dir $R/ue-candidate --asset-id <ASSET-ID>.<PART> --primary-source tripo-<task8> \
       --primary-role <role> --export-basename <SM_Name> --run-id <run>-ue-candidate \
       --profile static-candidate --build-profile <build-профиль>
   $T register-source --run-dir $R/ue-candidate --spec <source-spec>
   $T run --run-dir $R/ue-candidate          # preflight, adopt (без UE)
   ```

5. UE — раздел 5: `ue-passthrough` → `--ue-folder /Game/PipelineCandidates/<Asset>/<run>/Passthrough`,
   `ue-candidate` → `/Game/PipelineCandidates/<Asset>/<run>/Candidate` (у бочки `<Asset>` = `DecorBarrel`). Папки
   должны быть новыми (CLI откажет, если там чужие ассеты).

### 4.2 Персонаж (профиль skeletal-candidate, flow seated-parts)

1. Build-профиль `/2` (`<asset>-segmented-skeletal-um-fbx-v1-cli.json`), образец — профиль героя того же типа
   (гуманоид с оружием: Arthur/Merlin; крылья на arm-костях: Harpy). Ключи — PIPELINE.md, «Сборка по профилю».
   Обязательно: `fbx_preset` (UM_FBX_v1), `axes.expected_ue_front: "+X"`, `scale.top_part` + `figure_height_m`
   (высота фигуры, а не верх оружия), `armature.object: SKEL_UM_Humanoid`, 17 костей контракта, сокеты `Weapon`/`Head`
   (`location_uu: null` = прогноз build), имена UE и инстансы TeamColor.
2. Прогон:

   ```bash
   $T init --run-dir $R --asset-id <ASSET-ID> --primary-source tripo-<task8> --primary-role segmented-retopo-glb \
       --profile skeletal-candidate --build-profile <профиль /2>
   $T register-source --run-dir $R --spec <spec 1>; $T register-source --run-dir $R --spec <spec 2>
   $T run --run-dir $R                       # headless: preflight, import, verify, atlas, build (build: completed)
   ```

   Первый build перечисляет вывернутые части и откажет, пока `orientation.expected_inside_out_parts` профиля с ними не
   совпадёт — это не повод ослаблять проверку, а данные для нового файла профиля.
3. Проверить `reports/build-report.json` (все checks), `rig_deform_probe.py` (7/7, только headless), превью.
4. Сквозные дыры подставки (дыры-следы под ступнями: сборка вырезает контур стоп из верха подставки; build-report их
   не ловит). Только headless, 0 кредитов:

   ```bash
   python tools/tripo-pipeline/review/base_seethrough.py --out <evidence>/base-seethrough.json \
       <asset>=$R/export/SM_<Asset>_Base_Candidate.fbx,$R/export/SK_<Asset>_Candidate.fbx
   ```

   Лучи сверху и из игровой камеры (−55°, четыре стороны) через диск верха подставки; `base_only` — дыры в меше
   подставки, `with_figure` — то, что видно при стоящей фигуре. Порог (предложение): `with_figure` ≤ 0,1 uu² в каждом
   направлении, иначе это дефект сборки (находка в акт; исправляется в сборке подставки, не в UE); `base_only` выше
   порога при малом `with_figure` — скрытый дефект: записать в акт, он откроется при движении подола/ступней в клипах.
   Замер T3.1 (`base_only` / `with_figure`, максимум по направлениям): Medusa T4 54,8 / 27,6 uu² (дефект, видно в
   кадрах), Merlin 44,4 / 0,43 uu² (дыры под мантией, по краю подола щели до 0,43 uu²), Arthur 0,08 / 0,06, Harpy 0 / 0.

### 4.3 Оружие (в составе персонажа)

Отдельного UE-ассета оружия нет: меш оружия входит в скелетный FBX, веса 100 % на кости `weapon`
(ребёнок `hand.R` у правшей Arthur/Merlin, `hand.L` у Medusa), сокет `Weapon` = голова кости `weapon`.

- `meshes.weapon.mode`: `split-from-part` (вырезать из кулака: `weapon_split`), `parts` (собрать из частей), `part`
  (целая часть GLB) или `null` (нет оружия, у Harpy сокет `Weapon` стоит на `foot.R` — удар когтями, предложение).
- Проверки: `build-report` (оружие на своей стороне в кадре экспорта, веса 100 % `weapon`), UE-стадия
  (`sockets_weapon_head`), живой замер мирового положения сокета в контрольной сцене (раздел 6) против
  `target_ue_component_uu` ±0,05 uu.
- Высота фигуры меряется по `scale.top_part`; меч/посох выше фигуры проверку высоты не валят (`skeletal_top_as_build`).

## 5. UE: импорт в живой редактор

1. Снимок до (только чтение):

   ```bash
   python tools/tripo-pipeline/review/ue_content_snapshot.py <evidence>/snapshot-before.json --extra-folder /Game/ArtTests --extra-folder /Game/S08
   ```

   Записать: открытый уровень, 0 dirty-пакетов, `Interchange.FeatureFlags.Import.FBX`.
2. Импорт:

   ```bash
   $T --backend mcp ue-import --run-dir <run> --ue-folder /Game/PipelineCandidates/<Asset>/<run-id>[/Candidate]
   $T --backend mcp ue-import --run-dir <run>            # повтор: skipped
   $T --backend mcp ue-import --run-dir <run> --force    # свои ассеты удалены и импортированы заново, без Name_1
   $T --backend mcp ue-import --run-dir <run>            # снова skipped
   ```

   Статус отчёта `reports/ue-import-report.json` — `technically_imported`, все checks `passed` (классы, sRGB/компрессия
   текстур, граф материала, кости и кость 0, карта осей и фронт +X, высота по профилю, сокеты, треугольники подставки,
   не dirty).
3. Меши через MCP `import_file` импортируются при `Interchange.FeatureFlags.Import.FBX = true` (как оставлено в
   редакторе; измерено T4/T2.1/T3.1). **Анимации (FBX-клипы) — только legacy-путь:** на время импорта
   `Interchange.FeatureFlags.Import.FBX 0`, потом вернуть `1` (`tools/tripo-pipeline/review/ue_py/import_clips.py` делает
   это и пишет три значения). Масштаб импорта **1,0** (FBX_SCALE_UNITS + UnitScaleFactor 1.0); значение 100 из S05 дало
   ×100 на кости 0 (T2.1).
4. Снимок после с `--compare <evidence>/snapshot-before.json`: `protected_unchanged: true`, добавлены только свои ассеты.

## 6. Контрольная сцена P1.7

`tools/tripo-pipeline/review/control_scene.py` строит `/Game/ArtTests/P17ControlScene/L_P17ControlScene` с нуля при
каждом запуске (Cobble 5×6 из `L_ART005H_CornerReview`, камера UpdateBoardCamera, EV100 1,3) и снимает редакторные кадры.
Чтобы добавить ассет: запись в `SUBJECTS` (клетка S04 или место декора вне клеток, `yaw` по правилу S08FighterActor:
дальняя половина — лицом к камере, ближняя — спиной; для меша UM_FBX_v1 это +90/−90), при необходимости `team_alt`
(своп командного MI) и MI экземпляров в `MATERIAL_INSTANCES`.

**Декор: z = верх поверхности, на которой он стоит, а не 0.** Клетки доски Cobble лежат на z ≈ 0, а деревянный борт —
на **z = 5,0 uu** (верх `SM_ART005_BoardStoneV4_WoodUV`; угловые скобы ART005H — 5,2–8,8 uu). Декор задаётся как
`"location": [x, y, None], "place_on_surface": True`: build опускает лучи на нижний контур меша (вершины в пределах
0,5 uu от низа + сетка 1 uu) против видимых статических мешей уровня и ставит актёр на самое высокое попадание;
результат — `build.decor_support` отчёта сцены и `measurements.json decor_support` (`on_surface`: низ = верх опоры
±0,05 uu, разброс опоры ≤ 0,1 uu; разброс больше — край декора висит или контур вышел за борт: сдвинуть x/y).
Проверить глазами на кадре `k2-5x-<декор>`: нижний край (обруч, основание) не срезан бортом. Бочка в T3.1 сначала
стояла на z 0 и ушла в борт на 5 uu (19 % высоты; нижний обруч срезан) — чек-лист это пропустил.

```bash
for t in r1 r2 r3; do python tools/tripo-pipeline/review/control_scene.py --out C:/tmp/<task>/cs --tag $t; done
python tools/tripo-pipeline/review/control_scene_analyze.py --runs C:/tmp/<task>/cs --tags r1 r2 r3 --out <evidence>
python tools/art/classify_evidence.py <evidence>/frames        # все кадры editor-mcp-viewport, 0 rejected
```

Три повтора дают шум и порог E2 (2 × шум) в `noise.json`; `idempotency.json` сравнивает отчёты повторов. Скрипт в конце
сам загружает прежний уровень; проверить: открыт исходный уровень, dirty-пакетов 0, show-флаги сняты
(`ShowFlag.* 2`), экспозиция вьюпорта «Настройки игры».

Чек-лист модели (`model-checklist.json`, по ассету): спереди/сзади, оружие, кисти, ноги на подставке, **сквозные дыры
подставки**, пары клиппинга, командный цвет в сером, силуэт в игровой камере; у декора — **посадка на поверхность**
(`decor_support`). Числа берутся из `measurements.json` и `base-seethrough.json`, суждения пишутся с пометкой
«визуально, агент; не художественная приёмка».

- Сквозные дыры подставки: `base-seethrough.json` (раздел 4.2, п. 4) и кадры сцены — `measurements.json
  base_see_through_frames` (маски 5× `mask-k2-5x-void-*`: доска скрыта, пустота редактора = (0,0,0); подставка без
  фигуры и с фигурой; пиксели пустоты внутри проекции диска верха = просвет). Сравнивать с пустой доской нельзя: серые
  подставки и швы брусчатки совпадают с доской в пределах порога маски. Глазами — кадры `front-5x`/`back-5x` и `k2-1p6`
  (−55°) и маски `mask-k2-5x-base-*` (подставка без фигуры на доске): светлые пятна цвета доски на верхе подставки у
  стоп = просветы. «Ноги на подставке без зазора» не значит «подставка без дыр»: это разные пункты.
- Декор: `decor_support.on_surface = true` и кадр 5× без срезанного низа (см. выше).

## 7. Доказательства, реестр, коммит

1. Кадры в `evidence/`: JPEG 1200 px q92 (Pillow LANCZOS) + sidecar `*.evidence.json` (`png_before_jpeg`: sha/размер
   PNG); PNG остаются вне git:
   `python tools/tripo-pipeline/review/frames_to_jpeg.py --src C:/tmp/<task>/cs/r1 --out <evidence>/frames --png-kept-at C:/tmp/<task>/cs/r1 --exclude 'p17-mask-*'`.
2. Реестр: новый слой (`stage: ue-editor-import` / `ue-editor-frames`, статус максимум «технически импортировано», пути
   отчётов run-каталога — `kind: file`; UE-ассеты `/Game/PipelineCandidates/...` существуют только в локальном Content,
   поэтому в пути с `expect: exists` их не вносить, а назвать в `note`). Если меняешь файл с `sha256` в реестре — обнови
   sha. `python tools/tripo-pipeline/validate_registry.py` → PASS.
3. [DIRECTORY-MAP.md](DIRECTORY-MAP.md) — новые каталоги; PIPELINE.md — если изменилось поведение инструмента.
4. Коммит — только списком путей (`commit_manifest`), `git -c core.longpaths=true add --dry-run` по списку. Не
   коммитить: `work/`, `.staging/`, `run.lock`, `*.fbm/`, PNG кадров, `logs/*.log` (корневое `*.log`; нужен лог —
   `git add -f` или исключение `!*/logs/*.log` в `.gitignore` ассета).

## 8. Ловушки (проверенные)

| Ловушка | Что происходит | Что делать |
|---|---|---|
| `core.longpaths` | пути `art/animation-refs/**`, `*.fbm/` длиннее 260 символов; git падает на add/status | `git -c core.longpaths=true …` |
| CRLF | `core.autocrlf=true`: `.py` инструмента в checkout получают CRLF, хеш скрипта в отпечатке стадии меняется → стадия переисполняется (байты выходов те же) | не править концы строк; `art/pipeline-candidates/**`, `art/animation-refs/**`, `docs/art-pipeline/**` помечены `-text` в `.gitattributes` — файлы хешируются байт в байт |
| `-text` в `.gitattributes` | без него отчёты/manifest с sha256 не совпадут в другом checkout | новые каталоги с хешированными байтами — сразу в `.gitattributes` (`-text`) |
| Save-диалог Chrome | Tripo-экспорт остаётся `<guid>.tmp`, незавершённый Save-As дописывает чужая сессия | одна загрузка за раз, chunk-walk GLB, свой диалог закрыть |
| `-NoLiveCoding` | на **игровом** target: WITH_RELOAD=0 против precompiled движка → packaged-клиент падает при старте | только для UnmatchedEditor, никогда для `Unmatched` (память ue-pipeline-traps п. 11) |
| Interchange | клипы (FBX-анимации) на существующий Skeleton импортируются legacy-путём (`FbxImportUI`, `FBXIT_ANIMATION`, T2.1); путь Interchange для клипов не проверялся, меши через MCP идут при флаге `true` | `Interchange.FeatureFlags.Import.FBX 0` только на время импорта клипов, затем вернуть `1` и записать все три значения |
| масштаб 1,0 | UM_FBX_v1 + UnitScaleFactor 1.0: импорт 1,0; 100 даёт ×100 на кости 0 | `import_uniform_scale` не менять; ручной Scale — дефект (04 §1) |
| `MSYS_NO_PATHCONV` | Git Bash портит `/Game/...` | `export MSYS_NO_PATHCONV=1` |
| кости с точкой | UE переименовывает `foot.R` → `foot_R`; `add_socket` на `foot.R` падает | с `ue-candidate/4` CLI сам берёт UE-имя |
| вершинные цвета | MCP `StaticMeshTools.import_file` импортирует без вершинных цветов (`VertexColorImportOption = Ignore`); подставка `vertex-mask` (Harpy) рисуется целиком «горящей», метки экземпляров не видны | с `ue-candidate/6` CLI импортирует такую подставку editor-Python-скриптом с `Replace` (через консоль редактора, MCP SlateInspector) и проверяет `base_vertex_colors_imported` |
| class default через ObjectTools | `ObjectTools.set_properties` на `Default__…` (CDO) помечает dirty **все** загруженные ассеты класса — в T3.1 47 пакетов, в том числе `/Game/ART004/Medusa/Meshes/SM_Medusa_Base` | CDO не менять; если случилось — `EditorLoadingAndSavingUtils.reload_packages(…, ASSUME_POSITIVE)` для этих пакетов, **не сохранять** |
| принудительное удаление | `--force` удаляет свои ассеты, на которые ссылаются чужие пакеты (MI контрольной сцены): ссылки обнуляются в памяти, пакеты становятся dirty | после `--force` проверить dirty-пакеты (`ue_py/editor_state.py`); свои — пересобрать (control_scene.py) или перезагрузить с диска |
| `unreal.Rotator` | порядок позиционных аргументов в Python UE — (roll, pitch, yaw) | всегда ключевые аргументы `Rotator(roll=, pitch=, yaw=)` |
| дублирование уровня | `EditorAssetLibrary.duplicate_asset(<map>)` + `load_level` копии → фатальная ошибка «World Memory Leaks» (EditorServer.cpp:2544), редактор закрывается (T3.1) | уровень создавать `new_level` и копировать актёров данными (control_scene_ue.py); не держать в Python ссылки на актёров уровня, который выгружается |
| структуры из `get_editor_property` | обёртки `Color`/`Vector`/`Rotator` могут ссылаться на память объекта-владельца: после смены уровня скопированные цвета светов стали мусором (заливка (11,1,104) — кадры тёмно-синие; T3.1) | копировать как простые данные (`plain()` в control_scene_ue.py) и сверять прочитанные обратно свойства с источником |
| CaptureViewport | отдаёт размер вьюпорта (здесь 2033×1216), первый кадр после прыжка камеры бывает старым | центральный 16:9-кроп → 1920×1080; три захвата, берётся последний |
| экспозиция | вьюпорт «EV100 1,3» = гистограмма min = max = 2^1,3 при `ExtendDefaultLuminanceRange` off | объём в уровне P17 (калибровка — evidence p17, `exposure-calibration.json`) |
| оверлеи редактора | сетка, спрайты светов, каркас объёма попадают в кадр | `ShowFlag.Grid/BillboardSprites/Volumes 0`, после — `2` |
| декор на z 0 | клетки Cobble на z ≈ 0, борт — на 5,0 uu: декор с жёстким z 0 уходит в борт (бочка T3.1: 5 uu, нижний обруч срезан) | `place_on_surface` в `SUBJECTS`; `decor_support.on_surface` и кадр 5× |
| дыры-следы в подставке | сборка вырезает контур стоп из верха подставки; где контур шире стоп, в кадре −55° видна доска (Medusa T4 — до 27,6 uu²), под мантией дыры скрыты (Merlin — 44,4 uu² в меше) | `base_seethrough.py` (`with_figure` ≤ 0,1 uu²) + маски сцены `mask-k2-5x-void-*` (`base_see_through_frames`) |
| кость 0 | legacy-FBX делает объект арматуры костью 0; root motion читается с неё | анимировать объект арматуры (ue-pipeline-traps п. 2) |
| Build.bat | exit 0 при ошибке компиляции | искать `Result: Failed` в логе (UTF-16) |

## 9. Правило статусов и акт

Акт в `docs/art-pipeline/evidence/<задача>-<дата>/README.md`: что сделано, числа, что не проверялось, статусы.
Редакторные кадры помечаются «EDITOR frame … not K1/K2 acceptance»; K1/K2/K3, QA-010 и GD-058 закрываются только
кадрами packaged-live (`classify_evidence.py --require packaged-live --strict`).

## 10. Сводка шагов (чек-лист исполнителя)

1. Окружение (§0), снимок процессов.
2. Реестр/входы (§1). 3. Tripo или пропуск (§2). 4. Spec и исходники (§3).
5. Профиль и прогон CLI (§4.1/4.2/4.3). 6. Снимок UE до, ue-import ×4, снимок после (§5).
7. Контрольная сцена ×3, анализ, сквозные дыры подставки и посадка декора, чек-лист, классификатор (§4.2 п. 4, §6). 8. Кадры/реестр/карта/коммит-список (§7).
9. Акт (§9). 10. Свои процессы остановить по PID, редактор и Blender вернуть в исходное состояние.

## 11. Сухой повтор (T3.1)

Повтор на бочке: разделы 0 → 1 (1.1) → 3 → 4.1 → 5 без Tripo (0 кредитов), run
`art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p17-repro`, UE `/Game/PipelineCandidates/DecorBarrel/20260928-p17-repro`,
снимки §5 — `<evidence>/repro/snapshot-{before,after}.json`. Контрольная сцена с тегами r1–r3 (§6) должна уже быть снята.
Сверка с исходным прогоном и кадр бочки в контрольной сцене:

```bash
python tools/tripo-pipeline/review/control_scene.py --out C:/tmp/<task>/cs --tag repro --only barrel --barrel /Game/PipelineCandidates/DecorBarrel/20260928-p17-repro/Candidate/Meshes/SM_Decor_Barrel
python tools/tripo-pipeline/review/control_scene_analyze.py --runs C:/tmp/<task>/cs --tags r1 r2 r3 --repro-tag repro --out <evidence>
python tools/tripo-pipeline/review/repro_compare.py --base art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel --repro art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p17-repro --frames <evidence>/repro-frames.json --out <evidence>/repro/repro-report.json
```

Результат и журналы итераций исполнителя: [evidence/p17-control-scene-2026-09-28/repro/](evidence/p17-control-scene-2026-09-28/repro/repro-report.json).
