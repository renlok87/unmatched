# medusa: imagegen prompts

Дата: 2026-09-29. Инструмент: встроенный image_gen.imagegen. transparent_background: false. Один вызов на изображение. После генерации PNG скопированы без редактирования пикселей.

## Проверка и ограничения

Фронт — побайтовая копия предоставленного эталона, без новой генерации. Для новых видов использованы существующие ортопревью исходной модели из tripo-source/d562f057/inspection; в указанных папках текущего кандидата не найдено нужной пары бок/спина. Эти превью не доказывают полного совпадения с текущим retopo/FBX. Сам эталон уже отличается от low-poly по луку, ткани и пропорциям. На новых видах изменены контуры/направления змей, лук, драпировка, колчан и ремни; точное совпадение подставки, масштаба и орнамента между видами не достигнуто.

## front

Файл: medusa-front.png.
Источник: ../reference/medusa-quality-reference.png.
Новый промпт не отправлялся: эталон скопирован без изменений. Исходный промпт из другого чата здесь не восстанавливался.

## side

Файл: medusa-side.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/tripo-source/d562f057/inspection/left.png`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 EDIT TARGET is the actual Medusa model LEFT SIDE orthographic render, facing LEFT with bow in front. Paint directly over its body, preserving its exact profile silhouette, stance, proportions, arm pose and grip, leg placement, cloak contour, snake positions, quiver and bow orientation. Image 2 is the established FRONT MASTER of this SAME painted collectible miniature. Reproduce its exquisite craftsmanship, identity, outfit and colors consistently: ivory gray skin, same beautiful stern adult female face, olive-black snakes with detailed golden-edged scales and amber eyes, gold laurel diadem, charcoal plum pleated Grecian dress with antique gold Greek-meander borders, brown leather diagonal quiver strap, richly chased gold snake bracers and greaves, leather-strapped sandals, detailed gold serpentine bow with meander engraving. Keep bow source outline and pose while decorating it with reference motifs; do not create a new weapon. Quiver warm brown leather with gold meander rim and same feathered arrows. Very high painted miniature detail, cloth weave, fine folds, face and hand refinement, hammered metal and patina. Single strict LEFT side profile, no three-quarter view. Neutral charcoal gray background same as image 2. Full figure and whole circular dark base. Output portrait with SAME aspect ratio as image 2 (1021:1540), SAME physical scale and pedestal placement: base centered x45%, width70%, top y88%, bottom y96.8%; highest snake y2%, feet y88%. Uniformly reframe model from image 1 to match master image 2, keep body proportions unchanged. No perspective, text, labels, watermark, cropping or added anatomy.
```

## back

Файл: medusa-back.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/tripo-source/d562f057/inspection/back.png`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`
3. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/medusa/medusa-side.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 is the geometry EDIT TARGET, Medusa BACK orthographic low-poly render. Paint directly OVER its exact model structure: preserve body proportions, standing pose, arm positions, bow on viewer LEFT, quiver diagonally on viewer RIGHT upper back, seven-headed snake hair arrangement, cloak silhouette, legs, sandals and round base. Image 2 is established finished FRONT MASTER of SAME painted miniature; match exact colors/materials and costume details. Image 3 is finished left profile of same character for additional continuity. Exquisite premium painted collectible miniature: dark olive snakes with individually carved gold-edged scales, same gold laurel diadem, ivory-gray skin, charcoal-plum flowing Grecian drapery with precise antique gold Greek-meander borders, gold chased snake bracers/greaves, brown leather quiver with gold meander rim and feathered arrows, brown diagonal strap, rich gold snake-decorated bow with meander. Sculpt detail and cloth weave at image 2 level. Refine surfaces, no structural redesign or added appendages. Rear view only, no visible human face, preserve model occlusions. Neutral charcoal gray background and soft studio illumination matching image 2. Portrait aspect ratio 1021:1540 like master, same physical scale and pedestal placement: base centered x45%, width70%, top y88%, bottom y96.8%, highest snake y2%, feet y88%. Uniformly reframe source to match master while preserving source anatomy. Full figure and complete round base, orthographic no perspective, no crop, no text or watermark.
```


