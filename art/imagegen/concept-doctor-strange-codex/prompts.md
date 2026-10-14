# Промпты ASSET-DOCTOR-STRANGE-001 — этап 1a

Исправление только метаданных. Все приведённые промпты исторические; в этом запуске они не выполнялись. image_gen: 0 вызовов.

## 1a/design-front/u1

- Файл: `art/imagegen/concept-doctor-strange-codex/concepts/doctor-strange-design-front-u1.png`.
- Дата записи: 2026-10-13 08:49:44 UTC.
- Инструмент: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.
- Режим: text-to-image.
- referenced_image_paths (порядок исторического вызова): [].
- Точный внешний промпт скопирован из исходной записи; не выполнялся сейчас.

```text
Painted collectible tabletop miniature figure of Doctor Strange from the Marvel comics, high-end painted resin statue, product photo. Dark blue tunic, flowing red Cloak of Levitation with a high collar, golden Eye of Agamotto amulet, yellow gloves, grey temples and goatee, one hand raised in a mystic gesture. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## 1a/design-front/u1c

- Файл: `art/imagegen/concept-doctor-strange-codex/concepts/doctor-strange-design-front-u1c.png`.
- Дата записи: 2026-10-13 08:49:44 UTC.
- Инструмент: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.
- Режим: cleanup: corner logos painted out with background (Claude, PIL).
- referenced_image_paths (порядок исторического вызова): [].
- Точный внешний промпт скопирован из исходной записи; не выполнялся сейчас.

```text
Painted collectible tabletop miniature figure of Doctor Strange from the Marvel comics, high-end painted resin statue, product photo. Dark blue tunic, flowing red Cloak of Levitation with a high collar, golden Eye of Agamotto amulet, yellow gloves, grey temples and goatee, one hand raised in a mystic gesture. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## 1a/design-front/g3

- Файл: `art/imagegen/concept-doctor-strange-codex/concepts/doctor-strange-design-front-g3.png`.
- Дата записи: 2026-10-13T09:52:55+00:00.
- Инструмент: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps; Claude rebg.py historical postprocess; Codex metadata-only registration (0 generation calls).
- Режим: metadata-only registration of existing normalized design; unstability.ai historical source; Claude rebg.py historical background normalization; neither generation nor postprocess executed in this run.
- referenced_image_paths (порядок исторического вызова): [].
- Точный внешний промпт скопирован из исходной записи; не выполнялся сейчас.

```text
Painted collectible tabletop miniature figure of Doctor Strange from the Marvel comics, high-end painted resin statue, product photo. Dark blue tunic, flowing red Cloak of Levitation with a high collar, golden Eye of Agamotto amulet, yellow gloves, grey temples and goatee, one hand raised in a mystic gesture. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## Проверка и ограничения

Проверен только design-front; межвидовое соответствие и этап 1c не оценивались. PNG не изменялись. Новый g3 — побайтная копия текущего дизайна, уже исторически нормализованного Claude через rebg.py. Промпт g3 дословно совпадает с внешним промптом u1c и описывает историческое происхождение, а не новый вызов генератора.

Старые кандидаты проверены на временных побайтных копиях внутри пакета; их FAIL остаются историей. Финальный checker запускался последним на design/doctor-strange-front.png без --out. Визуальные пункты checklist не переоценивались. Статус: предложено.
