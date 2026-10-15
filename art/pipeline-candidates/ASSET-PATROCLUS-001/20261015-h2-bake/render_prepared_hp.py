"""Diagnostic views of the actual prepared HP. No pipeline preview/rig stage, no saved scene mutation."""
from pathlib import Path
import sys
import colorsys
import hashlib
import json
import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
sys.path.insert(0,str(REPO/"tools/tripo-pipeline/blender"))
from h2_bake import bl_util as U

U.require_background()
blend = OUT/"work/hp.blend"
before = hashlib.sha256(blend.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(blend))
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.threads_mode = "FIXED"
scene.render.threads = 4
scene.display.shading.light = "STUDIO"
scene.display.shading.studiolight_rotate_z = .35
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "BOTH"
scene.display.shading.curvature_ridge_factor = 1.3
scene.display.shading.curvature_valley_factor = 1.1
scene.display.shading.background_type = "WORLD"
scene.world = bpy.data.worlds.new("PreparedHPDiagnosticWorld")
scene.world.color = (.055,.065,.085)
scene.view_settings.view_transform = "Standard"
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
cam_data = bpy.data.cameras.new("PreparedHPDiagnosticCamera")
cam = bpy.data.objects.new("PreparedHPDiagnosticCamera",cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.type = "ORTHO"
cam_data.clip_start = .0001
cam_data.clip_end = 100
parts = {o.name.removeprefix("HPT_"):o for o in bpy.data.collections["HPT"].objects}
raw = list(bpy.data.collections["HPG"].objects)
for o in raw:
    o.hide_render = True
    o.hide_set(True)
for i,(n,o) in enumerate(sorted(parts.items(),key=lambda it:U.part_key(it[0]))):
    o.color = (*colorsys.hsv_to_rgb((i*.618034)%1,.46,.88),1)
    # Workbench texture mode uses the material's active image node. Choose actual Tripo BC, not normal/ORM.
    for mat in o.data.materials:
        if mat and mat.use_nodes:
            nodes = mat.node_tree.nodes
            bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"),None)
            if bsdf and bsdf.inputs["Base Color"].is_linked:
                node = bsdf.inputs["Base Color"].links[0].from_node
                if node.type == "TEX_IMAGE":
                    nodes.active = node
                    node.select = True

output = OUT/"diagnostic-preview"
output.mkdir(exist_ok=True)
records = []
def render(label,view,style="TEXTURE",focus=None,size=(1080,1440)):
    for o in parts.values():
        o.hide_render = False
        o.hide_set(False)
    coords = np.vstack([U.coords(o.data) for o in parts.values()]) if focus is None else np.vstack([U.coords(parts["tripo_part_%d"%i].data) for i in focus])
    low,high = coords.min(0),coords.max(0)
    center = Vector((low+high)/2)
    direction = Vector(view).normalized()
    cam.location = center + direction*2
    cam.rotation_euler = (center-cam.location).to_track_quat("-Z","Y").to_euler()
    local = (coords-np.array(center)) @ np.array(cam.rotation_euler.to_matrix())
    aspect = size[0]/size[1]
    # ortho_scale is camera width in landscape, height in portrait (sensor fit AUTO).
    frame_w,frame_h = float(np.ptp(local[:,0])),float(np.ptp(local[:,1]))
    cam_data.ortho_scale = max(frame_h,frame_w/aspect)*1.12 if aspect<1 else max(frame_w,frame_h*aspect)*1.12
    scene.render.resolution_x,scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.display.shading.color_type = style
    scene.render.filepath = str(output/(label+".png"))
    bpy.ops.render.render(write_still=True)
    records.append({"path":str(Path(scene.render.filepath).relative_to(REPO)).replace("\\","/"),"camera_view_vector":list(view),"focus_parts":focus,"color_mode":style,"resolution":list(size),"camera_ortho_scale_m":cam_data.ortho_scale,"label":"actual prepared HP diagnostic, no LP/rig/final-lookdev"})

render("prepared-hp-front-texture",(0,-2,0))
render("prepared-hp-right-texture",(-2,0,0))
render("prepared-hp-back-texture",(0,2,0))
render("prepared-hp-front34-parts",(.55,-2,.3),"OBJECT")
render("prepared-hp-right-grip",(-1.8,-2,.3),"TEXTURE",[8,9,16,21],(1200,1200))
render("prepared-hp-left-shield-rear",(-.6,2,.3),"TEXTURE",[2,11,17,18],(1200,1200))
images = [{"name":i.name,"size":list(i.size),"source":i.source} for i in bpy.data.images if i.type == "IMAGE"]
after = hashlib.sha256(blend.read_bytes()).hexdigest()
assert before == after
U.write_json(OUT/"diagnostic-preview/preview-record.json",{"schema":"unmatched.prepared-hp-diagnostics/1","hp_blend_sha256_before":before,"hp_blend_sha256_after":after,"hp_blend_untouched":True,"render_engine":scene.render.engine,"threads":4,"blender_version":bpy.app.version_string,"images":images,"renders":records,"claims":{"pipeline_preview_stage_run":False,"rig_authored":False,"game_ready":False,"art_accepted":False}})
print("PREPARED_HP_DIAGNOSTIC_OK",len(records),flush=True)
