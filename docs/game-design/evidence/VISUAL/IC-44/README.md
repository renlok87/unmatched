# IC-44 — лист приёмки `team-chip-p1` (чип команды P1 (круг))

Лист собран 2026-10-06: `draw_icons.py --sheet accept team-chip-p1` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08IconLegacy` → T_UI_TeamShape_Circle_12 (mvp-v1); трасса ARTLOOK `chips=v3|legacy(-S08IconLegacy)`, строка `HUD team chips ready=1 chips=v3 su=12 px=18`
**Решения по делегированию:** ВР-VS2-15, ВР-VS2-16, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Голый жетон: круг тела r 13 u, keyline 1 u снаружи (r 14); тело в текстуре белое (UMG умножает на team.p1.screen, И-5), мастер-превью — team.p1.screen. Экспорты 9 и 12 px — только лист проверки; в UE 18, 24, 32, 36, 48 и 64 (ВР-VS2-15).
- UE: `UI/UmTeamChip.{h,cpp}` грузит T_IV3_team_chip_p1_<px> (px — наименьший экспорт ≥ su × DPI × масштаб UI), Brush.ImageSize = su носителя, тон — Style.TeamChipColor(0) как прежде; точка подключения — `S08FlowGameMode.cpp` BuildArtHudWidgets (13 строк вместо 17, с двумя include).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-team-chip-p1.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-team-chip-p1.png`, `sheet-01-team-chip-p1-24.png`, `sheet-02-team-chip-p1-32.png`, `sheet-03-team-chip-p1-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (тег бойца HB-45 (24 su) и плашка HB-46, шаг H12) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-chips-x8.png`, `check-p1-p2.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | `HUD team chips ready=1 chips=v3 su=12 px=18`, ARTLOOK `chips=v3` (UE-тест) | частично |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/team-chip-p1-24.png` | 24×24 | e33a3418ab63f5ddc14c71d211b8dd89aaa5a81c2c1b8bb932f02de477015e01 |
| `art/imagegen/hud-icons-v3/sizes/team-chip-p1-32.png` | 32×32 | 0f9798fd180fa2ac90cc991b40d60b3d3fc3eabfac6d034c66e7d2a48dda79bd |
| `art/imagegen/hud-icons-v3/sizes/team-chip-p1-48.png` | 48×48 | 5c886324b69510a88ad0de05b233c6aaf855a58eb6ea5379919b910b48012268 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-team-chip-p1.png`, `check-chips-x8.png`, `check-p1-p2.png`, `sheet-01-team-chip-p1-24.png`, `sheet-02-team-chip-p1-32.png`, `sheet-03-team-chip-p1-48.png`, `sheet-sizes.png`.
- `check-chips-x8.png`: при 9 и 12 px ×8 круг не становится квадратом, шестигранник P2 читается гранями.
- `check-p1-p2.png`: P1 и P2 различимы формой в сером при 18–48 px (24 su при 720p / 100 % / 1440p / 150 %).
- UE-тесты: Unmatched.S08.Hud.TeamChip (выбор экспорта, текстуры, кисть, откат, ARTLOOK) и Unmatched.S08.ArtHudUmg.* (цвет TeamShape P1/P2) зелёные.
- audit: margin_px 64, seam_px 0.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Чип в теге и плашке пока в прежнем боксе 12 su (при 100 % — экспорт 18 px в 12 px); 24 su (ВР-78) — раскладка тега HB-45 и плашки HB-46 (ВР-VS2-16).
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (тег бойца HB-45 (24 su) и плашка HB-46, шаг H12); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
