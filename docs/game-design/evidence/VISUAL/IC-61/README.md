# IC-61 — лист приёмки `cursor-busy` (курсор «занято»)

Лист собран 2026-10-06: `draw_icons.py --sheet accept cursor-busy` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=cursor` (HB-12)
**Решения по делегированию:** ВР-VS2-19, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Песочные часы state-sent без плашки ×1,2 (высота 21 u) по центру, keyline 2 u (стык round); «воздух» колбы — тёмный keyline. 8 кадров с запечённым переворотом: f00…f03 — кадры 0, 2, 4, 6 `_sent_frames()`, f04 — кадр 6, повёрнутый на 90°, f05…f07 — кадры 7, 9, 11; файлы `layers/cursor-busy_fNN-{24,32,48,64}.png`. Цикл 1500 мс: 0 / 183 / 367 / 550 / 800 / 950 / 1170 / 1390; reduced — f00. Горячая точка — центр.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-cursor-busy.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-cursor-busy.png`, `sheet-01-cursor-busy-24.png`, `sheet-02-cursor-busy-32.png`, `sheet-03-cursor-busy-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок курсоров HB-12) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-cursor.png`, `check-frames.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | курсор — флипбук `check-frames.png` |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/cursor-busy-24.png` | 24×24 | 9508419a0d63e9e563b35ea7a2a54168dede3d4c816ee1b8bdd2f17396903e7c |
| `art/imagegen/hud-icons-v3/sizes/cursor-busy-32.png` | 32×32 | 09c83fff1825a8fd1c69bf008ae3690afd9367aba0898ded20751d5b3af08502 |
| `art/imagegen/hud-icons-v3/sizes/cursor-busy-48.png` | 48×48 | 3b2796349df29b952b717d42fb454755d81d4fc270b411f43585e8392ab343fe |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-cursor-busy.png`, `check-cursor.png`, `check-frames.png`, `sheet-01-cursor-busy-24.png`, `sheet-02-cursor-busy-32.png`, `sheet-03-cursor-busy-48.png`, `sheet-sizes.png`.
- `check-frames.png`: пересыпание и переворот (90° на 800 мс) читаются при 24 и 32 px без серой каши, на navy и на светлом пространстве, в сером.
- `check-cursor.png`: на трёх фонах.
- audit: margin_px [198, 112, 198, 112], seam_px 0.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- UE (T_Cursor_Busy_00…07, флипбук UUmCursor, HUD-CURSOR state=busy) — HB-12.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок курсоров HB-12); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
