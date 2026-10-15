"""Raw high-poly boundary/section scout, NOT prepare/retopo/close/rig/bake stages."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
sys.path.insert(0, str(REPO / "tools/tripo-pipeline/blender"))
from h2_bake import bl_util as U, profile as P, st_close as C
U.require_background()
inv = json.loads((OUT / "source-inventory.json").read_text())
src = REPO / inv["source"]["path"]
before = P.sha256(src)
assert before == inv["source"]["sha256_before"]
scene = U.reset()
parts = U.import_glb_parts(src, "DETAIL_")
# Explicit proposal only: handbook helper/hero ratio 0.78 +/- 0.06; Merlin base precedent.
scale = {"figure_top_m": 0.43, "base_diameter_m": 0.24, "base_height_m": 0.05,
         "figure_top_part": "tripo_part_4"}
base = U.coords(parts["tripo_part_1"].data)
top = float(U.coords(parts["tripo_part_4"].data)[:, 2].max())
fmap = P.frame_map((base.min(0), base.max(0)), top, scale)
for name, obj in parts.items():
    co = U.coords(obj.data)
    # Apply existing frame-map math to memory only; no mesh file is saved/exported.
    mapped = np.array([P.map_point(fmap, p, name == "tripo_part_1") for p in co])
    U.set_coords(obj.data, mapped)
bvhs = {n:C.part_bvh(o) for n,o in parts.items()}
loops, sections, bounds = {}, {}, {}
for n,o in parts.items():
    co=U.coords(o.data)
    bounds[n]=[U.rv(co.min(0)),U.rv(co.max(0))]
    others={k:v for k,v in bvhs.items() if k != n}
    loops[n]=C.loop_rows(o, others, min_perimeter_m=0.005)
    for row in loops[n]:
        # st_close rows contain point arrays needed only internally; keep bounded JSON scalars.
        for key in list(row):
            if isinstance(row[key], np.ndarray):
                row[key] = row[key].tolist()
        row.pop("points", None)
    z0,z1=co[:,2].min(),co[:,2].max()
    sections[n]=[]
    for frac in (0.1,0.25,0.5,0.75,0.9):
        z=float(z0+(z1-z0)*frac)
        hit=co[np.abs(co[:,2]-z)<0.0015]
        if len(hit):
            sections[n].append({"fraction":frac,"z_m":round(z,6),"band_half_m":0.0015,
                                "vertices":len(hit),"bounds_m":[U.rv(hit.min(0)),U.rv(hit.max(0))],
                                "median_m":U.rv(np.median(hit,axis=0))})
    print("DETAIL_DONE",n,len(loops[n]),flush=True)

# Multi-hit through raw cape along Y: preliminary wall observation; not an LP closure verdict.
cape=parts["tripo_part_0"]
ray_rows=[]
for x,z in [(0.00,0.12),(0.00,0.20),(0.00,0.29),(-0.035,0.24),(0.035,0.24),(-0.045,0.33),(0.045,0.33)]:
    origin=Vector((x,-0.20,z)); direction=Vector((0,1,0)); hits=[]
    for step in range(12):
        loc,normal,idx,dist=bvhs["tripo_part_0"].ray_cast(origin,direction,0.50)
        if loc is None: break
        hits.append({"position_m":U.rv(loc),"normal_y":round(normal.y,5)})
        origin=loc+direction*0.00001
    ray_rows.append({"x_m":x,"z_m":z,"direction":[0,1,0],"hits":hits})

scene.render.engine="BLENDER_WORKBENCH"
scene.display.shading.light="STUDIO"
scene.display.shading.color_type="OBJECT"
scene.display.shading.show_cavity=True
scene.display.shading.cavity_type="BOTH"
scene.display.shading.background_type="WORLD"
scene.world=bpy.data.worlds.new("DetailsWorld");scene.world.color=(0.055,0.065,0.085)
scene.view_settings.view_transform="Standard"
scene.render.image_settings.file_format="PNG"
camdata=bpy.data.cameras.new("DetailsCam");cam=bpy.data.objects.new("DetailsCam",camdata)
scene.collection.objects.link(cam);scene.camera=cam;camdata.type="ORTHO"
camdata.clip_start=0.0001;camdata.clip_end=100
(OUT/"details").mkdir(exist_ok=True)

def render(label, group, focus, view, scale_m):
    for n,o in parts.items():
        o.hide_render=n not in group
        o.color=(1.0,0.30,0.06,1) if n in focus else (0.30,0.34,0.40,1)
    co=np.vstack([U.coords(parts[n].data) for n in focus]);center=Vector((co.min(0)+co.max(0))/2)
    cam.location=center+Vector(view).normalized()*1.5
    cam.rotation_euler=(center-cam.location).to_track_quat("-Z","Y").to_euler()
    camdata.ortho_scale=scale_m
    scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.filepath=str(OUT/"details"/(label+".png"));bpy.ops.render.render(write_still=True)

for n in ("tripo_part_19","tripo_part_20","tripo_part_21"):
    render(n+"-context",list(parts),[n],(-0.65,-2,0.5),0.20 if n!="tripo_part_21" else 0.115)
render("sword-grip-isolated",["tripo_part_8","tripo_part_16","tripo_part_21"],["tripo_part_16","tripo_part_21"],(-2,-0.5,0.5),0.12)
render("left-shield-grip",["tripo_part_2","tripo_part_11","tripo_part_17","tripo_part_18"],["tripo_part_18"],(-1.0,2,0.5),0.17)
after=P.sha256(src);assert before==after
data={"schema":"patroclus.raw-hp-scout-measurements/1","source_sha256":before,"source_sha256_after":after,
      "scale_proposal":scale,"scale_status":"UNADOPTED; asset card has GAME_ROLE sidekick but no FIGURE_HEIGHT_M; 0.43/0.55=0.7818 within handbook 0.78 +/- 0.06; base follows Merlin 0.24 x 0.05m",
      "frame_map":fmap,"proposed_final_bounds_m":bounds,
      "boundary_inventory_raw_hp":loops,"boundary_note":"Existing st_close.loop_rows on raw imported HP in proposed scale, NOT retopologized LP. Must repeat after real prepare/retopo with textured geometry identity proven. No caps made.",
      "sections_raw_hp":sections,"cape_through_y_rays":ray_rows,
      "claims":{"lp_authored":False,"rig_authored":False,"final_bake":False,"cloth_shell_required":None}}
(OUT/"measurements.json").write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
print("DETAILS_COMPLETE",flush=True)
