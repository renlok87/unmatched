# ASSET-SHERLOCK-HOLMES-001 concept 1c - Codex task (views over the draft orthos)

Written by Claude from art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/asset-card.yaml and the step-1b orthos (template concept-sheet.md §8.1;
tools/art/pipeline_batch/make_1c.py). The task to execute is the text in the section **Task**. The header is
provenance only.

| field | value |
|---|---|
| id | ASSET-SHERLOCK-HOLMES-001-concept-views (stage 1c) |
| date | 2026-10-15 |
| template | concept-sheet.md 1c (ledger template id T-CODEX-HEROVIEWS) |
| package | `art/imagegen/concept-sherlock-holmes-codex/` |
| asset card | `art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/asset-card.yaml`, sha256 9aa196c86f032178daf80b21fe93b6766495cca27b5a5ce1bb61b6064d7c75ca |
| image generations allowed in this run | front 2, side 2, back 2 |

## Inputs

| # | path | what | sha256 |
|---|---|---|---|
| 1 | `art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_front.png` | draft render FRONT (image 1 of the front view) | ed6053edbd78ec3d0032cee459f0045749c9a907aeb74d3ce32baa11aaa07b4a |
| 2 | `art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_left.png` | draft render LEFT SIDE (image 1 of the side view) | 7d5cc0b4da94a7ae08ab246f83b0b82725e2ea2fb284e85f04607b92226c1773 |
| 3 | `art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_back.png` | draft render BACK (image 1 of the back view) | fd3e8d3f29f6fdd02595c07f659a434e52e125e1bbd1e3270b255d3e7231feaf |
| 4 | `art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho-framing.json` | framing numbers of the draft renders (not an image input) | 8e5c98b1699824c29228384f2ac7f5945f76e0bdeaf44b87c6f61160bca2cf6e |
| 5 | `art/imagegen/concept-sherlock-holmes-codex/design/sherlock-holmes-front.png` | approved design front (image 2 of every view) | face103a3f693a31f0121c1cf0c09dd053dc0ce50c7a7be9e0aa08e3ac2f8a0a |
| 6 | `art/imagegen/concept-sherlock-holmes-codex/palette.json` | palette of the asset card (not an image input) | ec132ae6e4521307568fb325f9a0ef58f38ed30b8a7533c2ea35c39f31e09078 |

## Task

```text
Task ASSET-SHERLOCK-HOLMES-001 concept 1c - front,side,back views painted over the draft orthographic renders.
Package contract.
- Write ONLY inside art/imagegen/concept-sherlock-holmes-codex/. Nothing else on disk changes. Files there that you
  did not create (palette.json, earlier runs) stay as they are unless this task says otherwise.
- The records of an earlier run in this package (for example stage 1a before 1c) are history: append, never drop.
  README.md and prompts.md: add a section for this run on top and keep the earlier sections below unchanged;
  generation-records.json and prompts/concept-prompts.json: add entries, keep the earlier ones as they are;
  verification.json: the fields of this run at the top level, the whole earlier object kept in previous_runs [...];
  source-hashes-before.json: a new block. manifest-sha256.json is rewritten last.
- No git commands at all (no add, commit, stash, reset, checkout, branch). Claude reviews and commits.
- Do not open, edit or build anything under unreal/. No Unreal, no Tripo, no SYNTX, no downloads.
- Inputs are only the files listed in this task. Card scans, hero avatars, card art and frames of commercial digital
  editions are never inputs.
- Do not load or read skills: no npx openskills read, no SKILL.md files (the AGENTS.md skill table, superpowers, the
  imagegen skill). This task is complete as written; use the built-in image_gen tool directly.
- Before work, record sha256 of every input in source-hashes-before.json (a corrective run appends a new block and
  keeps the old one); after work, prove in verification.json that the inputs are unchanged.
- One image_gen call = one image = one view. Do not pass a size: the tool chooses the pixels; ask for the aspect ratio
  in the prompt text only.
- Never retouch, resize, crop, recolour or re-encode a generated image. image_gen saves its own copy outside the
  package: copy each result byte for byte into concepts/sherlock-holmes-<view>-g<N>.png at once, leave the tool's copy
  where it is, and log both paths. Never overwrite a file in concepts/.
- Check every candidate into its own folder: check_concept_views.py ... --out
  art/imagegen/concept-sherlock-holmes-codex/checks/<view>-g<N> (the same <view>-g<N> as its concepts/ file). Only
  the final run on the selected file(s) writes the report without --out.
- Log every generation in generation-records.json: id, card_id (ASSET-SHERLOCK-HOLMES-001), stage (1a or 1c), view, side_view,
  attempt, tool, mode, references [{path, sha256}] in call order, prompt_key, correction (null or its lines),
  original_path, saved_path, sha256, width, height, date, selected.
- Every path you write into a record (references, saved_path, checks) is relative to the repository root with
  forward slashes (art/imagegen/concept-sherlock-holmes-codex/concepts/...), except original_path, which is the
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
   front: [art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_front.png, art/imagegen/concept-sherlock-holmes-codex/design/sherlock-holmes-front.png]
   side:  [art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_left.png, art/imagegen/concept-sherlock-holmes-codex/design/sherlock-holmes-front.png]
   back:  [art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_back.png, art/imagegen/concept-sherlock-holmes-codex/design/sherlock-holmes-front.png, art/imagegen/concept-sherlock-holmes-codex/sherlock-holmes-side.png]  (a prop without a side view: no third image)
   Copy the result to concepts/sherlock-holmes-<view>-g<N>.png (prompt_key 1c/<view>/g<N>) and byte for byte to
   art/imagegen/concept-sherlock-holmes-codex/sherlock-holmes-<view>.png.
2. Check the candidate into its own folder:
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-sherlock-holmes-codex --key sherlock-holmes --views <view> --role hero --out art/imagegen/concept-sherlock-holmes-codex/checks/<view>-g<N>
   Exit 0 = no FAIL, 1 = a FAIL check, 2 = input or tool error, NOT a FAIL: on 2 do not generate again; write the
   error text into verification.json and stop. Then check the CHECKLIST of the view with your eyes.
3. Only if the script exits 1 or a CHECKLIST item fails for the view, and generations of the view remain in this run:
   generate the view again with its CORE followed by exactly this block, at most 3 lines, each line naming the
   failed check id or CHECKLIST item, only what to fix, never against the CORE:
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate of the view (selected = true) and copy it byte for byte to art/imagegen/concept-sherlock-holmes-codex/sherlock-holmes-<view>.png
   before the next view starts (the back view uses the selected side view as image 3).
5. If the generations of the view in this run are used up and a CHECKLIST item still fails, keep the best candidate,
   record the view and the failed items in verification.json limit_reached and in README.md, and go on: the acceptor
   decides. This is not a blocker.
After all views, one final run WITHOUT --out on the selected files (it writes art/imagegen/concept-sherlock-holmes-codex/checks-report.json and the sheet):
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-sherlock-holmes-codex --key sherlock-holmes --views front,side,back --role hero --palette art/imagegen/concept-sherlock-holmes-codex/palette.json --sheet
   Exit 1 here (a set check such as set.height or set.base_center) with generations left: regenerate the view the
   failed check points to, as in step 3, then repeat this final run. Exit 2: as in step 2.
Then write prompts.md, prompts/concept-prompts.json, README.md, verification.json, manifest-sha256.json last.
CHECKLIST (per view, passed/failed with a note in verification.json):
- the view is exactly the one asked for: front, a strict profile of the left side, or a strict back view;
  camera exactly level; no three-quarter, no perspective, no collage, no text or watermark;
- silhouette, pose, arm and weapon positions follow image 1 (the draft render); no added anatomy, no new weapon;
- identity, costume, colours and materials follow the approved design; every anchor visible from this side is there;
- weapon side: front and side - The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view; back - The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT;
- framing as in image 1: the same pedestal position and size; the same highest point; the whole subject visible;
- the same plain flat dark gray background in every view.
Framing and background are measured by check_concept_views.py (view.top_margin, view.side_margin, view.bottom_margin,
view.border_uniform, view.bg_neutral, view.bg_dark; in the final run also set.base_bottom, set.base_center,
set.height, set.bg_same): PASS or WARN there means these CHECKLIST items pass. By eye fail them only for a gross
defect the script cannot measure (a cropped part, a visible floor, gradient or vignette, a camera that is visibly not
level). A difference of a few pixels, a few tenths of a percent or a few RGB levels is never a reason to regenerate.
CORE-FRONT:
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x21.0%-79.0%, pedestal top y85.5%, pedestal bottom y94.0%, highest point
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
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x21.0%-79.0%, pedestal top y85.5%, pedestal bottom y94.0%, highest point
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
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x21.0%-79.0%, pedestal top y85.5%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
Return: at most 10 lines: selected generation per view, generations used per view, the final script exit code, what
failed.
```
