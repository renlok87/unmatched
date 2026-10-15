# Tomoe Gozen portrait source candidate - CP-32

Status: **source-candidate-only**. Built-in `image_gen.imagegen`: one generation, zero corrections. No runtime import or acceptance; independent review is pending.

Exact roster key: `tomoe-gozen`, read from `scraped-data/api/heroes/tomoe-gozen.json` (id 37). No live database query and no avatar image input. Current own concept is **accepted by delegation** for this exact SHA-256: `dffd47153ec5f6f8196467b868b5f432d736a64ac9d69e20be02c50113eb1c16`; its acceptance card is `art/pipeline-candidates/ASSET-TOMOE-GOZEN-001/evidence/acceptance-concept/20261013-front-r1/card.json` (pass, 8.8). The older concept README says proposed; the later exact-hash acceptance card is the recorded authority here. This does not approve the new portrait or advance any model stage.

`original-g1.png` and `portrait-source-candidate.png` are byte-identical untouched copies of the built-in original: 1254 x 1254 PNG, SHA-256 `35e560ea8a47e452eb75d5ce917d19d5e0d2d5adbabbade21152dceada55cce5`. The original Codex path is preserved in `generation-record.json` and remains on disk. No crop, resize, retouch, recolor or recompression was applied to either source copy.

Exact prompt: `prompt-g1.txt`; exact call arguments: `tool-call-g1.json`. `preflight.json` records source/roster/runtime hashes, the actual source acceptance state, CP-32 registration and the focused earlier-wave absence lookup. Runtime currently lists only five existing MVP portrait keys; this key is absent. One unrelated inaccessible concept-elektra temporary directory was reported by the lookup, so this is a focused filename audit rather than an exhaustive visual audit.

The saved candidate and `review/full100-review-sheet.png` were opened with `view_image`. Review derivatives use the complete square at zero zoom, a centered circle whose diameter equals 100% of the side, and native 80 px/40 px tiles. They are diagnostics only.

White headband with two ties to viewer right, high black ponytail, dark eyes, red lacquered o-yoroi, navy cords and gold fastening medallions preserve the current own-project design. The face and tie arrangement are generated interpretations, not a pixel-identical face transfer; no actor likeness was requested or used.

Whole head, high ponytail crown, ears, white headband and both cloth tie ends visible. Highest hair is about 6 percent below the upper edge rather than the requested 15 percent; head is larger than the requested 38 percent height. Eye midpoint is around x45 percent, y39 percent, slightly left and higher than requested. Long hair and shoulders continue below the frame.

Centered full100 circle preserves the whole head, ponytail crown, white headband and both tie ends. Lower outer shoulder armor and descending hair/chest are removed by the bottom side arcs. White ties on viewer right reduce tolerance for a tighter off-center crop.

80 px: White headband and ties, black ponytail, dark eyes, red-and-blue armor and gold fastenings remain readable. Fine facial and cord detail is reduced.

40 px: White headband/ties, black hair mass, face and red armor distinguish the broad silhouette; exact facial identity, irises, medallion design and lacing detail do not resolve reliably.

Limitations:

- Top breathing room and face size do not meet the requested generous numeric framing targets, though no actual head/headgear clipping was observed.
- Face is slightly left of center; do not assume a tighter crop will preserve both ties.
- Lower shoulder armor, chest and descending hair are removed by the circle.
- Fine facial, eye and lacing detail collapses at 40 px.
- tomoe-gozen is absent from hero-links.json; exact key is verified against its actual raw roster and own asset-card, not added here.
- No runtime widget, DPI, interaction state or independent review tested.

Source and acceptance/roster/runtime hashes were checked again after generation and remained unchanged. See `self-review.json` for observations, `coordinator-handoff.json` for central integration/review, and `manifest-sha256.json` for package hashes. Only this assigned character folder was written manually. No git mutation, code/registry/ledger/shared-root edits, paid external services or agents. No background process was started.
