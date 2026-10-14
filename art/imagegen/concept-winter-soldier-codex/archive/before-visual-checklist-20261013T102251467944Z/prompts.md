# Промпты ASSET-WINTER-SOLDIER-001 — этап 1a

Дата корректирующей регистрации: 2026-10-13T10:20:24+00:00.

В этой правке выполнена только регистрация метаданных. Генераций изображений и вызовов image_gen: **0**.
Все тексты ниже — точные исторические промпты внешнего источника; сейчас они не выполнялись.

## 1a/design-front/u1

Файл: `art/imagegen/concept-winter-soldier-codex/concepts/winter-soldier-design-front-u1.png`.
Дата записи: 2026-10-13 08:49:44 UTC. Инструмент: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.
Режим: text-to-image.
Исторические referenced_image_paths (в порядке вызова): `[]` (text-to-image).
Историческая генерация unstability.ai; промпт взят из прежней записи без изменений.

```text
Painted collectible tabletop miniature figure of The Winter Soldier from the Marvel comics, high-end painted resin statue, product photo. Long dark hair, black tactical gear with straps, silver metal left arm with a red star on the shoulder, black mask over the lower face, rifle held in the right hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## 1a/design-front/g2

Файл: `art/imagegen/concept-winter-soldier-codex/concepts/winter-soldier-design-front-g2.png`.
Дата записи: 2026-10-13T10:20:24+00:00. Инструмент: unstability.ai source; Claude rebg.py historical postprocess; metadata-only registration.
Режим: metadata-only registration of unstability.ai source after historical Claude rebg.py postprocess; zero generation calls.
referenced_image_paths для генерации: `[]`; в этой правке вызова генерации не было.
Вход регистрации — существующий нормализованный дизайн; references новой записи обозначают происхождение байтов.

```text
Painted collectible tabletop miniature figure of The Winter Soldier from the Marvel comics, high-end painted resin statue, product photo. Long dark hair, black tactical gear with straps, silver metal left arm with a red star on the shoulder, black mask over the lower face, rifle held in the right hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## Проверка и ограничения

Зарегистрирован только front. Сравнение разных видов не проводилось.
Новый ключ g2 повторяет исторический внешний промпт u1 дословно; выполнения промпта сейчас не было.
Claude исторически нормализовал фон через rebg.py; это не операция данного запуска.
Текущий дизайн и прежние PNG сохранены байт-в-байт. Checker проверял временные копии кандидатов внутри пакета.
Визуальная приёмка и визуальная переоценка CHECKLIST не выполнены. Статус — предложено.
