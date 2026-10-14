# Исторические промпты ASSET-BULLSEYE-001 — этап 1a

Дата исправления метаданных: 2026-10-13T10:37:33+00:00.

В этом запуске генераций: **0**. Ни один промпт не выполнялся.

## 1a/design-front/u1

Файл: `art/imagegen/concept-bullseye-codex/concepts/bullseye-design-front-u1.png`.

Дата записи: 2026-10-13 08:49:44 UTC.

Инструмент: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.

Историческая внешняя генерация; эта запись в текущем запуске не выполнялась.

referenced_image_paths (в порядке вызова): `[]` — исторический text-to-image без image-reference; в текущем запуске вызова нет.

Точный исторический промпт:

```text
Painted collectible tabletop miniature figure of Bullseye from the Marvel comics, high-end painted resin statue, product photo. Black and dark blue costume with a white target symbol on the forehead, throwing knives fanned in his right hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## 1a/design-front/g2

Файл: `art/imagegen/concept-bullseye-codex/concepts/bullseye-design-front-g2.png`.

Дата записи: 2026-10-13T10:37:33+00:00.

Инструмент: unstability.ai source (historical); Claude rebg.py historical postprocess; Python metadata-only registration.

Регистрация существующего нормализованного дизайна; точная копия исторического внешнего промпта.

referenced_image_paths (в порядке вызова): `[]` — исторический text-to-image без image-reference; в текущем запуске вызова нет.

Точный исторический промпт:

```text
Painted collectible tabletop miniature figure of Bullseye from the Marvel comics, high-end painted resin statue, product photo. Black and dark blue costume with a white target symbol on the forehead, throwing knives fanned in his right hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## Проверка и ограничения

В пакете только design-front; сравнения между видами нет. Новый кандидат совпадает побайтно с существовавшим нормализованным дизайном. Исторический u1 и raw не заменялись. Нормализация Claude rebg.py — историческое действие, не действие этого запуска. Полный CORE ImageGen историческим внешним промптом не подменяется. Аспект исходного PNG 4:5 вместо 3:4. Визуальные пункты заново не оценивались: permitted inputs использованы только для хешей и checker. Статус — предложено; художественная приёмка не заявляется.
