# AN-154 — Actor / Shakespeare

Status: **proposed/source-only**. One original adult humanoid FRONT DESIGN REFERENCE, representing one of Shakespeare's three confirmed Actor support pieces. Three distinct live-avatar variations were not produced. This is not stage0 registration, formal acceptance, or a game-ready asset.

Selected source: [design-front.png](design-front.png), an unchanged byte-for-byte copy of [attempt-01.png](attempt-01.png), 1024 × 1536. Built-in `image_gen.imagegen` only: one generation and one framing correction. Both tool originals remain intact in the tool output directory and both attempts are preserved here without crop, resize, retouch or re-encoding.

The design is a clean-shaven adult auburn-haired theatre player in a muted amber doublet, burgundy hose and cap, small cream ruff and soft shoes. The plain cream half-mask is in his own LEFT hand (viewer right); his RIGHT hand is empty. The owner and Medusa references were opened with `view_image` before generation for cohort/material/quality guidance. The owner identity and elaborate dark costume were not copied wholesale. No commercial actor portrait, scan, franchise key art or outside generation source was used.

## Actual failures and selection

- Attempt 01: cap begins around y=34, approximately 2.2% top margin instead of 6%; pedestal bottom around y=1397, approximately 91.0% instead of 90%.
- Attempt 02: the permitted correction moves the cap to around y=111 (7.2%) but moves the pedestal bottom to around y=1244 (81.0%). It also slightly rerenders the face/costume rather than applying an exact reframing.
- Attempt 01 is selected because it keeps more readable facial and cloth detail and the pedestal is closer to the requested bottom position. **Neither attempt meets exact framing.** No further generation was made after the one allowed correction.

The self-review finds a front-facing whole figure with visible hands and limb gaps, correct prop handedness, two horizontal stone base bands, and no visible upper pedestal surface, VFX, scenery, text or UI. Finger overlaps mean the anatomy of every individual digit is not certified. A single front raster also cannot prove camera mathematics or round pedestal depth. Root coordinates independent review; these observations are not formal acceptance.

## Evidence and records

`owner-evidence.json` confirms Shakespeare owns three Actor pieces, each health 1, movement 2, melee. The local flattened raw owner data was independently decoded and the three rows matched. Owner-reference and raw hashes match the evidence; all input files remained unchanged. Raw `shakespeare` maps explicitly to owner reference key `william-shakespeare`. Existing-source absence is supported by the supplied root audit and a focused worker path search; that search reported an unrelated inaccessible Elektra temporary directory, so it is not an exhaustive repository claim.

- [input-verification.json](input-verification.json): owner/raw/evidence/quality hashes, reference dimensions, decoded rows, and source-search limits.
- [prompt-attempt-01.txt](prompt-attempt-01.txt) and [prompt-attempt-02.txt](prompt-attempt-02.txt): generation and correction prompts.
- [generation-records.json](generation-records.json): exact tool prompt strings, arguments, original paths, byte sizes, original/result SHA256 and dimensions, selection and call accounting.
- [verification.json](verification.json): explicit self-review, actual failures, limitations and source-only status.
- [manifest-sha256.json](manifest-sha256.json): every file in this folder except the manifest itself.

All work is confined to this assigned folder. No git, ledger, registries, code or services were changed. No agents or persistent processes were launched. No game-ready, acceptance, three-variant completion or ownership-of-generated-likeness claim is made.
