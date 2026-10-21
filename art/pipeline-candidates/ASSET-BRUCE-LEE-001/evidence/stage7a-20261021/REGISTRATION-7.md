# ASSET-BRUCE-LEE-001 (Bruce Lee) — строки регистрации этапа 7 для регистратора пачки

Исполнитель 7a, слот 1, 2026-10-21. Общие файлы (ДС-3b) не тронуты. Ниже то, что регистратор вносит одним шагом после
закрытия всех слотов (references/new-character-registration.md §5). Значения взяты из заявки
(art/pipeline-candidates/ASSET-BRUCE-LEE-001/asset-card.yaml) и из замера UE
(20261021-h2ld-ue-import/reports/ue-import-report.json).

| Поле | Значение |
|---|---|
| FighterName / KEY / Stage | `Bruce Lee` / `BruceLee` / `H2LD` |
| HERO_SLUG | `bruce-lee` (на сервере `hasSidekicks: false`, помощника нет) |
| Бюджет / диапазон | 55,0 uu / 52,0–56,0 (FIGURE_HEIGHT_M 0,55, FIGURE_HEIGHT_RANGE_M [0,52; 0,56]) |
| FigureTopUU | 55,0 (build_figure_top_uu, часть tripo_part_2, голова с волосами) |
| BoundsTopUU | 54,9994 (ue_skeletal_top_uu; над головой ничего нет) |
| Низ bounds SK | 5,776 uu (rig-report; тест Assets требует 0…8) |
| IdleSeconds / ContactFrame | 2,5 / 7 |
| AUDIO_KEY / HIT_TYPE | `BRUCELEE` / `CLAW` |
| CLIP_PREFIX | `BRUC` (clip-manifest: BRUC-* technically_imported, MANIFEST_CHECK PASS) |

## Р7-1, Р7-2 — de010 / de011 (шаг 7b, `--only BruceLee`)

- `tools/art/de010/de010.py` `HEROES`:
  `("BruceLee", "H2LD", "ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2anim.json", 7),`
- `tools/art/de011/de011.py` `CAPTURE_LOOKS`: `"BruceLee": "P2",`. P2 выбран потому, что акцент P1 (золото #E8C06A) на
  жёлтом костюме даёт светло-кремовые лампасы. В UE это ΔE 35,6–41,7 против ткани (review/r1 measure). Синие лампасы P2
  на съёмке растворения видны лучше.

## Р7-3, Р7-4, Р7-5 — C++

- `S08HeroesV2.cpp` `Specs()`:
  `{TEXT("Bruce Lee"), TEXT("BruceLee"), TEXT("H2LD"), true, 55.0f, 52.0f, 56.0f, 55.0f, 54.9994f, 2.5f, 7},`
- `S08HeroesV2Tests.cpp`:
  - добавить `TEXT("Bruce Lee")` в список Mapping;
  - увеличить счётчик `Specs().Num()` на число новых строк пачки;
  - `WantMs`: `{TEXT("BruceLee"), 291.667f}`;
  - `WantSeconds`: `{TEXT("BruceLee"), 0.5f}`.
  - Имя `Bruce Lee` в тестах как «незнакомый герой» не используется. Перед правкой проверить
    `grep -in '"Bruce Lee"' unreal/Unmatched/Source/Unmatched/S08/*Tests.cpp`.
- `S08AudioBank.cpp`:
  - `CharacterKey`: `if (Name.Contains(TEXT("bruce"), ESearchCase::IgnoreCase)) return TEXT("BRUCELEE");`. Подстрока
    «bruce» с другими именами не пересекается.
  - `HitType`: `if (Key == TEXT("BRUCELEE")) return TEXT("CLAW");`.
- `S08AudioTests.cpp`:
  - `TestEqual("bruce key", S08AudioBank::CharacterKey(TEXT("Bruce Lee")), FString(TEXT("BRUCELEE")));`
  - `TestEqual("bruce hit", S08AudioBank::HitType(TEXT("BRUCELEE")), FString(TEXT("CLAW")));`
- Витрина. `UmHeroShowcase.cpp` `UmShowcase::HiPolyPath`, строку поставить перед строкой Medusa:
  `if (K == TEXT("BruceLee")) { return TEXT("/Game/PipelineCandidates/BruceLee/HP2/bruce-lee-h2-tripo-14235c8d-tex8k-pbr-clean.bruce-lee-h2-tripo-14235c8d-tex8k-pbr-clean"); }`
  - Посадку `Frame()` считает по bounds сам. Bounds меша HP2 в UE: min (−21,06; −10,03; 10,75), max (21,12; 24,29; 97,87).
  - Поворот по умолчанию — HiPolyYaw 45/135. Оружия нет, кисти-«когти» на уровне груди, ниже лица. Нужен ли свой yaw
    (как у Arthur), решают слепой раунд и живой кадр 7b.

## Р7-6 — cue-table.json

- CUE-011 `clip.sequence_by_fighter`:
  `"BruceLee": "/Game/PipelineCandidates/BruceLee/H2Anim/AM_BruceLee_HitReact.AM_BruceLee_HitReact"`
- CUE-013:
  `"BruceLee": "/Game/PipelineCandidates/BruceLee/H2Anim/AM_BruceLee_DeathSettle.AM_BruceLee_DeathSettle"`
- Проверка: `python tools/s08/cue_contract/cue_contract.py validate-table`.

## Р7-7 — DefaultGame.ini

```ini
+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/BruceLee/H2LD")
+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/BruceLee/Rig")
+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/BruceLee/HP2")
+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/BruceLee/H2Anim")
```

Строка HP2 нужна витрине. В папке HP2 лежат материал `tripo_part_1_material` и 3 его текстуры: это подставка Tripo,
меш их не использует (≈ 61 МБ uasset). С `DirectoriesToAlwaysCook` они попадут в пак. Вариант — удалить их до кука; у
KingArthur/HP2 то же самое.

## Р7-8 — S08FighterNames.json

`"bruce-lee": {"hero": {"en": "Bruce Lee", "ru": "Брюс Ли"}}`. Помощника нет: `sidekick` необязателен
(UmWorldLayer.cpp читает его через TryGetObjectField).

## Р7-9 — 03-asset-registry.csv (registry_writer.py rows, 7b)

- `SK_BruceLee_H2LD`:
  - area `hero`, ue_path `/Game/PipelineCandidates/BruceLee/H2LD/Meshes/SK_BruceLee_H2LD`;
  - rollback `-S08HeroesLegacy (серый Body: блок-аута ART-003 у нового персонажа нет)`;
  - бюджет: LOD0 39 659 tris (только тело), подставка 1 413, 1 LOD, 1 слот;
  - подставка двухъярусная, vertex-mask: кольцо команды по высоте нижнего яруса;
  - link `ASSET-BRUCE-LEE-001; AN-51; AN-156; AN-157; AN-158; AN-159`.
- `AM_BruceLee_{Idle,LungeAttack,HitReact,DeathSettle}` (area `anim`): 2500 / 583 / 417 / 875 мс, 60 / 14 / 10 / 21 к.,
  17 костей. Карточки — evidence/acceptance-anim/20261021-r1/<Clip>/card.json.
- Строку витрины HP2 добавить, если её ведут для KingArthur.

## Р7-10 — .uasset (git add -f поимённо)

Список — `C:/tmp/ASSET-BRUCE-LEE-001-stage7/uassets-new.txt`, 60 файлов:

- `<Key>/H2LD/**` — 18 файлов;
- `<Key>/Rig/**` — 2;
- `<Key>/H2Anim/**` — 4;
- `<Key>/HP2/**` — 37, ≈ 124 МБ. У KingArthur/HP2 файлов в git нет (`git ls-files` пуст), так что решение по HP2 —
  за оркестратором.

После de010/de011: `AM_BruceLee_LungeAttack` будет пересохранён с notify, плюс
`/Game/UM/Materials/v2/Dissolve/MI_BruceLee_H2LD_{P1,P2}_Dissolve`. `M_UM_Figure_v2` не сохранялся: грязный пакет
сброшен через discard_master.

## Р7-11 — варианты bench-фикстур (в контейнере unmatched-backend)

`env_bench_fixtures.cts --variant BruceLee --hero-name "Bruce Lee" --hero-slug bruce-lee`, без `--sidekick-name`:
помощника нет. Затем `--check`.

## Реестр asset-registry.json (7b)

`registry_writer.py entry --phase 7b-frames`. Пути: import run 20261021-h2ld-ue-import, профиль
build-profiles/bruce-lee-h2ld-lookdev-ue-import-r3.json (живой), review 20261021-h2ld-ldc-ue, evidence
evidence/stage7a-20261021.
