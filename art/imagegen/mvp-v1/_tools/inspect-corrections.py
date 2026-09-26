"""Read-only PNG measurements for the correction brief; no raster is edited."""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
m = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8-sig'))
rows = []
for entry in m.get('correctionDeliverables', []):
    p = ROOT / entry['path']
    assert hashlib.sha256(p.read_bytes()).hexdigest() == entry['sha256'], p
    image = Image.open(p).convert('RGBA')
    a = np.asarray(image)
    rgb = a[..., :3].astype(float)
    h, w = a.shape[:2]
    border = np.concatenate([rgb[:20].reshape(-1, 3), rgb[-20:].reshape(-1, 3), rgb[:, :20].reshape(-1, 3), rgb[:, -20:].reshape(-1, 3)])
    luminance = border @ np.array([.2126, .7152, .0722])
    bg = np.median(border, axis=0)
    mask = a[..., 3] > 8 if entry['alpha'] else np.max(np.abs(rgb-bg), axis=2) > 15
    ys, xs = np.nonzero(mask)
    bounds = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if xs.size else None
    edge_alpha = np.concatenate([a[0,:,3], a[-1,:,3], a[:,0,3], a[:,-1,3]])
    rows.append({'path':entry['path'], 'size':[w,h], 'exact1024':w==h==1024,
                 'backgroundBorderMeanRgb':[round(float(v),3) for v in bg],
                 'backgroundBorderLuminanceStd':round(float(luminance.std()),4),
                 'backgroundBorderStdBelow3':None if entry['alpha'] else bool(luminance.std()<3),
                 'backgroundStatisticApplicable':not entry['alpha'],
                 'estimatedForegroundBounds':bounds,
                 'estimatedBaselineFraction':round((bounds[3]+1)/h,5) if bounds else None,
                 'estimatedMarginsFraction':[round(bounds[0]/w,4),round(bounds[1]/h,4),round((w-1-bounds[2])/w,4),round((h-1-bounds[3])/h,4)] if bounds else None,
                 'outerBorderMaxAlpha':int(edge_alpha.max())})
report={'method':'Original PNG hashes verified. RGB background statistics use 20-pixel border, not full background segmentation. Foreground bounds use RGB distance >15 from border median, or alpha >8. Geometry, view identity and topology require visual review.', 'images':rows}
(ROOT/'correction-metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'inspected':len(rows),'exact1024':sum(r['exact1024'] for r in rows),'borderStdFailures':[r['path'] for r in rows if r['backgroundBorderStdBelow3'] is False]}))
