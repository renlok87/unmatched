from pathlib import Path
import json
import hashlib
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont

ROOT = Path('C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hud-icons-v2/glyphs')
records = json.loads((ROOT / 'qa/generation-record.json').read_text(encoding='utf-8'))
(ROOT / 'prompts').mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
sheet = Image.new('RGB', (1110, len(records) * 170 + 50), (34, 34, 34))
draw = ImageDraw.Draw(sheet)
draw.text((18, 12), 'Generated mask | overview 128px | 16px x4 | 24px native / x6 | 32px native / x4', font=font, fill='white')
measurements = []
for index, rec in enumerate(records):
    source = Image.open(rec['source']).convert('RGBA')
    # Remove transparent-extraction residue, retain the generated geometry.
    alpha = np.asarray(source.getchannel('A')) >= 128
    labels, count = ndimage.label(alpha)
    areas = np.bincount(labels.ravel())
    keep = areas >= max(32, alpha.sum() * 0.0002)
    keep[0] = False
    alpha = keep[labels]
    alpha = ndimage.median_filter(alpha, size=3)
    mask = Image.fromarray(alpha.astype(np.uint8) * 255)
    bbox = mask.getbbox()
    assert bbox, rec['id']
    crop = mask.crop(bbox)
    factor = 768 / max(crop.size)
    extent = tuple(round(v * factor) for v in crop.size)
    crop = crop.resize(extent, Image.Resampling.LANCZOS)
    final_alpha = Image.new('L', (1024, 1024), 0)
    final_alpha.paste(crop, ((1024 - extent[0]) // 2, (1024 - extent[1]) // 2))
    result = Image.new('RGBA', (1024, 1024), (255, 255, 255, 0))
    result.putalpha(final_alpha)
    target = ROOT / (rec['id'] + '.png')
    result.save(target)
    (ROOT / 'prompts' / (rec['id'] + '.txt')).write_text(rec['prompt'] + '\n', encoding='utf-8')
    y = 50 + index * 170
    draw.text((18, y + 58), rec['id'], font=font, fill='white')
    overview = result.resize((128, 128), Image.Resampling.LANCZOS)
    sheet.paste(overview, (265, y + 14), overview)
    for size, x, zoom in [(16, 430, 4), (24, 540, 6), (32, 770, 4)]:
        reduced = result.resize((size, size), Image.Resampling.LANCZOS)
        reduced.save(ROOT / 'qa' / (rec['id'] + '-' + str(size) + 'px.png'))
        sheet.paste(reduced, (x, y + 20), reduced)
        magnified = reduced.resize((size * zoom, size * zoom), Image.Resampling.NEAREST)
        sheet.paste(magnified, (x + 45, y + 14), magnified)
    arr = np.asarray(result)
    visible = arr[:, :, 3] > 0
    assert np.all(arr[:, :, :3][visible] == 255), rec['id']
    assert result.size == (1024, 1024) and result.mode == 'RGBA'
    assert final_alpha.getextrema() == (0, 255)
    item = {'id': rec['id'], 'file': rec['id'] + '.png', 'prompt': 'prompts/' + rec['id'] + '.txt', 'width': 1024, 'height': 1024, 'alpha': True, 'attempts': rec['attempts'], 'status': 'generated', 'review': 'pending', 'source_dimensions': list(source.size), 'bbox': list(final_alpha.point(lambda p: 255 if p >= 128 else 0).getbbox()), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    measurements.append(item)
sheet.save(ROOT / 'qa/readability-sheet.png')
manifest = {'schema': 'unmatched.hud-icons-v2.glyphs/1', 'date': '2026-10-03', 'brief': 'docs/unreal/contracts/hud/IMAGEGEN-BRIEF-icons.md', 'generator': 'ImageGen (Codex)', 'normalization': {'authorized_by_user': True, 'description': 'Generated alpha threshold 128; remove tiny alpha residue components; 3px median edge cleanup; preserve generated silhouette; fit extent to 768px on centered 1024px canvas; exact white RGB; antialiased alpha.', 'script': 'qa/normalize-and-check.py'}, 'glyphs': measurements}
(ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
expected = {r['id'] + '.png' for r in records}
actual = {p.name for p in ROOT.glob('*.png')}
assert actual == expected, (actual, expected)
assert all(name == name.strip() for name in actual)
for row in measurements:
    print(row['file'], '1024x1024 RGBA #FFFFFF', 'attempts=' + str(row['attempts']), 'bbox=' + str(row['bbox']))
print('Filenames exact; manifest JSON valid; visual review pending.')
