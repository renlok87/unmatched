"""Focused artifact verification; no engine, git or external writes."""
from pathlib import Path
import hashlib
import json
import sys
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'hud-icons-v3'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    before=json.loads((ROOT/'source-hashes-before.json').read_text(encoding='utf-8'))
    after={str(p.relative_to(SOURCE)):sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    changed=[p for p,h in before.items() if after.get(p)!=h]
    added=sorted(set(after)-set(before))
    assert not changed and not added, ('v3 source changed during run',changed,added)
    assert sha(SOURCE/'_tools/draw_icons.py')==sha(ROOT/'_tools/draw_icons_v3_snapshot.py')
    rows={}
    baseline_matches={}
    for folder in ['vector-as-is','vector-codex']:
        for size in [16,24,32,1024]:
            paths=list((ROOT/folder/str(size)).glob('*.png'))
            assert len(paths)>=8
            for p in paths:
                im=Image.open(p)
                assert im.mode=='RGBA' and im.size==(size,size), (p,im.mode,im.size)
                a=np.asarray(im)
                assert a[...,3].any(),p
                touches_edge=bool(a[0,:,3].any() or a[-1,:,3].any() or a[:,0,3].any() or a[:,-1,3].any())
                ys,xs=np.where(a[...,3]>0)
                margins=[int(xs.min()),int(ys.min()),int(size-1-xs.max()),int(size-1-ys.max())]
                if size==1024: assert min(margins)>=32,(p,margins)
                if p.stem.endswith('-gray'):
                    assert np.array_equal(a[...,0],a[...,1]) and np.array_equal(a[...,1],a[...,2]),p
                rows[str(p.relative_to(ROOT))]={'mode':im.mode,'size':list(im.size),'margin_px':margins,'touches_edge':touches_edge}
                if folder=='vector-as-is' and not p.stem.endswith('-gray'):
                    src=SOURCE/('masters' if size==1024 else 'sizes')/(p.name if size==1024 else f'{p.stem}-{size}.png')
                    if src.exists():
                        equal=np.array_equal(a,np.asarray(Image.open(src).convert('RGBA')))
                        assert equal,('baseline differs from saved v3',p,src)
                        baseline_matches[str(p.relative_to(ROOT))]=True
    concept_ids=['turn-a','turn-b','fallen-a','fallen-b','stamp-a','stamp-b','slot-a','slot-b']
    assert {p.stem for p in (ROOT/'concepts').glob('*.png')}==set(concept_ids)
    for id in concept_ids:
        with Image.open(ROOT/'concepts'/(id+'.png')) as im: im.verify()
        for size in [16,24,32,1024]:
            for suffix in ['', '-gray']:
                p=ROOT/'concept-previews'/str(size)/(id+suffix+'.png')
                assert Image.open(p).size==(size,size),p
    for size in [16,24,32]:
        for mode in ['color','gray']:
            assert (ROOT/f'comparison/compare-{size}px-{mode}.png').exists()
    for p in (ROOT/'comparison').glob('*-gray.png'):
        a=np.asarray(Image.open(p).convert('RGB'))
        assert np.array_equal(a[...,0],a[...,1]) and np.array_equal(a[...,1],a[...,2]),p
    for record in json.loads((ROOT/'generation-records.json').read_text(encoding='utf-8')):
        assert sha(Path(record['original_path']))==sha(ROOT/record['saved_path']),record['id']
    # Display both complete generated storyboards without altering their content.
    board=Image.new('RGB',(1600,2280),'#161A28')
    d=ImageDraw.Draw(board)
    f=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',30)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',21)
    d.text((24,20),'DE-011 / DE-028 / A-B ART REFERENCES',fill='#FAF8F2',font=f)
    for i,(name,label) in enumerate([('ash-a-material','A / ASH / material-only erosion, narrow team-colored edge'),('smoke-b','B / SMOKE / alternative requiring additional FX')]):
        im=Image.open(ROOT/'de011'/(name+'.png')).convert('RGB')
        im.thumbnail((1552,1000),Image.Resampling.LANCZOS)
        y=90+i*1080
        d.text((24,y),label,fill='#B9B2A6',font=small)
        board.paste(im,((1600-im.width)//2,y+40))
    d.text((24,2220),'Generated figure reconstruction: effect reference only. Hero 500 ms / sidekick 400 ms.',fill='#B9B2A6',font=small)
    board.save(ROOT/'de011/ab-sheet.png')
    audit={'source_v3_files_unchanged':len(before),'generator_snapshot_sha256':sha(ROOT/'_tools/draw_icons_v3_snapshot.py'),
           'baseline_pngs_equal_to_saved_v3':baseline_matches,'generated_hud_concepts':len(concept_ids),
           'generated_dissolve_concepts':2,'ash_refinement':1,'exports':rows,'checks':'PASS'}
    (ROOT/'verification.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    manifest={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name!='manifest-sha256.json'}
    (ROOT/'manifest-sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'PASS: {len(before)} v3 inputs unchanged; {len(baseline_matches)} saved baseline PNGs identical; {len(rows)} vector exports valid; {len(manifest)} deliverables fingerprinted.')

if __name__=='__main__':main()
