"""Record the measured generic scheme/discard luma conflict, no image changes."""
import sys
sys.dont_write_bytecode=True
from types import SimpleNamespace
import build_mockups as b

def run():
    b.V=b.load(b.PKG/'verification.json');b.FACTS=b.load(b.PKG/'facts.json');b.hb.FACTS=b.FACTS
    b.V['gray_pairs']=[]
    for board in ['marmoreal','sarpedon']:
        for w,h,ui,s in b.CONFIGS:
            samples=[SimpleNamespace(board=board,state=st,id=f'HB-34-{board}-{st}-{w}x{h}-{ui}') for st in b.STATES]
            b.gray_pairs(samples)
    b.acceptance();b.dump(b.PKG/'verification.json',b.V);b.readme()
    b.V['sizes']['package_bytes']=sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file())
    b.V['acceptance']['P15 package budget']['measured']=b.V['sizes']['package_bytes']
    b.V['acceptance']['P15 package budget']['passed']=b.V['sizes']['package_bytes']<=30*1024*1024
    b.dump(b.PKG/'verification.json',b.V);b.manifest()
    print('Generic ribbon luma conflict recorded honestly; manifest written last.')

if __name__=='__main__':run()
