"""Shared library of the `build` stage (skeletal-candidate profile) of tools/tripo-pipeline.

Loaded by blender/build_candidate.py inside Blender (headless `blender -b` or the live GUI through
blender_mcp.py) from the directory named by params["lib_dir"]; the entry script loads a fresh copy on
every run (a live Blender session never keeps a stale module).

Modules (the ones marked "pure" import no bpy and are also used by tripo_pipeline.py and the unit tests):
  core         constants, FBX preset/determinism, scene context, checks, export and round trip helpers
  measure      measurements (UV cells, ray-escape orientation, weights, meshes, closure diagnostics)
  mesh_ops     part preparation: bake, corner normals, weld, islands, atlas material, labels, join
  weapon       weapon assembly: split off a fused part, grip bridge on a fitted axis, staff parts
  closure      caps: base top footprint holes, soles, fan caps of open loops
  rig          armature (final or source frame), rule weights, bone heat, rigid, wing span, axis blend
  orientation  per-face orientation vote against a reference high-poly GLB
  base         parametric base with a vertex-colour mask and its preview material
  anatomy      (pure) part roles from the profile or auto-detected from part geometry
  profile_schema (pure) validation of build profiles for both flows
  flow_whole_figure  flow "whole-figure": the T4 Medusa candidate (whole figure scaled, base stretched)
  flow_seated        flow "seated-parts": heroes (figure seated on a normalised or parametric base)
"""

LIB_VERSION = "candidate-build/2"
FLOWS = ("whole-figure", "seated-parts")
