# Библиотека анимаций

Срез 2026-09-28, задача P1.6. Статусы: **предложено → измерено → технически импортировано → художественно принято**. В манифесте они записаны как `proposed`, `measured`, `technically_imported`, `artistically_accepted`, плюс `draft_test` (черновой тестовый файл) и `rejected`. Ни один клип не имеет статуса «художественно принято».

| Файл | Что это |
| --- | --- |
| [clip-manifest.schema.json](clip-manifest.schema.json) | JSON-схема (draft 2020-12). Правила: `artistically_accepted` требует `acceptance_evidence`; записи `role: test` не могут стать принятыми |
| [clip-manifest.json](clip-manifest.json) | данные: 16 production-слотов (15 безусловных, HAR-HitReact условный) + 7 тестовых записей |
| [VALIDATION.md](VALIDATION.md) | валидатор клипа, результаты на старых клипах Medusa, отложенные UE-шаги |
| [VIDEO-TO-MOTION.md](VIDEO-TO-MOTION.md) | инструменты видео → скелет, лицензии, формат приёма, рекомендация |
| [validation/](validation/) | отчёты `validate_clip.py` и `summary.json` |
| [../rig/RIG-CONTRACT.md](../rig/RIG-CONTRACT.md) | контракт скелета, на который ссылаются записи |

Сборка и проверка манифеста:

```bash
python tools/tripo-pipeline/anim/run_p16_validation.py      # пересчитать отчёты валидации; код 1, если кейс пропущен или итог не совпал
python tools/tripo-pipeline/anim/clip_manifest.py build     # пересобрать манифест (hash, fps, длительности из отчётов)
python tools/tripo-pipeline/anim/clip_manifest.py check     # схема + файлы + sha256 + правила статусов
# фикстуры (BVH, GLB, FBX пресета Tripo) лежат в отслеживаемом fixtures/ кандидата p16;
# пересоздать: blender -b --factory-startup --python tools/tripo-pipeline/anim/make_fixtures.py -- all
```

Blender-скрипты этой папки запускаются только headless (`blender -b`). Без `-b` скрипт бросает `RuntimeError` и ничего не делает, процесс Blender остаётся жив. `SystemExit`, `sys.exit` и `os._exit` в живом Blender завершают весь процесс. Подробности — в [VALIDATION.md](VALIDATION.md).

## Минимальный набор (сверено с брифом 18 §4 и аудитом)

Бриф и аудит сходятся: слотов **16** = 4 клипа D-11 × 4 персонажа. Из них 15 безусловны, а `HAR-HitReact` условен до решения AD-CNF-30 (бриф 18, стр. 10; при HP 1 HitReact у Harpy почти недостижим). В манифесте у него `required_mvp: false`. Дополнительных клипов 0. Остальные события закрываются VFX, материалом или движением актора (из 32 событий реестра 28 не требуют скелетной анимации).

| Клип | CUE | Целевая длительность | Loop | Root |
| --- | --- | --- | --- | --- |
| Idle | нет запускающего CUE; фон `state:Idle`; CUE-017 ставит на паузу | 2–3 с (ПРЕДЛОЖЕНИЕ, 04 §111) | да | in place |
| LungeAttack | CUE-008 (600 мс, единственная умышленная пауза) | 0,6 с (ПРЕДЛОЖЕНИЕ) | нет | in place, RM = 0 (ART-004) |
| HitReact | CUE-011 (цифра урона 900 мс) | 0,4 с (04) против 0,9 с (CUE-011) — ОТКРЫТО | нет | in place |
| DeathSettle | CUE-013 (≤950 мс, затем fade-out) | 0,9 с (04), ≤0,95 с — ОТКРЫТО | нет | in place |

Персонажи и ID: Medusa `MED-*` (ASSET-MEDUSA-001), Harpy `HAR-*` (ASSET-HARPY-001, крылья = руки; HitReact при HP 1 почти недостижим, AD-CNF-30), Arthur `ARTH-*` (ASSET-KING-ARTHUR-001), Merlin `MER-*` (ASSET-MERLIN-001). У Harpy, Arthur и Merlin пока нет производственного меша, их слоты в статусе `proposed`.

## Тестовые записи (не для игры)

| ID | Источник | Статус | Валидация |
| --- | --- | --- | --- |
| MED-Idle-draft | `blender/ASSET-MEDUSA-001/export/AM_Medusa_Idle.fbx` (ключи Blender-скрипта ART-004) | `draft_test`; в UE технически импортирован в `/Game/ART004` | PASS с WARN: пик 1,2 % роста — ниже предложенного порога 2 %, визуально не проверено |
| MED-LungeAttack-draft | `AM_Medusa_LungeAttack.fbx` | `draft_test` | PASS (технически) |
| MED-HitReact-draft | `AM_Medusa_HitReact.fbx` | `draft_test` | PASS; 0,375 с — в допуске ±0,05 с от 0,4 с (04), вне 0,9 с (CUE-011); вопрос открыт |
| MED-DeathSettle-draft | `AM_Medusa_DeathSettle.fbx` | `draft_test` | PASS |
| MED-Idle-tripo-preset-test | пресет Tripo «стоя_отдых» на принудительном риге d562f057 | `rejected` | технический PASS через карту ретаргета, визуально неприемлем |
| MED-LungeAttack-bvh-fixture | BVH, round-trip из FBX (`fixtures/`) | `draft_test` | PASS: проверка ветки BVH |
| MED-LungeAttack-glb-fixture | GLB, round-trip из FBX (`fixtures/`) | `draft_test` | PASS: проверка ветки GLB; рост и пик сдвига сверены с FBX |

У четырёх черновых клипов и GLB-фикстуры есть WARN `armature_object_name`: объект арматуры называется `SKEL_Medusa`, а по контракту — `SKEL_UM_Humanoid` ([RIG-CONTRACT §2](../rig/RIG-CONTRACT.md)).

По решению пользователя работа над анимациями Medusa остановлена до пайплайна с видео-референсами. Черновые клипы остаются тестовыми файлами пайплайна.
