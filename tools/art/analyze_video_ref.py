"""Measure camera/background stability and figure extents of an image-to-video reference clip.
Usage: python tools/art/analyze_video_ref.py <video.mp4> <out.json>

Frames are decoded by ffmpeg into a TemporaryDirectory, loaded into memory and the
directory is removed on exit (also on error), so no frame dumps are left in %TEMP%."""
import json, subprocess, sys, os, tempfile, glob
import numpy as np
from PIL import Image

vid, out = sys.argv[1], sys.argv[2]
with tempfile.TemporaryDirectory(prefix='analyze_video_ref_') as tmp:
    subprocess.run(['ffmpeg', '-v', 'error', '-i', vid, os.path.join(tmp, 'f%04d.png')], check=True)
    files = sorted(glob.glob(os.path.join(tmp, 'f*.png')))
    frames = []
    for f in files:
        with Image.open(f) as im:
            frames.append(np.asarray(im.convert('RGB')).astype(np.float32))
H, W, _ = frames[0].shape
# background colour: median of 4 corner patches of frame 0
c = 24
corners = np.concatenate([frames[0][:c, :c].reshape(-1, 3), frames[0][:c, -c:].reshape(-1, 3),
                          frames[0][-c:, :c].reshape(-1, 3), frames[0][-c:, -c:].reshape(-1, 3)])
bg = np.median(corners, axis=0)
m = int(0.06 * W)  # border strip
def border(f):
    return np.concatenate([f[:m].reshape(-1, 3), f[-m:].reshape(-1, 3), f[:, :m].reshape(-1, 3), f[:, -m:].reshape(-1, 3)])
b0 = border(frames[0])
rows = []
prev = None
for i, f in enumerate(frames):
    diff = np.abs(f - bg).max(axis=2)
    mask = diff > 28
    ys, xs = np.nonzero(mask)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    # base: dark pixels (value < 80) in the lower 25% of the frame
    lum = f.mean(axis=2)
    low = lum[int(H * 0.75):] < 80
    by, bx = np.nonzero(low)
    base = None
    if len(bx):
        yb = int(by.max())  # lowest dark row = bottom rim of the base
        row = low[max(yb - 8, 0)]  # rim row 8 px above the bottom: the body cannot cover it from the front
        rx = np.nonzero(row)[0]
        base = [int(rx.min()), int(yb - 8 + int(H * 0.75)), int(rx.max()), int(yb + int(H * 0.75))] if len(rx) else None
    bdiff = float(np.abs(border(f) - b0).mean())
    motion = float(np.abs(f - prev).mean()) if prev is not None else 0.0
    touches = bbox is not None and (bbox[0] <= 1 or bbox[1] <= 1 or bbox[2] >= W - 2 or bbox[3] >= H - 2)
    rows.append({'frame': i, 'fg_bbox': bbox, 'base_bbox': base, 'border_mad': round(bdiff, 3),
                 'motion_mad': round(motion, 3), 'fg_touches_edge': bool(touches)})
    prev = f
bases = np.array([r['base_bbox'] for r in rows if r['base_bbox']], dtype=float)
base_cx = (bases[:, 0] + bases[:, 2]) / 2
base_bottom = bases[:, 3]
base_w = bases[:, 2] - bases[:, 0]
summary = {
    'video': os.path.basename(vid), 'frames': len(frames), 'width': W, 'height': H,
    'bg_rgb': [round(float(v), 1) for v in bg],
    'border_mad_max': max(r['border_mad'] for r in rows),
    'base_center_x_range_px': round(float(base_cx.max() - base_cx.min()), 1),
    'base_bottom_y_range_px': round(float(base_bottom.max() - base_bottom.min()), 1),
    'base_width_range_px': round(float(base_w.max() - base_w.min()), 1),
    'base_width_median_px': round(float(np.median(base_w)), 1),
    'fg_touches_edge_frames': [r['frame'] for r in rows if r['fg_touches_edge']],
    'fg_bbox_union': [min(r['fg_bbox'][0] for r in rows), min(r['fg_bbox'][1] for r in rows),
                      max(r['fg_bbox'][2] for r in rows), max(r['fg_bbox'][3] for r in rows)],
    'motion_mad_max': max(r['motion_mad'] for r in rows),
    'motion_peak_frames': sorted(range(len(rows)), key=lambda i: -rows[i]['motion_mad'])[:5],
    'method': 'ffmpeg decode -> numpy; fg = max|rgb-bg|>28; base = lum<80 in lower 25%, width/center at rim row 8px above lowest dark row; border strip 6% vs frame0',
}
json.dump({'summary': summary, 'per_frame': rows}, open(out, 'w'), indent=1)
print(json.dumps(summary, indent=1))
