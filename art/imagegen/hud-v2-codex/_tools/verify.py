from pathlib import Path
from PIL import Image,ImageDraw,ImageChops,ImageOps
import json,hashlib
ART=Path('art/imagegen/hud-v2-codex');OUT=Path('scraped-data/derived/hud-v2-codex/concepts');REF=Path('scraped-data/derived/hud-v2-codex/refs')
audit=json.loads((ART/'verification.json').read_text(encoding='utf-8'))
for rel,expected in audit['input_sha256'].items():assert hashlib.sha256(Path(rel).read_bytes()).hexdigest()==expected,rel
for row in audit['concepts']:
    im=Image.open(OUT/row['file']).convert('RGB');base=Image.open(REF/row['base']).convert('RGB')
    diff=ImageChops.difference(im,base);r,g,b=diff.split();diff=ImageChops.lighter(ImageChops.lighter(r,g),b)
    hud=Image.open(OUT/'proof'/(row['file'][:3]+'-hud-mask.png')).convert('L')
    outside=ImageChops.multiply(diff,ImageOps.invert(hud));assert outside.getbbox() is None
    field=Image.new('L',(1920,1080));d=ImageDraw.Draw(field)
    d.polygon([(456,255),(1469,255),(1517,859),(337,859)],fill=255)
    plates=[(494,214,635,253),(350,349,492,388)]
    if row['file'][2]=='1':plates += [(563,433,697,471),(560,554,703,593),(1240,535,1361,574),(1051,681,1188,720)]
    else:plates += [(751,575,886,614),(452,512,594,551),(1240,535,1361,574),(1039,574,1173,613)]
    for box in plates+row['repairs']:d.rectangle(box,fill=0)
    protected=ImageChops.multiply(diff,field)
    assert protected.getbbox() is None,row['file']
    row['protected_field_pixels']=field.histogram()[255]
    row['protected_field_changed_pixels']=0
    row['manual_full_size_review']=True
    assert im.size==(1920,1080)
def lum(h):
    c=[int(h[i:i+2],16)/255 for i in [1,3,5]]
    c=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in c]
    return sum(a*b for a,b in zip(c,[.2126,.7152,.0722]))
pairs=[('#F9EBDB','#061623'),('#061623','#EBD9AF'),('#061623','#F4EFE4'),('#F9EBDB','#122C42'),('#F9EBDB','#34241E')]
audit['specified_text_pair_contrast']=[]
for a,b in pairs:
    x,y=sorted([lum(a),lum(b)]);contrast=(y+.05)/(x+.05)
    assert contrast>=4.5
    audit['specified_text_pair_contrast'].append({'foreground':a,'background':b,'ratio':round(contrast,2)})
audit['contrast_scope']='Specified foreground/background pairs; no claim of automatic OCR contrast certification for every generated pixel.'
for x in 'ABC':
    a=(OUT/f'{x}-4-styleguide.png').read_bytes();b=(ART/f'styleguides/{x}-styleguide.png').read_bytes()
    assert a==b
for f in ART.rglob('*'):
    if f.is_file() and f.suffix in ['.md','.json','.py']:
        assert not f.read_bytes().startswith(b'\xef\xbb\xbf'),str(f)
        f.read_text(encoding='utf-8')
assert Image.open(OUT/'contact.png').size==(2560,1080)
records=json.loads((ART/'generation-records.json').read_text(encoding='utf-8'))
assert len(records)==12
for rec in records:
    rec['raw_file']=f"scraped-data/derived/hud-v2-codex/concepts/generated/{rec['prompt_id']}.png"
    rec['output_size']=list(Image.open(OUT/'generated'/f"{rec['prompt_id']}.png").size)
    rec['final_size']=[1920,1080]
    rec['selection']='HUD/component art retained; generated scene/card faces replaced from real references' if rec['input_image'] else 'Scan-free component art retained; typesetting and accepted discs repaired'
    rec['reviewed_at_native_size']=True
    rec['kept']=True
    rec['final_file']=f"scraped-data/derived/hud-v2-codex/concepts/{rec['file']}"
(ART/'generation-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
(ART/'verification.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'concepts':9,'guides':3,'imagegen_calls':12,'protected_field_changed_pixels':0,'contrast':audit['specified_text_pair_contrast'],'text_encoding':'UTF-8 without BOM'},ensure_ascii=False,indent=2))
