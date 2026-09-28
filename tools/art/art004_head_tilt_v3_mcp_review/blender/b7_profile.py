import bpy, json
import numpy as np
body = bpy.data.objects["SK_Medusa_Body_A1V3v2"]  # appended source copy (metres)
me = body.data
part = np.empty(len(me.polygons), dtype=np.int64); me.attributes["a1v3_part"].data.foreach_get("value", part)
co = np.array([v.co[:] for v in me.vertices])
fv = sorted({v for p in me.polygons if part[p.index] == 10 for v in p.vertices})
f = co[fv] * 100
out = []
for z in np.arange(38.5, 48.0, 0.5):
    m = (f[:, 2] >= z) & (f[:, 2] < z + 0.5) & (np.abs(f[:, 0] + 2.1) < 0.6)
    if m.any():
        out.append((round(float(z), 1), round(float(f[m, 1].min()), 2), int(m.sum())))
print(json.dumps(out))
