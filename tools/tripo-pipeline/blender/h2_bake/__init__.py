"""H2 bake: game model from a Tripo H2 high-poly ("по частям", ~2M tris) + its 8K/PBR textured twin.

Iteration «проработка героев H2» (2026-09-29). A NEW module next to candidate_build/: it does not change
tripo_pipeline.py, candidate/atlas.py or candidate_build/* (wave 4 owns those files); it only imports
candidate_build.core (UM_FBX_v1 export: rotation, determinism pins, unit patch), candidate_build.measure (read-back
measurements) and candidate_build.closure (boundary loops) read-only.

Stages (driver: run_h2_bake.py; Blender stages run headless: blender -b --factory-startup):
  prepare   import both GLBs, match parts, prove identical geometry, scale to the card-04 frame,
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

Statuses: every number is "измерено" at most; budgets are "предложено"; nothing here is art-accepted.
"""

VERSION = "h2-bake/0.4.0"  # 0.4.0: --mode lookdev (lookdev.py, st_lookdev.py); the h2 stages are unchanged
