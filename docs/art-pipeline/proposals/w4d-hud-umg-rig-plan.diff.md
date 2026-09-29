# Предложение: гибрид UMG сейчас, контракт рига v2 в 04, план 13 после решений 2026-09-28 (не применено)

Статус: **предложено**. Файлы `docs/game-design/02`, `04`, `13`, `17` принадлежат автору; этот документ их не меняет. Основание — решения пользователя U-1, U-2, U-4 ([журнал 2026-09-29](../../game-design/decisions/2026-09-29-render-ui-user-decisions.md)), контракт рига v2 ([RIG-CONTRACT.md](../rig/RIG-CONTRACT.md) §0), правила HUD ([HUD-RULES.md](../../unreal/contracts/hud/HUD-RULES.md)) и контракт CUE-слоя ([CUE-DISPATCHER.md](../../unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md)).

Срез: 2026-09-29, волна 4, W4-D, `fix/admin-panel` 4a1cad9a; файлы не изменены относительно HEAD.

| Файл | sha256 (blob HEAD 4a1cad9a) |
| --- | --- |
| `docs/game-design/02-ux-ui-spec.md` | `f5ce949e36e638f1b1866a0eda06cc7a2348a8330bd80ec19c18857dc5f922ea` |
| `docs/game-design/04-blender-production.md` | `080e05283975d129625b9c32647aaf0de73921147ff8bc3b510f225a818b23cd` |
| `docs/game-design/13-sprint-plan.md` | `f061f8a8a920fae06b7ea7ce94b86ea2ec055529eeab815025dac52563d5af86` |
| `docs/game-design/17-art-production-spec.md` | `483dfaf98520e175acafdced7226a79d8379e71bbee50afa16006206e4202cef` |

## Diff (предложенный; не применён)

```diff
--- a/docs/game-design/02-ux-ui-spec.md
+++ b/docs/game-design/02-ux-ui-spec.md
@@ -59 +59,2 @@
 ПРЕДЛОЖЕНИЕ (идея из прежнего плана `docs/unreal/05-ui-screens.md`, §1.2): четыре слоя CommonUI — `Game` (HUD), `Menu` (экраны маршрута BOOT→LOGIN→LOBBY→ROOM), `Modal` (инспектор, настройки, подтверждения, результат), `Toast/Overlay` (реконнект, всплывающие ошибки). …
+РЕШЕНИЕ пользователя 2026-09-28 («HUD: гибрид UMG сейчас», [журнал](decisions/2026-09-29-render-ui-user-decisions.md) U-4): блоки UI-HUD-* и экраны UI-SCR-* делаются на UMG (C++-база с `BindWidget` + WBP) уже сейчас; Slate остаётся для операторской панели F10, трасс и проб. Слои выше реализуются стеком UMG-виджетов; CommonUI — после MVP вместе с геймпадом (D-05). Правила: панель = класс, токены стиля, гейты по трассам `SHOT widget`, StringTable/`why.*` ([HUD-RULES](../unreal/contracts/hud/HUD-RULES.md)).
```

```diff
--- a/docs/game-design/04-blender-production.md
+++ b/docs/game-design/04-blender-production.md
@@ -32 +32 @@
-| **Rig** | Лёгкий (D-11): `root + hips + spine + head + 2×(arm: upper/lower/hand) + 2×(leg: upper/lower/foot) + weapon` — ~15 костей; ≤ **4 влияний** на вершину; масштаб костей единичный. Совместимость анимаций — один шаблон скелета на всех персонажей (имена костей из шаблона `blender/_shared/rig_template.blend`). |
+| **Rig** | Лёгкий (D-11), контракт `UM_HUMANOID_17_v2` ([RIG-CONTRACT](../art-pipeline/rig/RIG-CONTRACT.md), [rig-contract.json](../art-pipeline/rig/rig-contract.json)): `root + hips + spine + head + 2×(arm: upper/lower/hand) + 2×(leg: upper/lower/foot)` + кость оружия **по стороне** — `weapon.L` (под `hand.L`) или `weapon.R` (под `hand.R`), у героя только своя (Harpy — без оружия); объект арматуры (кость 0 в UE) — `SKEL_UM_Humanoid` у всех; ≤ **4 влияний** на вершину; масштаб костей единичный. SK и клипы экспортируются только UM_FBX_v1 (лицо +X); кадр 0 и последний кадр клипа — rest-поза (кроме DeathSettle); in place, при импорте `bForceRootLock`. Проверка — `validate_clip.py` (`--character`, `--clip-role`). Общий UE Skeleton на всех персонажей — не доказан (RIG-CONTRACT §8). |
```

```diff
--- a/docs/game-design/13-sprint-plan.md
+++ b/docs/game-design/13-sprint-plan.md
@@ -69 +69,3 @@
 **Следующая частичная самоприёмка K3, 2026-09-28:** …
+
+**Решения пользователя 2026-09-28 (волна 4, [журнал](decisions/2026-09-29-render-ui-user-decisions.md)):** DX12 + Lumen сейчас; эталон приёмки K1–K3 и ACC-022 — High; TeamColor на базе, кольце и одежде; HUD — гибрид UMG сейчас. Следствия для плана: (1) финальные packaged K1–K3 для GD-058 снимаются только после перехода на DX12/SM6 + Lumen и явного High (кадры DX11 — диагностика); (2) до ART-006..008 фиксируется контракт рига v2 (кость 0, оружие по стороне, UM_FBX_v1, границы клипа) и пересобираются Medusa (по согласию пользователя), Arthur и Merlin (профиль с `weapon.R`: `/4` или `/3` um-master + `weapon.R`); (3) к ART-006 у каждого героя есть TeamMask; (4) перенос HUD на UMG начинается сейчас, до GD-047: сначала UI-HUD-HAND и UI-HUD-PANEL-LOC поверх `FS09HudModel` и перевод пиксельных гейтов S09/S10 на трассы `SHOT widget`; остальные блоки и экраны — в S12 как прежде; (5) CUE-слой GD-044 реализует контракт `FS08CueDispatcher` (таблица, трасса `CUE fx … result=`, фикстуры без мира). Perf-gate ACC-022 на железе D-07 остаётся открытым (AD-OPEN-20); риск Lumen на GTX 1060 — высокий (оценка).
@@ -100,2 +102,2 @@
-| S11    | Эталон в полной игре: GD-042..045                                 |        7 | Принятый ранее визуал работает вместе с HUD, сетью и CUE; бюджеты измерены в packaged, старый CUE не повторяется                        |
-| S12    | Полный контент и два языка: GD-046..049                           |        7 | Четыре типа моделей, шесть бойцов, финальная доска, 27 cardArt-привязок, 18 CUE, девять экранов, RU/EN                                  |
+| S11    | Эталон в полной игре: GD-042..045                                 |        7 | Принятый ранее визуал (DX12 + Lumen, эталон High) работает вместе с HUD (первые блоки UMG), сетью и CUE-диспетчером по таблице; бюджеты измерены в packaged, старый CUE не повторяется (гейт `CUE fx`) |
+| S12    | Полный контент и два языка: GD-046..049                           |        7 | Четыре типа моделей, шесть бойцов, финальная доска, 27 cardArt-привязок, 18 CUE, девять экранов на UMG, RU/EN (StringTable, `why.*`) |
@@ -113 +115 @@
-| A03   | ART-006..011, 21 день | Модели после GD-058 и rules-gate S06; UI/feedback после соответствующего серого HUD/боя S09 | Модели/доска к GD-046; UI к GD-047; CUE к GD-049                                      |
+| A03   | ART-006..011, 21 день + TeamMask 0,5–1 дня на героя | Модели после GD-058, rules-gate S06 и контракта рига v2; UI/feedback после соответствующего серого HUD/боя S09 | Модели/доска к GD-046; UI (WBP по токенам) к GD-047; CUE (ассеты таблицы `cue-table.json`) к GD-049 |
```

```diff
--- a/docs/game-design/17-art-production-spec.md
+++ b/docs/game-design/17-art-production-spec.md
@@ -1038 +1038,2 @@
 Фактическое состояние (ИЗМЕРЕНО). UMG-HUD партии (11 блоков) в UE нет. …
+Решение пользователя 2026-09-28: HUD — гибрид UMG сейчас (блоки и экраны на UMG, Slate для F10 и проб; CommonUI после MVP) — [журнал решений](decisions/2026-09-29-render-ui-user-decisions.md) U-4, правила — [HUD-RULES](../unreal/contracts/hud/HUD-RULES.md). Форма поставки ART-011 не меняется (текстуры с 9-slice-отступами, .ttf/.otf подходят и для Slate, и для UMG).
```

## Что не входит

- `14-sprint-backlog.csv` (оценки GD-047 и новые задачи перехода на DX12/UMG) — после решения автора по этому diff.
- `18-animation-production-brief.md` (§9 «родитель weapon открыт») — закрывается ссылкой на RIG-CONTRACT v2 при следующей правке брифа.
