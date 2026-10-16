# SEL showcase: Arthur's head (tripo_part_6) after the H2 symmetrize on the HIGH-poly - topology of the mirror seam and
# the Tripo base-colour size. Run: blender -b --factory-startup --python tools/art/showcase/hp_head_check.py
import json
import sys
from pathlib import Path

import bmesh
import bpy

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools/tripo-pipeline/blender/h2_bake_arthur"))
import bl  # noqa: E402
import repairs  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
profile = json.loads((REPO / "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-skeletal-um-fbx-v1-h2.json").read_text(encoding="utf-8"))
high, _ = bl.import_glb_parts(REPO / "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-tripo/source/king-arthur-h2-tripo-c24eeff0-tex8k-pbr.glb", "HP")
repairs.apply_geometry_repairs(high, profile)
head = high["tripo_part_6"]
if "--fix" in sys.argv:
    sys.path.insert(0, str(REPO / "tools/art/showcase"))
    import hp_lookdev_bake  # noqa: E402
    print("SEAMFIX", json.dumps(hp_lookdev_bake.fix_mirror_seam(head, -0.0077)))
bm = bmesh.new()
bm.from_mesh(head.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
plane = -0.0077
boundary = [e for e in bm.edges if len(e.link_faces) == 1]
nonman = [e for e in bm.edges if len(e.link_faces) > 2]
seam_b = [e for e in boundary if all(abs(v.co.x - plane) < 2e-4 for v in e.verts)]
front = [e for e in seam_b if all(v.co.y < -0.03 for v in e.verts)]
img = None
for n in head.data.materials[0].node_tree.nodes:
    if n.type == "TEX_IMAGE" and n.image and any(l.to_socket.name == "Base Color" for l in n.outputs["Color"].links):
        img = n.image
print("HEADCHK", json.dumps({"verts": len(bm.verts), "faces": len(bm.faces), "boundary_edges": len(boundary),
                             "nonmanifold_edges": len(nonman), "boundary_on_mirror_plane": len(seam_b),
                             "boundary_on_plane_front_face": len(front),
                             "tripo_bc": list(img.size) if img else None}))
