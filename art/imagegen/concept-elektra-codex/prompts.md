# Промпты: история и регистрация 1a

Ниже исторические промпты unstability.ai; сейчас не выполнялись. Генераций и вызовов image_gen: **0**.
Claude ранее нормализовал фон через rebg.py. Сейчас — только побайтовая регистрация готового дизайна.

## ASSET-ELEKTRA-001-1a-design-front-u1

- Date: 2026-10-13 08:49:44 UTC
- Tool: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps
- Mode: text-to-image
- File: art/imagegen/concept-elektra-codex/concepts/elektra-design-front-u1.png
- Original source: unstability.ai download (Downloads/unstability-<uuid>.png)
- Prompt key: 1a/design-front/u1
- referenced_image_paths (ordered): []
- Executed in this repair run: false

Точный исторический текст внешнего промпта:

Painted collectible tabletop miniature figure of Elektra from the Marvel comics, high-end painted resin statue, product photo. Dark-haired female assassin in a red outfit with a long red headband and sash, a sai in each hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.

## ASSET-ELEKTRA-001-1a-design-front-g2

- Date: 2026-10-13T10:36:13+00:00
- Tool: unstability.ai historical source; Claude rebg.py historical postprocess; metadata-only registration
- Mode: historical external postprocess registration; zero generation calls in this repair run
- File: art/imagegen/concept-elektra-codex/concepts/elektra-design-front-g2.png
- Original source: C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/concept-elektra-codex/design/elektra-front.png
- Prompt key: 1a/design-front/g2
- referenced_image_paths (ordered): []
- Executed in this repair run: false

Точный исторический текст внешнего промпта:

Painted collectible tabletop miniature figure of Elektra from the Marvel comics, high-end painted resin statue, product photo. Dark-haired female assassin in a red outfit with a long red headband and sash, a sai in each hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.

## Проверка и ограничения

Один фронт; сравнения между видами нет. Ключ g2 содержит точную копию промпта u1, а не новый запрос.
g2 и design/elektra-front.png совпадают побайтно; u1 и raw сохранены. Историческая обработка: verification.json#design_source.post.
Checker: u1 — код 1, g2 и финальный дизайн — код 0. Художественная приёмка не заявлена.
Верх подставки виден, справа серый участок; клинки не читаются как саи, длинного конца пояса нет. Запрет оружия конфликтует с требованием саев. Аспект 4:5 вместо 3:4; на подставке каменная раскладка.
Статус: предложено. Генераций и изменений PNG не было.
