# Промпты ASSET-SHE-HULK-001 — этап 1a

Image generations and image_gen calls in this corrective run: 0. The external source prompt below is historical and was not executed now.

## 1a/design-front/u1 - Historical external generation

Date: 2026-10-13 08:49:44 UTC

Tool: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps

Mode: text-to-image

File: art/imagegen/concept-she-hulk-codex/concepts/she-hulk-design-front-u1.png

referenced_image_paths (in order): []

Original record preserved except selected. Its historical original_path string is retained; the exact download path is unknown.

Exact historical prompt:

```text
Painted collectible tabletop miniature figure of She-Hulk from the Marvel comics, high-end painted resin statue, product photo. Tall muscular green-skinned woman with long dark green hair, purple and white athletic suit, confident stance. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## 1a/design-front/g2 - Metadata-only registration; historical prompt, not executed now

Date: 2026-10-13T10:00:44.593241+00:00

Tool: unstability.ai source; Claude rebg.py historical postprocess; metadata-only registration (zero generator calls)

Mode: metadata-only byte-copy registration of unstability.ai source after Claude rebg.py historical postprocess; no generation or postprocess executed now

File: art/imagegen/concept-she-hulk-codex/concepts/she-hulk-design-front-g2.png

referenced_image_paths (in order): [] (no generator call)

Byte-copy source: C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/concept-she-hulk-codex/design/she-hulk-front.png. Record references describe registration input, not image-generation references. Claude rebg.py historical postprocessing was not executed now.

Exact historical prompt:

```text
Painted collectible tabletop miniature figure of She-Hulk from the Marvel comics, high-end painted resin statue, product photo. Tall muscular green-skinned woman with long dark green hair, purple and white athletic suit, confident stance. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.
```

## Проверка и ограничения

Only design-front is present; no cross-view consistency claim is made. Registered g2 is byte-identical to the pre-existing normalized design. Historical background normalization is documented in verification.json#design_source.post, not performed in this repair. The old u1 and raw PNGs are unchanged. Historical checker failures are retained in checks/design-front-g1. The selected design was checked last without --out. Its top margin WARN is 2.375% versus 4%. The full visual checklist was not reassessed: image inputs were used only for hashing and automated checks. Missing evidence is explicit in verification.json. Статус: предложено.
