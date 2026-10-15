# Casey Jones — AN-154

Status: **proposed / source-only**. Owner: **Raphael**. This folder contains an original proposed adult human front design reference, not stage0 registration, formal acceptance or a game-ready asset. Independent review is pending root coordination.

The selected image is `design-front.png` (1024 × 1536 RGB), copied byte for byte from built-in `image_gen` attempt 2. Both unmodified tool originals are preserved in `attempts/`. No image postprocessing was used. Exact prompts, tool parameters, original paths, SHA256 hashes and dimensions are in `generation-records.json`; prompts are also saved separately in `prompts/`.

Confirmed mechanics are count **1**, health **8**, movement **2**, attack **`range`**. The worker checked the owner-evidence entry against the decoded local raw Raphael sidekick row and verified the raw and owner PNG hashes. The hockey stick is the authorized visual direction and does not change the range stat. See `input-evidence.json` for the supplied evidence entry and its limitations.

Both the Raphael owner PNG and Medusa quality PNG were opened with `view_image` before generation. They informed finish, cohort and restrained material treatment. The proposed subject has human anatomy, long dark hair, a plain vented white hockey mask, charcoal padded sleeveless vest, indigo trousers, scuffed boots, one wooden hockey stick held in the anatomical right hand, an empty left hand, and a small sports bag behind the back. No owner identity, shell, red bandanna, sai, classical costume or franchise insignia was requested. No actor likeness, commercial scan, external generation or purchase was used.

## Self-review and actual failures

- Attempt 1: fully framed subject and equipment, but head/hair began around y=51/1536 (3.3%), short of the requested 6% top margin. Base bottom was around y=1358 (88.4%), short of the requested 90%.
- Attempt 2: the single authorized correction addressed framing only. Head/hair now begins around y=97 (6.3%). The pedestal still ends around y=1355 (88.2%), approximately 1.8 percentage points above the requested 90%; this is a remaining actual framing deviation. Attempt 2 was selected because it improves head clearance while preserving the design.
- The figure reads straight-on, with level shoulders and front-facing boots. Both hands are visible, the right hand grips the shaft, and the left is empty and separated from the trousers. No gross hand defect is apparent; overlap and the grip prevent independent certification of every digit. Elbows are only mildly bent.
- There are exactly two shallow stone bands and no broad visible top ellipse. A thin lit/beveled upper rim remains; strictly zero visible top surface cannot be certified from this raster. Background is charcoal with subtle studio tonal variation, without a ground scene, VFX, text or UI.
- The bag is mainly hidden, with only its strap and a side glimpse visible. Front orthographic appearance and pixel positions are visual estimates, not a 3D-camera or segmentation validation. This review does not provide external similarity clearance.

One initial generation and one correction were used; no further call was made. All remaining limitations are retained for independent review. `verification.json` records source integrity and the honest constraint outcome; `manifest-sha256.json` inventories every file in this folder except itself.

Only this assigned folder was changed. No git, ledger, registry, code or running service was changed, and no agent or persistent service was started.
