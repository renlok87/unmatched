"""H2 bake: game model from a Tripo H2 high-poly ("по частям", ~2M tris) + its 8K/PBR textured twin.

Iteration «проработка героев H2» (2026-09-29). A NEW module next to candidate_build/: it does not change
tripo_pipeline.py, candidate/atlas.py or candidate_build/* (wave 4 owns those files); it only imports
candidate_build.core (UM_FBX_v1 export: rotation, determinism pins, unit patch), candidate_build.measure (read-back
measurements) and candidate_build.closure (boundary loops) read-only.

Stages (driver: run_h2_bake.py; Blender stages run headless: blender -b --factory-startup):
  prepare   import both GLBs, match parts, prove identical geometry, scale to the card-04 frame, optional
            prepare.part_offsets_m (seat a detached rigid detail: final frame, after the map; st_prepare.py),
            ray-escape orientation of every high-poly part                      -> work/hp.blend
  retopo    per-part collapse decimation to the profile budget (two-step for dense regions: face),
            cleanup, caps of the base-top holes, deviation low<->high            -> work/lp.blend
  close     contact caps (st_close.py): every Tripo contact opening that a pose can expose (dress under the fist,
            fist, armholes, shoulder tops, slits, thigh and greave tops, hem floor, soles) gets a separate cap on the
            exact rim loop; caps must stay hidden at rest (ray-cast views with / without caps)
                                                                                 -> work/lp_closed.blend
  uv        seam-based charts per part (charts.py), equal texel density, priority scale (face/hands/
            weapon; caps), one 4K atlas with >= 8 px gaps and no overlap (measured on a raster), rim-transfer
            weights of the cap texels and of the contact footprints (faces hidden at rest under the neighbour)
                                                                                 -> work/lp_uv.blend, work/uv/*.npz
  bake      Cycles selected-to-active per part (only the part's own high-poly is a ray target;
            the whole high-poly figure occludes AO): Normal (tangent, OpenGL), AO, BaseColor and
            Roughness/Metallic from the Tripo PBR maps (emission pass-through)    -> work/bake/*.npy
  aux       (H2.1) rest-position map of every texel (UV raster of the low-poly) and the AO of parts re-baked
            without occluders that move away in the animation (bake.ao_exclusions: the fist on the belt)
                                                                                 -> work/uv/position.npy, work/bake/AO_EX.npy
  textures  (plain Python, numpy + Pillow) composite, pad, DX/OpenGL normals, ORM, TeamMask,
            footprints and cap texels from their surroundings (BC/ORM harmonic from rim samples; caps: flat N),
            4K master + 2K runtime; H2.1 material pass (materials.py, profile textures.materials): AO without the
            fist, rim filters of contact caps, metal mask from BC hue/sat/value + Tripo parts + 3D gates, BC/ORM
            remap of metal (metallic 0.9-1, roughness 0.32-0.45), metallic 0 elsewhere
                                                                                 -> textures/*.png
  rig       UM_HUMANOID_17_v2 armature, positional chain weights (+ junction bands: collar), UM_FBX_v1 export
            + read-back
                                                                                 -> export/*.fbx
  probes    rig_deform_probe.py on the .blend and on the FBX read back, validate_clip.py (v2)   -> reports/
  seams     probe poses: junction openings, rim loops that open (share of perimeter > 1.5 mm), see-through
            ray test (back faces seen, .blend and FBX), Workbench frames with backface culling  -> reports/
  preview   Cycles frames with the baked PBR set (labelled "blender")            -> work/preview_raw
  compose   side-by-side sheets (concept | high-poly | H2 | previous), close-ups, K2, culled probe sheets
                                                                                 -> preview/*.jpg
  curve     (optional, --stages curve) exploratory triangles -> deviation curve  -> reports/decimation-curve.json

Driver services (0.7.0): every h2 stage records its fingerprint (profile blocks, code, inputs, Blender) in
work/stages.json; --reuse-from <old run> takes over the unchanged stages (reuse.py); --compare-with gives a determinism
verdict by the tolerance table of determinism.py (exit code 1 outside it).

Statuses: every number is "измерено" at most; budgets are "предложено"; nothing here is art-accepted.
"""

VERSION = "h2-bake/0.8.0"  # 0.8.0 (W1-d/W1-e + W2-c 2026-10-14): extended rig probes gate profile_version >= 2 (rig.probe_skip), opt-in base.flatten_bottom, base.rim_smooth, team_mask.base_band.height_m (UM_Mask.R), textures.band_repaint, look-dev metal_f0; outputs without the new keys unchanged; 0.7.0 (W1-d 2026-10-14): stage ledger work/stages.json + --reuse-from (reuse.py), determinism verdict with a tolerance table and exit code 1 (determinism.py), new-hero profile rules (profile.new_hero_problems), ld_fbx through staging; outputs of every stage unchanged; 0.6.1: preview.previous_candidate / preview.baseline optional, concept framing from preview.frame / look-dev frame (framing.py), TeamAccent hem / ribbon optional (new characters; Medusa outputs unchanged); 0.6.0: weapon side / no weapon from the profile and rig contract (D-1; Medusa outputs unchanged); 0.5.0: --mode teamaccent (lookdev_accent.py, st_team.py); 0.4.0: --mode lookdev; the h2 stages are unchanged
