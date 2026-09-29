# king-arthur: imagegen prompts

Дата: 2026-09-29. Инструмент: встроенный image_gen.imagegen. transparent_background: false. Один вызов на изображение. После генерации PNG скопированы без редактирования пикселей.

## Проверка и ограничения

Силуэт и поза узнаваемо сохранены, но не совпадают пиксельно. Корона, гарда/навершие меча, контуры наплечников и складки плаща изменены. На боковом виде слегка раскрыт торс. Между видами отличаются рисунки гравировки, точная форма складок и ширина/положение подставки. Это концепты по модели, не геометрически точные проекции.

## front

Файл: king-arthur-front.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260928-blender-um-fbx-v1/preview/ortho_front.jpg`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Edit image 1 directly: paint over the low-poly King Arthur FRONT orthographic render, preserving its exact silhouette, body proportions, pose, sword outline and orientation, crown outline, cloak outline, feet, round pedestal geometry and framing. Image 2 is ONLY the painted miniature craftsmanship and detail reference (Medusa); do not copy her anatomy, costume, camera or base. Produce one single front view, not a sheet. Extremely detailed premium painted collectible miniature, as refined as image 2: dark gunmetal plate with antique gold edging, intricate Celtic-British knotwork engraving and shallow chased dragon relief inside existing plates, keep central gold diamond; deep burgundy cloak and tabard with finely embroidered Celtic borders, realistic woven cloth and drapery inside existing contours. Excalibur remains the same straight upright sword in the same hand, add finely etched blade and gold dragon/knotwork hilt within existing geometry. Keep the same mature dark-haired bearded king and gold crown, refine face, eyes, hair and articulated fingers. Neutral dark charcoal gray background, soft studio light, full body and whole round base, orthographic no perspective, no cropping, no text, no watermark, no extra objects. Preserve input 1 normalized coordinates and image aspect ratio 9:10, base spans x24.8%-75.2%, y87.2%-96.2%; sword tip y4.2%. Surface detailing only, no new silhouette elements.
```

## side

Файл: king-arthur-side.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260928-blender-um-fbx-v1/preview/ortho_left.jpg`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/king-arthur/king-arthur-front.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET, low-poly King Arthur exact LEFT SIDE orthographic view facing left. Paint directly over that geometry. Image 2 is the finished front of this SAME miniature, defining all materials and decorative details. Produce a single left side image consistent with image 2, but preserve image 1 side silhouette, proportions, pose, upright sword placement and outline, crown, hands, feet and cloak contour. Rich dark gunmetal and antique gold armor with fine Celtic knotwork and dragon chasing, central gold diamond, same dark hair and beard, burgundy cloak with gold knotwork borders, same Excalibur engraving, detailed face and gauntlets. Premium painted collectible miniature, extraordinary crisp sculpted surface detail and cloth weave. Neutral charcoal background and lighting identical to image 2. Match image 2 canvas aspect ratio 9:10, physical scale and base position: round base x24.5%-73.7%, top y83.8%, bottom y93.3%; feet at y84%, sword tip y3%, crown y11.3%. Rescale the entire image 1 uniformly to that framing, no anatomical changes. Strict side orthographic projection, no three-quarter view, no perspective, no crop, no text, no watermark, no added silhouette ornaments.
```

## back

Файл: king-arthur-back.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260928-blender-um-fbx-v1/preview/ortho_back.jpg`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/king-arthur/king-arthur-front.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: low-poly King Arthur exact BACK orthographic render. Paint directly over the existing shape, preserving silhouette, proportions, pose, arms, upright sword on viewer RIGHT, crown, cloak outline, feet and round base. Image 2 is the approved detailed FRONT of the SAME miniature; use identical colors, armor, crown, dark hair, sword and burgundy cloak with gold Celtic knotwork borders. Extremely detailed painted collectible miniature: deep crimson woven cloth with realistic fine drapery inside the same outer contour, consistent gold embroidered knotwork at all cloak edges, subtle tone-on-tone Celtic dragon embroidery on back, finely engraved dark gunmetal and gold visible armor. Rear view only, no face visible. Neutral charcoal gray backdrop, same studio lighting as image 2. Match image 2 aspect ratio 9:10, physical scale and base position: round base spans x24.5%-73.7%, top y83.8%, bottom y93.3%; feet y84%, sword tip y3%, crown y11.3%. Uniform reframing only; preserve input 1 anatomy and geometry. Orthographic no perspective, full body and base, no cropping, no text or watermark. One image, no sheet.
```


