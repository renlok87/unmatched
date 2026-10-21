# ASSET-DR-WATSON-001 (Dr. Watson) — строки регистрации этапа 7 для регистратора пачки

Исполнитель 7a, слот 1, 2026-10-21. Общие файлы (ДС-3b) не тронуты. Ниже то, что регистратор вносит одним шагом после
закрытия всех слотов (references/new-character-registration.md §5). Значения — из заявки
(art/pipeline-candidates/ASSET-DR-WATSON-001/asset-card.yaml) и замера UE
(20261021-h2ld-ue-import/reports/ue-import-report.json).

| Поле | Значение |
|---|---|
| FighterName / KEY / Stage | `Dr. Watson` / `DrWatson` / `H2LD` |
| Роль | помощник (GAME_ROLE sidekick) героя `sherlock-holmes` (Sherlock Holmes, та же пачка); в Specs() — `false` (как Merlin) |
| Бюджет / диапазон | 45,0 uu / 40,0–48,0 (FIGURE_HEIGHT_M 0,45, FIGURE_HEIGHT_RANGE_M [0,40; 0,48]) |
| FigureTopUU | 45,0 (build_figure_top_uu, часть tripo_part_9 — верх котелка) |
| BoundsTopUU | 45,0007 (ue_skeletal_top_uu; револьвер ниже — 0,396 м) |
| Низ bounds SK | 4,805 uu (ue-import skeletal_bounds min z; тест Assets требует 0…8) |
| IdleSeconds / ContactFrame | 56/24 = 2,3333 / 8 |
| AUDIO_KEY / HIT_TYPE | `WATSON` / `ARROW` |
| CLIP_PREFIX | `WAT` (clip-manifest: WAT-* technically_imported, MANIFEST_CHECK PASS clips 47) |
| Треугольники | LOD0 44 169 (тело 41 870 + револьвер 2 299), подставка 1 384, 1 LOD, 1 слот |

## Р7-1, Р7-2 — de010 / de011 (7b, `--only DrWatson`)

- `tools/art/de010/de010.py` `HEROES`:
  `("DrWatson", "H2LD", "ASSET-DR-WATSON-001/build-profiles/dr-watson-h2anim.json", 8),`
- `tools/art/de011/de011.py` `CAPTURE_LOOKS`: `"DrWatson": "P1",` — окрашена только лента котелка (silk); золото P1 на
  чёрном котелке читается лучше голубого P2 (review r3 K2 5×: обе ленты видны, P1 контрастнее).

## Р7-3, Р7-4, Р7-5 — C++

- `S08HeroesV2.cpp` `Specs()`:
  `{TEXT("Dr. Watson"), TEXT("DrWatson"), TEXT("H2LD"), false, 45.0f, 40.0f, 48.0f, 45.0f, 45.0007f, 56.0f / 24.0f, 8},`
- `S08HeroesV2Tests.cpp`:
  - добавить `TEXT("Dr. Watson")` в список Mapping;
  - счётчик `Specs().Num()` — на число новых строк пачки;
  - `WantMs`: `{TEXT("DrWatson"), 583.333f}` (LungeAttack 14 к.);
  - `WantSeconds`: `{TEXT("DrWatson"), 0.333333f}` (контакт к.8 / 24).
  - Перед правкой: `grep -in '"Dr. Watson"\|watson' unreal/Unmatched/Source/Unmatched/S08/*Tests.cpp`.
- `S08AudioBank.cpp`:
  - `CharacterKey`: `if (Name.Contains(TEXT("watson"), ESearchCase::IgnoreCase)) return TEXT("WATSON");`;
  - `HitType`: `if (Key == TEXT("WATSON")) return TEXT("ARROW");`.
- `S08AudioTests.cpp`:
  - `TestEqual("watson key", S08AudioBank::CharacterKey(TEXT("Dr. Watson")), FString(TEXT("WATSON")));`
  - `TestEqual("watson hit", S08AudioBank::HitType(TEXT("WATSON")), FString(TEXT("ARROW")));`
- Витрина: не нужна (помощник; экраны выбора показывают героев). `UmShowcase::HiPolyPath` не трогать.

## Р7-6 — cue-table.json

- CUE-011 `clip.sequence_by_fighter`:
  `"DrWatson": "/Game/PipelineCandidates/DrWatson/H2Anim/AM_DrWatson_HitReact.AM_DrWatson_HitReact"`
- CUE-013:
  `"DrWatson": "/Game/PipelineCandidates/DrWatson/H2Anim/AM_DrWatson_DeathSettle.AM_DrWatson_DeathSettle"`
- Проверка: `python tools/s08/cue_contract/cue_contract.py validate-table`.

## Р7-7 — DefaultGame.ini

```ini
+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/DrWatson/H2LD")
+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/DrWatson/Rig")
+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/DrWatson/H2Anim")
```

## Р7-8 — S08FighterNames.json

В запись владельца `"sherlock-holmes"` (её добавляет 7a/7b Sherlock) — `"sidekick": {"en": "Dr. Watson", "ru": "Доктор Ватсон"}`.

## Р7-9 — 03-asset-registry.csv (registry_writer.py rows, 7b)

- `SK_DrWatson_H2LD`: area `hero` (помощник), ue_path `/Game/PipelineCandidates/DrWatson/H2LD/Meshes/SK_DrWatson_H2LD`;
  rollback `-S08HeroesLegacy`; LOD0 44 169 tris, подставка 1 384, 1 LOD, 1 слот; подставка двухъярусная Ø0,24 × 0,05 м,
  vertex-mask (кольцо команды по высоте нижнего яруса); link `ASSET-DR-WATSON-001; AN-64; AN-164; AN-165; AN-166; AN-167`.
- `AM_DrWatson_{Idle,LungeAttack,HitReact,DeathSettle}` (area `anim`): 2333 / 583 / 417 / 875 мс, 56 / 14 / 10 / 21 к.,
  18 костей (с weapon_R). Карточки — evidence/acceptance-anim/20261021-r1/<Clip>/card.json.

## Р7-10 — .uasset (git add -f поимённо)

Список — `C:/tmp/ASSET-DR-WATSON-001-stage7/uassets-new.txt`, 23 файла: `H2LD/**` 17 (2 меша, 8 MI, 7 текстур),
`Rig/**` 2, `H2Anim/**` 4. После de010/de011 добавятся пересохранённый `AM_DrWatson_LungeAttack` (notify Contact) и
`/Game/UM/Materials/v2/Dissolve/MI_DrWatson_H2LD_{P1,P2}_Dissolve`. `M_UM_Figure_v2` не сохранялся (discard_master).

## Р7-11 — варианты bench-фикстур (в контейнере unmatched-backend)

Владелец Sherlock Holmes регистрируется в той же пачке — одной строкой с ним:
`env_bench_fixtures.cts --variant SherlockHolmes --hero-name "Sherlock Holmes" --hero-slug sherlock-holmes --sidekick-name "Dr. Watson"`
(имя варианта — как у 7b Sherlock); если Sherlock не входит в 7b — вариант помощника
`--variant DrWatson --hero-name "Sherlock Holmes" --hero-slug sherlock-holmes --sidekick-name "Dr. Watson"`. Затем `--check`.

## Реестр asset-registry.json (7b)

`registry_writer.py entry --phase 7b-frames`. Пути: import run 20261021-h2ld-ue-import, профиль
build-profiles/dr-watson-h2ld-lookdev-ue-import-r3.json (живой), review 20261021-h2ld-ldc-ue, evidence
evidence/stage7a-20261021.
