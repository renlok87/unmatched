"""Пересоздаёт отслеживаемые фикстуры валидатора клипов P1.6 (только headless).

ТОЛЬКО headless (`blender -b`): вызывается read_factory_settings, который в живом
Blender (MCP :9876/:9877) выгружает аддон MCP и очищает сцену. Без `-b` скрипт бросает
RuntimeError и ничего не делает; процесс Blender остаётся жив. SystemExit/sys.exit/os._exit
для guard не годятся: в живом Blender они завершают весь процесс.

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/tripo-pipeline/anim/make_fixtures.py -- [bvh|glb|tripo|all] [--out-dir=<dir>]

bvh   — round-trip BVH из AM_Medusa_LungeAttack.fbx (Z-up, как пишет Blender) для ветки BVH;
glb   — GLB из того же FBX: меш со скином на арматуре, без картинок и материалов, для ветки GLB
        (при импорте glTF появляется служебный Icosphere, арматура масштабирована 0.01);
tripo — FBX пресета Tripo «стоя_отдых», извлечённый из source/*.zip (без текстур .fbm).
Исходники только читаются. По умолчанию пишет в
art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/fixtures/.
"""
import os
import sys
import zipfile

import bpy

if not bpy.app.background:
    # RuntimeError, не SystemExit: SystemExit в живом Blender завершает весь процесс.
    raise RuntimeError("make_fixtures.py: только headless (blender -b)")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUN = os.path.join(REPO, "art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16")
LUNGE_FBX = os.path.join(REPO, "blender/ASSET-MEDUSA-001/export/AM_Medusa_LungeAttack.fbx")
TRIPO_ZIP = os.path.join(RUN, "source/d562f057-ue5-forced-anim-preset-stoya-otdyh-inplace-fbx-blender.zip")
TRIPO_MEMBER = "tripo_convert_93b4445d-b871-4057-a0d7-1317f45a1548.fbx"


def load_lunge():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=LUNGE_FBX, use_anim=True)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    return arm


def make_bvh(out_dir):
    arm = load_lunge()
    s, e = [int(round(x)) for x in arm.animation_data.action.frame_range]
    out = os.path.join(out_dir, "AM_Medusa_LungeAttack.bvh")
    bpy.ops.export_anim.bvh(filepath=out, frame_start=s, frame_end=e)
    print("FIXTURE_OK", out, os.path.getsize(out))


def make_glb(out_dir):
    arm = load_lunge()
    for ob in bpy.context.scene.objects:
        ob.select_set(ob.type in ("ARMATURE", "MESH"))
    out = os.path.join(out_dir, "AM_Medusa_LungeAttack.glb")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True,
                              export_image_format="NONE", export_materials="NONE",
                              export_animations=True)
    print("FIXTURE_OK", out, os.path.getsize(out))


def make_tripo(out_dir):
    sub = os.path.join(out_dir, "tripo-preset-stoya-otdyh-d562")
    os.makedirs(sub, exist_ok=True)
    out = os.path.join(sub, TRIPO_MEMBER)
    with zipfile.ZipFile(TRIPO_ZIP) as z, open(out, "wb") as f:
        f.write(z.read(TRIPO_MEMBER))
    print("FIXTURE_OK", out, os.path.getsize(out))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    what = next((a for a in argv if not a.startswith("--")), "all")
    out_dir = next((a.split("=", 1)[1] for a in argv if a.startswith("--out-dir=")), os.path.join(RUN, "fixtures"))
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    jobs = {"bvh": make_bvh, "glb": make_glb, "tripo": make_tripo}
    if what not in jobs and what != "all":
        raise SystemExit(f"unknown fixture: {what}")
    for name, fn in jobs.items():
        if what in (name, "all"):
            fn(out_dir)


main()
