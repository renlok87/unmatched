"""Face readability proxy in UE K2 frames using the pixel-aligned Blender facial-feature mask."""
import json
import numpy as np
from PIL import Image
from scipy import ndimage


def lum(rgb):
    c = rgb / 255.0
    l = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]


res = {}
for tag in ("v2", "v3"):
    idm = np.array(Image.open(f"blender/renders/idsplit-k2-front-d300-{tag}.png").convert("RGBA")).astype(int)
    a = idm[..., 3] > 127
    face = a & (np.abs(idm[..., :3] - [255, 0, 0]).sum(axis=2) < 30)
    crown = a & (np.abs(idm[..., :3] - [0, 255, 0]).sum(axis=2) < 30)
    fe = ndimage.binary_erosion(face, iterations=1)
    # face_eroded_px = pixels the gradient statistics use; the sum grows with this area,
    # the per-pixel mean does not (vc 2026-09-28: +64..69 % sum vs +4..8 % mean).
    # Throat (face part below z=42 cm) is painted (1, .5, 0) in b8 = sRGB (255, 188, 0). The first run
    # matched (255, 128, 0) and stored neck_px = 0; fixed 2026-09-28. quiver = whole visible quiver.
    throat = a & (np.abs(idm[..., :3] - [255, 188, 0]).sum(axis=2) < 30)
    quiver = a & (np.abs(idm[..., :3] - [255, 255, 255]).sum(axis=2) < 30)
    r = {"face_features_px": int(face.sum()), "face_eroded_px": int(fe.sum()), "throat_px": int(throat.sum()),
         "quiver_px": int(quiver.sum()), "crown_px": int(crown.sum())}
    for light in ("cobble", "forest-probe", "paddock-probe"):
        im = np.array(Image.open(f"frames_ev13/ue-mcp-{light}-d10-k2-d300-{tag}.png").convert("RGB")).astype(float)
        L = lum(im); g = np.hypot(ndimage.sobel(L, 0), ndimage.sobel(L, 1))
        r[light] = {"face_lum_mean": round(float(L[fe].mean()), 4), "face_lum_std": round(float(L[fe].std()), 4),
                    "face_gradient_mean": round(float(g[fe].mean()), 4), "face_gradient_sum": round(float(g[fe].sum()), 1),
                    "crown_lum_mean": round(float(L[crown].mean()), 4)}
    res[tag] = r
json.dump(res, open("ue_face_metrics.json", "w"), indent=1)
