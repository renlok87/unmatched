# merlin: imagegen prompts

Дата: 2026-09-29. Инструмент: встроенный image_gen.imagegen. transparent_background: false. Один вызов на изображение. После генерации PNG скопированы без редактирования пикселей.

## Проверка и ограничения

Сохранены направление ракурсов, основные цвета, посох, поза рук и общий силуэт. Изменены контуры капюшона, бороды, кристалла, посоха и складок; более детальная кисть не является точной копией геометрии. На боковом виде подставка уже, на заднем фигура/подставка немного выше; масштаб и положение не совпадают точно. Звёзды на спине — дорисованная деталь, не подтверждённая исходной моделью.

## front

Файл: merlin-front.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-MERLIN-001/20260928-blender-um-fbx-v1/preview/ortho_front.png`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 EDIT TARGET: paint directly over the low-poly Merlin FRONT orthographic render. Image 2 is ONLY the craftsmanship reference, highly detailed painted Medusa miniature. Keep every structural feature of image 1: elderly hooded wizard with tied white beard, blue robes, right hand holding crooked wooden staff on viewer LEFT crowned by blue crystal, left hand at belt, existing feet stance, round base, exact silhouette, proportions, pose and staff shape. Refine only surface detail to reference level: weathered wise face and finely sculpted hands, individual white beard strands with same brown tie, midnight-blue woven hood and robe, antique gold embroidered rune-like nonverbal motifs and stars along existing two vertical stoles, cuffs, hood border and hem, fine drapery staying inside existing folds; worn brown leather belt and shoes. Gnarled dark wooden staff with delicate engraved ornamental marks and a faceted sapphire-blue crystal, retain crystal size and silhouette, no magical effects. Ultra-detailed premium painted miniature, subtle brush highlights, cloth weave, wood grain, patinated metal trim. Single front orthographic view, no perspective, full body and whole round dark pedestal. Neutral dark charcoal gray background, studio illumination like image 2. Aspect ratio 9:10, keep exact target normalized framing: base x26.2%-73.8%, y85.8%-94.5%, crystal tip y5.8%, hood top y14.4%. No text, labels, watermark, extra accessories or cropping.
```

## side

Файл: merlin-side.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-MERLIN-001/20260928-blender-um-fbx-v1/preview/ortho_right.png`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/merlin/merlin-front.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 EDIT TARGET is the low-poly Merlin RIGHT SIDE orthographic view facing right. Paint directly over it, preserve body silhouette, hood contour, hunched elderly proportions, robe contour and major folds, hands pose, staff shape and position, crystal outline, feet and base. Image 2 defines the same character's finished FRONT design: match its midnight blue woven cloth, gold stars and ornamental rune-like embroidery on hood border, cuffs, vertical stoles and hem, brown belt and shoes, white tied beard, engraved gnarled brown staff and sapphire blue crystal. Extremely refined painted collectible miniature at image 2 detail level, realistic sculpted wrinkles, fingers, individual beard hairs, embroidered threads, wood grain and subtle metal patina. No new accessories or protrusions. Single strict right profile, not three-quarter; orthographic no perspective. Dark charcoal background and studio lighting same as image 2. Output aspect ratio 9:10, same character scale and base position as image 2: base spans x25.2%-73.8%, y84%-93.5%, staff crystal top y4.2%, hood top y12.3%. Uniformly reframe image 1 to these coordinates; retain its anatomy. Full body whole round base, no crop, no text, no watermark.
```

## back

Файл: merlin-back.png.

referenced_image_paths (порядок изображений):

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-MERLIN-001/20260928-blender-um-fbx-v1/preview/ortho_back.png`
2. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/merlin/merlin-front.png`

Точный отправленный prompt:

```text
Use case: style-transfer. Image 1 EDIT TARGET is low-poly Merlin BACK orthographic render. Paint directly over its geometry; preserve silhouette, hood shape, proportions, pose, robe contour, belt height, feet, staff on viewer RIGHT and blue crystal geometry. Image 2 defines this SAME miniature's finished front: match blue woven robe, antique gold star/rune-like ornamental embroidery at hood border, cuffs and hem, brown belt/shoes, engraved crooked wooden staff and sapphire crystal, dark round base. Back robe remains blue with subtle stitched stars, no huge new emblem or accessories; intricate cloth texture and fine drapery within the original volumes, realistic wood grain and painted highlights. Highest-detail painted collectible miniature. Single exact rear orthographic view, no face, no perspective, no three-quarter view, full body and whole round base. Neutral dark charcoal background and lighting same as image 2. Output aspect ratio 9:10, same physical scale and pedestal position as image 2: base x25.2%-73.8%, top y84%, bottom y93.5%; crystal tip y4.2%, hood y12.3%. Only uniform reframing of target, no structural redesign. No text, watermark or crop.
```


