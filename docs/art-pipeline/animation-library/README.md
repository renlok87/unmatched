# Библиотека анимаций

Срез 2026-09-28 (задача P1.6), дополнен 2026-09-29 (волна 5c, раздел «Библиотека v2 (H2Anim)»). Статусы: **предложено → измерено → технически импортировано → художественно принято**. В манифесте они записаны как `proposed`, `measured`, `technically_imported`, `artistically_accepted`, плюс `draft_test` (черновой тестовый файл) и `rejected`. Ни один клип не имеет статуса «художественно принято»; 16 production-слотов с 2026-09-29 заполнены кандидатами H2Anim в статусе «технически импортировано».

| Файл | Что это |
| --- | --- |
| [clip-manifest.schema.json](clip-manifest.schema.json) | JSON-схема (draft 2020-12). Правила: `artistically_accepted` требует `acceptance_evidence`; записи `role: test` не могут стать принятыми |
| [clip-manifest.json](clip-manifest.json) | данные: 16 production-слотов (15 безусловных, HAR-HitReact условный; контракт UM_HUMANOID_17_v2, кандидаты H2Anim) + 7 тестовых записей (v1) |
| [validation-h2anim/](validation-h2anim/) | отчёты `validate_clip.py` v2 для клипов H2Anim |
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

Персонажи и ID: Medusa `MED-*` (ASSET-MEDUSA-001), Harpy `HAR-*` (ASSET-HARPY-001, крылья = руки; HitReact при HP 1 почти недостижим, AD-CNF-30), Arthur `ARTH-*` (ASSET-KING-ARTHUR-001), Merlin `MER-*` (ASSET-MERLIN-001). С 2026-09-29 все 16 слотов заполнены кандидатами H2Anim — см. раздел ниже.

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

Раньше работа над анимациями Medusa была остановлена до появления пайплайна с видео-референсами (решение пользователя). Остановка снята в волне 5c: референсы `art/animation-refs/` появились, пользователь делегировал работу. Черновые клипы остаются тестовыми файлами пайплайна и служат шаблоном тайминга и дельт для H2Anim.

## Библиотека v2 (H2Anim, волна 5c, 2026-09-29)

**Что это.** 16 клипов D-11 (Idle, LungeAttack, HitReact, DeathSettle × Medusa, Arthur, Merlin, Harpy) на H2-мешах героев (у Harpy — H3). Контракт — UM_HUMANOID_17_v2: лицо +X, объект арматуры `SKEL_UM_Humanoid` = кость 0 UE. Кадр 24 fps, клипы in place.

**Статус — «технически импортировано».** По каждому клипу:
- validate_clip v2: PASS;
- контакты: PASS (без FAIL; WARN перечислены в «Ограничениях» и в журнале решений, исправление L);
- UE-импорт: legacy FbxFactory, bForceRootLock, кадр 0 = ref pose (0,0 uu), кость 0 неподвижна, масштаб 1,0.

Художественно клипы не приняты. Решения и открытые вопросы — [2026-09-29-anim-v2-decisions.md](../../game-design/decisions/2026-09-29-anim-v2-decisions.md).

### Как устроено

| Шаг | Инструмент | Что делает |
| --- | --- | --- |
| Спека героя | `art/pipeline-candidates/<ASSET>/build-profiles/<hero>-h2anim.json` (схема `unmatched.h2anim-spec/1`) | Цель: `SK_*_H2.fbx` и подставка, sha256 зафиксирован. Клипы: N интервалов, роль, шаблон, ключи, волны, IK стоп, hand_pin. |
| Авторинг | `tools/tripo-pipeline/anim/clip_author.py` + `clip_curves.py` (headless Blender) | Дельты поворота в осях арматуры цели (+X вперёд, +Y влево, Z вверх), поэтому ключ не зависит от roll костей героя. Шаблон черновика `AM_Medusa_*` переводится в кадр v2 сопряжением Rz(+90°). Ключи `aim`: направление или ориентация кости, сплайн SQUAD для больших поворотов. Двухзвенная IK стоп и руки (посох-опора Merlin). Экспорт UM_FBX_v1 без второго +90°. После экспорта rest клипа сверяется с SK покостно (≤ 1e-4). |
| Проверка контракта | `anim/validate_clip.py --skeleton=UM_HUMANOID_17_v2 --character=<Hero>` | Роль, fps 24, длительность N/24, in place, пиковый сдвиг ≥ 2 %. Для Idle — ещё и шов петли. |
| Контакты | `anim/clip_contact_check.py` | Скольжение подошвы ≤ 0,5 % роста. Пересечения по BVH: оружие ↔ тело; руки или крылья ↔ корпус, голова, ноги — новая область или рост > 3× + 20 пар = FAIL для всех героев; зона стыка плеча исключена. Разрыв скина `skin_stretch`: ребро > 5× rest и > 2 % роста, видимое хотя бы с одного из 24 направлений, = FAIL. Опора на оружие `weapon_tip`: острие в круге подставки на уровне её верха (±0,2 % роста). Фигура не ниже верха подставки; подол проверяется отдельно, WARN до 1,5 %. Скоростной шов петли. |
| Лист поз в Blender | `anim/clip_pose_probe.py` (функции `rig_deform_probe.py`, сам файл не правится) + `anim/overlay_bones.py` | Workbench: тело светлое, оружие оранжевое. Виды front / left / q34, наложены кости. |
| Прогон героя | `anim/h2anim_run.py <spec>` | Все четыре шага подряд. Blender только headless, по одному процессу. |
| UE | `anim/h2anim_ue.py skeleton / import / measure / frames / sheet <spec>` | Канонический скелет `…/<Hero>/Rig/SK_<Hero>_Skeleton` (`review/ue_py/canonical_skeleton.py`). Импорт клипов в `…/<Hero>/H2Anim` (`review/ue_py/import_clips.py`: CLI клипы не импортирует). Замеры (`measure_clips.py`). Лист поз под светом cobble-probe, High; уровень не сохраняется. Длинные захваты — по одному клипу (`--clips=X`), крупный план — `--closeup`; лист собирается из кадров на диске, кадры от другой версии FBX не берутся. |
| Меш на каноническом скелете | `tripo_pipeline.py` 0.8.0, профиль skeletal-adopt, `ue.target_skeleton` | Меш импортируется на существующий скелет. `ue_delete_owned` не удаляет скелет вне папки прогона. |
| Манифест | `anim/clip_manifest.py build/check` | Функция `h2anim()` ставит `technically_imported`, только если validate PASS, контакты PASS и импорт того же sha256 сходятся. |

```bash
python tools/tripo-pipeline/anim/h2anim_run.py art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json
MSYS_NO_PATHCONV=1 python tools/tripo-pipeline/anim/h2anim_ue.py skeleton|import|measure art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json
MSYS_NO_PATHCONV=1 python tools/tripo-pipeline/anim/h2anim_ue.py frames <spec> [--base=/Game/.../SM_<Hero>_H2_Base] --clips=Idle   # по клипу за вызов
MSYS_NO_PATHCONV=1 python tools/tripo-pipeline/anim/h2anim_ue.py frames <spec> --clips=LungeAttack --frames=3,4,5 --closeup      # крупный план 1920×1080
python tools/tripo-pipeline/anim/h2anim_ue.py sheet <spec>                                                                       # лист UE из снятых кадров
python tools/tripo-pipeline/anim/clip_manifest.py build
```

### Клипы

Длительности HitReact (0,417 с) и DeathSettle (0,875 с) — ПРЕДЛОЖЕНИЕ, `target_status: open`.

| Герой | UE-папка клипов | Скелет | Idle | Особенности |
| --- | --- | --- | --- | --- |
| Medusa | `/Game/PipelineCandidates/Medusa/H2Anim` | `Medusa/Rig/SK_Medusa_Skeleton` | 2,33 с | Выстрел из лука по референсу MED-LungeAttack: корпус боком к цели, лук на вытянутой левой руке спинкой к цели (тетивой к лучнице), правая кисть у щеки, выпуск к. 8. Тетива — жёсткая часть меша, не натягивается. Смерть — поклон корпусом на почти прямых ногах. H2-меша Medusa в UE пока нет, превью на носителе `Rig/SK_Medusa`. |
| King Arthur | `…/KingArthur/H2Anim` | `KingArthur/Rig/SK_KingArthur_Skeleton` | 2,5 с | Замах: кисть с мечом перед правой грудью, меч остриём вверх-назад, плечо поднято не больше чем на 18°, затем рубящий удар вперёд. На H2-меше отведение плеча рвёт наплечник (106°), а при 36–38° в оболочке наруча и плаща у локтя видны дыры (крупный план UE). Смерть — крен вперёд-вправо с опорой на меч: острие на верхе подставки внутри круга (`weapon_tip` PASS). H2-меш переимпортирован на канонический скелет. |
| Merlin | `…/Merlin/H2Anim` | `Merlin/Rig/SK_Merlin_Skeleton` | 3,0 с | Посох-опора (hand_pin) в Idle, HitReact и DeathSettle. Атака: длинная подготовка и короткий выброс посоха. Двуручного хвата нет. H2-меш переимпортирован на канонический скелет. |
| Harpy | `…/Harpy/H2Anim` | `Harpy/Rig/SK_Harpy_Skeleton` | 2,0 с | Крылья = руки: полувзмах в Idle; атака — взмах и выброс лапы с когтями (цель IK стопы). Смерть — оседание с раскрытыми крыльями. Запечено на rest H3 (первый проход был на H2). HitReact условен (AD-CNF-30). |

### Ограничения

- Подол мантий и платьев скинен жёстко, без симуляции ткани. Поэтому полного падения на колени (как в видео-референсах) нет. Смерти — «на ногах»: у Arthur и Medusa ноги почти прямые (присед рвёт внутренний подол, `skin_stretch`), поклон — корпусом. Подол уходит в подставку не глубже 0,76 % роста (WARN у Arthur LungeAttack и Medusa DeathSettle).
- `skin_stretch` ловит только разрывы, где рёбра растянуты больше чем в 5 раз. Дыры оболочки на сгибах, где края расходятся без такого растяжения, видны только на крупном плане. Для рук с оружием в атаке нужен крупный план UE (`h2anim_ue.py frames --closeup`).
- UE-шаги выполняются только под блокировкой `C:/tmp/ue-editor.lock` (`tools/art/material_library/ue_lock.py`, по одному клипу на блокировку), потому что редактор общий.
- Оставшиеся WARN контактов: `limb_body_R` у Arthur LungeAttack и DeathSettle (рост пересечений правой руки с корпусом в области rest-контакта, ниже порога FAIL); `skin_stretch` у 11 клипов (натяжение на сгибах; у Harpy DeathSettle закрытые со всех сторон разрывы в области таза). Полный список — журнал решений, исправление L.
- Пик сдвига суставов в Idle — 2,5–7 % роста по валидатору (головы и хвосты костей). UE `measure_clips` считает только суставы: у Medusa 1,7 %, у Merlin 1,5 %.
- Переход S08 на лицо +X не сделан (волна 5c-B). Клипы H2Anim в игру не подключены.
