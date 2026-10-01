"""ASSET-MAP-FRAME-002: review renders of the EXPORTED frame modules, assembled by reports/frame-layout.json
(headless Blender, Cycles on the CPU).

  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-MAP-FRAME-002/scripts/frame_preview.py -- <frame-params.json>

Every module FBX is read back and placed per frame-layout.json (board-actor space, yaw, scaleX 1.0). Context: a neutral
map proxy plate (891.333 x 577.333 at z -0.5; NOT the map illustration, ENV-U3) and a flat earth proxy of the themed
ground (z -1) on the tray rectangle; the "before" shot puts the current frame (4 cube bars 24 x 14, z -10..+4, the same
wood) in the same place. Wood = T_old_wood_D/N/ORM_1024 (the ART-005 wood that M_MapFrameWood samples) with the P4
frameWood grade approximated (linear x0.4563, saturation 0.75); iron = T_MapFrame002_Iron_*. Neutral review rig (key
along (-55, 30, 0)), not the night profiles. Output: <run>/preview/frame-*.jpg + preview.json.
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

WOOD = REPO / "art/imagegen/mvp-v1/materials/export"


def wood_material():
    m = K.textured_material("frame_wood_preview", WOOD / "T_old_wood_D_1024.png", WOOD / "T_old_wood_N_1024.png",
                            WOOD / "T_old_wood_ORM_1024.png")
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    src = b.inputs["Base Color"].links[0].from_socket
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = 0.75
    nt.links.new(src, hs.inputs["Color"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(hs.outputs["Color"], mul.inputs[6])
    mul.inputs[7].default_value = (0.4563, 0.4563, 0.4563, 1.0)
    nt.links.new(mul.outputs[2], b.inputs["Base Color"])
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
    out = run / "preview"
    lay = json.loads((run / "reports" / "frame-layout.json").read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = K.setup_cycles_cpu(pv["samples"], pv["resolution"])
    wood = wood_material()
    exp = run / "export"
    pre = P["iron_textures"]["prefix"]
    iron = K.textured_material("frame_iron_preview", exp / ("%s_BC.png" % pre), exp / ("%s_N.png" % pre),
                              exp / ("%s_ORM.png" % pre))
    new = []
    for inst in lay["instances"]:
        objs = K.import_fbx_placed(exp / ("%s.fbx" % lay["meshes"][inst["module"]]), inst["loc"], inst["yawDeg"])
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(wood)
            o.data.materials.append(iron)
            new.append(o)
    hx, hy = lay["mapHalfUU"]
    F = float(P["map"]["frame_uu"])
    old = []
    for n, lo, hi in (("OldN", (-hx - F, -hy - F), (hx + F, -hy)), ("OldS", (-hx - F, hy), (hx + F, hy + F)),
                      ("OldW", (-hx - F, -hy), (-hx, hy)), ("OldE", (hx, -hy), (hx + F, hy))):
        old.append(box(n, K.ue(lo[0], hi[1], -10.0), K.ue(hi[0], lo[1], 4.0), wood))
    box("MapProxy", K.ue(-hx, hy, -1.0), K.ue(hx, -hy, -0.5), K.flat_material("map_proxy", (0.30, 0.31, 0.27), 0.8))
    gmat = K.flat_material("ground", (0.075, 0.06, 0.045))
    # non-overlapping strips (coincident faces would render black in Cycles)
    gx = hx + F - 2
    for n, lo, hi in (("GN", (-gx, -515), (gx, -hy - F + 2)), ("GS", (-gx, hy + F - 2), (gx, 425)),
                      ("GW", (-780, -515), (-gx, 425)), ("GE", (gx, -515), (780, 425))):
        box(n, K.ue(lo[0], hi[1], -3.0), K.ue(hi[0], lo[1], -1.0), gmat)
    K.review_rig(sc, key_energy=2.6, fill_energy=0.6)
    cam = K.camera(sc, pv["hfov_deg"])
    shots = [
        ("k1", "game: K1 x1.25 (D %.0f) on the map centre" % pv["k1_distance_uu"], K.game_view((0, 0, 0), pv["k1_distance_uu"]),
         None, "new"),
        ("closeup-corner-NE", "game camera model, close (D %.0f) on the near-east corner" % pv["closeup_distance_uu"],
         K.game_view((400, 250, 0), pv["closeup_distance_uu"]), None, "new"),
        ("closeup-corner-NE-before", "the same camera on the current frame (cube bars, before)",
         K.game_view((400, 250, 0), pv["closeup_distance_uu"]), None, "old"),
        ("follow16-near-mid", "game: 1.6x follow (D %.0f) on the near side's middle (mid-edge bracket)" % pv["follow_distance_uu"],
         K.game_view((0, 250, 0), pv["follow_distance_uu"]), None, "new"),
        ("diag-corner-NE-low", "NOT a game view: low three-quarter of the near-east corner",
         (K.ue(560, 420, 60), K.ue(440, 285, 0)), None, "new"),
        ("diag-mid-far-low", "NOT a game view: low view of the far side's middle bracket from inside the map",
         (K.ue(-60, -150, 45), K.ue(0, -300, 4)), None, "new"),
    ]
    info = {"schema": "unmatched.map-frame-002.preview/1", "renderer": "Cycles CPU", "samples": sc.cycles.samples,
            "resolution": pv["resolution"], "note": __doc__.split("\n\n")[1].replace("\n", " "), "shots": []}
    for name, title, (c, f), ortho, which in shots:
        for o in new:
            o.hide_render = which != "new"
        for o in old:
            o.hide_render = which != "old"
        path = out / ("frame-%s.jpg" % name)
        K.render(sc, cam, path, c, f, ortho)
        info["shots"].append({"file": path.name, "title": title, "frame": which,
                              "cameraUE": [round(c.x * 100, 1), round(-c.y * 100, 1), round(c.z * 100, 1)],
                              "targetUE": [round(f.x * 100, 1), round(-f.y * 100, 1), round(f.z * 100, 1)]})
        print("FRAME-PREVIEW", path.name, flush=True)
    K.write_json(out / "preview.json", info)


main()
