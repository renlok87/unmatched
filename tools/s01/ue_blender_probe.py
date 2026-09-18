import bpy
from pathlib import Path
root = Path(__file__).resolve().parents[2]
out = root / 'blender/_shared/s01-import'
out.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1.0
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0))
obj = bpy.context.object
obj.name = 'SM_S01_Cube'
for v in obj.data.vertices: v.co.z += .5
mat = bpy.data.materials.new('M_S01_Clay'); mat.diffuse_color = (.35,.22,.12,1)
obj.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'s01-cube.blend'))
bpy.ops.export_scene.fbx(filepath=str(out/'SM_S01_Cube.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
print('S01_BLENDER_EXPORTED unit_scale=1 dimensions=1,1,1 pivot=bottom material=M_S01_Clay')
