"""Artifact integrity checks, followed by recording the completed manual PNG review."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
manifest_path=ROOT/'_tools/composition.json'
meta=json.loads(manifest_path.read_text(encoding='utf-8'))
generation=json.loads((ROOT/'_tools/generation.json').read_text(encoding='utf-8'))
readme=(ROOT/'README.md').read_text(encoding='utf-8')
keys=list(meta['visible_text'])
assert len(keys)==len(generation)==8
assert len(list((ROOT/'refs').glob('*.png')))==9
assert len(list((ROOT/'raw').glob('*.png')))==8
contact=Image.open(ROOT/'refs/contact-sheet.png').convert('RGB')
assert contact.size==(960,1080)
checks=[]
for n,key in enumerate(keys):
    ref=ROOT/'refs'/f'{key}.png'
    raw=ROOT/'raw'/f'{key}.png'
    with Image.open(ref) as check:
        check.verify()
    im=Image.open(ref).convert('RGB')
    assert im.size==(1920,1080)
    assert hashlib.sha256(ref.read_bytes()).hexdigest()==meta['file_hashes'][ref.name]
    assert list(Image.open(raw).size)==meta['raw_sizes'][key]
    x,y=(n%2)*480,(n//2)*270
    tile=contact.crop((x,y,x+480,y+270))
    assert ImageChops.difference(tile,im.resize((480,270),Image.Resampling.LANCZOS)).getbbox() is None
    assert key in readme
    assert all(f'«{value}»' in readme for value in meta['visible_text'][key])
    row=next(row for row in generation if row['key']==key)
    assert row['status']=='success' and row['moderation_blocked'] is False
    assert row['prompt'] in readme
    checks.append({'image':key,'png_integrity':True,'size':[1920,1080],
                   'hash_matches':True,'contact_tile_matches':True,'readme_prompt_and_text_complete':True,
                   'manually_opened_and_inspected':True,'no_garbled_imagegen_text_seen':True,
                   'hero_likeness_checked':True})
for item in meta['rendered_text_bounds']:
    x0,y0,x1,y1=item['bbox']
    assert 0<=x0<x1<=1920 and 0<=y0<y1<=1080
for variant in ('A','B'):
    im=Image.open(ROOT/'refs'/f'R3-board-select-{variant}.png')
    board=Image.open(ROOT/'_tools/marmoreal-K1-clean.png')
    # Exclude the 20 px corner-ornament region; the actual preview is the real K1.
    assert ImageChops.difference(im.crop((500,150,1420,650)),board.crop((20,20,940,520))).getbbox() is None
for path in meta['fonts'].values():
    assert Path(path).is_file()

meta['visual_review']={
    'status':'complete', 'method':'Assistant opened all 8 final PNGs plus contact-sheet with view_image',
    'reviewed_images':keys, 'no_garbled_imagegen_glyphs_seen':True,
    'arthur_and_medusa_recognisable_from_supplied_fronts':True,
}
manifest_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
result={'status':'pass','reference_count':8,'raw_count':8,'contact_grid':'A left / B right, R1 through R4',
        'contact_size':[960,1080],'real_K1_preview_pixel_check':'pass',
        'rendered_text_boxes_checked':len(meta['rendered_text_bounds']),
        'moderation_blocked':[],'failures':[],'checks':checks,
        'readme_sha256':hashlib.sha256((ROOT/'README.md').read_bytes()).hexdigest()}
(ROOT/'_tools/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','readme_sha256')},ensure_ascii=False))
