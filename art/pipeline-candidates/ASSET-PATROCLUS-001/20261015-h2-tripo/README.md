# Patroclus — H2 source complete, 2026-10-15

Existing task `e0b4d474-e9bd-40d4-b382-7ab52571564d`: H3.1 Private, Ultra 2M triangle, Balanced parts; accepted 1c front/right/back, left slot empty. Generate 60 + 8K/remove-lighting texture 30 + PBR 5 = **95 credits**, observed balance 20505 → 20410. Every paid operation was logged before the next. Pack UV was enabled for both original exports.

Both unmodified GLBs are local ignored sources: **24 mesh parts, 1,967,447 triangles each**. Textured export has one material and three embedded **8192 × 8192** maps. File/spec hashes, bytes and texture measurements are in [completion-checkpoint.json](reports/completion-checkpoint.json); original interim checkpoints remain historical.

Root personally opened [front](preview/ortho_front.png), [right](preview/ortho_right.png), [left](preview/ortho_left.png) and [back](preview/ortho_back.png). Own-right sword, own-left shield, white plume, bronze equipment, linen corslet and blue cape are retained. Right profile exposes the weapon grip; left profile is occluded by the shield.

`register-source` and the four previews exited 0; local processing spent no credits. The register manifest captured its evidence before the completed report existed: its report SHA is the original empty-object placeholder, not the final report SHA. The final report and raw sources are pinned by the completion record and this run's manifest. The mutable global ledger has subsequent CP33 records. No evidence snapshot was silently rewritten.

This is a high-poly source checkpoint. Model art acceptance, LP, bake, rig, animation and Unreal import remain open. The [24-part assembly handoff](../20261015-h2-prep/HANDOFF.md) maps all parts and records actual mixed-material, cape/closure and grip risks; its scale and targets are proposals.
