# ASSET-MARTIAN-INVADER-001 concept 1a fix1 - Codex task (design front)

Written by Claude from art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/asset-card.yaml by the 3d-model-pipeline skill (references/concept-sheet.md).
The task to execute is the text in the section **Task**. The header is provenance only.

| field | value |
|---|---|
| id | ASSET-MARTIAN-INVADER-001-concept (stage 1a) |
| date | 2026-10-13 |
| template | concept-sheet.md 1a (ledger template id T-CODEX-HEROVIEWS) |
| package | `art/imagegen/concept-martian-invader-codex/` |
| asset card | `art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/asset-card.yaml`, sha256 38256439e7ac77af4d7701f2e9d5de168ae18f4dd0c39692690d6f0e87dbb7fe |
| image generations allowed in this run | 2 |

## Corrective run provenance

Base task: `docs/game-design/visual/06-tasks/prompts/ASSET-MARTIAN-INVADER-001-concept.codex.md`. Re-generate only `design-front` for acceptance cycle r2.
Final prior decision: `art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/evidence/acceptance-concept/20261013-front-r1/final.json`.
CORRECTION sources: `art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/evidence/acceptance-concept/20261013-front-r1/card-2.json` (S, Q, P) and `art/pipeline-candidates/ASSET-MARTIAN-INVADER-001/evidence/acceptance-concept/20261013-front-r1/card.json` (empty rework_fix_list).
GENERATIONS_ALLOWED = 2 = min(2, 4 - 2); 2 design-front entries already exist.
User delegation (2026-10-13, verbatim): «начинай делать все остальные параллельно согласно скиллу».
This bounded task covers corrective stage 1a only; no other pipeline stages.

## Inputs

| # | path | what | sha256 |
|---|---|---|---|
| 1 | `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` | craftsmanship reference (image 1, the only image input) | e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9 |
| 2 | `art/imagegen/concept-martian-invader-codex/palette.json` | palette of the asset card (not an image input) | f64b7fa9f52a99cef3fa6756c6f90bd798c5636f3c86f9ef806d7aca36644640 |

## Task

```text
Task ASSET-MARTIAN-INVADER-001 concept 1a - one front design of a new collectible miniature (stage 1a of the 3D model pipeline).
Package contract.
- Write ONLY inside art/imagegen/concept-martian-invader-codex/. Nothing else on disk changes. Files there that you
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
  package: copy each result byte for byte into concepts/martian-invader-<view>-g<N>.png at once, leave the tool's copy
  where it is, and log both paths. Never overwrite a file in concepts/.
- Check every candidate into its own folder: check_concept_views.py ... --out
  art/imagegen/concept-martian-invader-codex/checks/<view>-g<N> (the same <view>-g<N> as its concepts/ file). Only
  the final run on the selected file(s) writes the report without --out.
- Log every generation in generation-records.json: id, card_id (ASSET-MARTIAN-INVADER-001), stage (1a or 1c), view, side_view,
  attempt, tool, mode, references [{path, sha256}] in call order, prompt_key, correction (null or its lines),
  original_path, saved_path, sha256, width, height, date, selected.
- Every path you write into a record (references, saved_path, checks) is relative to the repository root with
  forward slashes (art/imagegen/concept-martian-invader-codex/concepts/...), except original_path, which is the
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
Corrective-run rules: continue generation numbering from the existing records (next attempt g3);
use at most 2 new image generations and never exceed four design-front generations in stage 1a.
Keep all earlier concepts, candidate reports, prompt texts and generation records. Append new history;
update selected flags and final package metadata to the best new candidate. Do not modify CORE.
The REQUIRED CORRECTION applies to the first corrective generation and any permitted retry.
A checklist failure on retry may refine CORRECTION within three lines; retain applicable acceptance fixes.
Do not use browsers or invoke other agents. No git commands.
Steps.
1. Generation <N>: call image_gen once with referenced_image_paths = [input 1] and the CORE below exactly as written
   (plus the REQUIRED CORRECTION block after CORE on EVERY generation in this corrective run). Copy the result to
   concepts/martian-invader-design-front-g<N>.png (view design-front, prompt_key 1a/design-front/g<N>).
2. Copy that candidate byte for byte to design/martian-invader-front.png and check it into its own folder:
   python tools/art/concept/check_concept_views.py --set art/imagegen/concept-martian-invader-codex/design --key martian-invader --views front --role hero --min-top-pct 4 --out art/imagegen/concept-martian-invader-codex/checks/design-front-g<N>
   Exit 0 = no FAIL (WARN, including view.frame_top, is allowed). Exit 1 = a FAIL check. Exit 2 = input or tool error,
   NOT a FAIL: do not generate again; write the error text into verification.json and stop. Then check the CHECKLIST
   with your eyes.
3. Only if the script exits 1 or a CHECKLIST item fails, and generations remain in this run: generate again with the
   CORE followed by exactly this block, at most 3 lines, each line naming the failed check id or CHECKLIST item, only
   what to fix, never against the CORE:
   CORRECTION (fix only this; everything above still applies):
   - <failed check id or CHECKLIST item>: <what is wrong> -> <how it must be>
   The CORE text never changes. WARN results and thin parts that are too thin are not a reason to retry.
4. Select the best candidate (selected = true in generation-records.json) and copy it byte for byte to
   design/martian-invader-front.png. Run the step 2 command on it once more WITHOUT --out: this final run writes
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
- every identity anchor is visible: ray gun in the RIGHT hand; glass dome helmet; big exposed brain; silver space suit with fins;
- main colours and the accent of the palette are present; no team colour, no coloured ring or band on the base.
CORE:
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Martian Invader, a pulp-era villain (Unmatched: Tales to Amaze): big-brained alien with a large exposed head inside a glass dome helmet, slim body in a silver space suit with fins, ray gun in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: ray gun in the RIGHT hand; glass dome helmet; big exposed brain; silver space suit with fins.
PALETTE: suit silver #B8BEC4, skin green #7AA65A, fin red #B3202A, accent ray cyan #4AD9E0. These are the main colours plus one accent; no other strong colours.
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
- martian-invader-front.png / S: the right elbow is strongly bent and the gun is raised near the head -> Neutral standing rest pose: lower the ray-gun arm so the right elbow is only slightly bent and the ray gun is held at hip height pointing forward-down beside the body with a clear gap to the torso; keep the left arm slightly away from the body.
- martian-invader-front.png / Q: large suit panels have less surface detail than the craftsmanship reference -> Raise surface detail on the plain suit zones to the Medusa reference level: add sculpted panel trims, rivet rows, ribbed seams and engraved retro-sci-fi ornament on the sleeves, thighs, shins and boots, painted like a collectible miniature.
- martian-invader-front.png / P: fins are dark brick-red and skin is olive-yellow instead of the asset palette -> Paint all fins in fin red #B3202A (brighter crimson, not dark brick) and the head and hands in skin green #7AA65A (less olive-yellow), keeping suit silver #B8BEC4 and ray cyan #4AD9E0 unchanged.
Return: at most 10 lines: the selected generation, generations used, the final script exit code, what failed.
```
