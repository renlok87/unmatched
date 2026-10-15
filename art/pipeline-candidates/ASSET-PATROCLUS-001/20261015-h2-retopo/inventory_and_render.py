"""Read-only diagnostics of the failed actual LP, native loop inventory helpers only; no close.run."""
from pathlib import Path
from collections import Counter
import colorsys
import hashlib
import json
import sys
import bmesh
import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True
OUT=Path(__file__).resolve().parent
REPO=OUT.parents[3]
sys.path.insert(0,str(REPO/"tools/tripo-pipeline/blender"))
from h2_bake import bl_util as U, st_close as C
from candidate_build.closure import ordered_boundary_loops

U.require_background()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
lp_file=OUT/"work/lp.blend"
hp_file=OUT/"work/hp.blend"
before={"lp":sha(lp_file),"hp":sha(hp_file)}
bpy.ops.wm.open_mainfile(filepath=str(lp_file))
scene=bpy.context.scene
parts={o.name.removeprefix("LP_"):o for o in bpy.data.collections["LP"].objects}
bvhs={n:C.part_bvh(o) for n,o in parts.items()}
points={n:U.coords(o.data) for n,o in parts.items()}
focus_ids={1,7,10,12,16,17,18,19,21,22,23}
inventory={}
for n,o in sorted(parts.items(),key=lambda it:U.part_key(it[0])):
    bm=bmesh.new();bm.from_mesh(o.data)
    all_loops=ordered_boundary_loops(bm)
    sizes=[sum((lp["verts"][(i+1)%len(lp["verts"])].co-v.co).length for i,v in enumerate(lp["verts"])) for lp in all_loops]
    bm.free()
    minimum=.001 if int(n.rsplit("_",1)[1]) in focus_ids else .005
    rows=C.loop_rows(o,{other:b for other,b in bvhs.items() if other!=n},minimum)
    entries=[]
    for i,row in enumerate(rows):
        co=row["co"]
        entries.append({"loop_id":n+"/lp-loop-%04d"%i,"native_sorted_index_with_threshold":i,"vertex_indices":row["verts"],"coordinates_m":co.tolist(),"closed":row["closed"],"perimeter_cm":row["perimeter_m"]*100,"centre_m":row["centre_m"].tolist(),"bounds_m":[co.min(0).tolist(),co.max(0).tolist()],"nearest":[{"part":nm,"median_mm":dist*1000,"p90_mm":p90*1000} for dist,nm,p90 in row["nearest"]],"significant_ge_0_5cm":row["perimeter_m"]>=.005})
    inventory[n]={"all_loop_count":len(all_loops),"all_loop_closed_count":sum(lp["closed"] for lp in all_loops),"significant_ge_0_5cm_count":sum(x>=.005 for x in sizes),"ge_1cm_count":sum(x>=.01 for x in sizes),"retained_min_perimeter_cm":minimum*100,"retained_loops":entries,"bounds_m":[points[n].min(0).tolist(),points[n].max(0).tolist()]}
    print("INVENTORY_PART",n,len(all_loops),len(entries),flush=True)

def distance_summary(a,b):
    co=points[a]
    dist=np.array([bvhs[b].find_nearest(Vector(p))[3] for p in co])*1000
    return {"from":a,"to":b,"method":"all LP vertices to nearest triangle, unsigned rest distance, not area weighted","samples":len(dist),"distance_mm":{"min":float(dist.min()),"p10":float(np.percentile(dist,10)),"median":float(np.median(dist)),"p90":float(np.percentile(dist,90)),"max":float(dist.max())},"vertex_fraction_le_1_5mm":float(np.mean(dist<=1.5)),"vertex_fraction_le_3mm":float(np.mean(dist<=3)),"nearest_source_vertex_m":co[int(np.argmin(dist))].tolist()}
pairs=[(16,8),(16,21),(21,8),(18,2),(11,2),(18,11),(10,12),(14,7),(7,1),(12,1),(22,12),(23,7),(0,3),(0,15),(0,17),(3,15),(3,17),(5,3)]
contacts=[]
for a,b in pairs:
    for x,y in [(a,b),(b,a)]:contacts.append(distance_summary("tripo_part_%d"%x,"tripo_part_%d"%y))

hp_m=json.loads((OUT.parent/"20261015-h2-bake/measurements-own-hp.json").read_text(encoding="utf-8"))
sections={}
for key,old in hp_m["sections"].items():
    if "parts" not in old:continue
    co=np.concatenate([points["tripo_part_%d"%i] for i in old["parts"]])
    band=co[np.abs(co[:,2]-old["z_m"])<=old["half_band_m"]]
    if len(band)>=3:
        anchor=(band.min(0)+band.max(0))/2;anchor[2]=old["z_m"]
        delta=(anchor-np.array(old["anchor_m"]))*1000
        sections[key]={"parts":old["parts"],"z_m":old["z_m"],"half_band_m":old["half_band_m"],"LP_sample_vertices":len(band),"LP_anchor_m":anchor.tolist(),"HP_anchor_m":old["anchor_m"],"delta_mm":delta.tolist(),"delta_length_mm":float(np.linalg.norm(delta)),"bounds_m":[band.min(0).tolist(),band.max(0).tolist()],"status":"measured failed LP, no bones changed"}
    else:
        sections[key]={"parts":old["parts"],"LP_sample_vertices":len(band),"status":"insufficient LP band sample; do not substitute guessed bone"}

# Append HPG only, for read-only topology/duplicate evidence and contextual silhouette comparison.
with bpy.data.libraries.load(str(hp_file),link=False) as (src,dst):
    dst.collections=["HPG"]
hpcol=dst.collections[0]
scene.collection.children.link(hpcol)
hps={o.name.removeprefix("HPG_"):o for o in hpcol.objects}
hp_boundary={}
for n in ["tripo_part_0","tripo_part_1","tripo_part_17","tripo_part_19"]:
    obj=hps[n];co=U.coords(obj.data)
    bm=bmesh.new();bm.from_mesh(obj.data)
    edges=[e for e in bm.edges if e.is_boundary]
    keys=[]
    for e in edges:
        a,b=[tuple(round(float(x),7) for x in v.co) for v in e.verts]
        keys.append(tuple(sorted((a,b))))
    counter=Counter(keys)
    matched=sum(count for count in counter.values() if count>1)
    hp_boundary[n]={"HP_vertices":len(co),"HP_unique_positions_round7":int(len(np.unique(np.round(co,7),axis=0))),"HP_boundary_edges":len(edges),"coincident_boundary_edges_endpoint_round7":matched,"coincident_fraction":matched/max(len(edges),1),"note":"Read-only coordinate comparison at 0.1 micrometre rounding; no weld/decimation experiment was run. Coincidence does not prove all cracks safely weldable."}
    bm.free()

U.write_json(OUT/"reports/lp-boundary-contact-inventory.json",{"schema":"unmatched.patroclus-lp-inventory/1","source_lp_sha256":before["lp"],"retopo_status":"FAIL, diagnostic candidate only","threshold":"retain every native loop >=0.5 cm, plus >=0.1 cm on knee/base/feet/grips/failing17/19","native_helper":"h2_bake.st_close.loop_rows, read-only; st_close.run NEVER called","perimeter_note":"Native helper wraps last vertex to first even on open chains; closed=false rows are not valid cap cycles.","parts":inventory,"contacts":contacts,"LP_sections_compared_to_HP":sections,"HP_boundary_causal_evidence":hp_boundary,"claims":{"closure_run":False,"caps_authored":False,"rig_authored":False,"art_accepted":False,"game_ready":False}})

scene.render.engine="BLENDER_WORKBENCH"
scene.render.threads_mode="FIXED";scene.render.threads=4
scene.display.shading.light="STUDIO"
scene.display.shading.studiolight_rotate_z=.35
scene.display.shading.color_type="OBJECT"
scene.display.shading.show_shadows=True
scene.display.shading.show_cavity=True
scene.display.shading.cavity_type="BOTH"
scene.display.shading.background_type="WORLD"
scene.world=bpy.data.worlds.new("FailedLPDiagnosticWorld");scene.world.color=(.055,.065,.085)
scene.view_settings.view_transform="Standard"
scene.render.image_settings.file_format="PNG"
cam_data=bpy.data.cameras.new("FailedLPDiagnosticCamera");cam=bpy.data.objects.new("FailedLPDiagnosticCamera",cam_data)
scene.collection.objects.link(cam);scene.camera=cam;cam_data.type="ORTHO";cam_data.clip_start=.0001;cam_data.clip_end=100
for i,(n,o) in enumerate(sorted(parts.items(),key=lambda it:U.part_key(it[0]))):o.color=(*colorsys.hsv_to_rgb((i*.618034)%1,.46,.88),1)
for o in hps.values():o.color=(.72,.74,.78,1)
curves=[]
def boundary_curve(names):
    for curve in curves:bpy.data.objects.remove(curve,do_unlink=True)
    curves.clear()
    for n in names:
        data=bpy.data.curves.new("BOUNDARY_"+n,"CURVE");data.dimensions="3D";data.bevel_depth=.00015;data.bevel_resolution=0;data.resolution_u=1
        for row in inventory[n]["retained_loops"]:
            pts=row["coordinates_m"]
            spline=data.splines.new("POLY");spline.points.add(len(pts)-1)
            for point,co in zip(spline.points,pts):point.co=(*co,1)
            spline.use_cyclic_u=row["closed"]
        obj=bpy.data.objects.new("BOUNDARY_"+n,data);scene.collection.objects.link(obj);obj.color=(1,.025,.01,1);curves.append(obj)

dest=OUT/"diagnostic-preview";dest.mkdir(exist_ok=True)
renders=[]
def render(label,ids,view,focus=None,boundaries=False,hp=False,size=(1080,1440)):
    names=["tripo_part_%d"%i for i in ids]
    shown=hps if hp else parts
    for group in [parts,hps]:
        for n,o in group.items():o.hide_render=(group is not shown or n not in names)
    boundary_curve(names if boundaries and not hp else [])
    framing=names if focus is None else ["tripo_part_%d"%i for i in focus]
    coords=np.vstack([U.coords(shown[n].data) for n in framing])
    low,high=coords.min(0),coords.max(0);center=Vector((low+high)/2)
    cam.location=center+Vector(view).normalized()*2
    cam.rotation_euler=(center-cam.location).to_track_quat("-Z","Y").to_euler()
    local=(coords-np.array(center))@np.array(cam.rotation_euler.to_matrix())
    aspect=size[0]/size[1];w,h=float(np.ptp(local[:,0])),float(np.ptp(local[:,1]))
    cam_data.ortho_scale=(max(h,w/aspect) if aspect<1 else max(w,h*aspect))*1.14
    scene.render.resolution_x,scene.render.resolution_y=size;scene.render.resolution_percentage=100
    scene.render.filepath=str(dest/(label+".png"));bpy.ops.render.render(write_still=True)
    renders.append({"path":str(Path(scene.render.filepath).relative_to(REPO)).replace("\\","/"),"parts":ids,"focus_parts":focus,"camera_view":list(view),"source":"HPG copied prepare" if hp else "failed retopo LP","boundary_overlay":boundaries,"dimensions":list(size),"note":"technical diagnostic only, no formal art/rig acceptance"})

allids=list(range(24))
render("lp-front",allids,(0,-2,0))
render("lp-right",allids,(-2,0,0))
render("lp-back",allids,(0,2,0))
render("lp-front34",allids,(.55,-2,.3))
render("hp-front34-reference",allids,(.55,-2,.3),hp=True)
render("lp-left-knee-boundaries",[10,12],(-1,-2,.4),boundaries=True,size=(1200,1200))
render("lp-foot-base-boundaries",[1,7,12,22,23],(.5,-2,2),boundaries=True,size=(1200,1200))
render("lp-sword-grip-front",[8,9,16,21],(-1,-2,.3),focus=[16,21],boundaries=True,size=(1200,1200))
render("lp-sword-grip-back",[8,9,16,21],(1,2,.3),focus=[16,21],boundaries=True,size=(1200,1200))
render("lp-shield-hand-rear",[2,11,17,18],(-.7,2,.3),boundaries=True,size=(1200,1200))
render("lp-failed-upper-arm17",[17],(-1,2,.4),boundaries=True,size=(1200,1200))
render("lp-failed-waist-panel19-front",[19],(0,-2,0),boundaries=True,size=(1200,1200))
render("lp-failed-waist-panel19-back",[19],(0,2,0),boundaries=True,size=(1200,1200))
render("lp-cape-boundaries",[0],(0,2,.3),boundaries=True)
after={"lp":sha(lp_file),"hp":sha(hp_file)}
assert before==after
U.write_json(OUT/"diagnostic-preview/preview-record.json",{"schema":"unmatched.patroclus-lp-diagnostics/1","input_sha256_before":before,"input_sha256_after":after,"inputs_untouched":True,"renders":renders,"blender_version":bpy.app.version_string,"render_engine":scene.render.engine,"threads":4,"pipeline_stages_executed_in_this_script":[],"claims":{"closure_run":False,"rig_authored":False,"art_accepted":False,"game_ready":False}})
print("LP_INVENTORY_DIAGNOSTIC_OK",sum(x["significant_ge_0_5cm_count"] for x in inventory.values()),len(renders),flush=True)
