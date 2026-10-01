# ENV-MAPS P5, трек B: поднос T2b, водопад и море (2026-10-01)

Статус: **предложено**. Это этап CREATE: UnrealEditor, UBT и packaged-сборки не запускались. Поэтому C++ не скомпилирован, в UE ничего не импортировано, и статуса «технически импортировано» нет. Художественная приёмка — только решение пользователя. Tripo, SYNTX, покупки, Fab/Epic и новые CC0-наборы не использовались. Сеточные доски (Cobble) не затронуты: весь новый код срабатывает только на досках с картой (map-image) и только из ground-секции раскладки Sarpedon.

Исходные ассеты — линия K (`../p5k-blender-assets-2026-10-01/README.md`): `SM_TableBase_T2b` (run `20261001-tray-t2b`) и `SM_Env_S_{Waterfall,WaterfallFoam,WaterfallLip,SeaRing}` (run `20261001-waterfall-v1`).

## Что сделано

| Часть | Файлы | Суть |
|---|---|---|
| Импорт T2b | `tools/art/env_kit/ue_import_tray_t2.py` (`--variant t2b`, теперь по умолчанию; `--variant t2` работает как раньше) | `SM_TableBase_T2b` в `/Game/PipelineCandidates/TableBase/T2b`, vertex colours **REPLACE** (только для этого импорта), без коллизии, Nanite выключен. Каменные текстуры T2 берутся из папки T2 (их sha256 проверяется по run T2). Новые текстуры мха `T_TableBase_T2b_Moss_{BC,N}`. Мастер `M_TableBase_T2b` = граф T2 (M_UM_Figure: BC, N DirectX, ORM) плюс lerp к `MossBC × MossTint` по `VertexColor.R` (MossAmount, MossContrast, MossBreakup), G даёт вариацию по кускам, B — затемнение по глубине (`DepthTint`), лепестки в мху (`PetalColor`). При нейтральных значениях материал совпадает с T2 (это проверяет тест на CPU-зеркале). MI: общий `MI_TableBase_T2b` и `MI_TableBase_T2b_{Marmoreal,Sarpedon}`. Значения лежат в `ground-params.json` (`trayLook` и `maps.<key>.trayLook`): у Marmoreal мох с лепестками, у Sarpedon тёмный влажный камень с тонким мхом. После импорта проверяются: границы = сборка (±0,5 uu), треугольники в пределах 1 %, наличие vertex colours, огибающая T2b из `S08Diorama.h` |
| Выбор подноса | `S08Diorama.h/.cpp`, `S08DioramaT2Tests.cpp` | `LoadTrayT2(MapName)`: сначала T2b, если её нет в сборке — T2, если нет и её — плейсхолдер T1. Материал: MI карты, иначе общий (`LoadTrayT2Material`). Добавлены `PickTrayT2`, `TrayT2KindOf`, `T2bMapMaterialPath` и трасса `tray-t2 loaded mesh=… kind=T2b`. Огибающая T2b: свес ≤ 40, глубина 180..230 uu. Верх и губа те же, что у T2, поэтому `FitTrayT2`, поля и раскладки не меняются. Новые тесты: `T2bPick` и `T2bAssets`; `T2Actor` теперь ждёт тот вид подноса, который выбирает `LoadTrayT2` |
| Водопад-меш | `S08EnvGround.h/.cpp`, `ground_splat.py`, `ue_import_env_ground.py` | У записи `ground.waterfalls[]` появилось поле `mesh`: sheet / foam / lip, `loc` (−144,1; 425; 0), `yawDeg` 90, `sheetCard` (193,8; 185,231), `foamCards` (пена 261,34 × 70, туман 243,97 × 76). Лист получает MID `MI_EnvWaterfall_Sarpedon` с `FallCard = (sheetCard, 0)`. Пена и туман получают MID на каждый слот с `kind 1`. Камень-выступ получает `MI_TableBase_T2b_Sarpedon` и отбрасывает тень. Spill-плоскость остаётся. Если меша листа нет в сборке, ставится прежняя плоская карточка P4. Выступ без своего материала не ставится: камень в материале по умолчанию выглядел бы дырой |
| Море | те же файлы | Секция `ground.sea`: `SM_Env_S_SeaRing` в (0, −45, −172) с `MI_EnvSea_Sarpedon`, без коллизии и тени. Новый `M_EnvSea`: тёмная вода, `Col.R` — пена у скал (шум дрейфует), `Col.G` — затухание вдаль к `SeaFar`, рябь `T_Ground_WaterRipple_N`, ночной грейд карты, лёгкий эмиссив. Статусы в трассе: `sea=ok / missing-mesh / missing-material` |
| Раскладка | `sarpedon.layout.json` (только секция `ground`), `sarpedon.splat.json`, `sarpedon.preview.png`, `ground-params.json` | `ground_splat.py --maps sarpedon --write-layouts`: splat и aux побайтно прежние, пропы и свет трека A не тронуты. `--check` сверяет `mesh` и `sea` с генератором, с пределами C++ и с отчётами run K: ширина листа = x1 − x0, центр, край подноса, поднос сборки. Marmoreal без изменений |
| Кук | `DefaultGame.ini` | `+DirectoriesToAlwaysCook=/Game/PipelineCandidates/TableBase/T2b`. Меши водопада и моря лежат в `/Game/EnvKit/Ground/Sarpedon`: эта папка уже куется, и в ней нет «чужих» ассетов для импортёра env-kit |

Строка трассы ground получает хвост ` fallMeshes=M fallMeshParts=P sea=<s>` только если в секции есть меш-водопад или море. Все прежние строки (Marmoreal, тесты) не меняются ни на байт.

## Проверки (без UE)

```
python -m pytest tools/art/tests -q                                # 312 passed, 91 subtests
python -B tools/art/env_kit/ground_splat.py --check                # marmoreal OK, sarpedon OK
python -B tools/art/env_kit/ue_import_env_ground.py --check        # ENVGROUND-IMPORT-RESULT ok
python -B tools/art/env_kit/ue_import_tray_t2.py --check           # ok variant=t2b, sources verified 3 (+ T2 rock 3)
python -B tools/art/env_kit/ue_import_tray_t2.py --check --variant t2   # ok variant=t2
python -B tools/art/env_kit/layout_check.py                        # -> OK
```

Новые тесты Python: `tools/art/tests/test_tray_t2b_import.py` (11) и класс `MeshPieces` в `test_env_ground.py` (9). Они проверяют, что константы C++ (`S08Diorama.h`, `S08EnvGround.h`) совпадают со стороной Python. Новые C++-тесты автоматизации (будут скомпилированы на Integrate): `Unmatched.S08.Diorama.T2bPick`, `T2bAssets`, `Unmatched.S08.EnvLayout.GroundMeshParse`, `GroundMeshGeometry`, `GroundMeshSpawn`; расширены `T2Actor` и `GroundShipped`.

Влияние T2b на края подноса: верх тот же (1560 × 940 на Z −3), губа поднимается до +1,71 только в полосе 20 uu (у T2 было +1,51), свес по сторонам 23 uu (у T2 15,8). Ground-полосы доходят до края верха на Z −1 и, как и раньше, уходят под камни губы. Проверка просветов из отчёта K даёт 0 дыр на глубинах от −3,5 до −55. Границы подноса в `layout_check` (`TRAY_T2`, `RIM_UU`, `LIP_UU`) не меняются. P4-карточка водопада (резерв) стоит на y 457, на 9 uu дальше свеса T2b. Море на Z −172 лежит выше низа обоих подносов (T2 −179,5, T2b −215,7), поэтому его внутренний край прячется под скалой.

## Порядок на Integrate

1. Применить патч `S08BoardActor.cpp` (файл трека C). Текст патча — в приложении ниже (копия: `C:/tmp/trackb/S08BoardActor-T2b-integrate.txt`): `PlaceDioramaTrayT2` переходит на `S08Diorama::LoadTrayT2` / `LoadTrayT2Material` и `kind=%s`. Без патча актор продолжит грузить T2, и `T2Actor` упадёт, как только T2b будет импортирована.
2. Сборка с тестами `Unmatched.S08.Diorama` и `Unmatched.S08.EnvLayout`.
3. Импорт (редактор закрыт): сначала `ue_import_tray_t2.py` (t2b; создаёт и `MI_TableBase_T2b_Sarpedon` для выступа), затем `ue_import_env_ground.py` (M_EnvSea, MI_EnvSea_Sarpedon, четыре меша).
4. После того как трек A закончит пропы, ещё раз запустить `ground_splat.py --write-layouts` (идемпотентно): meta Sarpedon сейчас записала промежуточный хэш пропов трека A (43 пропа), на сам splat это не повлияло.
5. Packaged-сборка с проверкой кука T2b, затем кадры и `render_bench.py`.

## Честные оговорки

- C++ не компилировался (этап CREATE). Код написан по образцу соседнего и прочитан построчно, но первая сборка может найти опечатки.
- Материалы `M_TableBase_T2b` и `M_EnvSea` не видели ни UE, ни кадра. Все параметры вида (MossTint, DepthTint, SeaColor и т. д.) только предложены.
- Направление и масштаб UV листа и пены взяты из отчёта K («UV0 подходит M_EnvWaterfall»). В UE это не проверено.
- `sarpedon.preview.png` перерисован: на оверлее видны текущие (незавершённые) пропы трека A.

## Приложение: патч `S08BoardActor.cpp` (Integrate)

```text
Track B -> Integrate: switch the map-image tray of AS08BoardActor to S08Diorama::LoadTrayT2 (T2b first, T2 fallback,
per-map MI). File owned by track C: unreal/Unmatched/Source/Unmatched/S08/S08BoardActor.cpp, AS08BoardActor::PlaceDioramaTrayT2.
No header change. Grid boards are untouched (PlaceDioramaTray / T1 path unchanged).

1) Replace the first-use load block

  if (!bTrayT2Tried) {
    // Loaded on the first map-image board only: a run that never shows a map loads nothing new.
    bTrayT2Tried = true;
    TrayT2Mesh = LoadObject<UStaticMesh>(nullptr, S08Diorama::T2MeshPath);
    TrayT2Mi = LoadObject<UMaterialInterface>(nullptr, S08Diorama::T2MaterialPath);
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW diorama tray-t2 %s mesh=%s mi=%s%s"), TrayT2Mesh ? TEXT("loaded") : TEXT("absent"),
        S08Diorama::T2MeshPath, TrayT2Mi ? *TrayT2Mi->GetName() : TEXT("missing(mesh default)"),
        TrayT2Mesh ? TEXT("") : TEXT(" (import: tools/art/env_kit/ue_import_tray_t2.py) -> T1 placeholder")));
  }
  if (!TrayT2Mesh) return false;
  if (DioramaTray->GetStaticMesh() != TrayT2Mesh) {
    DioramaTray->SetStaticMesh(TrayT2Mesh);
    DioramaTray->SetMaterial(0, TrayT2Mi);  // nullptr = the mesh's own material
  }

with

  const FString MapName = ActiveProfile.Map.Name;  // "" in a profile-less test world -> the shared MI
  if (!bTrayT2Tried) {
    // Loaded on the first map-image board only: a run that never shows a map loads nothing new. P5 track B: the
    // chunky T2b when it is in the build, else T2 (S08Diorama::LoadTrayT2), else the T1 placeholder below.
    bTrayT2Tried = true;
    const S08Diorama::FTrayT2Assets Assets = S08Diorama::LoadTrayT2(MapName);
    TrayT2Mesh = Assets.Mesh;
    TrayT2Mi = Assets.Material;
    FS08Trace::Write(S08Diorama::TrayT2LoadTraceLine(Assets));
  }
  if (!TrayT2Mesh) return false;
  // T2b: the map's MI (MI_TableBase_T2b_<Map>: Marmoreal moss + petals / Sarpedon damp rock) when imported, else the
  // shared one; T2: MI_TableBase_T2 (nullptr = the mesh's own material)
  UMaterialInterface* MapMi =
      S08Diorama::LoadTrayT2Material(S08Diorama::TrayT2KindOf(TrayT2Mesh), MapName);
  if (!MapMi) MapMi = TrayT2Mi;
  if (DioramaTray->GetStaticMesh() != TrayT2Mesh) DioramaTray->SetStaticMesh(TrayT2Mesh);
  if (DioramaTray->GetMaterial(0) != MapMi) DioramaTray->SetMaterial(0, MapMi);

2) In the tray trace line of the same function replace the literal "kind=T2" in the format string with "kind=%s" and
   pass  S08Diorama::TrayT2KindName(S08Diorama::TrayT2KindOf(TrayT2Mesh))  as the matching argument (between
   "collision=none" and "topHalf=" - i.e. right after S08Diorama::T2MinApronUU(FrameHalf, OffsetY)). The value is "T2b"
   or "T2" ("kind=T2b" still matches a 'kind=T2' substring grep).

Tests that need this patch: Unmatched.S08.Diorama.T2Actor (expects the LoadTrayT2 kind) - with T2b imported but the patch
missing it fails on 'tray mesh = .../SM_TableBase_T2b' (the actor would still load T2).
```
