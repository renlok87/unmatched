"""ASSET-ENV-M-BACKWALL-001: review renders of the EXPORTED back wall modules behind the Marmoreal colonnade
(headless Blender, Cycles on the CPU).

  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/scripts/backwall_preview.py -- <backwall-params.json>

The modules are read back from their FBX and placed per reports/backwall-layout.json; the colonnade (SM_Env_ArcadeBay
x4, SM_Env_Portal, the two urns and the NW/NE cypresses) is placed per the shipped marmoreal.layout.json with its env-kit
BC textures (M_UM_Figure look, not the MI recolours). Context: a flat paving-grey ground on the tray at z -1 and a
neutral map plate (NOT the map illustration, ENV-U3). The wall material = T_Env_BackWall_BC/N/ORM, emission =
T_Env_BackWall_E x warm colour x emission_strength (a stand-in for M_EnvProp's EmissiveWindow). Neutral review rig
(key along (-55, 30, 0)) dimmed so the glow reads. Output: <run>/preview/backwall-*.jpg + preview.json.
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

KIT = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/export"
LAYOUT = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts/marmoreal.layout.json"


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
    lay = json.loads((run / "reports" / "backwall-layout.json").read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = K.setup_cycles_cpu(pv["samples"], pv["resolution"])
    exp = run / "export"
    pre = P["texture_prefix"]
    wall = K.textured_material("backwall", exp / ("%s_BC.png" % pre), exp / ("%s_N.png" % pre), exp / ("%s_ORM.png" % pre),
                               emission=(exp / ("%s_E.png" % pre), (1.0, 0.62, 0.3), float(pv["emission_strength"])))
    walls = []
    for e in lay["props"]:
        name = e["mesh"].rsplit("/", 1)[-1]
        for o in K.import_fbx_placed(exp / ("%s.fbx" % name), e["loc"], e["yawDeg"], e["scale"]):
            o.data.materials.clear()
            o.data.materials.append(wall)
            walls.append(o)
    ml = json.loads(LAYOUT.read_text(encoding="utf-8"))
    kit_mats = {}
    for p in ml["props"]:
        name = p["mesh"].rsplit("/", 1)[-1]
        if name not in ("SM_Env_ArcadeBay", "SM_Env_Portal", "SM_Env_Urn", "SM_Env_Cypress"):
            continue
        if name not in kit_mats:
            stem = name.replace("SM_", "T_")
            kit_mats[name] = K.textured_material(name + "_m", KIT / ("%s_BC.png" % stem), KIT / ("%s_N.png" % stem),
                                                 KIT / ("%s_ORM.png" % stem))
        for o in K.import_fbx_placed(KIT / ("%s.fbx" % name), p["loc"], p["yawDeg"], p["scale"]):
            o.data.materials.clear()
            o.data.materials.append(kit_mats[name])
    box("Ground", K.ue(-780, 425, -3.0), K.ue(780, -515, -1.0), K.flat_material("ground", (0.2, 0.2, 0.19), 0.6))
    box("MapProxy", K.ue(-445.667, 288.667, -1.0), K.ue(445.667, -288.667, -0.5), K.flat_material("map", (0.3, 0.3, 0.26)))
    K.review_rig(sc, key_energy=1.2, fill_energy=0.25, world_rgb=(0.006, 0.008, 0.016))
    cam = K.camera(sc, pv["hfov_deg"])
    shots = [
        ("follow16-colonnade", "game: 1.6x follow (D %.0f) on the far colonnade" % pv["follow_distance_uu"],
         K.game_view((0, -330, 40), pv["follow_distance_uu"])),
        ("k1", "game: K1 x1.25 (D %.0f) on the map centre" % pv["k1_distance_uu"], K.game_view((0, 0, 0), pv["k1_distance_uu"])),
        ("zoomout065", "game: zoom-out 0.65x (D %.0f)" % pv["zoom_out_distance_uu"], K.game_view((0, 0, 0), pv["zoom_out_distance_uu"])),
        ("diag-through-arches", "NOT a game view: low view of the arcade, the lit wall behind the arches",
         (K.ue(-150, -150, 70), K.ue(-200, -460, 80))),
        ("diag-wall-only-ortho", "NOT a game view: orthographic front elevation of the wall row alone",
         (K.ue(0, 1000, 120), K.ue(0, -460, 120))),
    ]
    info = {"schema": "unmatched.env-m-backwall.preview/1", "renderer": "Cycles CPU", "samples": sc.cycles.samples,
            "resolution": pv["resolution"], "note": __doc__.split("\n\n")[1].replace("\n", " "), "shots": []}
    others = [o for o in sc.objects if o.type == "MESH" and o not in walls]
    for name, title, (c, f) in shots:
        only = name.endswith("wall-only-ortho")
        for o in others:
            o.hide_render = only
        path = run / "preview" / ("backwall-%s.jpg" % name)
        K.render(sc, cam, path, c, f, 9.0 if only else None)
        info["shots"].append({"file": path.name, "title": title,
                              "cameraUE": [round(c.x * 100, 1), round(-c.y * 100, 1), round(c.z * 100, 1)],
                              "targetUE": [round(f.x * 100, 1), round(-f.y * 100, 1), round(f.z * 100, 1)]})
        print("BACKWALL-PREVIEW", path.name, flush=True)
    K.write_json(run / "preview" / "preview.json", info)


main()
