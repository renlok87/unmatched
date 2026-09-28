# ART-004 · почему не запустился живой packaged K2 с Medusa v3

Дата: 2026-09-28. Арт-трек, п.2. Это диагностика по следам. UE, сборки и прогоны в этой задаче не запускались: UE занят другим workflow. Время в хронологии местное (UTC+5), в логах UE — UTC.

Редакция 2 (тот же день, исправления по ревью P1). Команды проверки в шагах 2 и 3 исправлены и проверены запуском. Механизм переписан: это запись за границу статика (`DeferredRegistry.h:102`), подтверждённая дизассемблером прекомпилированного движка, а не «шаг чтения». Добавлены прецедент S01/S05 и риск R14. Порог `startGame` исправлен на +28 с, время кука — на 06:31. В патче отсутствующая трасса теперь даёт отдельную ошибку, а комментарий защиты больше не утверждает, что падение неизбежно. UE, сборки и прогоны не запускались и в этой редакции.

Редакция 3 (тот же день, замечания к коммиту). Патч не менялся. Добавлен раздел [«Патч в git: окончания строк и хэши»](#патч-в-git-окончания-строк-и-хэши): при коммите git нормализует патч в LF, поэтому sha256 `7ecc6c08…43eb` относится только к нынешнему незакоммиченному файлу. Там же указаны устойчивый идентификатор (blob `8ab88e3`) и природа строк `index`. UE, сборки и прогоны не запускались.

## Вывод

1. **Доказано.** Оба запуска с v3 (08:28:37 и 08:33:20) упали в хост-клиенте примерно через 1,3 с после старта. Падение произошло при регистрации UClass `AS08BoardActor` в `FEngineLoop::PreInitPostStartupScreen`, то есть до загрузки карты, до открытия S08-трассы и до создания комнаты. Код выбора v3 (тела `BeginPlay` и `ApplyFighter`) и ассет `SK_Medusa_HeadTilt_v3Candidate` к этому моменту не исполнялись и не загружались. Ассет v3 при этом был в куке. **Причина не в кандидате v3 и не в логике экспериментального патча.**
2. **Причина: сильная гипотеза, не доказана (A/B-сборки не было).** Отдельные звенья доказаны, связь с этим AV — нет (разбор в [§C](#c-флаг--nolivecoding)).
   - **Доказано.** Обе упавшие сборки игрового target `Unmatched` шли с флагом UBT `-NoLiveCoding`. Флаг задаёт `WITH_LIVE_CODING=0`, а в монолитной игре это означает и `WITH_RELOAD=0`. Сборка компилировала только исходники проекта и линковала прекомпилированные объекты движка UnrealGame, собранные с `WITH_RELOAD=1`. Поэтому статик регистрации класса `FClassRegistrationInfo` у проекта занимает 24 байта, а движок считает его 32-байтным. При регистрации каждого UCLASS проекта движок выполняет `InInfo.ReloadVersionInfo = InVersion` (`DeferredRegistry.h:102`) одной 16-байтной записью по смещению 16. Значит, он пишет 8 байт за конец статика проекта `Z_Registration_Info_UClass_*`, в то, что лежит в памяти следом. Запись видна в дизассемблере прекомпилированного `CoreUObject`.
   - **Гипотеза.** Эта порча и дала мусорный указатель, на котором падает `Z_Construct_UClass_AS08BoardActor`.
   - **Это не «шаг чтения» массива.** В каждом gen.cpp модуля ровно один элемент `ClassInfo[]`, поэтому разница шага массивов у проекта и движка ни на что не влияет.
   - **Контрпример к «флаг всегда роняет клиент».** S01 и S05 собирали игровой target с тем же флагом, и их упакованный клиент работал. Вероятное объяснение: результат порчи зависит от раскладки памяти, а в модуле тогда был один UCLASS без отражённых свойств. Это объяснение тоже гипотеза.
   - Среди сборок игрового target за 2026-09-28 `-NoLiveCoding` есть только у двух упавших.
3. **Доказано.** Контрольный прогон на 45 с без v3 прошёл без снимков, и длительность тут ни при чём. `-ArtPreviewBoardId 'cobble-city'` — это контентный slug, а не id строки `Board` в БД. Бэкенд сохранил строку как есть, доску не нашёл и молча собрал пустую сетку 20×20. Арт-доска 5×6 не активировалась, а в режиме ArtPreview других путей к снимку нет, поэтому снимка не было бы при любой длительности. Рабочие K2-прогоны шли с `cmuhgs4b2001mwik4f2b2xtf8` (5×6) и `-RunSeconds 38`. v3-запуски шли с тем же ошибочным `cobble-city`: даже без падения они не дали бы K2.

Статусы. v3 **технически импортирован** в изолированный `/Game/ArtPreview/Medusa` арт-worktree и **художественно не принят** ([акт v3](#источники)). Живой packaged K2 с v3 **не выполнен**. Место и момент падения **доказаны**, причина падения — **гипотеза**. Патч ниже **предложен** и не применён. Все длительности **измерены** по трассам, бюджетами они не являются.

## Хронология

| Время | Что | Источник | Итог |
| --- | --- | --- | --- |
| 08:15–08:16 | Игровой импорт v3 в `/Game/ArtPreview/Medusa/Meshes/SK_Medusa_HeadTilt_v3Candidate` | `Artifacts/ART004Face/headtilt-game-import{,-v2}.log` | `ART004_GAME_CANDIDATE_IMPORT_OK` |
| 08:17:55 | `package-client.ps1` (BuildCookRun `-build`) | `headtilt-package.log` | `Unable to build while Live Coding is active` → `BUILD FAILED`, ExitCode 6 |
| 08:19:35 | `Build.bat UnmatchedEditor … -NoHotReloadFromIDE -NoLiveCoding -MaxParallelActions=4` (XGE) | `headtilt-editor-build.log` | `C3859`/`C1076`: не хватило виртуальной памяти под PCH, системная ошибка 1455 |
| 08:22:57 | То же с `-NoXGE -NoUBA -MaxParallelActions=2` | `headtilt-editor-build-local.log` | Succeeded |
| 08:23:22 | `Build.bat Unmatched … -NoHotReloadFromIDE -NoLiveCoding -NoXGE -NoUBA -MaxParallelActions=2` | `headtilt-game-build-local.log` | Succeeded |
| 08:24:49 | `package-client.ps1 -SkipBuild` (временная правка) | `headtilt-package-skipbuild.log` | BUILD SUCCESSFUL, 606 пакетов |
| 08:26:53 | Отдельный бэкенд на `:3100` (та же БД 55434 и Redis 6381 из `backend/.env`) | `headtilt-backend.log` | запущен |
| 08:28:37 | `run-phase2-demo.ps1 … -ArtPreviewBoardId 'cobble-city' -ArtPreviewFocusZoom 5 -ArtPreviewHeadTiltV3 -RunSeconds 55` | stdout в журнале агента | `host pid=3484` → `host client exited before publishing a code`, скрипт отработал за 1,85 с |
| 08:31:22 | `Build.bat Unmatched … -Rebuild -NoHotReloadFromIDE -NoLiveCoding …` | `headtilt-game-rebuild-local.log` | Succeeded |
| 08:32:39 | `package-client.ps1 -SkipBuild` | `headtilt-package-rebuild.log` | BUILD SUCCESSFUL |
| 08:33:20 | Тот же прогон v3 | stdout в журнале агента | `host pid=46404` → то же падение, 1,82 с |
| 08:37:01 | Эксперимент сохранён в `headtilt-live-flag-experiment.patch` и откатан (`git restore`) | журнал агента | — |
| 08:37:18 | `Build.bat Unmatched … -Rebuild -WaitMutex -NoXGE -NoUBA -MaxParallelActions=2`, **без** `-NoLiveCoding` | `baseline-game-rebuild-local.log` | Succeeded |
| 08:38:39 | BuildCookRun `-skipbuild` | `baseline-package.log` | BUILD SUCCESSFUL |
| 08:40:18 | Контроль: `… -ArtPreviewBoardId 'cobble-city' -ArtPreviewFocusZoom 5 -RunSeconds 45` | `%TEMP%/s08-phase2-20260928-084018-50660/*.trace.log` | Клиенты стартовали, комната создана, `BOARD 20x20`, снимков нет: `evidence shot missing for host` |

Логи сборок лежат в `C:/Users/ren/.codex/worktrees/art-foundation/unmached/unreal/Unmatched/Artifacts/ART004Face/` (каталог `Artifacts/` в git не входит). Журнал агента: `C:/Users/ren/.codex/sessions/2026/09/27/rollout-2026-09-27T08-29-12-01a0e0e8-dd50-7753-a50d-89d27fdadb9d.jsonl`, строки 21749–22000.

## Доказательства

### A. Как упал клиент

Упакованный `Unmatched.log` из `Saved/StagedBuilds/Windows/Unmatched/Saved/Logs/` не сохранился: следующая упаковка чистит stage-каталог (`Cleaning Stage Directory`). Строки ниже агент прочитал из этого файла до очистки, и они сохранились в его журнале (строки 21770 и 21858). Запуск 08:28:

```text
[2026.09.28-03.28.39:065] LogWindows: Error: Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0xffffffffffffffff
[Callstack] Unmatched.exe!FPropertyReferenceCollector::HandleObjectReference()
[Callstack] Unmatched.exe!FObjectPropertyBase::AddReferencedObjects()
[Callstack] Unmatched.exe!FArrayProperty::AddReferencedObjects()
[Callstack] Unmatched.exe!UStruct::Link()
[Callstack] Unmatched.exe!UStruct::StaticLink()
[Callstack] Unmatched.exe!CollectSetReferences<11>()
[Callstack] Unmatched.exe!Z_Construct_UClass_AS08BoardActor() [...UHT\S08BoardActor.gen.cpp:199]
[Callstack] Unmatched.exe!UObjectInitialized()
[Callstack] Unmatched.exe!ProcessNewlyLoadedUObjects()
[Callstack] Unmatched.exe!FEngineLoop::PreInitPostStartupScreen()
[Callstack] Unmatched.exe!GuardedMain()
```

В запуске 08:33 (`03.33.21:733` UTC) стек тот же, адреса другие.

В командной строке клиента были `-ArtPreview -ForceRes -ArtPreviewHeadTiltV3 … -ArtPreviewBoardId=cobble-city -ArtPreviewShotAfter=30 -ArtPreviewSelectOwnHero -ArtPreviewFocusZoom=5`.

Независимые подтверждения:

- Staging-каталоги `%TEMP%/s08-phase2-20260928-082837-40852` и `…-083320-45880` пусты, время изменения совпадает со временем создания. Значит, `FS08Trace::Open()` не вызывался. Он вызывается в `AS08FlowGameMode::BeginPlay` ([S08FlowGameMode.cpp:187](../../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp)), а до этого вызова клиент не дошёл.
- В `headtilt-backend.log` между 08:26:53 и 08:40:22 нет ни одного `GameActionProcessor`. Первые записи появляются только в контрольном прогоне.
- В журнале Windows Application за 08:26–08:40 нет событий Application Error для `Unmatched.exe`. Это ожидаемо: UE перехватывает исключение сам, а CrashReportClient не стартовал (`Could not start crash report client`).

### B. Почему дело не в v3 и не в логике патча

- Порядок исполнения. Падение происходит в PreInit, при построении UClass, до загрузки карты `/Game/S08/S08Arena`. `AS08BoardActor::BeginPlay` и `AS08FighterActor::ApplyFighter`, куда патч добавил `FParse::Param(…"ArtPreviewHeadTiltV3")`, выполняются после входа в матч. Раньше этого они сработать не могли.
- Патч менял только тела функций в `.cpp`. `S08BoardActor.h` и `UPROPERTY` он не трогал, поэтому `S08BoardActor.gen.cpp` от него не зависит (эксперимент: `…/Artifacts/ART004Face/headtilt-live-flag-experiment.patch`).
- Ассет v3 попал в пак. `/Game/ArtPreview/Medusa` входит в `+DirectoriesToAlwaysCook` ([DefaultGame.ini:18](../../../../unreal/Unmatched/Config/DefaultGame.ini)), поэтому ловушка п.5 из ue-pipeline-traps (мягкие ссылки `LoadObject` выпадают из кука) здесь не срабатывает. Все три кука после импорта v3 дали `Total 606`. Кук перед K2-прогонами завершился в 06:31 и дал `Total 603` (журнал агента, строка 18646, `01:31:55Z`). Тот же `Total 603` записан и в `Artifacts/ART004Face/art-preview-uat-selection-corners.log` (06:18). В текущем `Saved/Cooked/Windows/Unmatched/Metadata/DevelopmentAssetRegistry.bin` арт-worktree есть `SK_Medusa_HeadTilt_v3Candidate` и `…_Skeleton`.
- `LoadObject` на отсутствующий ассет не роняет клиент: код проверяет `nullptr` и пишет `ARTPREVIEW Cobble assets missing` или `visual=0`.
- Гипотеза агента «повреждённые объектники после прерванной компиляции» опровергнута: полная пересборка `-Rebuild` в 08:31 дала то же падение.

### C. Флаг `-NoLiveCoding`

Сборки игрового target `Unmatched` за 2026-09-28 по журналу агента (время UTC):

| Сборки | Флаги | Упакованный клиент |
| --- | --- | --- |
| 00:21, 00:28–01:17 (6 шт.), 01:31, 01:38, 01:54, 02:19–02:30 | `-WaitMutex -NoXGE …`, `-WaitMutex -NoHotReloadFromIDE -NoXGE …`, `-NoXGE -MaxParallelActions=2` | работал: опубликованы K1, ART-003/005 и четыре K2 |
| 03:23, 03:31 (`-Rebuild`) | `-WaitMutex -NoHotReloadFromIDE -NoLiveCoding -NoXGE -NoUBA -MaxParallelActions=2` | **падал на старте** |
| 03:37 (`-Rebuild`, без патча) | `-WaitMutex -NoXGE -NoUBA -MaxParallelActions=2` | стартовал: трасса, комната, HUD |

`-NoHotReloadFromIDE` был и в рабочих сборках, `-NoXGE -NoUBA` есть и в рабочей сборке 03:37. Среди сборок игрового target за 2026-09-28 остаётся `-NoLiveCoding`. Но это сравнение ограничено одним днём, и за его пределами есть контрпример.

#### Прецедент S01/S05: тот же флаг, клиент работал

- Отслеживаемые git скрипты `tools/s01/ue_build.ps1:16` и `tools/s05/s05_build.ps1:29` собирают игровой target `Unmatched` с `-WaitMutex -NoHotReloadFromIDE -NoLiveCoding`. Затем они упаковывают его через `BuildCookRun` без `-build`, то есть в пак идёт exe, собранный с этим флагом. В `tools/s01/ue_build.ps1` строка 16 была такой же уже в базовом коммите S01 `c8957e4`.
- Эти клиенты работали на том же UE 5.8.2 CL 56702186:
  - S01, 2026-09-18: `S01_SMOKE_READY` и `S01_SMOKE_COMPLETE`, код выхода 0 (`docs/game-design/evidence/S01/ue/runtime-output.txt`, `build-manifest.json`).
  - 2026-09-25: регрессия S01 прошла в 15:17:12Z, упакованный смоук S05 — в 15:37:32Z, exit 0 (`docs/game-design/evidence/S05/art-references/art-visual-reference-report.md`).
- В worktree `glm-sprint-check` (ветка `codex/s05-abilities-medusa`) у игрового target во всех 8 `SharedDefinitions.*.h` стоит `#define WITH_LIVE_CODING 0` (от 2026-09-25 13:27). Хэш упакованного `Artifacts/S05/Windows/Unmatched/Binaries/Win64/Unmatched.exe` совпадает с `Binaries/Win64/Unmatched.exe` (`09ffc850…`). Значит, флаг действительно попал в exe, который работал.
- Модуль тогда был другим: один `SmokeGameMode.gen.cpp`, один UCLASS `ASmokeGameMode`, ни одного отражённого свойства. Сейчас в модуле четыре UCLASS. У `AS08BoardActor` 11 `UPROPERTY`, среди них `TArray<TObjectPtr<AS08FighterActor>> FighterActors`.

Вывод: утверждение «с `-NoLiveCoding` игровой клиент падает всегда» неверно. Запись за границу (см. ниже) происходит при регистрации каждого UCLASS проекта. Упадёт ли клиент, зависит от того, что лежит в памяти следом за статиком и разыменовывается ли это при старте. С одним классом без свойств порча могла прийтись на место, которое при старте не читается. Это объяснение — **гипотеза**, и уверенность в причине держится на нём. Практический вывод: если сборка с флагом «запустилась», это не доказывает, что флаг безопасен. Любая правка модуля может сдвинуть раскладку (риск R14).

#### Механизм

Всё по исходникам установленного UE 5.8 (`C:/Program Files/Epic Games/UE_5.8/Engine/Source/`) и его прекомпилированным объектам:

- `Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:1585–1591`: `[CommandLine("-NoLiveCoding", Value = "false")] bWithLiveCoding`. По умолчанию значение `true` для Win64, не Shipping/Test, не Program.
- `Configuration/UEBuildTarget.cs:6599–6606`: в зависимости от флага задаётся `WITH_LIVE_CODING=1` или `0` для всего окружения компиляции проекта.
- `Runtime/Core/Public/Misc/Build.h:150`: `WITH_HOT_RELOAD = (!IS_MONOLITHIC && … && !UE_GAME …)`. Для монолитной игры это 0. Строка 163: `WITH_RELOAD = (WITH_HOT_RELOAD || WITH_LIVE_CODING)`, то есть в игре `WITH_RELOAD` совпадает с `WITH_LIVE_CODING`.
- `Runtime/CoreUObject/Public/UObject/UObjectBase.h:513–549`: `FClassRegistrationInfo = TRegistrationInfo<UClass, FClassReloadVersionInfo>`, то есть `{ InnerSingleton, OuterSingleton, ReloadVersionInfo }`. Это статик `Z_Registration_Info_UClass_*` в каждом gen.cpp. Поля `FClassReloadVersionInfo` (`SIZE_T Size; uint32 Hash;`, строки 527–533) существуют только `#if WITH_RELOAD`, без него структура пустая. В `Class.h:2595` поле `UFunction::SingletonPtr` тоже существует только `#if WITH_LIVE_CODING`.
- Раскладка **измерена** на модели этих определений компилятором `cl` из того же каталога MSVC `14.44.35207`, что указан в логах упавших сборок:

  | Структура | `WITH_RELOAD=0` (проект с флагом) | `WITH_RELOAD=1` (движок) |
  | --- | --- | --- |
  | `FClassRegistrationInfo` | 24 байта, `ReloadVersionInfo` по смещению 16 (1 байт) | 32 байта, `ReloadVersionInfo` по смещению 16 (16 байт) |
  | `FClassRegisterCompiledInInfo` | 32 байта, `VersionInfo` по смещению 24 | 40 байт, `VersionInfo` по смещению 24 |
  | `FPackageRegistrationInfo` | 24 байта | 24 байта |

- `Runtime/CoreUObject/Private/UObject/DeferredRegistry.h:95–102`: `TDeferredRegistry::AddRegistration` под `#if WITH_RELOAD` выполняет `InInfo.ReloadVersionInfo = InVersion;` (строка 102). Здесь `InInfo` — статик проекта `Z_Registration_Info_UClass_*`, а `InVersion` — поле `VersionInfo` из `ClassInfo[0]` проекта. Вызов идёт из `RegisterCompiledInInfo` (`UObjectBase.cpp:755–758`, цикл 787–791) во время статической инициализации модуля, до `PreInit`.
- **Дизассемблер** прекомпилированного `Engine/Intermediate/Build/Win64/x64/UnrealGame/Development/CoreUObject/Module.CoreUObject.13.cpp.obj` (`dumpbin /disasm`, функция `TDeferredRegistry<FClassRegistrationInfo>::AddRegistration`, ветка новой регистрации):

  ```text
  mov    r14,qword ptr [rsp+0F0h]     ; InInfo
  movups xmm0,xmmword ptr [r10]       ; InVersion, 16 байт
  movups xmmword ptr [r14+10h],xmm0   ; запись в байты 16…31
  ```

  Для 24-байтного статика проекта байты 24…31 лежат **за его концом**: затираются 8 байт того, что расположено следом. Чтение тоже выходит за границу. Движок берёт 16 байт со смещения 24 из 32-байтного элемента `ClassInfo[0]`, то есть 8 байт после конца массива. Поэтому в затёртые 8 байт попадает содержимое памяти сразу за массивом `ClassInfo[]` проекта (массив `static constexpr`, скорее всего в `.rdata`). В модуле 4 UCLASS, значит, таких записей 4. Для пакета записи за границу нет: 8 байт `FPackageReloadVersionInfo` помещаются в 24 байта.
- **Это не «шаг чтения» массива.** В каждом gen.cpp модуля (`S08BoardActor`, `S08FighterActor`, `S08FlowGameMode`, `SmokeGameMode`) ровно один элемент `ClassInfo[]` и нет массивов структур или перечислений. Разница шага 32 и 40 байт поэтому не влияет на `Register`, `Name` и `Info`.
- Сторона движка: в том же `Module.CoreUObject.13.cpp.obj` есть вызов `IsReloadActive` и запись Fatal-лога «Trying to recreate changed class». Оба компилируются только `#if WITH_RELOAD` (`UObjectBase.cpp:759–765`). Кроме того, символ `UClass::HotReloadPrivateStaticClass` определён только `#if WITH_RELOAD` (`CoreUObject/Private/UObject/Class.cpp:6809–6811`) и есть в 2 прекомпилированных `Module.CoreUObject.*.cpp.obj`. Значит, движок UnrealGame собран с `WITH_RELOAD=1`.
- Движок при сборке не перекомпилировался. В логах упавших сборок 33 и 34 действия: общий PCH проекта, `Module.Unmatched.cpp`, исходники проекта, `Link Unmatched.exe`. Сборки заняли 54 и 64 с. `Module.Unmatched.cpp` включает все gen.cpp модуля в одну единицу трансляции, в порядке `S08BoardActor` → `S08FighterActor` → `S08FlowGameMode` → `SmokeGameMode` → `Unmatched.init`.
- Сторона проекта: флаг действительно меняет define.
  - В арт-worktree `Intermediate/Build/Win64/x64/UnmatchedEditor/Development/*/SharedDefinitions.*.h` (сборка 08:19–08:23 с `-NoLiveCoding`) содержит `#define WITH_LIVE_CODING 0`.
  - Игровой `…/x64/Unmatched/Development/*/SharedDefinitions.*.h` после рабочей сборки 08:37 содержит `#define WITH_LIVE_CODING 1` во всех 8 файлах. Определения игрового target упавших сборок затёрты этой сборкой.
  - Для игрового target с флагом значение 0 видно в `glm-sprint-check` (8 файлов, см. прецедент выше).
- Почему редактор и кук с тем же флагом не падали: в модульном редакторе `WITH_HOT_RELOAD=1`, поэтому `WITH_RELOAD=1` при любом значении `WITH_LIVE_CODING`, и раскладка регистрации совпадает. Расходится только `UFunction::SingletonPtr`. Куки 08:24, 08:32 и 08:38 с этой DLL завершились с ExitCode 0.
- Откуда взялся флаг: `BuildCookRun -build` сначала собирает `UnmatchedEditor`. Движок `UnrealEditor.exe` общий с открытым редактором пользователя, у того включён Live Coding, и UBT отказался собирать. Агент обошёл это отдельной сборкой с `-NoLiveCoding` и перенёс флаг на игровой target, которому он не нужен.

#### Что доказано, а что гипотеза

**Доказано** (логи, исходники, дизассемблер, измерение):

1. Хост-клиент упал при построении UClass `AS08BoardActor`, до загрузки карты и открытия трассы (§A).
2. Обе упавшие сборки игрового target собраны с `-NoLiveCoding`. Остальные сборки игрового target за 2026-09-28 собраны без него, и их клиенты работали.
3. С этим флагом проект компилируется с `WITH_LIVE_CODING=0`, то есть `WITH_RELOAD=0`. Прекомпилированный движок UnrealGame собран с `WITH_RELOAD=1`, и при сборке игры он не перекомпилировался.
4. При таком сочетании движок при регистрации каждого UCLASS проекта пишет 8 байт за конец его статика `Z_Registration_Info_UClass_*` (`DeferredRegistry.h:102`, `movups [r14+10h]`).
5. S01 и S05 с тем же флагом работали. Их модуль содержал 1 UCLASS без отражённых свойств.

**Гипотеза** (сильная, не доказана):

- Запись за границу затёрла указатель, который разыменовывается при построении `AS08BoardActor`. Один из правдоподобных кандидатов — `InnerSingleton` регистрации `AS08FighterActor`. Аргументы:
  - все gen.cpp лежат в одной единице трансляции, и в исходном тексте следующий статик регистрации класса после `AS08BoardActor` — статик `AS08FighterActor`. Между ними ещё пустой объект `FRegisterCompiledInInfo`, а фактический порядок в `.bss` определяют компилятор и линкер;
  - падение идёт через `FArrayProperty` → `FObjectPropertyBase::AddReferencedObjects`, а у `AS08BoardActor` единственный массив объектов класса проекта — `FighterActors`;
  - движок не разыменовывает результат `InnerRegister` при регистрации (`UObjectBase.cpp:830–839`), поэтому испорченный указатель впервые читается при построении свойств другого класса.

  Раскладку `.bss` упавшего exe проверить нельзя: exe и его PDB затёрты сборкой 08:37. Адрес `0xffffffffffffffff` в отчёте Windows об AV обычно означает неканонический адрес. Это согласуется с мусором вместо указателя, но ничего не доказывает.
- Прецедент S01/S05 не опровергает гипотезу, только если исход порчи зависит от раскладки (см. выше). Это тоже не проверено.

**Как проверить** (A/B, когда UE освободится):

1. Собрать базовый код без патча с `-NoLiveCoding`. Ожидается то же падение.
2. Собрать код с патчем без флага. Ожидается нормальный старт.
3. Если сборка с патчем без флага упадёт так же, гипотеза опровергнута.
4. Дополнительно в сборке с флагом проверить по PDB, что лежит сразу за `Z_Registration_Info_UClass_AS08BoardActor`.

### D. Контрольный прогон 45 с без снимков

Команда: `run-phase2-demo.ps1 -Api http://localhost:3100/graphql -EvidenceDir unreal/Unmatched/Artifacts/ART004Face/baseline-packaged-smoke -ArtPreviewBoardId 'cobble-city' -ArtPreviewFocusZoom 5 -RunSeconds 45 -ClientFps 30`. Результат: `both clients exited`, комната прогона отменена (`ABORTED (verified)`), затем исключение `evidence shot missing for host` ([run-phase2-demo.ps1:405](../../../../tools/s08/run-phase2-demo.ps1)).

Трассы (`%TEMP%/s08-phase2-20260928-084018-50660/`): у хоста и у присоединившегося есть `BOARD 20x20 cells`, `ARTPREVIEW Cobble assets ready`, `HUD seq=1 phase=ACTION_MANEUVER`, `HANDLE_APPLIED … boardValid=1`. Нет ни `ARTPREVIEW Cobble active 5x6`, ни `ARTPREVIEW fighter=Medusa`, ни одной строки `SHOT`. Трассы закрываются через 45 с (03.40.19 → 03.41.04 и 03.40.23 → 03.41.09).

Почему получилось 20×20:

- `backend/src/games/game.service.ts:114`: `boardId` из запроса сохраняется как есть. `Game.boardId` — обычный `String` без связи с `Board` (`backend/prisma/schema.prisma:200`), поэтому несуществующий id принимается. Проверка boardId в скрипте сравнивает ту же строку и проходит.
- `backend/src/games/services/game-initialization.service.ts:82–85`: `prisma.board.findUnique({ where: { id: 'cobble-city' } })` возвращает `null`. Тогда `buildBoardState(null)` (строки 341–343) молча собирает пустую сетку `FALLBACK_BOARD_SIZE=20`. Будь строка найдена с пустыми `cells`, в логе появилось бы `Доска «…»: cells пусты`, а такой строки в `headtilt-backend.log` нет. `cobble-city` — id контентного описания 6×4 (`backend/src/content/data/boards/cobble-city.ts`), а не строки БД.
- Клиент: `SupportsCobbleArt` ([S08BoardActor.cpp:29–36](../../../../unreal/Unmatched/Source/Unmatched/S08/S08BoardActor.cpp)) требует 5×6, 30 клеток `Normal` и ровно одну зону `blue` или `red`. `bArtActive = bArtAssetsReady && SupportsCobbleArt(Board)` (строка 258), и этот же флаг передаётся в `ApplyFighter` (строка 426). На 20×20 кандидат Medusa не подключается вовсе.

Почему не было снимков при любой длительности ([S08FlowGameMode.cpp:3208–3257](../../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp)):

- Снимок ArtPreview (строка 3236) требует `BoardActor->IsArtActive()`, а на 20×20 он ложен.
- Запасной путь S08 снимает после завершённого манёвра у хоста или после cue у присоединившегося. В режиме ArtPreview скрипт не передаёт `-S08Maneuver` (строки 325–331), манёвра нет, cue нет, и этот путь тоже не срабатывает.

#### Какая нужна длительность и когда делается снимок

По четырём успешным K2 (`live-k2-zoom-probe-{1p6,5x}`, `live-k2-label-probe-{1p6,5x}`, все с `-RunSeconds 38`), от открытия трассы хоста (T0):

| Событие | Хост | Присоединившийся |
| --- | --- | --- |
| Трасса открыта | T0 | T0 + 4…5 с |
| `createGame` / `joinGame` | +3 с | +3 с от своего старта |
| `startGame` | +18 с во всех четырёх | — |
| `BOARD 5x6` | +18…19 с | T0 + 19…20 с |
| `ARTPREVIEW selection` и `camera focus` (K2) | +28 с (ShotAfter − 2) | — |
| `SHOT requested` | +30 с | +30 с от своего старта (T0 + 34…35 с) |
| Трасса закрыта, процесс выходит | +38 с | +38 с от своего старта (T0 + 42…43 с) |

Точность — 1 с (так пишутся метки времени в трассе). `Elapsed` в `AS08FlowGameMode::Tick` считается от старта режима каждого клиента отдельно, это примерно T0 его трассы.

Условия снимка ArtPreview (все одновременно):

1. `-ArtPreview`, `-ArtPreviewShotAfter=30` у обоих клиентов и `-S08Shot=<путь>`. Всё это задаёт скрипт.
2. Снапшот содержит доску 5×6, 30 клеток `Normal`, у каждой одна зона blue или red. Board id берётся из БД: `cmuhgs4b2001mwik4f2b2xtf8`.
3. Загружены все арт-ассеты, включая **выбранную** сетку Medusa со скелетом, подставку и две MI (иначе `bArtAssetsReady=false`).
4. Стадия `Started`, применён снапшот с `SequenceNumber > 0`.
5. С `BeginPlay` режима прошло не меньше 30 с, и процесс ещё жив.
6. Для K2 у хоста: `-ArtPreviewSelectOwnHero`, свой герой жив, `-ArtPreviewFocusZoom > 1`. Выбор героя происходит в первый тик, когда `Elapsed ≥ ShotAfter − 2` (28 с), арт-доска активна и стадия `Started`. Если доска активна к +28 с, у камеры есть 2 с на подлёт.

Длительность. 38 с проверены 4 раза. После снимка присоединившегося до выхода **хоста** остаётся 3–4 с, до выхода **самого присоединившегося** — 8 с. **Рекомендуется `-RunSeconds 45`**: это добавляет 7 с к обоим запасам на запись PNG 1920×1080 и на медленный старт присоединившегося.

Порог `startGame` (вывод из порядка кода в одном `Tick`, [S08FlowGameMode.cpp:3208–3241](../../../../unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp): выбор, затем `UpdateBoardCamera`, затем снимок; поздний старт не наблюдался):

- Арт-доска активна к +28 с (по трассе хоста это `startGame` плюс не больше 1 с до `BOARD 5x6`): выбор в +28 с, снимок в +30 с, полные 2 с подлёта.
- Активна между +28 и +30 с: выбор сразу при активации, подлёта меньше 2 с.
- Активна в +30 с или позже: выбор и снимок в одном тике, K2-кадр снимется до подлёта камеры.

Порог в коде — +28 с. **+26 с — рабочий запас**, а не порог: он покрывает задержку между `startGame` и активацией доски и шаг тика. Если `startGame` приходит позже, нужно поднять `ArtPreviewShotAfter` (в скрипте жёстко 30, строки 326 и 389) и держать `RunSeconds ≥ ShotAfter + 15` (при `ShotAfter` 30 это те же 45 с), чтобы сохранить рекомендованные запасы. Увеличение одной длительности без правильной доски снимков не даст.

## Минимальный безопасный план подключения кандидата

Принципы:

- Производственные `/Game/ART004/Medusa` и `SK_Medusa` не трогаются.
- Выбор кандидата — опциональный флаг командной строки, по умолчанию остаётся v2. Разрешены только пути из списка в `/Game/ArtPreview/Medusa`.
- Прогон делается в арт-worktree, потому что только там есть `.uasset` v3 (`Content/` игнорируется git).
- UE запускать только после того, как T4 освободит его.

### Патч (предложен, не применён)

[v3-live-hookup.patch](v3-live-hookup.patch), редакция 2, sha256 `7ecc6c08…43eb` (первая редакция — `04b9f778…e531`). Этот sha256 — байты нынешнего незакоммиченного файла; после коммита он не совпадёт, см. [ниже](#патч-в-git-окончания-строк-и-хэши). Что изменилось:

- в `run-phase2-demo.ps1` появилась отдельная ошибка для отсутствующей трассы;
- комментарий защиты в `package-client.ps1` теперь говорит «can then crash», а не «then crashes», в соответствии с прецедентом S01/S05;
- строки `index` для обоих `.ps1` обновлены: `bb50e9b` и `3248938`.

Проверки редакции 2:

- `git apply --check` (только проверка, без применения) проходит в арт-worktree и на `fix/admin-panel`. В обоих checkout проходят и варианты патча, целиком переведённые в LF или в CRLF, так что нормализация окончаний строк при коммите его не сломает.
- Патч применён к копиям четырёх файлов во временном каталоге. Хэши всех пяти результирующих файлов совпадают со строками `index` патча. Оба `.ps1` разбираются парсером Windows PowerShell 5.1 без ошибок.
- Новая проверка трасс вынута из пропатченного скрипта через AST и прогнана на пяти синтетических случаях и на настоящих трассах:
  - пустой staging-каталог v3-запуска 08:28 → «trace missing»;
  - контроль 08:40 (20×20) → «no 'BOARD 5x6'»;
  - K2 `live-k2-zoom-probe-5x` → проходит.
- Новый заголовок проверен `cl /Zs /std:c++20` на заглушках в первой редакции и с тех пор не менялся.

Полная сборка UE не выполнялась.

| Файл | Изменение |
| --- | --- |
| `unreal/Unmatched/Source/Unmatched/S08/S08ArtPreviewMedusa.h` (новый) | Список вариантов: `face-neck-v2` (по умолчанию) и `head-tilt-v3` → путь `/Game/ArtPreview/Medusa/Meshes/…Candidate`. Для неизвестного значения сетки нет: доска остаётся серой, и прогон падает явно, а не показывает v2 под именем v3 |
| `S08/S08BoardActor.cpp` | Проверка готовности арт-доски грузит выбранный вариант. В трассу пишутся `ARTPREVIEW medusa candidate variant=… mesh=…`, а при неудаче `ARTPREVIEW Cobble assets missing medusaVariant=… medusa=0/1` (раньше это уходило только в UE-лог) |
| `S08/S08FighterActor.cpp` | Герой-Medusa грузит выбранный вариант, остальная логика прежняя |
| `tools/s08/run-phase2-demo.ps1` | `-ArtPreviewMedusaVariant face-neck-v2\|head-tilt-v3` (ValidateSet, только вместе с `-ArtPreviewBoardId`). Флаг передаётся обоим клиентам. До проверки снимков идут две разные явные ошибки. Если файла трассы нет, клиент вышел до `AS08FlowGameMode::BeginPlay`: сообщение `trace missing` советует сохранить `Saved\Logs` до следующей упаковки. Если трасса есть, но в ней нет `BOARD 5x6`, виноват `ArtPreviewBoardId`. Трасса хоста к этому моменту есть всегда: без неё скрипт раньше падает на `host client exited before publishing a code`. Поэтому первая ошибка на практике относится к присоединившемуся. Для хоста и присоединившегося проверяются `variant=…`, `visual=1 mesh=<ожидаемая сетка>`, `boardValid=1` и `HUD seq=`. В `art-preview-status.json` добавлено `medusaVariant` |
| `tools/s08/package-client.ps1` | `-SkipBuild` (упаковка уже собранного клиента). С этим флагом упаковка останавливается, если в `Intermediate/…/Unmatched/Development/*/SharedDefinitions.*.h` игрового target есть `WITH_LIVE_CODING 0`. Проверено на текущих файлах: игровой target в обоих checkout проходит, каталоги редактора (там 0) детектор ловит |

Отличия от отменённого эксперимента: список вариантов вместо булева флага; явная ошибка вместо тихого v2; защита от `-NoLiveCoding`; проверка доски 5×6; строки трассы с вариантом.

### Патч в git: окончания строк и хэши

Сейчас файл занимает 13 013 байт, в нём 225 строк. 189 строк тела (контекст, `+`, `-`) кончаются CRLF, как рабочие файлы в checkout. 36 строк заголовков (`diff --git`, `index`, `new file mode`, `---`, `+++`, `@@`) кончаются LF. Это следствие того, что diff снят с рабочих файлов с CRLF, а не порча.

**Что будет при коммите.** В системном `C:/Program Files/Git/etc/gitconfig` стоит `core.autocrlf=true`, `core.safecrlf` не задан, правил `.gitattributes` для этого пути нет. Проверено в отдельном репозитории в `C:/tmp` с той же настройкой: `git add`, удаление файла, `git checkout` из индекса, без коммитов.

| Вариант | Байт | sha256 | git blob |
| --- | --- | --- | --- |
| Нынешний незакоммиченный файл (смешанные окончания) | 13 013 | `7ecc6c08…43eb` | — |
| Что `git add` положит в репозиторий (всё LF) | 12 824 | `77b49fbe…3460` | `8ab88e3` |
| Checkout на Windows с `autocrlf=true` (всё CRLF) | 13 049 | `5a28f635…ed54` | `8ab88e3` |

`git add` предупреждает `LF will be replaced by CRLF the next time Git touches it` и завершается успешно. После коммита sha256 `7ecc6c08…43eb` не совпадёт ни в одном checkout. Устойчивый идентификатор — blob `8ab88e316d970dca8a49774ffbdb663ef411dce2`. Его дают `git rev-parse HEAD:docs/game-design/evidence/ART-004/v3-live-hookup.patch` после коммита и `git hash-object --path=<путь> <файл>` для любого из трёх вариантов при `autocrlf=true`.

Сохранить байты как есть можно правилом `docs/game-design/evidence/ART-004/*.patch -text` в `.gitattributes`, как уже сделано для свидетельств S08 и S09. Тогда blob будет `c9837ca`, а sha256 останется `7ecc6c08…43eb`. `.gitattributes` вне этой задачи, решение за оркестратором.

Работе патча нормализация не мешает:

- `git apply --check` проходит для нынешнего файла, для LF- и для CRLF-варианта в обоих checkout (`fix/admin-panel` `c43826d`, арт-worktree `3950132`), код выхода 0.
- В отдельном репозитории с теми же исходными blob и CRLF в рабочих файлах все четыре варианта (нынешний, LF, CRLF и восстановленный из индекса) дают побайтно одинаковые пять файлов. Их хэши совпадают со строками `index` патча.

Ещё две особенности патча:

- **Строки `index`.** Это хэши рабочих файлов с CRLF (`git hash-object --no-filters`), а не blob репозитория. В HEAD обоих checkout эти четыре файла лежат как `dbb88a8`, `23cbfac`, `280d8a2` и `7706bda`, а blob `edfaf9f`, `35954fd`, `cdc0ac4` и `f4b5672` в репозитории нет. Обычный `git apply` (шаг 1) на них не смотрит. Запасной трёхсторонний `git apply --3way` не сработает: ему не из чего восстановить исходную версию.
- **Предупреждения о пробелах.** `git apply` без `--check` для нынешнего, CRLF- и восстановленного варианта пишет `trailing whitespace` и `31 lines add whitespace errors`; у LF-варианта их нет. Это CR в конце строк нового файла `S08ArtPreviewMedusa.h`. Код выхода 0, результат тот же. `apply.whitespace` в обоих checkout не задан. Если выставить его в `error`, применять с `--whitespace=nowarn`.

### Шаги (PowerShell, корень арт-worktree `C:\Users\ren\.codex\worktrees\art-foundation\unmached`)

0. **Предусловия.** T4 закончил и освободил UE. `unreal\Unmatched\Content\ArtPreview\Medusa\Meshes\SK_Medusa_HeadTilt_v3Candidate.uasset` (5 268 450 байт, 08:16:54) и `…_Skeleton.uasset` на месте. Повторно импортировать не нужно.
1. **Патч:**
   ```powershell
   $patch = 'C:\Users\ren\WebstormProjects\unmached\unmached\docs\game-design\evidence\ART-004\v3-live-hookup.patch'
   git apply --check $patch; if ($LASTEXITCODE) { throw 'patch does not apply' }
   git apply $patch
   ```
2. **Сборка только игрового target, без `-NoLiveCoding`**, около 1 мин. Редактор не пересобирать: куку новые тела функций не нужны, а сборку редактора блокирует Live Coding открытого редактора.
   ```powershell
   $ue = 'C:\Program Files\Epic Games\UE_5.8'
   $proj = (Resolve-Path 'unreal\Unmatched\Unmatched.uproject').Path
   $log = 'unreal\Unmatched\Artifacts\ART004Face\v3live-game-build.log'
   $p = Start-Process "$ue\Engine\Build\BatchFiles\Build.bat" -ArgumentList @('Unmatched','Win64','Development',$proj,'-WaitMutex','-NoXGE','-NoUBA','-MaxParallelActions=2') -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $log -RedirectStandardError "$log.err"
   if (-not (Select-String -LiteralPath $log -SimpleMatch -Pattern 'Result: Succeeded' -Quiet)) { throw 'game build failed' }  # Build.bat может вернуть 0 при ошибке
   ```
   Параметры только именованные. В первой редакции было `Select-String $log -SimpleMatch 'Result: Succeeded'`: первый позиционный параметр — `-Pattern`, второй — `-Path`, поэтому путь становился шаблоном, а искомая строка — путём. Windows PowerShell 5.1 отвечал `DriveNotFoundException` (диск `Result`), и проверка отбраковывала любую успешную сборку. Исправленная строка проверена в Windows PowerShell 5.1 на настоящих логах арт-worktree. На `baseline-game-rebuild-local.log` получилось `True`, проверка проходит. На `headtilt-package.log` (без `Result: Succeeded`) получилось `False`, срабатывает `throw`.
3. **Упаковка**, около 17 с. Защита внутри скрипта остановит упаковку при `WITH_LIVE_CODING 0`.
   ```powershell
   & tools\s08\package-client.ps1 -SkipBuild -Log 'unreal\Unmatched\Artifacts\ART004Face\v3live-package.log'
   if (-not (Select-String -LiteralPath 'unreal\Unmatched\Saved\Cooked\Windows\Unmatched\Metadata\DevelopmentAssetRegistry.bin' -SimpleMatch -Pattern 'SK_Medusa_HeadTilt_v3Candidate' -Quiet)) { throw 'v3 candidate not cooked' }
   Get-FileHash 'unreal\Unmatched\Binaries\Win64\Unmatched.exe','unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched\Binaries\Win64\Unmatched.exe'  # хэши равны; корневой exe — заглушка
   ```
   Проверка реестра тоже исправлена на именованные параметры. В первой редакции `Select-String` получал имя ассета как путь, давал `ItemNotFoundException`, и обещанного `True` быть не могло. Исправленная строка проверена в Windows PowerShell 5.1 на текущем `DevelopmentAssetRegistry.bin` арт-worktree (кук 08:38). Для `SK_Medusa_HeadTilt_v3Candidate` получилось `True`, для несуществующего имени — `False`. PowerShell 7 на машине не установлен и не проверялся.
4. **Бэкенд.** Изолированный тестовый бэкенд арт-worktree, как в успешных прогонах: `backend/.env` (`PORT=3120`, Postgres 55434, Redis 6381). В каталоге `backend` запустить `node -r dotenv/config dist/src/main.js` скрыто и записать PID. Проверка `{ __typename }` на `http://localhost:3120/graphql`. Нужен один экземпляр: второй бэкенд на той же БД и Redis дублирует планировщики.
5. **Контроль v2 на том же бинарнике, 45 с.** Проверяет сборку, доску и снимки до сравнения. Переменные `S08_DEMO_*` берутся из `backend/.env` только в окружение процесса, как раньше.
   ```powershell
   & tools\s08\run-phase2-demo.ps1 -Api 'http://localhost:3120/graphql' -ArtPreviewBoardId 'cmuhgs4b2001mwik4f2b2xtf8' -ArtPreviewFocusZoom 5 -RunSeconds 45 -ClientFps 30 -EvidenceDir 'docs\game-design\evidence\ART-004\live-v2-k2-control'
   ```
6. **v3, 45 с:** та же команда с `-ArtPreviewMedusaVariant head-tilt-v3 -EvidenceDir 'docs\game-design\evidence\ART-004\live-head-tilt-v3-k2'`. По желанию та же пара с `-ArtPreviewFocusZoom 1.6` для предложенного K2-зума.
7. **Сразу после каждого прогона** скопировать `unreal\Unmatched\Saved\StagedBuilds\Windows\Unmatched\Saved\Logs\Unmatched*.log` в `Artifacts\ART004Face\`: следующая упаковка их сотрёт.
8. **Проверки.** Скрипт завершается успешно, только если выполнено всё:
   - в обеих трассах есть `BOARD 5x6`, `ARTPREVIEW Cobble assets ready`, `ARTPREVIEW medusa candidate variant=head-tilt-v3 mesh=SK_Medusa_HeadTilt_v3Candidate`, `ARTPREVIEW fighter=Medusa hero=1 eligible=1 visual=1 mesh=SK_Medusa_HeadTilt_v3Candidate`, `ARTPREVIEW Cobble active 5x6 zones=30 …`, `HANDLE_APPLIED … fightersValid=1 boardValid=1`, `HUD seq=1 phase=ACTION_MANEUVER`, `FIGHTERS synced n=6`, `SHOT ctx`;
   - у хоста есть `ARTPREVIEW camera focus requested zoom=5.00` и `SHOT fighter f-0-hero … projected=1 alive=1` в пределах K2-проверки скрипта;
   - у присоединившегося есть `WS DROPPED` и `WS reconnected`, в кадре шесть бойцов;
   - оба PNG 1920×1080 свежие, `*-artcheck.json` с `pass: true` (доска, верхний HUD, рука).

   Вручную: `startGame` в трассе хоста не позже +28 с (порог кода), лучше не позже +26 с (рабочий запас). Сравнить v2 и v3 в кадре хоста: читаемость лица, клин у шеи (P1), зазор до колчана (P2). Статус после прогона — **измерено**. Художественное решение по v3 уже принято отдельно («доработать до v3.1»), живой K2 только добавляет доказательства.
9. **Уборка.** Скрипт сам отменяет свою комнату. Бэкенд остановить по записанному PID, предварительно сверив командную строку. Редактор UE и Blender пользователя не трогать. Патч остаётся незакоммиченным до ревью. Для v3.1 достаточно одной строки в `S08ArtPreviewMedusa.h`, одного значения в `ValidateSet` и игрового импорта.

Ориентировочное время: сборка около 60 с (54–64 с в логах), упаковка 15–17 с, каждый прогон 45 с плюс около 5 с на подготовку.

## Риски

| # | Риск | Мера |
| --- | --- | --- |
| R1 | Игровой target снова соберут с `-NoLiveCoding`, и клиент упадёт на старте | Не передавать этот флаг игровому target. Защита в `package-client.ps1 -SkipBuild` из патча закрывает только этот путь, скрипты S01/S05 — см. R14 |
| R2 | Неверный `ArtPreviewBoardId` (slug вроде `cobble-city`): бэкенд молча даёт 20×20, снимков нет | Использовать id из БД `cmuhgs4b2001mwik4f2b2xtf8`; скрипт с патчем явно пишет, что нет `BOARD 5x6` |
| R3 | `UnmatchedEditor` в обоих checkout собран с `WITH_LIVE_CODING 0`, и этой DLL пользуется кукер. Для регистрации это безопасно (`WITH_RELOAD=1`), но раскладка `UFunction` расходится с движком | Куки пока проходят (3 из 3). Пересобрать редактор без флага, когда редактор пользователя закрыт или Live Coding в нём выключен. Живой редактор пользователя не трогать |
| R4 | Live Coding открытого редактора блокирует `BuildCookRun -build` | Отдельно `Build.bat Unmatched …`, затем `package-client.ps1 -SkipBuild` |
| R5 | Нехватка виртуальной памяти под PCH (`C3859`/`C1076`, ошибка 1455) при XGE и 4 потоках | `-NoXGE -NoUBA -MaxParallelActions=2` |
| R6 | `.uasset` v3 есть только в арт-worktree (`Content/` в `.gitignore`). В `fix/admin-panel` с флагом v3 доска останется серой, и прогон упадёт явно (так задумано) | Интегрировать через `git add -f` (2 файла, около 5,3 МБ) только после художественного решения |
| R7 | Логи упакованного клиента стираются следующей упаковкой. Логи упавших v3-запусков сохранились только в журнале агента | Копировать логи сразу после прогона (шаг 7) |
| R8 | `Build.bat` возвращает 0 при ошибке компиляции | Искать `Result: Succeeded` |
| R9 | Корневой `StagedBuilds\Windows\Unmatched.exe` — заглушка | Сравнивать хэш внутреннего exe с `Binaries\Win64\Unmatched.exe` |
| R10 | Поздний `startGame`. Если арт-доска активируется после +28 с, подлёт камеры короче 2 с; с +30 с K2-кадр снимается до подлёта | Смотреть время `startGame` (порог +28 с, рабочий запас +26 с). При необходимости поднять `ArtPreviewShotAfter` и `RunSeconds` |
| R11 | Нагрузка на GPU: два offscreen-клиента | `-ClientFps 30` на процесс (AGENTS.md), не запускать параллельно с UE из T4 |
| R12 | С патчем проверка готовности доски зависит от выбранного варианта: без v3 гаснет вся доска Cobble, а не только Medusa | Так задумано, прогон падает явно |
| R13 | Дефекты v3 (P1 клин у шеи, P2 колчан, сокет `Head`), сообщения MikkTSpace о нормали нулевой длины при импорте | Живой прогон их не исправляет; это задача v3.1 |
| R14 | Отслеживаемые `tools/s01/ue_build.ps1:16` и `tools/s05/s05_build.ps1:29` по-прежнему собирают игровой target `Unmatched` с `-NoLiveCoding` и пакуют его без `-build`. Модуль теперь содержит 4 UCLASS (3 из S08 и `ASmokeGameMode`), раскладка статиков не та, что в S01/S05. Регрессия S01 или смоук S05 может упасть на старте так же, как v3 (гипотеза, не проверялось) | Предложено, в этой задаче не правилось (файлы вне группы). Убрать `-NoLiveCoding` из строки игрового target в обоих скриптах; у строки `UnmatchedEditor` флаг можно оставить (R3, R4). Либо добавить ту же проверку `WITH_LIVE_CODING 0` по `SharedDefinitions` игрового target перед упаковкой |

## Что сделано в этой задаче

Только чтение: git reflog, stash list и status в обоих checkout, логи `Artifacts/ART004Face`, staging-каталоги в `%TEMP%`, журнал Codex-агента, исходники проекта, UBT и движка, журнал Windows Application. Проверки: `git apply --check` патча в обоих checkout, `cl /Zs` заголовка на заглушках в `C:/tmp`, разбор `.ps1` парсером PowerShell, проверка логики защиты на текущих `SharedDefinitions`. UE, Blender, Tripo и SYNTX не использовались. Внешних расходов нет. Коммитов и изменений в чужих файлах нет. Новые файлы — этот отчёт и [v3-live-hookup.patch](v3-live-hookup.patch).

Редакция 2 правила только эти два файла. Проверки, все без записи в оба checkout:

- **Исходники движка.** Перечитаны `DeferredRegistry.h`, `UObjectBase.h`, `UObjectBase.cpp` и `ObjectMacros.h`.
- **Дизассемблер.** `dumpbin /symbols` и `/disasm` прекомпилированного `Module.CoreUObject.13.cpp.obj`.
- **Раскладка структур.** Модель собрана `cl` 14.44.35207 при `WITH_RELOAD=0` и `WITH_RELOAD=1`, плюс `/FAs` присваивания на той же модели.
- **Проект.** gen.cpp и `Module.Unmatched.cpp` арт-worktree; логи сборок `headtilt-*` и `baseline-*`; поиск `Total 603` в журнале агента.
- **Прецедент S01/S05.** `glm-sprint-check`: `SharedDefinitions`, gen.cpp, хэши exe. Отчёты S01/S05.
- **Хронометраж.** Трассы четырёх K2.
- **Команды отчёта.** Обе строки `Select-String` в Windows PowerShell 5.1: старая форма (ошибка) и новая (`True`/`False`).
- **Патч.** `git apply --check` патча и его LF- и CRLF-вариантов в обоих checkout. Применение к копиям в `C:/tmp`, парсер `.ps1`. Функциональная проверка нового блока трасс на синтетике и на настоящих трассах.

Редакция 3 правила только этот отчёт, патч не менялся. Проверки:

- **Конфигурация git.** `core.autocrlf`, `core.safecrlf`, `apply.whitespace`, `git check-attr` для пути патча, `.gitattributes`.
- **Хэши.** sha256 нынешнего файла и его LF- и CRLF-вариантов; `git hash-object` с фильтрами и без.
- **Нормализация.** Отдельный репозиторий в `C:/tmp` с исходными blob из HEAD арт-worktree: `git add` и `git checkout` из индекса, без коммитов.
- **Патч.** `git apply --check` трёх вариантов в обоих checkout; применение четырёх вариантов в отдельном репозитории со сравнением результатов; поиск blob из строк `index` в обоих checkout.

Временные файлы в `C:/tmp` удалены, запущенных процессов не осталось.

## Источники

- Акт v3 (только в арт-worktree): `C:/Users/ren/.codex/worktrees/art-foundation/unmached/docs/game-design/evidence/ART-004/head-tilt-v3-self-acceptance-2026-09-28.md`; отчёт импорта: `…/head-tilt-v3-game-import-report.json`.
- Отменённый эксперимент: `C:/Users/ren/.codex/worktrees/art-foundation/unmached/unreal/Unmatched/Artifacts/ART004Face/headtilt-live-flag-experiment.patch`; там же логи `headtilt-*`, `baseline-*`.
- Успешные K2 для хронометража: [live-k2-zoom-probe-5x](live-k2-zoom-probe-5x/), [live-k2-zoom-probe-1p6](live-k2-zoom-probe-1p6/), [live-k2-label-probe-5x](live-k2-label-probe-5x/), [live-k2-label-probe-1p6](live-k2-label-probe-1p6/); сравнение — [live-k2-zoom-comparison-2026-09-28.md](live-k2-zoom-comparison-2026-09-28.md).
- Карта владения и слоёв Medusa: [DIRECTORY-MAP.md](../../../art-pipeline/DIRECTORY-MAP.md).
