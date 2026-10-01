"""ASSET-TABLE-BASE-001 T2b: review renders of the EXPORTED SM_TableBase_T2b.fbx (headless Blender, Cycles on the CPU).

  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2b_preview.py -- <tray-t2b-params.json>

The FBX is read back (frame = UE with Y negated), placed like the board actor places it (tray centre at UE
(0, offsetY)), with the neutral map proxy of tray_t2_preview.py (flat plate 891.333 x 577.333 at Z -0.5 + the 24 uu
frame; NOT the map illustration, ENV-U3) and a flat earth proxy of the themed ground up to Z -1. The rock uses the T2
rock set; the moss band is previewed as Col.R x (Moss_BC x tint) over the rock: a stand-in for the future
MI_TableBase_T2b parameters (Marmoreal: green moss; Sarpedon: dark damp rock), not a calibrated look. For the
before/after the T2 FBX is rendered from the same diagnostic camera. Lighting: the neutral review rig (key along the
art profiles' (-55, 30, 0)), not the night profiles. Output: <run>/preview/tray-t2b-*.jpg + preview.json.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import k_blender as K  # noqa: E402

LOOKS = {"marmoreal": {"tint": (0.55, 0.85, 0.45), "amount": 1.0, "rock": (1.0, 1.0, 1.0)},
         "sarpedon": {"tint": (0.25, 0.35, 0.32), "amount": 0.7, "rock": (0.8, 0.85, 0.92)}}


def tray_material(P, look):
    d = REPO / P["rock_textures"]["dir"]
    pre = P["rock_textures"]["prefix"]
    mp = REPO / P["run_dir"] / "export" / ("%s_BC.png" % P["moss_textures"]["prefix"])
    L = LOOKS[look]
    m = bpy.data.materials.new("T2b_preview_" + look)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

    def img(path, cs):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(path))
        t.image.colorspace_settings.name = cs
        t.extension = "REPEAT"
        return t
    bc = img(d / ("%s_BC.png" % pre), "sRGB")
    orm = img(d / ("%s_ORM.png" % pre), "Non-Color")
    moss = img(mp, "sRGB")
    # the moss texture at 2.5x the rock frequency
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    sc.inputs["Scale"].default_value = 2.5
    nt.links.new(uvn.outputs["UV"], sc.inputs[0])
    nt.links.new(sc.outputs[0], moss.inputs["Vector"])
    rock = nt.nodes.new("ShaderNodeMix")
    rock.data_type = "RGBA"
    rock.blend_type = "MULTIPLY"
    rock.inputs["Factor"].default_value = 1.0
    nt.links.new(bc.outputs["Color"], rock.inputs[6])
    rock.inputs[7].default_value = (*L["rock"], 1.0)
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    nt.links.new(moss.outputs["Color"], tint.inputs[6])
    tint.inputs[7].default_value = (*L["tint"], 1.0)
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vc.outputs["Color"], sep.inputs["Color"])
    # the FBX value is the mask; Blender's import linearised it -> back to the mask value with a 1/2.2 power
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 1.0 / 2.2
    nt.links.new(sep.outputs["Red"], pw.inputs[0])
    amt = nt.nodes.new("ShaderNodeMath")
    amt.operation = "MULTIPLY"
    amt.inputs[1].default_value = L["amount"]
    nt.links.new(pw.outputs[0], amt.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(amt.outputs[0], mix.inputs["Factor"])
    nt.links.new(rock.outputs[2], mix.inputs[6])
    nt.links.new(tint.outputs[2], mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    s2 = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], s2.inputs["Color"])
    nt.links.new(s2.outputs["Green"], b.inputs["Roughness"])
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
    pv, tray = P["preview"], P["tray"]
    out = P["_run"] / "preview"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = K.setup_cycles_cpu(pv["samples"], pv["resolution"])
    oy = float(tray["offset_y_ue"])
    t2b = K.import_fbx_placed(P["_run"] / "export" / ("%s.fbx" % P["asset_name"]), (0.0, oy, 0.0))[0]
    t2 = K.import_fbx_placed(REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2/export/SM_TableBase_T2.fbx",
                             (0.0, oy, 0.0))[0]
    mats = {k: tray_material(P, k) for k in LOOKS}
    t2.data.materials.clear()
    t2.data.materials.append(mats["sarpedon"])
    mhx, mhy, fr = 445.667, 288.667, 24.0
    plate = K.flat_material("map_proxy", (0.10, 0.11, 0.09), 0.8)
    wood = K.flat_material("frame_wood", (0.06, 0.035, 0.02), 0.7)
    box("MapProxy", K.ue(-mhx, mhy, -1.0), K.ue(mhx, -mhy, -0.5), plate)
    for n, lo, hi in (("FrameN", (-mhx - fr, -mhy - fr), (mhx + fr, -mhy)), ("FrameS", (-mhx - fr, mhy), (mhx + fr, mhy + fr)),
                      ("FrameW", (-mhx - fr, -mhy), (-mhx, mhy)), ("FrameE", (mhx, -mhy), (mhx + fr, mhy))):
        box(n, K.ue(lo[0], hi[1], -10.0), K.ue(hi[0], lo[1], 4.0), wood)
    hx, hy = float(tray["half_x_ue"]), float(tray["half_y_ue"])
    box("GroundProxy", K.ue(-hx, oy + hy, -3.0), K.ue(hx, oy - hy, -1.0), K.flat_material("ground", (0.075, 0.06, 0.045)))
    K.review_rig(sc)
    cam = K.camera(sc, pv["hfov_deg"])
    shots = [
        ("k1-marmoreal", "game: K1 x1.25 (D %.0f), moss look stand-in Marmoreal" % pv["k1_distance_uu"], "marmoreal",
         K.game_view((0, 0, 0), pv["k1_distance_uu"]), None, "t2b"),
        ("zoomout065-marmoreal", "game: zoom-out 0.65x (D %.0f), Marmoreal stand-in" % pv["zoom_out_distance_uu"],
         "marmoreal", K.game_view((0, 0, 0), pv["zoom_out_distance_uu"]), None, "t2b"),
        ("zoomout065-sarpedon", "game: zoom-out 0.65x, Sarpedon damp stand-in", "sarpedon",
         K.game_view((0, 0, 0), pv["zoom_out_distance_uu"]), None, "t2b"),
        ("follow16-nearE", "game: 1.6x follow on a near-east space (UE 300, 250)", "marmoreal",
         K.game_view((300, 250, 28), pv["follow_distance_uu"]), None, "t2b"),
        ("diag-corner-NE-low", "NOT a game view: low three-quarter of the near-east corner (T2b)", "marmoreal",
         (K.ue(1350, 1250, 180), K.ue(700, 380, -90)), None, "t2b"),
        ("diag-corner-NE-low-T2-before", "NOT a game view: the same camera on the T2 tray (before)", "sarpedon",
         (K.ue(1350, 1250, 180), K.ue(700, 380, -90)), None, "t2"),
        ("diag-front-ortho", "NOT a game view: orthographic front elevation of the near side (UE +Y)", "marmoreal",
         (K.ue(0, 2500, -100), K.ue(0, 0, -100)), 17.5, "t2b"),
    ]
    info = {"schema": "unmatched.table-base-t2b.preview/1", "renderer": "Cycles CPU", "samples": sc.cycles.samples,
            "resolution": pv["resolution"], "note": __doc__.split("\n\n")[1].replace("\n", " "), "shots": []}
    for name, title, look, (c, f), ortho, which in shots:
        t2b.hide_render = which != "t2b"
        t2.hide_render = which != "t2"
        t2b.data.materials.clear()
        t2b.data.materials.append(mats[look])
        path = out / ("tray-t2b-%s.jpg" % name)
        K.render(sc, cam, path, c, f, ortho)
        info["shots"].append({"file": path.name, "title": title, "look": look,
                              "cameraUE": [round(c.x * 100, 1), round(-c.y * 100, 1), round(c.z * 100, 1)],
                              "targetUE": [round(f.x * 100, 1), round(-f.y * 100, 1), round(f.z * 100, 1)]})
        print("T2B-PREVIEW", path.name, flush=True)
    K.write_json(out / "preview.json", info)


main()
