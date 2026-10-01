"""ASSET-ENV-S-WATERFALL-001: review renders of the EXPORTED waterfall pieces + sea ring on the T2b tray
(headless Blender, Cycles on the CPU).

  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/scripts/waterfall_preview.py -- <waterfall-params.json>

Every FBX is read back and placed per reports/waterfall-layout.json (fall pieces at the fall centre on the near tray
edge, yaw 90; the sea ring at the tray centre, z = the sheet bottom), together with SM_TableBase_T2b at (0, offsetY, 0).
Context proxies (NOT the map illustration, ENV-U3): a flat sand/earth ground on the tray at z -1, a dark map plate, the
spill as a flat water strip (z 2.5, y 397..457, the existing ground 'waterfalls' spill). Water materials are stand-ins
for M_EnvWaterfall / a future M_EnvSea (streaks = a noise texture along UV0 v; foam ring = Col.R), not the UE look.
Neutral review rig (key along (-55, 30, 0)). Output: <run>/preview/waterfall-*.jpg + preview.json.
"""

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import k_blender as K  # noqa: E402

T2B = REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2b/export/SM_TableBase_T2b.fbx"
ROCK = REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2/export"


def water_material(name, rgb, alpha, streak=True, foam_from_vcol=False, emission=0.15):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Roughness"].default_value = 0.1
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Emission Color"].default_value = (*rgb, 1.0)
    b.inputs["Emission Strength"].default_value = emission
    b.inputs["Alpha"].default_value = alpha
    if streak:
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (24.0, 2.5, 1.0)
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.0
        nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*rgb, 1.0)
        ramp.color_ramp.elements[1].color = (0.75, 0.82, 0.88, 1.0)
        ramp.color_ramp.elements[0].position = 0.45
        nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
    if foam_from_vcol:
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(vc.outputs["Color"], sep.inputs["Color"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(sep.outputs["Red"], mix.inputs["Factor"])
        mix.inputs[6].default_value = (*rgb, 1.0)
        mix.inputs[7].default_value = (0.55, 0.62, 0.68, 1.0)
        nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def box(name, lo, hi, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.active_object
    o.name = name
    a, b = Vector(lo), Vector(hi)
    o.location = (a + b) / 2
    o.scale = Vector((abs(b.x - a.x), abs(b.y - a.y), abs(b.z - a.z)))
    o.data.materials.append(mat)
    return o


def main():
    P = K.load_params(K.script_args()[0])
    pv = P["preview"]
    run = P["_run"]
    lay = json.loads((run / "reports" / "waterfall-layout.json").read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = K.setup_cycles_cpu(pv["samples"], pv["resolution"])
    T = P["tray"]
    oy = float(T["offset_y_ue"])
    rock = K.textured_material("rock", ROCK / "T_TableBase_T2_BC.png", None, ROCK / "T_TableBase_T2_ORM.png",
                               vcol_tint=("Red", (0.5, 0.62, 0.55)))
    for o in K.import_fbx_placed(T2B, (0.0, oy, 0.0)):
        o.data.materials.clear()
        o.data.materials.append(rock)
    fp = lay["fallPieces"]
    exp = run / "export"
    sheet_m = water_material("sheet", (0.06, 0.13, 0.24), 0.8)
    foam_m = water_material("foam", (0.45, 0.52, 0.58), 0.7, streak=True, emission=0.1)
    mist_m = water_material("mist", (0.55, 0.6, 0.66), 0.35, streak=True, emission=0.05)
    sea_m = water_material("sea", (0.012, 0.03, 0.06), 1.0, streak=False, foam_from_vcol=True, emission=0.0)
    for name, mats in (("SM_Env_S_WaterfallLip", [rock]), ("SM_Env_S_Waterfall", [sheet_m]),
                       ("SM_Env_S_WaterfallFoam", [foam_m, mist_m])):
        for o in K.import_fbx_placed(exp / ("%s.fbx" % name), fp["loc"], fp["yawDeg"]):
            o.data.materials.clear()
            for m in mats:
                o.data.materials.append(m)
    for o in K.import_fbx_placed(exp / "SM_Env_S_SeaRing.fbx", lay["sea"]["loc"], 0.0):
        o.data.materials.clear()
        o.data.materials.append(sea_m)
    hx, hy = float(T["half_x_ue"]), float(T["half_y_ue"])
    box("Ground", K.ue(-hx, oy + hy, -3.0), K.ue(hx, oy - hy, -1.0), K.flat_material("ground", (0.16, 0.12, 0.08)))
    box("MapProxy", K.ue(-445.667, 288.667, -1.0), K.ue(445.667, -288.667, -0.5), K.flat_material("map", (0.3, 0.3, 0.26)))
    e = P["source_entry"]
    box("Spill", K.ue(float(e["x0"]), float(e["y"]), 2.3), K.ue(float(e["x1"]), float(e["y"]) - float(e["spillUU"]), 2.5),
        water_material("spill", (0.06, 0.13, 0.24), 0.85, streak=False))
    K.review_rig(sc, key_energy=2.4, fill_energy=0.6)
    cam = K.camera(sc, pv["hfov_deg"])
    xc = fp["loc"][0]
    shots = [
        ("follow16-river-mouth", "game: 1.6x follow (D %.0f) on the south river mouth" % pv["follow_distance_uu"],
         K.game_view((xc, 430, -60), pv["follow_distance_uu"])),
        ("k1", "game: K1 x1.25 (D %.0f) on the map centre" % pv["k1_distance_uu"], K.game_view((0, 0, 0), pv["k1_distance_uu"])),
        ("zoomout065", "game: zoom-out 0.65x (D %.0f) - the sea ring around the island" % pv["zoom_out_distance_uu"],
         K.game_view((0, 0, 0), pv["zoom_out_distance_uu"])),
        ("diag-low-sw", "NOT a game view: low three-quarter of the waterfall from the south-west",
         (K.ue(xc - 380, 820, 40), K.ue(xc, 450, -80))),
        ("diag-side", "NOT a game view: side view along the edge (sheet vs cliff clearance)",
         (K.ue(xc - 520, 470, -70), K.ue(xc, 470, -70))),
    ]
    info = {"schema": "unmatched.env-s-waterfall.preview/1", "renderer": "Cycles CPU", "samples": sc.cycles.samples,
            "resolution": pv["resolution"], "note": __doc__.split("\n\n")[1].replace("\n", " "), "shots": []}
    for name, title, (c, f) in shots:
        path = run / "preview" / ("waterfall-%s.jpg" % name)
        K.render(sc, cam, path, c, f)
        info["shots"].append({"file": path.name, "title": title,
                              "cameraUE": [round(c.x * 100, 1), round(-c.y * 100, 1), round(c.z * 100, 1)],
                              "targetUE": [round(f.x * 100, 1), round(-f.y * 100, 1), round(f.z * 100, 1)]})
        print("WATERFALL-PREVIEW", path.name, flush=True)
    K.write_json(run / "preview" / "preview.json", info)


main()
