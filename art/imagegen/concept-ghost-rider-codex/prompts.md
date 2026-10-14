# Исторические промпты ASSET-GHOST-RIDER-001, этап 1a

Дата исправления: 2026-10-13. Генераций и вызовов image_gen в этом запуске: **0**. Все приведённые промпты исторические; сейчас ни один не выполнялся. Референсы изображений не передавались генератору.

## 1a/design-front/u1

Date: 2026-10-13 08:49:44 UTC

Tool: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps

Mode: text-to-image

File: `art/imagegen/concept-ghost-rider-codex/concepts/ghost-rider-design-front-u1.png`

referenced_image_paths (historical call order): []

Историческая генерация unstability.ai, не выполнена в этом запуске. Исходный неизменяемый кандидат сохранён.

Исторический промпт, точный текст:

```text
Painted collectible tabletop miniature figure of Ghost Rider from the Marvel comics, high-end painted resin statue, product photo. Flaming skull head, black leather biker jacket with silver spikes, heavy chain wrapped around the right arm, orange flames. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## 1a/design-front/g2

Date: 2026-10-13 10:52:01 UTC

Tool: unstability.ai source; Claude rebg.py historical postprocess; metadata-only registration

Mode: metadata-only byte-for-byte registration of existing normalized design; unstability.ai source; historical Claude rebg.py postprocess; zero generation calls in this repair run

File: `art/imagegen/concept-ghost-rider-codex/concepts/ghost-rider-design-front-g2.png`

referenced_image_paths (historical call order): []

Регистрация побайтовой копии существовавшего нормализованного дизайна после исторической обработки Claude rebg.py. Новый ключ содержит точный промпт прежнего внешнего источника; промпт сейчас не выполнялся.

Исходник регистрации: `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/concept-ghost-rider-codex/design/ghost-rider-front.png`

prompt_executed_in_run = false; image_gen_calls_in_run = 0.

Исторический промпт, точный текст:

```text
Painted collectible tabletop miniature figure of Ghost Rider from the Marvel comics, high-end painted resin statue, product photo. Flaming skull head, black leather biker jacket with silver spikes, heavy chain wrapped around the right arm, orange flames. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## Проверка и ограничения

Создана только новая неизменяемая копия текущего дизайна, без ретуши, изменения размера или кодирования. g2 и design имеют одинаковый SHA256; u1 и raw сохранены. Запись u1 не описывает нормализованный файл: это различие раскрыто, а не скрыто.

Проверяется один фронт; боковой и задний виды отсутствуют, согласованность между видами не оценивалась. Историческая проверка u1 — код 1; проверка g2 и финальная проверка дизайна — код 0. Визуально виден верх подставки и неровный фон за ней; CHECKLIST имеет два невыполненных пункта. Размер 4:5 и низ y95% также сохранены и раскрыты. Генераций 0; статус «предложено», художественная приёмка не заявляется.
