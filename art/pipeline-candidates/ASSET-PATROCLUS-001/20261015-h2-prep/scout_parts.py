"""Read-only GLB scout; run only with Blender --background --factory-startup.
All generated files go to this script's folder. No blend/FBX/texture bake.
"""
import sys
sys.dont_write_bytecode = True
import colorsys
import hashlib
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
sys.path.insert(0, str(REPO / "tools/tripo-pipeline/blender"))
from h2_bake import bl_util as U

U.require_background()
SRC = REPO / "art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-tripo/source/patroclus-h2-tripo-e0b4d474-parts24.glb"

def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def main():
    before = digest(SRC)
    scene = U.reset()
    parts = U.import_glb_parts(SRC, "SCOUT_")
    assert len(parts) == 24, len(parts)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studiolight_rotate_z = 0.35
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.4
    scene.display.shading.curvature_valley_factor = 1.1
    scene.display.shading.background_type = "WORLD"
    scene.world = bpy.data.worlds.new("ScoutWorld")
    scene.world.color = (0.055, 0.065, 0.085)
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    cam_data = bpy.data.cameras.new("ScoutCamera")
    cam = bpy.data.objects.new("ScoutCamera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.type = "ORTHO"
    cam_data.clip_start = 0.0001
    cam_data.clip_end = 100
    (OUT / "renders").mkdir(exist_ok=True)
    inv = {}
    for idx, (name, obj) in enumerate(parts.items()):
        co = U.coords(obj.data)
        col = colorsys.hsv_to_rgb((idx * 0.618034) % 1, 0.46, 0.88)
        obj.color = (*col, 1.0)
        inv[name] = {"vertices": len(co), "triangles": U.triangles(obj.data),
                     "source_blender_bounds": [U.rv(co.min(0)), U.rv(co.max(0))],
                     "color_rgb": [round(c * 255) for c in col],
                     "material_count": len(obj.data.materials), "uv_layers": len(obj.data.uv_layers)}

    def render(names, view, filename, size=420):
        coords = np.vstack([U.coords(parts[n].data) for n in names])
        for name, obj in parts.items():
            obj.hide_render = name not in names
        lo, hi = coords.min(0), coords.max(0)
        center = Vector((lo + hi) / 2)
        direction = Vector(view).normalized()
        cam.location = center + direction * max(float(np.linalg.norm(hi - lo)) * 3, 1)
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        local = (coords - np.array(center)) @ np.array(cam.rotation_euler.to_matrix())
        cam_data.ortho_scale = max(float(np.ptp(local[:, 0])), float(np.ptp(local[:, 1]))) * 1.14
        scene.render.resolution_x = size
        scene.render.resolution_y = size
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(OUT / "renders" / filename)
        bpy.ops.render.render(write_still=True)

    # Same global directions for all isolates; front sign is verified visually afterwards.
    views = {"front34": (0.55, -2.0, 0.40), "back34": (-0.55, 2.0, 0.40)}
    for name in parts:
        for view, pos in views.items():
            render([name], pos, name + "-" + view + ".png")
        print("SCOUT_PART_DONE", name, flush=True)
    for label, pos in {**views, "ownright": (-2.0, -0.15, 0.25), "front": (0, -2, 0), "back": (0, 2, 0)}.items():
        render(list(parts), pos, "assembled-" + label + ".png", 1200)
    card_path = REPO / "art/pipeline-candidates/ASSET-PATROCLUS-001/evidence/acceptance-concept/20261015-sheet-r1/card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    checked = [{**x, "actual_sha256": digest(REPO / x["path"]),
                "matches": digest(REPO / x["path"]) == x["sha256"]} for x in card["accepted_object"]]
    assert all(x["matches"] for x in checked), checked
    after = digest(SRC)
    assert before == after
    data = {"schema": "patroclus.h2-prep-source-inventory/1", "source": {"path": str(SRC.relative_to(REPO)).replace("\\", "/"), "bytes": SRC.stat().st_size, "sha256_before": before, "sha256_after": after, "untouched": before == after},
            "blender_version": bpy.app.version_string, "part_count": len(parts),
            "total_triangles": sum(p["triangles"] for p in inv.values()),
            "coordinate_frame": "Blender glTF import; node transforms applied in memory by existing h2_bake.bl_util.import_glb_parts; source not written",
            "views": views, "acceptance_card": {"path": str(card_path.relative_to(REPO)).replace("\\", "/"), "sha256": digest(card_path), "score": card["score"], "verdict": card["verdict"], "accepted_objects_verified": checked},
            "parts": inv, "claims": {"final_bake": False, "rig_authored": False, "geometry_accepted": False}}
    (OUT / "source-inventory.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("SCOUT_COMPLETE", len(parts), data["total_triangles"], before, flush=True)

main()
