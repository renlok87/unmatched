# ASSET-BEOWULF-001 concept 1c - Codex task (views over the draft orthos)

Written by Claude from art/pipeline-candidates/ASSET-BEOWULF-001/asset-card.yaml and the step-1b orthos by the 3d-model-pipeline skill
(references/concept-sheet.md §8; tools/art/pipeline_batch/make_1c.py). The task to execute is the text in the section
**Task**. The header is provenance only.

| field | value |
|---|---|
| id | ASSET-BEOWULF-001-concept-views (stage 1c) |
| date | 2026-10-14 |
| template | concept-sheet.md 1c (ledger template id T-CODEX-HEROVIEWS) |
| package | `art/imagegen/concept-beowulf-codex/` |
| asset card | `art/pipeline-candidates/ASSET-BEOWULF-001/asset-card.yaml`, sha256 4228ce596ed51c553262cd9a1849590a97e068795cda372716ed8018abee887a |
| image generations allowed in this run | front 2, side 2, back 2 |

## Inputs

| # | path | what | sha256 |
|---|---|---|---|
| 1 | `art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_front.png` | draft render FRONT (image 1 of the front view) | 525a792fe14196cb648d1518388c21fec28cfb16dec6ab810c514ed0bd5a4a8c |
| 2 | `art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_left.png` | draft render LEFT SIDE (image 1 of the side view) | 0204a225e3059d6a3870424cd379f8112b9b1d3d4c3ee9e85aea665fc50a5b7a |
| 3 | `art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_back.png` | draft render BACK (image 1 of the back view) | 365724996038892909d0d7eb027c8e9fcf4f2b186eb5bf2755c5c2dbc3a7ff8b |
| 4 | `art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho-framing.json` | framing numbers of the draft renders (not an image input) | b54950d756d300ae7087bea766ed81becf00949a934567f0ddc66bf62da673b8 |
| 5 | `art/imagegen/concept-beowulf-codex/design/beowulf-front.png` | approved design front (image 2 of every view) | 9fca88027c1287d84a83ecefa869a8d963fa61e393d40edcbb8f2a6dd37a3195 |
| 6 | `art/imagegen/concept-beowulf-codex/palette.json` | palette of the asset card (not an image input) | e7d64b412d64c430115e1c6dc313fd12f8046a6a36b9c5156e8afcb73a57cfde |

## Task

```text
Task ASSET-BEOWULF-001 concept 1c - front,side,back views painted over the draft orthographic renders.
Package contract.
- Write ONLY inside art/imagegen/concept-beowulf-codex/. Nothing else on disk changes. Files there that you
  did not create (palette.json, earlier runs) stay as they are unless this task says otherwise.
- No git commands at all (no add, commit, stash, reset, checkout, branch). Claude reviews and commits.
- Do not open, edit or build anything under unreal/. No Unreal, no Tripo, no SYNTX, no downloads.
- Inputs are only the files listed in this task. Card scans, hero avatars, card art and frames of commercial digital
  editions are never inputs.
- Before work, record sha256 of every input in source-hashes-before.json (a corrective run appends a new block and
  keeps the old one); after work, prove in verification.json that the inputs are unchanged.
- One image_gen call = one image = one view. Do not pass a size: the tool chooses the pixels; ask for the aspect ratio
  in the prompt text only.
- Never retouch, resize, crop, recolour or re-encode a generated image. image_gen saves its own copy outside the
  package: copy each result byte for byte into concepts/beowulf-<view>-g<N>.png at once, leave the tool's copy
  where it is, and log both paths. Never overwrite a file in concepts/.
- Check every candidate into its own folder: check_concept_views.py ... --out
  art/imagegen/concept-beowulf-codex/checks/<view>-g<N> (the same <view>-g<N> as its concepts/ file). Only
  the final run on the selected file(s) writes the report without --out.
- Log every generation in generation-records.json: id, card_id (ASSET-BEOWULF-001), stage (1a or 1c), view, side_view,
  attempt, tool, mode, references [{path, sha256}] in call order, prompt_key, correction (null or its lines),
  original_path, saved_path, sha256, width, height, date, selected.
- Every path you write into a record (references, saved_path, checks) is relative to the repository root with
  forward slashes (art/imagegen/concept-beowulf-codex/concepts/...), except original_path, which is the
  absolute path where image_gen saved its own copy.
- Save the exact prompt of every generation in prompts/concept-prompts.json (prompt_key "<stage>/<view>/g<N>" -> text)
  and in prompts.md: date, tool, then per file the referenced_image_paths in order, the exact prompt, and a closing
  section "Проверка и ограничения" (what matches between views, what changed).
- README.md in Russian: what was done, which generation is selected per view and why, what failed, status
  "предложено". A limit you could not meet goes into verification.json, not hidden.
- verification.json: source_unchanged, outside_folder (must be []), checks [{view, generation, exit_code,
  report}] for every run of check_concept_views.py, checklist [{view, item, passed, note}] for the selected file of
  each view, generations per view, limit_reached [{view, failed_items}] (empty list when no view ran out of
  generations with a failed CHECKLIST item).
- Encoding: write every text file of the package (JSON, Markdown) from Python as UTF-8 without BOM
  (Path.write_text(text, encoding="utf-8"); json.dumps(data, ensure_ascii=False, indent=2)). Never write a package
  file through PowerShell redirection (>, Out-File, Set-Content) or pipe Cyrillic text through the shell: it turns
  into "????".
- Write manifest-sha256.json last: sha256 and bytes of every package file except itself.
- Small decisions are yours; write them in README.md. Stop only on blockers (login, captcha, payment, image_gen
  unavailable).
Run every command from the repository root. PowerShell: set $env:PYTHONIOENCODING='utf-8' first; bash: export
PYTHONIOENCODING=utf-8.
Order: front,side,back, one view after the other. Per view: at most 2 generations in this run and never more than 4 for the
view in the whole of generation-records.json.
Per view <view>:
1. Call image_gen once with the CORE of that view (plus a CORRECTION block only on a retry, step 3) and its
   references in this order:
   front: [art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_front.png, art/imagegen/concept-beowulf-codex/design/beowulf-front.png]
   side:  [art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_left.png, art/imagegen/concept-beowulf-codex/design/beowulf-front.png]
   back:  [art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_back.png, art/imagegen/concept-beowulf-codex/design/beowulf-front.png, art/imagegen/concept-beowulf-codex/beowulf-side.png]  (a prop without a side view: no third image)
   Copy the result to concepts/beowulf-<view>-g<N>.png (prompt_key 1c/<view>/g<N>) and byte for byte to
   art/imagegen/concept-beowulf-codex/beowulf-<view>.png.
2. Check the candidate into its own folder:
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-beowulf-codex --key beowulf --views <view> --role hero --out art/imagegen/concept-beowulf-codex/checks/<view>-g<N>
   Exit 0 = no FAIL, 1 = a FAIL check, 2 = input or tool error, NOT a FAIL: on 2 do not generate again; write the
   error text into verification.json and stop. Then check the CHECKLIST of the view with your eyes.
3. Only if the script exits 1 or a CHECKLIST item fails for the view, and generations of the view remain in this run:
   generate the view again with its CORE followed by exactly this block, at most 3 lines, each line naming the
   failed check id or CHECKLIST item, only what to fix, never against the CORE:
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate of the view (selected = true) and copy it byte for byte to art/imagegen/concept-beowulf-codex/beowulf-<view>.png
   before the next view starts (the back view uses the selected side view as image 3).
5. If the generations of the view in this run are used up and a CHECKLIST item still fails, keep the best candidate,
   record the view and the failed items in verification.json limit_reached and in README.md, and go on: the acceptor
   decides. This is not a blocker.
After all views, one final run WITHOUT --out on the selected files (it writes art/imagegen/concept-beowulf-codex/checks-report.json and the sheet):
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-beowulf-codex --key beowulf --views front,side,back --role hero --palette art/imagegen/concept-beowulf-codex/palette.json --sheet
   Exit 1 here (a set check such as set.height or set.base_center) with generations left: regenerate the view the
   failed check points to, as in step 3, then repeat this final run. Exit 2: as in step 2.
Then write prompts.md, prompts/concept-prompts.json, README.md, verification.json, manifest-sha256.json last.
CHECKLIST (per view, passed/failed with a note in verification.json):
- the view is exactly the one asked for: front, a strict profile of the left side, or a strict back view;
  camera exactly level; no three-quarter, no perspective, no collage, no text or watermark;
- silhouette, pose, arm and weapon positions follow image 1 (the draft render); no added anatomy, no new weapon;
- identity, costume, colours and materials follow the approved design; every anchor visible from this side is there;
- weapon side: front and side - The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.; back - The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.;
- framing as in image 1: the same pedestal position and size; the same highest point; the whole subject visible;
- the same plain flat dark gray background in every view.
CORE-FRONT:
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.6%-82.4%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORE-SIDE:
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.9%-82.1%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORE-BACK:
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.6%-82.4%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
Return: at most 10 lines: selected generation per view, generations used per view, the final script exit code, what
failed.
```
