# harpy: imagegen prompts

Дата: 2026-09-29. Инструмент: встроенный image_gen.imagegen. transparent_background: false. Один вызов на изображение. После генерации PNG скопированы без редактирования пикселей.

## Проверка и ограничения

Сохранены присевшая поза, крылья вместо рук, палитра и золотая подставка. Изменены мелкие контуры и слои перьев, хохолок, лапы/когти; фронтальный размах немного шире относительно кадра. Боковой исходник был квадратным и крупнее фронта; генерация приведена к широкому кадру, но подставка всё ещё немного уже фронта. На заднем виде изменилась трактовка пальцев лап. Точного совпадения силуэтов и масштаба нет.

## front

Файл: harpy-front.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-HARPY-001/20260928-blender-um-fbx-v1/preview/ortho_front.jpg`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: low-poly Harpy FRONT orthographic miniature. Paint OVER this exact model, preserving its crouched squat pose, compact anatomy, fierce humanoid female face, pointed ears, swept feather crest, large spread WING-ARMS, precisely the existing primary feather count and outer shapes, chest feather covering, thighs, bird feet and talons, single ankle band on viewer RIGHT, short tail and gold round pedestal. Do NOT add human arms, hands, weapons or clothing. Image 2 is ONLY painted collectible miniature quality/style reference, not anatomy or costume. Achieve that extraordinary detail: individual feather barbs and fine layered coverts INSIDE existing silhouette, warm tawny/copper brown inner feathers, dark near-black brown outer flight feathers and neck ruff, ash-tan face with sharp predatory features and dark eyes, sculpted bird leg scales and glossy dark hooked talons; antique bronze etched feather motif on existing ankle band. Full painted miniature realism, controlled painted highlights, exquisite sculpt detail, no new silhouette feathers or altered wingspan. Plain neutral charcoal gray background, soft studio lighting. Single exact frontal orthographic view, no perspective, full wings and complete base. Match image 1 landscape aspect ratio 11:8, framing and uniform scale: wings x5.5%-94.5%, crest y10%, base x34.7%-65.3%, top y80.5%, bottom y90.2%. Preserve base gold color and cylinder shape, add subtle aged metallic texture. No text, no watermark, no crop, no extra ornaments.
```

## side

Файл: harpy-side.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-HARPY-001/20260928-blender-um-fbx-v1/preview/ortho_left.jpg`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/harpy/harpy-front.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 is the geometry EDIT TARGET: Harpy LEFT SIDE orthographic low-poly render facing left. Image 2 is the finished FRONT of the SAME painted miniature, its exact colors, materials and detail vocabulary. Paint over image 1 model, preserve exact crouched pose and anatomy, side wing shape, swept feather crest, pointed ear, face profile, thighs, tail, bird feet, claws, and single ankle band. Match image 2 warm copper/tawny coverts, very dark brown primary feathers and neck ruff, ash-tan face, gold feather-etched ankle band, glossy black talons, gold cylinder base. Extremely detailed collectible painted miniature: feather barbs and fine feathers within source outline, scales, refined face, aged metal; no added arms, weapons, accessories or silhouette ornaments. IMPORTANT FRAMING: output landscape 11:8 SAME as image 2, with SAME physical scale and base pixel size. Image 1 is more zoomed in: uniformly reduce/reframe its model to fit base x35%-65%, y81%-90.5%, crest y10%. Center pedestal at x50%. Leave generous blank space on either side of this narrow side view; do NOT enlarge to fill canvas. Preserve source side projection and exact relative size of body, wings and pedestal. Strict left profile orthographic, no perspective or three-quarter angle. Neutral charcoal backdrop and studio illumination same as image 2. Entire figure and round base visible, no crop, no text or watermark.
```

## back

Файл: harpy-back.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-HARPY-001/20260928-blender-um-fbx-v1/preview/ortho_back.jpg`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/harpy/harpy-front.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 is EDIT TARGET: low-poly Harpy BACK orthographic render. Paint OVER this exact geometry, preserve spread wings' outer silhouette and primary feather arrangement, crouched pose, proportions, head crest, neck ruff, thighs, short tail, bird feet and gold round pedestal. Image 2 is finished FRONT of SAME miniature and defines exact color palette/materials/detail: tawny copper inner feathers and thigh plumage, near-black brown primary feathers, dark neck ruff and tail, warm bird leg scales, glossy black talons, single gold feather-etched ankle band now on viewer LEFT. No human arms, weapons or accessories. Premium exquisitely detailed painted collectible miniature, individual barbs and layered small plumage inside original surfaces; keep sculpt contours fixed. Rear orthographic view only, no face, no perspective, full wingspan and whole base. Neutral charcoal backdrop with same lighting as image 2. Landscape aspect ratio 11:8 and SAME physical scale and position as image 2: wings x3.3%-96.5%, crest y9.5%, pedestal x35%-65%, top y81%, bottom y90.5%. Gold round base aged metallic texture. No text, watermark, cropping or additional silhouette elements.
```


