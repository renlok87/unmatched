# Exact generation prompts

Built-in `image_gen.imagegen`; one call per image.

Image input, craftsmanship only: `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`.

## g1

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: An original adult female vampire companion with natural human proportions, pale skin, very long near-black hair parted centrally and falling behind her shoulders, an original serene unsettling face with no likeness to any actor. She wears a modest high-neck antique ivory gown with a fitted bodice, narrow three-quarter sleeves and a simple ankle-length skirt, a narrow deep-burgundy waist sash and plain dark ankle boots. A small muted antique-brass sash buckle is the only jewellery. Both hands are empty, fingers naturally relaxed, arms held slightly apart so a charcoal-background gap is visible at both elbows. Keep her hair behind the upper arms so it does not fill the arm gaps. No weapon, no held object, no blood, no gore, no doll, no crown, no veil, no cape and no magical effects.
IDENTITY ANCHORS, each clearly visible: very long dark centrally-parted hair; pale adult face; high-neck ivory gown with narrow sleeves; burgundy sash; empty hands.
PALETTE: gown ivory #DED8CC, sash wine #6D283A, hair near-black #231E25, accent sash buckle brass #9A8464. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. No weapon or held object. Both hands are empty.
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

## g2

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: An original adult female vampire companion with natural human proportions, pale skin, very long near-black hair parted centrally and falling behind her shoulders, an original serene unsettling face with no likeness to any actor. She wears a modest high-neck antique ivory gown with a fitted bodice, narrow three-quarter sleeves and a simple ankle-length skirt, a narrow deep-burgundy waist sash and plain dark ankle boots. A small muted antique-brass sash buckle is the only jewellery. Both hands are empty, fingers naturally relaxed, arms held slightly apart so a charcoal-background gap is visible at both elbows. Keep her hair behind the upper arms so it does not fill the arm gaps. No weapon, no held object, no blood, no gore, no doll, no crown, no veil, no cape and no magical effects.
IDENTITY ANCHORS, each clearly visible: very long dark centrally-parted hair; pale adult face; high-neck ivory gown with narrow sleeves; burgundy sash; empty hands.
PALETTE: gown ivory #DED8CC, sash wine #6D283A, hair near-black #231E25, accent sash buckle brass #9A8464. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. No weapon or held object. Both hands are empty.
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
- strict front orthographic view: g1 showed the pedestal top as an ellipse -> make the two base discs exactly edge-on with straight horizontal top/front edges and no visible top surface behind the feet, retaining the full figure and round base in the frame.
- visible arm gaps: g1 long hair filled the space under both upper arms -> gather the long hair behind the torso, leaving unmistakable charcoal-background gaps between both elbows and the gown; hands stay empty and no hair is cut shorter.
```

No card scans, avatars or commercial game frames were image inputs.
