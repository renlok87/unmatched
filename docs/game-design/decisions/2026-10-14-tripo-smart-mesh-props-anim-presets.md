# 2026-10-14 — Tripo: Smart Mesh for props, free animation presets as motion reference

**Decision (user, 2026-10-14, verbatim):** «Хорошо, тогда в основном пайплайне оставляем, значит, умную сетку для
ассетов, бэкграунда, типа бочек фонарей. Вот, и бесплатный пресет анимации, как образец движения, а не клипы.»

Basis: the Tripo tools experiment on Beowulf
(`docs/art-pipeline/evidence/skill-check-beowulf-2026-10-14/tripo-tools-experiment/README.md`, 175 credits) and the
orchestrator's summary of what can and cannot enter the pipeline.

## What changes

1. **Props and background assets (branch `prop`: barrel, lantern, crate, decor) — Tripo «Умная сетка» (Smart Mesh)** is
   the default geometry route of stage 2 for a prop: P2.0 (Quad or Triangle, target polygon count, 1/2/4 variants; the
   button showed 100 for 1 and for 4 variants) or P1.0 Fast (triangles 500–20 000, 35). Smart Mesh has no texture and no
   parts in its form: texture and PBR are separate Studio steps on the same task, then the prop goes through the static
   prop build of stage 3 (HANDBOOK §5). Privacy of the Smart Mesh form resets to «Sharing Only» on every load — switch to
   Private before each run. Not verified on a real prop yet: the first prop through this route is its check (frames side
   by side with the multi-view route, as in the experiment).
2. **Heroes are unchanged:** H3.1 «HD модель» multi-view «по частям» → texture 8K «Удалить освещение» → PBR, stage 3 in
   Blender. Smart Mesh for a hero is a new generation, not a retopology of the accepted H2 (welded mesh, sword fused to
   the hand, no parts, ragged UV) — no.
3. **Free Tripo animation presets are a motion reference, never game clips.** Order of motion sources for stage 6
   (extends ДС-6): (1) a library pattern of a hero with the same weapon class; (2) when the library has none (unarmed,
   claws, unusual weapon or gait) — a free Tripo preset (idle, slash, hit, fall, defeat, chop…) watched and read for
   timing and key poses; (3) SYNTX video references only with a reason in `MOTION_SOURCE`. Clips are always authored on
   `UM_HUMANOID_17_v2` by the skill's tools and keep the D-11 lengths and the fixed base; Tripo clips are 3–6× longer, ride
   the base with the feet and live on a 61–65-bone skeleton. A preset needs a Tripo-rigged model (auto-rig 20 credits once,
   or any already rigged model in the account); presets start on a tile click without a price on a button — look before
   clicking. Export a reference with «Animation stay in Place» from the Animate page (the Model page skeleton export is
   broken).

Not adopted: auto-rig, remesh, Smart UV for heroes, Pack UV, animations as clips, Multi-stage Motion, Magic Brush, image
generation. Texture 4K (20) instead of 8K (30) was offered for a test and not chosen: heroes keep 8K.
