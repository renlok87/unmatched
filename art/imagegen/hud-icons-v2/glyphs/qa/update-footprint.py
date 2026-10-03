from pathlib import Path
import json
import hashlib
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont

ROOT = Path('C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hud-icons-v2/glyphs')
manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
record = next(r for r in json.loads((ROOT / 'qa/generation-record.json').read_text(encoding='utf-8')) if r['id'] == 'glyph-footprint')
others_before = {g['file']: hashlib.sha256((ROOT / g['file']).read_bytes()).hexdigest() for g in manifest['glyphs'] if g['id'] != 'glyph-footprint'}
source = Image.open(record['source']).convert('RGBA')
alpha = np.asarray(source.getchannel('A')) >= 128
labels, _ = ndimage.label(alpha)
areas = np.bincount(labels.ravel())
keep = areas >= max(32, alpha.sum() * 0.0002)
keep[0] = False
alpha = ndimage.median_filter(keep[labels], size=3)
mask = Image.fromarray(alpha.astype(np.uint8) * 255)
crop = mask.crop(mask.getbbox())
factor = 768 / max(crop.size)
extent = tuple(round(v * factor) for v in crop.size)
crop = crop.resize(extent, Image.Resampling.LANCZOS)
final_alpha = Image.new('L', (1024, 1024), 0)
final_alpha.paste(crop, ((1024 - extent[0]) // 2, (1024 - extent[1]) // 2))
result = Image.new('RGBA', (1024, 1024), (255, 255, 255, 0))
result.putalpha(final_alpha)
assert ndimage.label(np.asarray(final_alpha) >= 128)[1] == 2, 'Must have exactly two complete solid soles'
assert not (ndimage.binary_fill_holes(np.asarray(final_alpha) >= 128) & (np.asarray(final_alpha) < 128)).any(), 'No internal holes in boot prints'
result.save(ROOT / 'glyph-footprint.png')
(ROOT / 'prompts/glyph-footprint.txt').write_text(record['prompt'] + '\n', encoding='utf-8')
checks = {}
for size in (16, 24, 32):
    thumb = result.resize((size, size), Image.Resampling.LANCZOS)
    thumb.save(ROOT / 'qa' / ('glyph-footprint-' + str(size) + 'px.png'))
    ink = np.asarray(thumb.getchannel('A')) >= 128
    labels, count = ndimage.label(ink)
    holes = ndimage.label(ndimage.binary_fill_holes(ink) & ~ink)[1]
    boxes = ndimage.find_objects(labels)
    centroids = ndimage.center_of_mass(ink, labels, range(1, count + 1))
    assert count == 2 and holes == 0, (size, count, holes)
    sorted_centroids = sorted(centroids, key=lambda c: c[1])
    assert sorted_centroids[0][0] < sorted_centroids[1][0], 'Left footprint must be above right footprint'
    gap = float(ndimage.distance_transform_edt(labels != 1)[labels == 2].min())
    checks[str(size)] = {'solid_components': count, 'internal_holes': holes, 'min_component_distance_px': gap, 'centroids_yx': [[float(v) for v in c] for c in sorted_centroids]}
    print('glyph-footprint', size, 'px:', json.dumps(checks[str(size)]))
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
sheet = Image.new('RGB', (1110, len(manifest['glyphs']) * 170 + 50), (34, 34, 34))
draw = ImageDraw.Draw(sheet)
draw.text((18, 12), 'Generated mask | overview 128px | 16px x4 | 24px native / x6 | 32px native / x4', font=font, fill='white')
for index, item in enumerate(manifest['glyphs']):
    image = Image.open(ROOT / item['file']).convert('RGBA')
    y = 50 + index * 170
    draw.text((18, y + 58), item['id'], font=font, fill='white')
    preview = image.resize((128, 128), Image.Resampling.LANCZOS)
    sheet.paste(preview, (265, y + 14), preview)
    for size, x, zoom in ((16, 430, 4), (24, 540, 6), (32, 770, 4)):
        thumb = image.resize((size, size), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y + 20), thumb)
        big = thumb.resize((size * zoom, size * zoom), Image.Resampling.NEAREST)
        sheet.paste(big, (x + 45, y + 14), big)
sheet.save(ROOT / 'qa/readability-sheet.png')
item = next(g for g in manifest['glyphs'] if g['id'] == 'glyph-footprint')
item['attempts'] = record['attempts']
item['review'] = 'pending-visual-review'
item['source_dimensions'] = list(source.size)
item['bbox'] = list(final_alpha.point(lambda p: 255 if p >= 128 else 0).getbbox())
item['sha256'] = hashlib.sha256((ROOT / item['file']).read_bytes()).hexdigest()
item['review_notes'] = 'Revised per main-session feedback: two complete solid boot soles, left above and left of right, broad spacing, no separate heel.'
item['rejected_attempts'].append('Attempt 3 rejected by main session: single sole plus detached heel reads as conflict punctuation (!). User revised design to two whole staggered boot soles.')
item['geometry_checks'] = checks
item['brief_amendment'] = 'User clarification: two staggered complete solid boot prints instead of one sole with separate heel; about 20 degrees tilt; no toe detail.'
manifest['review']['total_generation_attempts'] = sum(g['attempts'] for g in manifest['glyphs'])
manifest['review']['status'] = 'pending-footprint-visual-review'
manifest['review']['limitations'][0] = 'At 16px lightbulb base details are marginal; two revised footprint silhouettes remain separated.'
(ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
others_after = {filename: hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() for filename in others_before}
assert others_after == others_before, 'Other glyph files must stay byte-identical'
(ROOT / 'qa/footprint-update-checks.json').write_text(json.dumps({'other_eight_png_unchanged': True, 'other_eight_sha256': others_after, 'footprint_geometry': checks}, indent=2) + '\n', encoding='utf-8')
print('Other eight PNGs remain byte-identical. Footprint attempts:', item['attempts'])
