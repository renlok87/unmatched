# Бриф ImageGen: глифы значков HUD, волна 1

Дата: 2026-10-03. Исполнитель: Codex (ImageGen) в приложении ChatGPT, проект unmached. Основание:
[HUD-AND-ICONS.md](HUD-AND-ICONS.md) §3.4 (состав волны 1) и §1.9 (правила И-1..И-10). Журнал ревью:
[HUD-AND-ICONS-review-log.md](HUD-AND-ICONS-review-log.md).

## 1. Что нужно

Нарисовать 9 глиф-масок для значков HUD с решением «перерисовать». Каждая маска — один белый плоский глиф на
прозрачном фоне, холст 1024×1024. Блок, кромку, цвет, состояния и размеры 24/32/48 не рисовать: значок из маски
собирает скрипт `art/imagegen/hud-icons-v2/_tools/compose_icons.py` с точными цветами токенов. Так решено по
ревью: точные hex и толщины диффузионная модель не держит (HUD-AND-ICONS §3.4).

Это не сцены. Не рисовать доски, фигурки, портреты, карты, руки, интерфейс, логотипы, надписи. Только один глиф по
центру пустого холста.

## 2. Условия работы (обязательно)

1. Писать файлы **по абсолютному пути** в основной checkout:
   `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hud-icons-v2/glyphs/`.
2. Имена файлов — ровно `<id>.png` из таблицы §5: латиница и дефисы. **Без пробелов в начале и в конце имени**
   (в прошлый раз была такая ошибка). После записи вывести список файлов и проверить имена.
3. Точный текст промпта каждого глифа — в `glyphs/prompts/<id>.txt`.
4. `glyphs/manifest.json` — по схеме §6.
5. **Никаких git-операций**: add, commit, stash, checkout, reset. Не трогать файлы вне `art/imagegen/hud-icons-v2/glyphs/`.
6. Никаких покупок, логинов и загрузок с внешних сайтов.

## 3. Референсы

| Что | Где |
|---|---|
| Текущие значки v2 (форма, место глифа) — 256 px | `art/imagegen/hud-icons-v2/reference-v2/v2-<id>-256.png` |
| Код значков v2 и полигоны глифов (звезда атаки, щит, молния, шевроны) — образец толщины и плоскости | `tools/art/move_selection/card_icons.py` |
| Лист MS-C-09 (значки рядом с реальными RU-картами) | `scraped-data/derived/move-selection/MS-C-09.png` |
| Реальные RU-карты (плоские белые глифы типа на цветных блоках) | `scraped-data/images/decks/*.webp`, сопоставление — `art/imagegen/mvp-v1/reused-cardart.json` (например, Medusa «Gaze of Stone» `AkZUXVmcOk18xfVMoXgu0.webp`, «Hiss and Slither» `WZH7yfWQPNzpj5csLKQeH.webp`, «Snipe» `anS2Y7A_VQGos_ARTBq1M.webp`) |
| Старые значки mvp-v1 (только смысл, стиль «кость, бронза, рельеф» не повторять) | `art/imagegen/mvp-v1/ui/**`, `markers/**` |

Сканы карт — только референс стиля глифов по указанию пользователя. Ничего с них не копировать: ни арт, ни
логотипы, ни надписи.

## 4. Стиль (общий для всех глифов)

- Один глиф, чисто белый `#FFFFFF`, плоский, без градиентов, рельефа, бликов, теней, свечения и текстуры.
- Фон прозрачный (PNG RGBA). Если прозрачность недоступна — ровный чёрный `#000000` без шума и виньетки: маска
  возьмётся по яркости.
- Толстые простые формы, как белые глифы типа на картах Unmatched (звезда-взрыв, щит, молния). Толщина любой
  линии — не меньше 1/8 габарита глифа. Внутренние отверстия — не меньше 1/6 габарита.
- Глиф занимает 70–80 % холста по большей стороне, по центру, не обрезан.
- **Без букв, слов и цифр.**

Общий хвост промпта (добавлять к каждому):

> single flat pure white glyph on a fully transparent background, centered, 1024x1024, solid white silhouette
> only, no outline, no gradient, no bevel, no emboss, no shadow, no glow, no texture, no frame, no background
> shape, no text, no letters, no numbers, very thick simple shapes and wide gaps so it stays readable at 24 pixels,
> in the style of the flat white type icons on modern board game cards

## 5. Глифы

| № | id | Значок (HUD-AND-ICONS §3.4) | Что исправить | Промпт (без общего хвоста §4) |
|---|---|---|---|---|
| 1 | `glyph-lock` | `state-enemy` (V-07, враг, путь закрыт) | сейчас Segoe UI Symbol U+1F512: тонкий, при 24 px дужка сливается с корпусом | a padlock: wide rectangular body with a round keyhole hole, thick rounded shackle on top with a clear gap inside |
| 2 | `glyph-hourglass` | `state-sent` (V-10, ждём сервер), курсор busy | Segoe U+231B тонкий; нужны толстые колбы и планки | an hourglass: two solid triangles meeting at the tips, a thick flat bar on top and on the bottom |
| 3 | `glyph-map-pin` | `state-pending-place` (V-12, «поместите») | булавка Segoe U+1F4CD тонкая и читается как «кнопка» | a map location pin: teardrop shape pointing down with a large round hole in the head |
| 4 | `glyph-move-arrows` | `state-pending-move` (V-11, «переместите») | молния — глиф типа «хитрость», а MOVE бывает у карт любого типа (И-10) | a move symbol: four thick arrows pointing up, down, left and right from a small center square, like a cross of arrows |
| 5 | `glyph-lightbulb` | `state-hint` (V-13, подсказка; ранг 1–3 — текстом рядом) | звезда занята атакой (И-10) | a simple light bulb: round bulb with a short thick screw base of two horizontal bars, no rays |
| 6 | `glyph-eye` | `state-threat` (V-16, угроза; число — текстом рядом) | Segoe U+1F441 тонкий, 4,0 : 1, при 24 px не читается | an eye: thick almond outline shape with a large solid round pupil in the middle and a clear gap between them |
| 7 | `glyph-chain` | `state-immobilized` («не может двигаться») | Segoe U+26D3 при 24 px — шум | two thick interlocked oval chain links on a diagonal, large holes, very bold |
| 8 | `glyph-footprint` | `action-maneuver` (манёвр) | след из кости с бронзой, рельеф | a single footprint sole seen from above, tilted slightly, with a separate round heel pad, no toes detail |
| 9 | `glyph-circular-arrow` | `resource-connection-reconnecting` (переподключение) | цепь в стрелках: цепь занята значением «не может двигаться» (И-10) | one thick circular arrow forming three quarters of a ring with a large arrowhead at the end |

## 6. Выход

```
art/imagegen/hud-icons-v2/glyphs/
  <id>.png            1024x1024, RGBA (или ровный чёрный фон)
  prompts/<id>.txt    точный промпт
  manifest.json
```

`glyphs/manifest.json`:

```json
{
  "schema": "unmatched.hud-icons-v2.glyphs/1",
  "date": "2026-10-03",
  "brief": "docs/unreal/contracts/hud/IMAGEGEN-BRIEF-icons.md",
  "generator": "ImageGen (Codex)",
  "glyphs": [
    {"id": "glyph-lock", "file": "glyph-lock.png", "prompt": "prompts/glyph-lock.txt",
     "width": 1024, "height": 1024, "alpha": true, "attempts": 1, "status": "generated"}
  ]
}
```

## 7. Критерии приёмки

Проверяет основная сессия на собранном значке (`compose_icons.py`) и на самой маске.

1. Значок читается при 24 и 32 px. Граница — 16 px (720p при масштабе 75 %, HUD-AND-ICONS HI-R-01).
2. Значки волны различаются в оттенках серого по силуэту и глифу.
3. Палитра и формы — как в v2: тело `card.navy`, кремовая кромка, белый плоский глиф. Маска строго белая и плоская.
4. На глифе нет букв и цифр.
5. Фон прозрачный или ровный чёрный; глиф по центру, не обрезан.
6. Имена файлов без пробелов; `manifest.json` валиден.

Не прошедший глиф возвращается Codex с конкретной правкой, номер попытки пишется в `attempts`. Итоговые значки и
лист сравнения «было → стало» собирает основная сессия:

- `art/imagegen/hud-icons-v2/<id>.png`;
- `compare-sheet.png`;
- `compare-gray-24px-x4.png` и `compare-gray-32px-x4.png`.
