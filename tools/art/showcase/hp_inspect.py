# SEL showcase: list the objects of the H2 work blends (frames, UV layers, sizes) before baking the game look onto the
# high-poly. Run: blender -b <blend> -P tools/art/showcase/hp_inspect.py
import bpy

print("BLEND", bpy.data.filepath)
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    if o.type != "MESH":
        print(f"  {o.name:36s} {o.type}")
        continue
    me = o.data
    uvs = [u.name for u in me.uv_layers]
    mats = [m.name if m else "-" for m in me.materials]
    bb = [o.matrix_world @ __import__("mathutils").Vector(c) for c in o.bound_box]
    mn = [min(v[i] for v in bb) for i in range(3)]
    mx = [max(v[i] for v in bb) for i in range(3)]
    print(f"  {o.name:36s} v={len(me.vertices):8d} f={len(me.polygons):8d} uv={uvs} mats={mats[:3]}{'...' if len(mats) > 3 else ''} "
          f"bb=({mn[0]:+.3f},{mn[1]:+.3f},{mn[2]:+.3f})..({mx[0]:+.3f},{mx[1]:+.3f},{mx[2]:+.3f})")
