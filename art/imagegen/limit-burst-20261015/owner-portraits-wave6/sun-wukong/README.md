# Sun Wukong portrait source candidate - CP-32

Status: **source-candidate-only**. Built-in `image_gen.imagegen`: one generation, zero corrections. No runtime import or acceptance; independent review is pending.

Exact roster key: `sun-wukong`, read from `scraped-data/api/heroes/sun-wukong.json` (id 16). No live database query and no avatar image input. Current own concept is **accepted by delegation** for this exact SHA-256: `6844d6986110b9624095e261de2498f355f59c754445dfcda8e556b99a1ae729`; its acceptance card is `art/pipeline-candidates/ASSET-SUN-WUKONG-001/evidence/acceptance-concept/20261013-front-r1/card.json` (pass, 8.8). The older concept README says proposed; the later exact-hash acceptance card is the recorded authority here. This does not approve the new portrait or advance any model stage.

`original-g1.png` and `portrait-source-candidate.png` are byte-identical untouched copies of the built-in original: 1254 x 1254 PNG, SHA-256 `9e12957e25d8a3affbce7165ad775ead53cf4e33fe0e2ecf6e922064dbd0f8e7`. The original Codex path is preserved in `generation-record.json` and remains on disk. No crop, resize, retouch, recolor or recompression was applied to either source copy.

Exact prompt: `prompt-g1.txt`; exact call arguments: `tool-call-g1.json`. `preflight.json` records source/roster/runtime hashes, the actual source acceptance state, CP-32 registration and the focused earlier-wave absence lookup. Runtime currently lists only five existing MVP portrait keys; this key is absent. One unrelated inaccessible concept-elektra temporary directory was reported by the lookup, so this is a focused filename audit rather than an exhaustive visual audit.

The saved candidate and `review/full100-review-sheet.png` were opened with `view_image`. Review derivatives use the complete square at zero zoom, a centered circle whose diameter equals 100% of the side, and native 80 px/40 px tiles. They are diagnostics only.

The golden monkey face, pointed chin fur, swept flame crest, paired spiral gold circlet, red armor and gold dragon shoulders preserve the current own-project design. The crest is taller and the paired spiral relief is interpreted more prominently than in the concept; this is a generated interpretation, not an exact face transfer.

Whole crest, ears, beard and circlet are visible. Crest tip is only about 2 percent below the upper edge, rather than the requested 15 percent; head occupies substantially more than the requested 40 percent image height. Eye line is approximately 42 percent height and horizontally centered. Shoulder armor and chest continue through the square edges.

Centered full100 circle preserves the whole head, ears, crest, circlet and beard. The crest is very close to the top arc. Lower dragon shoulder plates and chest are partly removed by the lower side arcs. This source has little tolerance for zoom, a smaller disc or a thick inward border.

80 px: Golden crest, paired circlet, monkey facial structure, red armor and gold shoulders remain readable. Eyes remain dark light-separated marks; intricate fur and dragon relief merge.

40 px: Golden head silhouette, face light-dark pattern, red armor and circlet color survive; individual irises, fine spiral definition and dragon anatomy do not resolve reliably. A 40 px thumbnail alone does not establish exact identity for an unfamiliar viewer.

Limitations:

- Top breathing room is much smaller than requested; no actual head/headgear clipping was observed.
- Lower shoulder dragons and chest are truncated by the circle.
- Tall generated crest slightly exaggerates the source silhouette.
- Fine eye, fur and armor detail collapses at 40 px.
- No runtime widget, DPI, interaction state or independent review tested.

Source and acceptance/roster/runtime hashes were checked again after generation and remained unchanged. See `self-review.json` for observations, `coordinator-handoff.json` for central integration/review, and `manifest-sha256.json` for package hashes. Only this assigned character folder was written manually. No git mutation, code/registry/ledger/shared-root edits, paid external services or agents. No background process was started.
