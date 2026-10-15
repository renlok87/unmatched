# Exact generation prompts

Built-in `image_gen.imagegen`; one call per image.

Image input, craftsmanship only: `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`.

## g1

```text
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate (selected = true in generation-records.json) and copy it byte for byte to
   design/wiglaf-front.png. Run the step 2 command on it once more WITHOUT --out: this final run writes
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
- every identity anchor is visible: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet;
- main colours and the accent of the palette are present; no team colour, no coloured ring or band on the base.
CORE:
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet.
PALETTE: leather #7A5634, moss green #4E6B3A, iron #5E6266, accent boar red #9A3428. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view: previous pedestal showed a top strip -> render both base discs exactly edge-on as horizontal straight bands, with no visible top ellipse.
- both arms clearly apart from the torso: cloak and shield filled the arm gaps -> draw clear charcoal-background gaps at both elbows, pull cloak behind the torso, keep axe right and shield left.
```

No card scans, avatars or commercial game frames were image inputs.
