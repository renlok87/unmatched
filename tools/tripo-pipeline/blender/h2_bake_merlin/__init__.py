"""H2 bake of Merlin (ASSET-MERLIN-001): Tripo H3.1 parts high-poly -> game mesh + baked 4K atlas + UM17 v2 rig.

New module of the H2 hero iteration (2026-09-29). It changes nothing in tools/tripo-pipeline/tripo_pipeline.py,
blender/candidate_build/, candidate/atlas.py or the rig contract (wave 4 owns them): candidate_build.core is only
imported (FBX determinism pins, UM_FBX_v1 export rotation, unit patch) and candidate_build.rig for bone heat and
the weight cleanup. The parallel hero agents keep their own h2_bake_<hero>/ packages; merging them into one
h2_bake/ library is a follow-up.

Stages (profile: art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-segmented-skeletal-h2.json):
  source   (Blender)  both GLBs: sha256/bytes, counts, part matching, geometry identity, winding + ray-escape
                       orientation, shared seam loops between parts            -> work/h2-source.blend
  retopo   (Blender)  weld, per-part sequential collapse decimation, caps/bridge, beautify, deviation
                       high<->low per part                                      -> work/h2-retopo.blend
  uv       (Blender)  Smart UV per part, uniform density x td_priority, one 4K pack; UV triangles for checks
                                                                                -> work/h2-uv.blend, work/uv/*.npz
  bake     (Blender)  Cycles selected-to-active per part: normal (OpenGL tangent), AO, base colour,
                       roughness, metallic (emission rewire of the Tripo PBR)   -> work/bake/*.npy
  maps     (python)   gutter fill, N (DirectX), ORM, BC, TeamMask (L) + TeamMaskRGBA, 4K + 2K,
                       padding / texel-density / miss checks                    -> textures/*.png
  rig      (Blender)  final frame, base normalisation, UM_HUMANOID_17_v2 armature, weights with seam sync,
                       sockets, UM_FBX_v1 export (SK + base) from a factory session (no host path in the
                       FBX), FBX readback checks                               -> export/*.fbx
  probe    (Blender)  anim/validate_clip.py (skeletal-mesh v2), anim/rig_deform_probe.py on the rig .blend and on
                       the FBX (fbx_to_authored_blend); PNG render stamps dropped
  preview  (Blender)  EEVEE PBR frames (ortho front/right/back, close-ups, K2 game camera, previous candidate)
  sheets   (python)   side-by-side sheets with the H2 concepts, labelled "blender"
  report.py          -> docs/art-pipeline/merlin-h2-report.json (checks, host-path audit, K2 basis, determinism)
  determinism.py     compare two run folders file by file -> reports/determinism.json sections

Driver: python tools/tripo-pipeline/blender/h2_bake_merlin/run.py --profile <profile> [stages...].
Every Blender stage runs headless only (blender -b --factory-startup); it refuses to run in a live session.
"""

MODULE_VERSION = "h2-bake-merlin/1"
