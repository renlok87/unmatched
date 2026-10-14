# Исторические промпты ASSET-BLACK-WIDOW-001

Документ восстановлен из прежней записи. В этом запуске генераций и вызовов image_gen: **0**. Все тексты ниже — исторические; сейчас они не исполнялись.

## 1a/design-front/u1

- Файл: `art/imagegen/concept-black-widow-codex/concepts/black-widow-design-front-u1.png`.
- Дата записи: 2026-10-13 08:49:44 UTC.
- Инструмент: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.
- Режим: text-to-image.
- referenced_image_paths в порядке вызова: `[]`.
- Историческая внешняя генерация unstability.ai; не повторялась.

Точный исторический промпт:

```text
Painted collectible tabletop miniature figure of Black Widow from the Marvel comics, high-end painted resin statue, product photo. Black tactical catsuit, shoulder-length red hair, red hourglass belt buckle, silver wrist bracelets, pistol in her right hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## 1a/design-front/g2

- Файл: `art/imagegen/concept-black-widow-codex/concepts/black-widow-design-front-g2.png`.
- Дата записи: 2026-10-13T10:12:13+00:00.
- Инструмент: unstability.ai historical source; Claude rebg.py HISTORICAL external postprocess; metadata-only registration (no generator invoked).
- Режим: metadata-only registration of existing normalized design; historical unstability.ai text-to-image + Claude rebg.py postprocess.
- referenced_image_paths в порядке вызова: `[]`.
- Только регистрация существующего нормализованного PNG; промпт дословно скопирован из 1a/design-front/u1.
- Claude rebg.py — историческая внешняя обработка, не выполнялась сейчас.

Точный исторический промпт:

```text
Painted collectible tabletop miniature figure of Black Widow from the Marvel comics, high-end painted resin statue, product photo. Black tactical catsuit, shoulder-length red hair, red hourglass belt buckle, silver wrist bracelets, pistol in her right hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## Проверка и ограничения

Представлен только design-front; согласованность нескольких видов не оценивалась. u1 неизменён; g2 — побайтовая копия текущего дизайна, а не новая генерация. Нормализация фона существовала до этого запуска.

Исторический u1: checker 1 (view.border_uniform, view.side_margin). g2 и финальный текущий дизайн: checker 0. Эти коды не означают художественную приёмку.

- Верх подставки виден: строгий уровень камеры и вид ребром не соблюдены.
- Фигура целиком; слева у подставки светлый остаток маски нарушает ровный фон.
- Пряжка: красный круг с перекрестием; однозначный знак песочных часов не подтверждён.

Лимит этого запуска — 0 генераций; исправления изображения запрещены. Статус: **предложено** (proposed).
