# Blackbeard portrait source candidate

CP-29; 2026-10-15. **Candidate only.** Built-in image_gen, one call, no correction. Not imported or accepted for runtime. Independent source review remains with the coordinator/reviewer.

Selected: `portrait-source-candidate.png`; untouched local original: `original-g1.png`. Both are byte-identical copies of the tool output: 1254 x 1254 PNG, SHA-256 `896bc43eb0160ee4e79e39752ecad46aee3b48f32ca6b1129e5ad380915d4ef0`. Original at `C:/Users/ren/.codex/generated_images/01a13e30-ffab-79c2-a1dc-9543b88b3962/exec-f4f30172-e111-4953-a799-2dc7f36ecd4d.png` was left untouched.

Accepted canonical 1a reference: `art/imagegen/concept-blackbeard-codex/design/blackbeard-front.png`; SHA-256 `05d18b22077fb04a8da587d5637bb0917c37d8042ac495aeca282caeed2d3197`. Passing acceptance card, read-only current live PostgreSQL owner row, raw key, focused filename/runtime absence lookup and timestamps are in `preflight.json`. The live Hero schema has cuid/name, not a slug column; raw data supplies `blackbeard`, consistent with hero-links. Runtime registry had five MVP portraits and no `portrait:blackbeard` entry. No commercial avatar or scan was opened.

Exact prompt: `prompt-g1.txt`; exact tool arguments: `tool-call-g1.json`. Provenance, source hashes before/after, dimensions and output hashes: `generation-record.json`.

Self-review: Whole hat corners/crown, scarf ends and beard visible. Outer coat and upper chest terminate at square edges as expected for a bust. Actual upper headroom visually about 4%, less than requested 18%; eye line around 33%, higher than requested 43%. No actual head/headgear clipping; one correction was reserved only for actual clipping or identity failure and was not used.

Circular full100: Centered circle at diameter 100% of square: whole tricorn, face, scarf ends and beard remain inside; lower coat corners, bandolier and pistol hints are partly removed. Crown is close to upper arc, leaving little tolerance for a tighter future crop or border. Keep full100; no zoom.

80 px: Hat, beard, coat and face remain recognizable; braid ties are color accents and individual eyes are small.

40 px: Broad pirate silhouette and facial light/dark read; precise eye color, small brass details and individual braids do not reliably resolve. Not proof of character identity to an unfamiliar viewer.

Identity/craft limits: Stern broad pirate face, strong dark brows, black moustache and braided black beard, scarlet ties, brass-edged tricorn and oxblood coat preserve the accepted project design. Slight facial refinement and larger ornamental hat edging are generated interpretation, not a pixel-identical face. No Seadog substitution. Sculpted hair and braid masses, painted worn cloth/leather and controlled brass read as premium miniature bust art. Skin has fine realistic surface texture; physical resin provenance is not claimed. Plain charcoal with a slight tonal gradient, no scenery, lettering, UI, frame or watermark seen. Not numerically uniform.

Actual diagnostic sheets are under `review/`: centered circle at 100% of original square side, no zoom; 320/160/80/40 px plus 320 grayscale. Only diagnostic derivatives are resampled/masked; source and selection pixels are unchanged. Saved source and sheet were opened with view_image. These checks do not establish runtime readability, DPI behavior or acceptance.

Only this assigned new folder was manually written; no shared/package-root files, git, registry, ledger, code, runtime import, external paid service or subagents. No background processes started.
