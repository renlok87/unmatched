"""H2 bake of King Arthur (ASSET-KING-ARTHUR-001): Tripo high-poly by parts -> game mesh + baked atlas + UM17 rig.

New module of the H2 hero iteration (2026-09-29). It does not change tools/tripo-pipeline/tripo_pipeline.py, the
candidate_build library, candidate/atlas.py or the rig contract (wave 4 owns them); candidate_build is imported
read-only for the UM_FBX_v1 export (rotation, determinism pins, unit patch) and the weight helpers.

Stages (profile: art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/*-h2.json):
  inspect   (Blender)  both GLBs, part matching, geometry identity, winding/orientation, part preview sheet
  lowpoly   (Blender)  per-part retopology (collapse decimation with boundary/sharp preservation), cleanup,
                        UV unwrap per part, texel-density priorities, one 4K atlas pack; work/h2-lowpoly.blend
  uvcheck   (python)   rasterised island gaps / overlap / texel density on the 4K atlas
  bake      (Blender)  Cycles selected-to-active per part: tangent normal (OpenGL), AO, BaseColor and
                        metallicRoughness from the Tripo textures (emission rewire), hit mask for the cage check
  textures  (python)   miss fill per UV island, phantom repaint (mirror / red-cloth donors, detail normals), N (DirectX)
                        + N_OpenGL, ORM, BC 4K master + 2K runtime, TeamMask (R cloth, G base band; normalised
                        edge + atlas fill), measured checks (edge row vs interior, colour residue)
  rig       (Blender)  scale/seat, UM_HUMANOID_17 armature, proxy heat weights + per-part rules, sockets,
                        UM_FBX_v1 export (SK + base, header path pinned run-dir-relative), FBX readback, rig_deform_probe blend
  review    (Blender)  EEVEE PBR frames (ortho front/side/back, close-ups, game cameras K1/K2, back views, TeamDye)
                        + silhouettes
  sheets    (python)   side-by-side sheets with the H2 concepts and the previous candidate, labelled "blender"

Look-dev v2 (2026-09-29; profile build-profiles/king-arthur-h2-lookdev.json, run 20260929-h2-lookdev, report
docs/art-pipeline/king-arthur-lookdev-v2.md): lookdev_state (H2.2 texel state rebuilt byte-exact), lookdev_export (UV1
in metres + FBX read-back), lookdev_maps (zones, MatID, TeamAccent, EdgeMask), lookdev_emul (numpy emulation of the
M_UM_Figure_v2 core for the Blender frames), lookdev_tone (steel / gold F0 and dielectric tone from the concept, LUT),
lookdev_render (studio_env + Cobble calibrated to the W4-A anchor + ID frames), lookdev_report; the H2 stages are unchanged.

Driver: tools/tripo-pipeline/blender/h2_bake_arthur/run.py (system python). Every Blender stage is headless only.
"""

MODULE_VERSION = "h2-bake-arthur/2"
