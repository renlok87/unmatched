import unreal as u
import json, hashlib
from pathlib import Path
root = Path(__file__).resolve().parents[2]
evidence = root/'docs/game-design/evidence/S01/ue'
task = u.AssetImportTask()
task.filename = str(root/'blender/_shared/s01-import/SM_S01_Cube.fbx')
task.destination_path = '/Game/S01'
task.automated = True; task.replace_existing = True; task.save = True
opts = u.FbxImportUI(); opts.import_mesh = True; opts.import_as_skeletal = False
opts.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
opts.import_materials = True; opts.import_textures = False
opts.static_mesh_import_data.combine_meshes = True
opts.static_mesh_import_data.import_uniform_scale = 1.0
task.options = opts
u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh = u.load_asset('/Game/S01/SM_S01_Cube')
assert mesh, 'Mesh import failed'
bounds = mesh.get_bounding_box()
report = {'min':[bounds.min.x,bounds.min.y,bounds.min.z],'max':[bounds.max.x,bounds.max.y,bounds.max.z], 'material_slots':len(mesh.static_materials),'materials':[str(s.material_interface.get_path_name()) if s.material_interface else None for s in mesh.static_materials]}
assert all(abs(v-100)<.1 for v in [bounds.max.x-bounds.min.x,bounds.max.y-bounds.min.y,bounds.max.z-bounds.min.z]), report
assert abs(bounds.min.z)<.1 and abs(bounds.min.x+bounds.max.x)<.1 and abs(bounds.min.y+bounds.max.y)<.1, report
assert report['material_slots']==1 and report['materials'][0], report
board=json.loads((root/'docs/game-design/evidence/S01/content-board.json').read_text(encoding='utf-8-sig'))['adminBoard']
fixture=json.loads((root/'docs/game-design/evidence/S01/duel-start-p1.json').read_text(encoding='utf-8-sig'))
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
if u.EditorAssetLibrary.does_asset_exist('/Game/S01/Smoke'):
 assert levels.load_level('/Game/S01/Smoke')
 for old in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
  if isinstance(old, (u.StaticMeshActor, u.DirectionalLight, u.SkyLight)):
   u.get_editor_subsystem(u.EditorActorSubsystem).destroy_actor(old)
else:
 assert levels.new_level('/Game/S01/Smoke')
def actor(mesh_asset, label, xyz, scale):
 a=u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor,u.Vector(*xyz))
 a.set_actor_label(label); a.static_mesh_component.set_static_mesh(mesh_asset); a.set_actor_scale3d(u.Vector(*scale)); return a
cube=u.load_asset('/Engine/BasicShapes/Cube.Cube'); sphere=u.load_asset('/Engine/BasicShapes/Sphere.Sphere')
for cell in board['cells']:
 x=(cell['x']-(board['width']-1)/2)*100; y=(cell['y']-(board['height']-1)/2)*100
 actor(cube, 'Cell_%s_%s_%s'%(cell['x'],cell['y'],cell['zones'][0]), (x,y,-6),(.94,.94,.1))
for f in fixture['fighters']:
 p=f['position']; x=(p['x']-(board['width']-1)/2)*100; y=(p['y']-(board['height']-1)/2)*100
 actor(sphere, f['name']+'_'+f['id'],(x,y,25),(.25,.25,.5))
probe=actor(mesh,'Blender_100uu_probe',(-360,0,0),(1,1,1))
probe.static_mesh_component.set_editor_property('cast_shadow',False)
light=u.EditorLevelLibrary.spawn_actor_from_class(u.DirectionalLight,u.Vector(0,0,700),u.Rotator(-55,-25,0))
light.light_component.set_editor_property('intensity',4.0)
sky=u.EditorLevelLibrary.spawn_actor_from_class(u.SkyLight,u.Vector(0,0,400))
sky.light_component.set_editor_property('intensity',1.0)
assert levels.save_current_level()
u.EditorAssetLibrary.save_directory('/Game/S01')
report.update({'board_width':board['width'],'board_height':board['height'],'cells':len(board['cells']),'fighters':len(fixture['fighters']), 'mapping':'((x-(W-1)/2)*100,(y-(H-1)/2)*100,0)', 'fixture_only':True})
projection={'board':{'width':board['width'],'height':board['height'],'cells':board['cells']},'fighters':[{k:f[k] for k in ['id','name','position','type']} for f in fixture['fighters']]}
report['fixture_geometry_sha256']=hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(',',':')).encode()).hexdigest()
(evidence/'import-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
u.log('S01_IMPORT_VERIFIED '+json.dumps(report))
