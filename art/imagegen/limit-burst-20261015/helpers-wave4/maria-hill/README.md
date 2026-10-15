# Maria Hill — proposed source-only front design reference

Task: **AN-152**. Owner: **Black Widow**. One adult humanoid helper: health **6**, movement **2**, ranged attack. Owner/stat data matches the supplied owner-evidence row and the local flattened raw owner file; owner/raw SHA256 values match the evidence.

Status: **proposed/source-only**. This is a design proposal with a known framing failure. No stage0 registration, formal acceptance, game-ready claim or engine integration. Root coordinates independent review.

Selected file: `design-front.png` (1024 × 1536), byte-identical to built-in image_gen correction output, SHA256 `a0124444a3d61fee08a6cf8005446614ec543e9a97472ce5213cafaaed8c256d`.

The proposed original adult field coordinator has short dark-brown hair, a slate-blue utilitarian jacket and trousers, simple belt pouches and plain boots. Both hands are visible; the compact pistol is in her right hand (viewer left), directed down and outward. The owner reference and Medusa quality reference were opened with view_image before generation and used for quality/cohort/palette guidance. The first call supplied no reference image as an edit target. No actor reference, purchased asset, scan or external generation fallback was used.

## Attempts and exact prompts

1. Initial built-in generation: `attempts/attempt-01.original.png`. Hair began around 3% rather than 6%; base ended around 88.5% rather than 90%.
2. One permitted framing correction: `attempts/attempt-02.original.png`, selected unchanged as `design-front.png`. Hair top is approximately 6.1%, but base bottom moved to approximately **85.2%**, leaving about 14.8% below it instead of the requested 10%. **The 90% base-bottom requirement remains failed.** No further call or image postprocessing was made.

Exact prompts are `attempts/attempt-01.prompt.txt` and `attempts/attempt-02.prompt.txt`; corresponding `*.request.json` files preserve all tool arguments. `generation-records.json` records exact requests, original tool paths, input/reference hashes, original/result dimensions and SHA256 values. All returned originals are retained byte for byte. The originals at the tool's default generated_images paths were left intact.

## Worker self-review and limits

Full figure, hair, hands, pistol, boots and base are visible. The body reads as a front elevation. Both arms have mild elbow bends with background gaps. One two-disc dark stone pedestal reads edge-on with no exposed top. No visible text, logos, UI, VFX or scenery. The charcoal backdrop has subtle studio tonal variation rather than perfectly uniform RGB.

The selected image still fails base placement; neither attempt meets every exact framing requirement. Raster inspection does not prove true orthographic projection, circular pedestal geometry, five-finger topology or absence of unintended resemblance. The pistol grip is visually plausible but exact trigger-finger separation merits independent review. The correction also changes some shading and small details; it is not a pixel-locked edit. Detailed observations and actual failures are in both `attempts/*.self-review.json` files and `verification.json`.

The supplied evidence lists no existing same-helper production PNG/card paths. A fresh local filename inventory found no Maria Hill matches outside this new folder, but an unrelated Elektra temporary directory denied read access, so the scan is not an exhaustive absence proof (`duplicate-scan.json`). No global ledger, registry, code, git state or running service was changed. No background service or subagent was started.

`manifest-sha256.json` covers every file in this folder except itself. These checks establish provenance and file integrity, not art acceptance.
