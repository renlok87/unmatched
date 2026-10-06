"""Regenerate only grayscale exports with exact rational Rec.709 rounding."""
import sys
sys.dont_write_bytecode=True
import build_mockups as b
from PIL import Image

def run():
    b.V=b.load(b.PKG/'verification.json');b.FACTS=b.load(b.PKG/'facts.json');b.hb.FACTS=b.FACTS
    prior=b.V['write_proof']['writes'];count=0
    for root in [b.DERIVED,b.PKG/'comparison']:
        for p in sorted(root.glob('*.png')):
            if p.stem.endswith('-gray'):continue
            with Image.open(p) as im:result=b.gray(im)
            b.save(p.with_name(p.stem+'-gray.png'),result);count+=1
    b.source_checks();b.V['write_proof']['writes']=sorted(set(prior+b.V['write_proof']['writes']))
    b.export_checks();b.acceptance()
    b.V['gray']['rational_rounding_fix']={'reason':'Floating-point summation could round exact half-luma values down by 1; all gray files were regenerated from unchanged color files.',
                                        'gray_exports_regenerated':count,'color_exports_changed':0}
    b.dump(b.PKG/'verification.json',b.V);b.readme()
    b.V['sizes']['package_bytes']=sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file())
    b.V['acceptance']['P15 package budget']['measured']=b.V['sizes']['package_bytes']
    b.V['acceptance']['P15 package budget']['passed']=b.V['sizes']['package_bytes']<=30*1024*1024
    b.dump(b.PKG/'verification.json',b.V);b.manifest()
    print(f'{count} grayscale exports regenerated; exact Rec.709 verified; manifest written last.',flush=True)

if __name__=='__main__':run()
