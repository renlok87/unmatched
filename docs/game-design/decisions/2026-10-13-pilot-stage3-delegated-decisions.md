# 2026-10-13 — stage-3 decisions of the 3d-model-pipeline pilot (taken by delegation)

**Basis.** The user's delegation of 2026-10-06 («Не знаю. Делай сам, меня это не касается. Все решения принимай»,
`2026-10-06-visual-delegated-decisions.md`) and the pilot request of 2026-10-13 («Сгенерировать модели можно все Но
сначала чтобы полностью обкатать скилл и итерационно его улучшить, можно это сделать на небольшой выборке»). The pilot
(Achilles, Angel, Ancient Leshen) exists to find where the skill and its tools break; the decisions below unblock it and
become skill rules after review of the pilot results.

Context: the first stage-3 run of Achilles (`art/pipeline-candidates/ASSET-ACHILLES-001/20261013-h2-bake`) stopped at
`rig` (hard-coded Medusa face part, fixed in `0e6e1bcc`); a scratch run past it showed two more blockers (see-through
single-sheet cloak, TeamAccent area 1.29 %). Full list — `docs/art-pipeline/evidence/skill-pilot-2026-10-13/NOTES.md`.

| № | Decision | Why |
|---|---|---|
| П3-1 | A weapon that Tripo splits into several parts: one part is the `weapon` mesh, the others go into the `body` mesh with weights 100 % on the weapon bone (`weapon.L`/`weapon.R`) | `profile.py` allows one weapon part; the pattern passed all rig probes on Achilles (spear = parts 10 + 13). No tool change |
| П3-2 | A shield (or other held object without its own bone) is weighted 100 % to the forearm/hand of its side; no new bone | a new bone is a stop (SKILL.md §5 п.5); the pattern passed all probes on Achilles |
| П3-3 | Single-sheet cloth (cloak, coat) that shows its back faces in probe poses: first profile means (junction weights at the attachment line, weights that keep the sheet with the torso, caps). If blobs remain above `seams.max_new_blob_px`, the tool gets an **opt-in** profile key that turns the listed cloth parts into a thin closed shell (inner copy offset inward by a fraction of a millimetre, flipped normals, same UV). Default off: Medusa and every existing profile stay byte-identical (test required) | hero materials are one-sided opaque by contract (`tripo_pipeline.py` `material_one_sided_opaque`), so two-sided materials are not an option; Tripo makes cloaks as open sheets, so every caped hero needs this |
| П3-4 | TeamAccent below 5 %: the profile's `area_share_range` is lowered for this hero to the area the rules allow (dyeable classes only: cloth trims, straps, gear leather, feathers; no metal, skin, patterned borders, no main garment colour), as for Arthur (3,56 %, `docs/art-pipeline/material-library/team-accent.md`); readability of the team is carried by the ring (5b-R). The measured share and the zones go into the hero's section of `team-accent.md` | the 5–12 % rule assumes cloth trims; armoured heroes (Achilles 1,29 %: kilt hem + baldric) cannot reach it without dyeing the main colour, which the user's rule «герой остаётся в цветах концепта» forbids |
| П3-4a | When П3-4 lowers a hero's area, the same hero's `render.readability.screen_share_min` (K2 5× front/back, default 0,01) is lowered to the measured share in that profile, recorded in the hero's section of `team-accent.md` | Angel (all-leather costume): accent 0,73 % of area, 0,39 % / 0,03 % of K2 5× pixels front/back; no dyeable zone is left without dyeing the main colour. A selector for a coat lining (inner face of a closed shell) or a band at a distance from a rim would raise it — a tool feature for after the pilot (NOTES F27) |
| П3-4b | A hero whose back is covered by an undyeable main-colour garment (Achilles' red cloak): the K2 5× back share may be 0; `screen_share_min` is set to 0 in that hero's profile, and the front share is recorded. The «dress unchanged outside the accent» share measured on fewer than 500 visible pixels is lowered to the measured floor (Achilles' kilt: 86 % of 225 px vs 90 %) | the cloak is the concept's main colour (never dyed); a 225-pixel sample makes a 90 % threshold noise. Both numbers go into the hero's section of `team-accent.md` |
| П3-5 | Missing stage-3 card fields (`CHARACTER`, `FIGURE_HEIGHT_M`, UE names, `FIGHTER_NAME`, `CLIP_PREFIX`) take defaults: `CHARACTER` = PascalCase of the content key, height 0,55 m (as Medusa/Arthur) unless the concept proportions say otherwise; written into `asset-card.yaml` with `decided_by: delegated` | the stage-0 batch did not write them; the skill will require them at stage 0 |

Status: in force for the pilot; each becomes a skill rule (or is reverted) when the pilot closes.
