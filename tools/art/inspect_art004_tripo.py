"""Inspect and render a downloaded pilot without changing its source GLB.

Run in background Blender: --python this.py -- source.glb output-directory
The preview is normalized to height 55 only for inspection, not asset acceptance.
"""
import bpy
import bmesh
import hashlib
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

source, output = [Path(p).resolve() for p in sys.argv[sys.argv.index('--') + 1:]]
output.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
report = {'source': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'blender': bpy.app.version_string, 'meshes': [], 'images': [],
          'armatures': len([o for o in bpy.context.scene.objects if o.type == 'ARMATURE']),
          'actions': len(bpy.data.actions), 'game_ready': False}
points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
report['original_bounds'] = {'min': list(lo), 'max': list(hi), 'dimensions': list(hi-lo)}
for obj in meshes:
    mesh = obj.data
    mesh.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    unseen = set(bm.verts)
    components = []
    while unseen:
        pending = [unseen.pop()]
        count = 0
        while pending:
            v = pending.pop()
            count += 1
            for edge in v.link_edges:
                other = edge.other_vert(v)
                if other in unseen:
                    unseen.remove(other)
                    pending.append(other)
        components.append(count)
    report['meshes'].append({
        'name': obj.name, 'vertices': len(mesh.vertices), 'polygons': len(mesh.polygons),
        'triangles': len(mesh.loop_triangles), 'uv_layers': [uv.name for uv in mesh.uv_layers],
        'material_slots': [slot.material.name if slot.material else None for slot in obj.material_slots],
        'boundary_edges': sum(e.is_boundary for e in bm.edges),
        'non_manifold_edges': sum(not e.is_manifold for e in bm.edges),
        'loose_vertices': sum(not v.link_edges for v in bm.verts),
        'degenerate_faces': sum(f.calc_area() < 1e-12 for f in bm.faces),
        'connected_component_vertex_counts': sorted(components, reverse=True),
    })
    # glTF splits vertices on UV/normal seams. Do not confuse these with holes.
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
    report['meshes'][-1]['diagnostic_weld_only'] = {
        'tolerance_source_units': 1e-7,
        'vertices': len(bm.verts),
        'boundary_edges': sum(e.is_boundary for e in bm.edges),
        'non_manifold_edges': sum(not e.is_manifold for e in bm.edges),
        'note': 'Diagnostic BMesh copy only; source and rendered mesh unchanged.'}
    bm.free()
for image in bpy.data.images:
    if image.type == 'IMAGE':
        report['images'].append({'name': image.name, 'size': list(image.size),
                                 'colorspace': image.colorspace_settings.name})
        image.filepath_raw = str(output / (bpy.path.clean_name(image.name) + '.png'))
        image.file_format = 'PNG'
        image.save()
report['materials'] = []
for material in bpy.data.materials:
    report['materials'].append({'name': material.name,
        'image_nodes': [{'node': n.name, 'image': n.image.name if n.image else None}
                        for n in material.node_tree.nodes if n.type == 'TEX_IMAGE']
                        if material.use_nodes else []})
(output/'mesh-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

# Preserve the imported topology. Only presentation transforms are applied.
scale = 55 / (hi.z-lo.z)
center = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, lo.z))
for obj in meshes:
    world = obj.matrix_world.copy()
    for v in obj.data.vertices:
        v.co = (world @ v.co-center)*scale
    obj.parent = None
    obj.matrix_world.identity()

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'
scene.render.threads = 6
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.world = bpy.data.worlds.new('InspectionWorld')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.18,0.18,0.18,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.8
scene.view_settings.view_transform = 'Standard'
scene.render.image_settings.file_format = 'PNG'
for name, position, power, size in [('Key',(60,-80,110),180000,80),('Fill',(-80,-20,60),90000,80),('Rim',(0,70,100),140000,70)]:
    light = bpy.data.lights.new(name, 'AREA')
    light.energy, light.shape, light.size = power, 'DISK', size
    obj = bpy.data.objects.new(name,light)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector((0,0,27))-obj.location).to_track_quat('-Z','Y').to_euler()
camera_data = bpy.data.cameras.new('InspectionCamera')
camera = bpy.data.objects.new('InspectionCamera', camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 65
camera_data.clip_end = 5000
for name, position in [('front',(0,-150,27.5)),('left',(150,0,27.5)),('back',(0,150,27.5)),('right',(-150,0,27.5)),('k1-angle-detail',(0,-103.24,174.94))]:
    camera.location = position
    camera.rotation_euler = (Vector((0,0,27.5))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath = str(output/f'{name}.png')
    bpy.ops.render.render(write_still=True)
# Actual K1 distance/FOV; isolated normalized figure, no board/HUD.
camera_data.type = 'PERSP'
camera_data.angle = math.radians(35)
camera.location = (0,-1032.4,1474.4)
camera.rotation_euler = (Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x, scene.render.resolution_y = 1920,1080
scene.render.filepath = str(output/'k1-scale-probe.png')
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output/'inspection.blend'))
print('ART004_INSPECTION_COMPLETE', json.dumps(report))
