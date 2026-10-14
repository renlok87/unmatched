# Concept prompts: ASSET-PIRATE-CREWMAN-001, stage 1a

Date: 2026-10-13
Tool: image_gen.imagegen; mode: generate; transparent_background: false.
No size argument. Aspect ratio requested in CORE only.
Reference paths below are repository-relative, in call order; the tool received the resolved absolute paths of these same files.

## art/imagegen/concept-pirate-crewman-codex/concepts/pirate-crewman-design-front-g1.png

Date: 2026-10-13T03:38:37.222391+00:00
Tool: image_gen.imagegen
prompt_key: 1a/design-front/g1

referenced_image_paths:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A pirate crewman of Blackbeard: wiry sailor with a bandana and an eyepatch, striped shirt, ragged trousers, bare feet, boarding axe in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: boarding axe in the figure's own RIGHT hand; bandana; eyepatch; striped shirt.
PALETTE: stripe white #E2DCCF, bandana red #A6322B, trouser brown #5E4632, accent brass earring #C9A24A. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not visible, its front edge is a straight horizontal line.
VIEW: strict front orthographic view, camera exactly level with the subject at its mid-height (zero elevation, not
looking down), no perspective, no three-quarter turn, the subject faces the camera.
FRAMING: portrait aspect ratio 3:4; one isolated subject; the pedestal, or the bottom of the object if it has no pedestal,
centred at x50% with its bottom at y93%; the highest point of the subject or of anything it holds no higher than y4%
(y >= 4%: at least 4% of the image height below the top edge); the whole subject and the whole pedestal visible,
nothing cropped.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background, no gradient, no vignette, no floor, no cast
shadow on the background; soft even studio lighting, no strong rim light, no depth of field.
READABILITY: large clear shapes; arms, wings and held objects separated from the body by visible gaps; thin parts such
as strings, shafts and staffs clearly readable, not hair-thin; fine detail stays inside the silhouette.
FORBIDDEN: text, letters, numbers, logos, watermark, frame, collage or several views, extra figures, extra limbs,
heads, wings or weapons, team colours, a coloured ring or metal band on the pedestal.
Output one single image.
```

## art/imagegen/concept-pirate-crewman-codex/concepts/pirate-crewman-design-front-g2.png

Date: 2026-10-13T03:39:54.391964+00:00
Tool: image_gen.imagegen
prompt_key: 1a/design-front/g2

referenced_image_paths:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A pirate crewman of Blackbeard: wiry sailor with a bandana and an eyepatch, striped shirt, ragged trousers, bare feet, boarding axe in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: boarding axe in the figure's own RIGHT hand; bandana; eyepatch; striped shirt.
PALETTE: stripe white #E2DCCF, bandana red #A6322B, trouser brown #5E4632, accent brass earring #C9A24A. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not visible, its front edge is a straight horizontal line.
VIEW: strict front orthographic view, camera exactly level with the subject at its mid-height (zero elevation, not
looking down), no perspective, no three-quarter turn, the subject faces the camera.
FRAMING: portrait aspect ratio 3:4; one isolated subject; the pedestal, or the bottom of the object if it has no pedestal,
centred at x50% with its bottom at y93%; the highest point of the subject or of anything it holds no higher than y4%
(y >= 4%: at least 4% of the image height below the top edge); the whole subject and the whole pedestal visible,
nothing cropped.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background, no gradient, no vignette, no floor, no cast
shadow on the background; soft even studio lighting, no strong rim light, no depth of field.
READABILITY: large clear shapes; arms, wings and held objects separated from the body by visible gaps; thin parts such
as strings, shafts and staffs clearly readable, not hair-thin; fine detail stays inside the silhouette.
FORBIDDEN: text, letters, numbers, logos, watermark, frame, collage or several views, extra figures, extra limbs,
heads, wings or weapons, team colours, a coloured ring or metal band on the pedestal.
Output one single image.
CORRECTION (fix only this; everything above still applies):
- strict front orthographic view, camera exactly level: the pedestal top surface is visible and its front edge curves -> show the pedestal exactly edge-on with no visible top surface and a straight horizontal front edge, using zero-elevation orthographic projection.
```

## Проверка и ограничения

На этапе 1a один фронтальный вид; согласованность front/side/back не оценивалась. Между кандидатами сохранены топор справа у фигуры, бандана, повязка, полосатая рубашка, рваные коричневые брюки, босые ступни и двухъярусная подставка. CORE одинаков; в g2 добавлена только одна строка CORRECTION.

В g2 исправлен ракурс подставки. Инструмент изменил складки, пояс, положение топора и хвоста банданы; после генерации пиксели не редактировались. g1: код 0, WARN view.frame_top; повтор вызван видимым верхом подставки. g2 и финальный прогон: код 0, 13 PASS / 0 WARN / 0 FAIL.

Латунная серьга g2 не читается уверенно, пункт палитры CHECKLIST failed. Дополнительный меч нарушает CORE. Низ подставки y94.406% вместо y93%. Лимит 2/2 исчерпан; статус «предложено».

## fix1 / design-front g3

Date: 2026-10-13T05:54:29.183632+00:00
Tool: image_gen.imagegen (generate)
File: art/imagegen/concept-pirate-crewman-codex/concepts/pirate-crewman-design-front-g3.png
Prompt key: 1a/design-front/g3
referenced_image_paths (call order):
1. C:\Users\ren\WebstormProjects\unmached\unmached\art\imagegen\hero-quality-v1\reference\medusa-quality-reference.png

```text
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate (selected = true in generation-records.json) and copy it byte for byte to
   design/pirate-crewman-front.png. Run the step 2 command on it once more WITHOUT --out: this final run writes
   design/checks-report.json, the report of the selected design.
5. If the generations of this run are used up and a CHECKLIST item still fails, keep the best candidate, record the
   view and the failed items in verification.json limit_reached and in README.md, and finish normally: the acceptor
   decides. This is not a blocker.
6. Write prompts.md, prompts/concept-prompts.json, README.md, verification.json, manifest-sha256.json last.
CHECKLIST (each item passed/failed with a note in verification.json):
- one subject, one pedestal, no collage, no second view, no text, letters, logo or watermark;
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible;
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background;
- The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view. (both arms clearly apart from the torso, not a T-pose, not an A-pose);
- every identity anchor is visible: boarding axe in the figure's own RIGHT hand; bandana; eyepatch; striped shirt;
- main colours and the accent of the palette are present; no team colour, no coloured ring or band on the base.
CORE:
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A pirate crewman of Blackbeard: wiry sailor with a bandana and an eyepatch, striped shirt, ragged trousers, bare feet, boarding axe in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: boarding axe in the figure's own RIGHT hand; bandana; eyepatch; striped shirt.
PALETTE: stripe white #E2DCCF, bandana red #A6322B, trouser brown #5E4632, accent brass earring #C9A24A. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not visible, its front edge is a straight horizontal line.
VIEW: strict front orthographic view, camera exactly level with the subject at its mid-height (zero elevation, not
looking down), no perspective, no three-quarter turn, the subject faces the camera.
FRAMING: portrait aspect ratio 3:4; one isolated subject; the pedestal, or the bottom of the object if it has no pedestal,
centred at x50% with its bottom at y93%; the highest point of the subject or of anything it holds no higher than y4%
(y >= 4%: at least 4% of the image height below the top edge); the whole subject and the whole pedestal visible,
nothing cropped.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background, no gradient, no vignette, no floor, no cast
shadow on the background; soft even studio lighting, no strong rim light, no depth of field.
READABILITY: large clear shapes; arms, wings and held objects separated from the body by visible gaps; thin parts such
as strings, shafts and staffs clearly readable, not hair-thin; fine detail stays inside the silhouette.
FORBIDDEN: text, letters, numbers, logos, watermark, frame, collage or several views, extra figures, extra limbs,
heads, wings or weapons, team colours, a coloured ring or metal band on the pedestal.
Output one single image.
CORRECTION (fix only this; everything above still applies):
- S design-front: Remove the entire extra sword, including its hilt, guard and scabbard, from the figure's own LEFT hip (viewer RIGHT), leaving the boarding axe in the figure's own RIGHT hand as the only weapon and preserving the current relaxed front pose.
```

## fix1 / design-front g4

Date: 2026-10-13T05:56:09.366172+00:00
Tool: image_gen.imagegen (generate)
File: art/imagegen/concept-pirate-crewman-codex/concepts/pirate-crewman-design-front-g4.png
Prompt key: 1a/design-front/g4
referenced_image_paths (call order):
1. C:\Users\ren\WebstormProjects\unmached\unmached\art\imagegen\hero-quality-v1\reference\medusa-quality-reference.png

```text
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate (selected = true in generation-records.json) and copy it byte for byte to
   design/pirate-crewman-front.png. Run the step 2 command on it once more WITHOUT --out: this final run writes
   design/checks-report.json, the report of the selected design.
5. If the generations of this run are used up and a CHECKLIST item still fails, keep the best candidate, record the
   view and the failed items in verification.json limit_reached and in README.md, and finish normally: the acceptor
   decides. This is not a blocker.
6. Write prompts.md, prompts/concept-prompts.json, README.md, verification.json, manifest-sha256.json last.
CHECKLIST (each item passed/failed with a note in verification.json):
- one subject, one pedestal, no collage, no second view, no text, letters, logo or watermark;
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible;
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background;
- The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view. (both arms clearly apart from the torso, not a T-pose, not an A-pose);
- every identity anchor is visible: boarding axe in the figure's own RIGHT hand; bandana; eyepatch; striped shirt;
- main colours and the accent of the palette are present; no team colour, no coloured ring or band on the base.
CORE:
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A pirate crewman of Blackbeard: wiry sailor with a bandana and an eyepatch, striped shirt, ragged trousers, bare feet, boarding axe in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: boarding axe in the figure's own RIGHT hand; bandana; eyepatch; striped shirt.
PALETTE: stripe white #E2DCCF, bandana red #A6322B, trouser brown #5E4632, accent brass earring #C9A24A. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not visible, its front edge is a straight horizontal line.
VIEW: strict front orthographic view, camera exactly level with the subject at its mid-height (zero elevation, not
looking down), no perspective, no three-quarter turn, the subject faces the camera.
FRAMING: portrait aspect ratio 3:4; one isolated subject; the pedestal, or the bottom of the object if it has no pedestal,
centred at x50% with its bottom at y93%; the highest point of the subject or of anything it holds no higher than y4%
(y >= 4%: at least 4% of the image height below the top edge); the whole subject and the whole pedestal visible,
nothing cropped.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background, no gradient, no vignette, no floor, no cast
shadow on the background; soft even studio lighting, no strong rim light, no depth of field.
READABILITY: large clear shapes; arms, wings and held objects separated from the body by visible gaps; thin parts such
as strings, shafts and staffs clearly readable, not hair-thin; fine detail stays inside the silhouette.
FORBIDDEN: text, letters, numbers, logos, watermark, frame, collage or several views, extra figures, extra limbs,
heads, wings or weapons, team colours, a coloured ring or metal band on the pedestal.
Output one single image.
CORRECTION (fix only this; everything above still applies):
- S design-front: Remove the entire extra sword, including its hilt, guard and scabbard, from the figure's own LEFT hip (viewer RIGHT), leaving the boarding axe in the figure's own RIGHT hand as the only weapon and preserving the current relaxed front pose.
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal still shows its top plane and curved upper front edge -> use zero-elevation front orthographic projection, hide the entire pedestal top plane and make both disc front edges straight horizontal.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the background has subtle shading and a vignette -> use one uniform flat dark charcoal gray background without any gradient, vignette, floor or cast shadow.
```

## Проверка и ограничения

Корректирующий запуск fix1, 2026-10-13: выбран design-front g4; использовано 2/2 генерации запуска, всего 4/4 для вида. На этапе 1a один фронтальный вид, межвидовые совпадения не оценивались. Между g3/g4 сохранены четыре якоря, палитра, босые ступни, расслабленная поза с зазорами у рук и только топор в правой руке. Сабля, гарда, рукоять и ножны отсутствуют в обоих новых кандидатах.

CORE одинаков дословно. В g3 добавлена коррекция карточки приёмки; в g4 она сохранена первой строкой и дополнена двумя неудачными пунктами CHECKLIST в том же блоке CORRECTION. Вид подставки и фон улучшены. Генератор также изменил лицо, бороду, серьгу, складки и детали топора; ручной обработки изображения не было.

g3: код 0, 12 PASS / 1 WARN / 0 FAIL; визуально видимый верх подставки и слабый градиент фона вызвали повтор. WARN верхнего поля не вызвал повтор. g4 и финальный прогон: код 0, 13 PASS / 0 WARN / 0 FAIL; шесть пунктов CHECKLIST passed. Низ y93.301% и центр x50.138% немного отклоняются от целей CORE и записаны в verification.json. Приёмка не выполнялась; статус «предложено».
