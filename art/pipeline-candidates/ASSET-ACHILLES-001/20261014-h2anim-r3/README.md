# ASSET-ACHILLES-001 — клипы на модели r3: UE-импорт и приёмка r2 (этап 7a), 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай»; 2026-10-13 «Сгенерировать модели можно все Но сначала чтобы полностью обкатать скилл и итерационно его
улучшить, можно это сделать на небольшой выборке». Трат нет.

## Вход (headless-часть — коммит 9b27a35d, доработка модели r3)
- Спека `../build-profiles/achilles-h2anim-r3.json`: цель — bake r3 `../20261014-h2-bake-r3/export/SK_Achilles_H2.fbx`
  (sha256 `29bd1170…0abb6`). `clips.*` — как в `achilles-h2anim.json` r1 (проверено: блоки равны). `H2ANIM["Achilles"]`
  указывает на эту спеку.
- `reports/h2anim-run.json`: все 4 клипа — author OK, validate PASS, контакты PASS.
  - Отчёты `grip-<Clip>.json` по числам совпадают с r1.
  - В LungeAttack ушёл WARN `limb_body_R` (r1: до 7 пар правой руки с кирасой на к.11–13). На модели r3 — pass: стыки
    весов руки с кирасой.

## UE (этап 7a, свой скрытый редактор, каждый шаг под `ue_lock.py`)
Редактор `-RenderOffScreen` + `ue_py/console_drop.py` (`UE_CONSOLE_DROP`), MCP :8123. Закрыт по `quit-editor`, грязных
пакетов 0: `M_UM_Figure_v2` перезагружен, `../evidence/stage7a-20261014/discard-master-r4.json`.

**Обход пилота: носитель превью клипов (пробел инструмента F145), как у Ancient Leshen r3.**
- Почему: `h2anim_ue.py skeleton` при существующем скелете ничего не делает. Поэтому носитель
  `/Game/PipelineCandidates/Achilles/Rig/SK_Achilles` (`ue.mesh_for_preview` спеки, на нём снимают `frames` и `measure`)
  оставался с геометрией bake r2.
- Что сделано: носитель переимпортирован из `../20261014-h2-bake-r3/export/SK_Achilles_H2.fbx` на существующий скелет
  задачей `../evidence/stage7a-20261014/tasks/refresh_carrier.py` (копия задачи Leshen). Отчёт —
  `reports/ue-carrier-refresh.json`.
- Скелет не изменился:
  - опорная поза 18 костей до и после совпадает (`ref_pose_equal: true`);
  - `.uasset` скелета не изменён (снимок после r4: изменён только `Rig/SK_Achilles`).
- Источник носителя теперь bake r3 (было bake r2). Габариты те же; вершин LOD0 31 691 → 31 693 (стыки весов r3).

**Клипы:**
- `skeleton` — скелет уже есть, 18 костей, кость 0 `SKEL_UM_Humanoid`.
- `import` — все 4 клипа, legacy-импорт, root lock, старые клипы удалены и импортированы заново.
- `measure` — длительности 2,5 / 0,583 / 0,417 / 0,875 с; кость 0 неподвижна; масштаб 1,0; смещение кадра 0 ≤ 0,003 uu.
  Все скалярные поля `ue-measure-clips.json` совпадают с r1.
- `frames` по клипу: `--base /Game/PipelineCandidates/Achilles/H2LD/Meshes/SM_Achilles_H2LD_Base` и
  `--light-pinned ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`.
  - Прогрев сошёлся: 1,09 → 0,28–0,30.
  - Крупный план LungeAttack к. 6, 7, 9 (`--closeup`, eye 100 / z 40 uu, те же кадры, что в r1) и `sheet`.
- Отчёты: `reports/ue-*.json`. Кадры: `preview/ue/`. Лист: `preview/Achilles-H2Anim-ue-sheet.jpg` (осмотрен: позы как
  в r1, фигура на подставке, спиной к камере нет).
- Манифест: `clip_manifest.py build` → `MANIFEST_CHECK PASS clips 35 production 28`, ACH-* `technically_imported`
  (sha256 FBX r3 = UE-импорт).

## Приёмка клипов r2 (`../evidence/acceptance-anim/20261014-r2/`)
Новые сессии «Sol 6.1 xhigh», по клипу. Промпт — заполненный промпт r1 того же клипа, правки скриптом
`../evidence/stage7a-20261014/tasks/prep_acceptance_r2.py`:
- цикл r2, пути на этот прогон и спеку r3, `accepted_object` с sha256 r3;
- `previous_card` = карточка r1 того же клипа;
- из известных пределов убран закрытый пункт «кромка у правой подмышки»;
- у DeathSettle — пункт r1 п.1 со статусом только «закрыт / не закрыт».

Кадры — тот же список файлов, что в карточке r1, из этого прогона: Blender-лист, крупные планы `preview/closeups-blender/`,
UE-кадры и лист. Итоги — в `../evidence/acceptance-anim/20261014-r2/<Clip>/card.json`, сводка — ниже.

| Клип | r1 (R/C/D/L → балл, вердикт) | r2 (R/C/D/L → балл, вердикт) | Сессия Sol r2 |
|---|---|---|---|
| Idle | 1,5/2/2/1,5 → 8,8 pass | 2/2/1,5/1,5 → 8,8 pass | `codex:01a137fd-2866-7342-919c-b441eab0192a` |
| LungeAttack | 2/2/1,5/2 → 9,4 pass | 2/2/1,5/2 → 9,4 pass | `codex:01a137fd-284c-7a52-b149-b82655d11990` |
| HitReact | 2/2/2/2 → 10,0 pass | 2/2/2/2 → 10,0 pass | `codex:01a137fd-2861-72c1-98a6-15b5ec394254` |
| DeathSettle | 2/2/0/2 → 7,5 rework_blender | 2/2/1,5/2 → 9,4 pass | `codex:01a137fd-285f-79b1-ba5e-9c580de95065` |

- `validate_card.py --print-verdict --check-files`: код 0 у всех четырёх. Полосы 8,0–8,4 нет, второй приёмщик не нужен.
  Все 4 клипа — pass: этап 6 героя закрыт.
- DeathSettle: «r1 п.1: закрыт (Achilles-DeathSettle-f21-q34b.jpg)» — кромка за правой подмышкой сомкнута. D = 1,5 за
  угловатость правого локтя и стык юбки с бедром на f21-right, без разрыва.
- Известные замечания для листа K1/K2 этапа 7b (`known_issues` карточек):
  - Idle: шов петли к.60→0 на кадрах не показан. L = 1,5, как и в r1.
  - LungeAttack: на крупном плане к.7 front видна тонкая дуга кромки кирасы у правой подмышки (без разрыва); копьё
    фронтально сокращается.
  - HitReact: skin_stretch WARN только в закрытых местах.
  - DeathSettle: угловатость локтя.
- В сессии Idle было 4 переподключения (503) — сеть, на карточку не повлияли.
