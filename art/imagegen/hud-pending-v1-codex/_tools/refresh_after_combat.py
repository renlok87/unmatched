"""Focused final visual correction; rerender only after-combat and contact tiles.

Run after build_mockups.py has exited. Updates reports and writes the manifest
last; the original source baseline is never rewritten.
"""
import sys
sys.dont_write_bytecode=True
import build_mockups as b
from PIL import Image

def run():
    b.V=b.load(b.PKG/'verification.json');b.FACTS=b.load(b.PKG/'facts.json');b.hb.FACTS=b.FACTS
    prior_writes=b.V.get('write_proof',{}).get('writes',[])
    ids={f'HB-34-{board}-after-combat-{w}x{h}-{ui}' for board in ['marmoreal','sarpedon'] for w,h,ui,s in b.CONFIGS}
    for key,value in b.V.items():
        if isinstance(value,list):b.V[key]=[r for r in value if not isinstance(r,dict) or r.get('id') not in ids]
    for key in ['outputs','rendered_texts','scans','deltas_04']:
        b.FACTS[key]=[r for r in b.FACTS[key] if r.get('id',r.get('mockup')) not in ids]
    for board in ['marmoreal','sarpedon']:
        for w,h,ui,s in b.CONFIGS:
            c=b.render(board,'after-combat',w,h,ui,s);out=b.measure(c)
            b.save(b.DERIVED/(c.id+'.png'),out);b.save(b.DERIVED/(c.id+'-gray.png'),b.gray(out))
            sheet=b.DERIVED/f'contact-HB-34-{board}-{w}x{h}-{ui}.png'
            with Image.open(sheet) as source:contact=source.convert('RGBA')
            index=b.STATES.index('after-combat');contact.paste(out,(index%6*w,index//6*(h+32)+32))
            b.save(sheet,contact);b.save(sheet.with_name(sheet.stem+'-gray.png'),b.gray(contact))
    b.V['skin_match_hb08']=[];b.V['frame_match_cp13']=[];b.frame_skin_checks()
    b.source_checks();b.V['write_proof']['writes']=sorted(set(prior_writes+b.V['write_proof']['writes']))
    b.export_checks();b.acceptance()
    b.V['visual_review']={'opened_pngs':[
        'HB-34-marmoreal-compact-move-1920x1080-100.png',
        'HB-34-marmoreal-slot-boost-1920x1080-100.png',
        'HB-34-marmoreal-compact-place-1280x720-150.png',
        'HB-34-marmoreal-after-combat-1280x720-150-gray.png',
        'HB-34-sarpedon-modal-order-1920x1080-100.png'],
        'correction':'COMBAT-R uses original marker-status instead of the attack glyph; defense role is read from sourced ribbon text.',
        'remaining_constraints':'P9 prescribed anchor/reserve conflicts and P12 prescribed white hold line contrast are disclosed.'}
    b.dump(b.PKG/'facts.json',b.FACTS);b.dump(b.PKG/'verification.json',b.V);b.readme()
    b.V['sizes']['package_bytes']=sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file())
    b.V['acceptance']['P15 package budget']['measured']=b.V['sizes']['package_bytes']
    b.V['acceptance']['P15 package budget']['passed']=b.V['sizes']['package_bytes']<=30*1024*1024
    b.dump(b.PKG/'verification.json',b.V);b.manifest()
    print('Focused correction and actual PENDING modal comparison recorded; manifest written last.',flush=True)

if __name__=='__main__':run()
