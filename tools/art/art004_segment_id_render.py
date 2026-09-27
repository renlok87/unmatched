"""Render Tripo's Medusa parts in distinct flat colors to locate the face mesh."""

import colorsys
import json
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-MEDUSA-001/tripo-source/b6253e58/medusa-segmented-retopo.glb"
OUTPUT = ROOT / "unreal/Unmatched/Artifacts/ART004Face/medusa-segment-ids.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
palette = {}
for index in range(15):
    name = f"tripo_part_{index}"
    obj = bpy.data.objects[name]
    rgb = colorsys.hsv_to_rgb(index / 15, .90, 1.0)
    material = bpy.data.materials.new("ID_" + name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*rgb, 1)
    emission.inputs["Strength"].default_value = 1
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(material)
    palette[name] = tuple(round(channel, 3) for channel in rgb)

camera_data = bpy.data.cameras.new("front")
camera_data.type = "ORTHO"
camera_data.ortho_scale = 1.25
camera = bpy.data.objects.new("front", camera_data)
bpy.context.scene.collection.objects.link(camera)
camera.location = (0, -2.0, .5)
target = Vector((0, 0, .5))
camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
scene = bpy.context.scene
scene.camera = camera
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(OUTPUT)
scene.world = bpy.data.worlds.new("ID_background")
scene.world.color = (.1, .1, .1)
scene.view_settings.view_transform = "Standard"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.render.render(write_still=True)
OUTPUT.with_suffix(".json").write_text(json.dumps(palette, indent=2) + "\n")
print("ART004_SEGMENT_ID_RENDER_COMPLETE", OUTPUT)
