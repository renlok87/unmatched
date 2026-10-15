"""Index all kit files; verify hashes, scope and preserved A bytes."""
import sys
sys.dont_write_bytecode=True
from build_kit import *

def main():
    assets=json.loads((KIT/'assets.json').read_text('utf-8'))
    runtime={v['path']:(d,v) for d in assets.values() for v in d['files'].values()}
    files={}
    for p in sorted(KIT.rglob('*')):
        if not p.is_file() or p.name=='manifest.json':continue
        rel=str(p.relative_to(ART)).replace('\\','/')
        d,v=runtime.get(rel,({},{}))
        rec={'size_px':list(Image.open(p).size) if p.suffix=='.png' else None,'scale':v.get('scale'),
            'slice_margins_px':v.get('slice_px'),'sha256':sha(p),'bytes':p.stat().st_size,
            'role':d.get('role','ImageGen source master, not runtime' if p.parent.name=='source-masters' and p.suffix=='.png' else 'catalog, no scans' if p.name=='catalog.png' else 'kit metadata / preservation record'),
            'ue_skin_key':d.get('ue_skin_key'),'widget':d.get('widget'),'asset_name':d.get('name'),'stretch':d.get('stretch')}
        if d:
            rec.update({'body_color':d['body_color'],'body_opacity':d['body_opacity'],'text_color':d['text_color'],'size_su':d['size_su'],'source_masters':d['source_masters']})
            assert rec['sha256']==v['sha256'],rel
        files[rel]=rec
    manifest={'stage':'B2','direction':'A Marble Acropolis','status':'ornament kit assembled; fixed-colour contrast exceptions recorded; Unreal import pending',
        'verification':'../verification.json (stage_b2)','asset_count':len(assets),'runtime_png_count':len(runtime),'source_master_count':11,'scale_folders':{'x1':1,'x2':2,'masters':4},
        'slice_unit':'physical px, L/T/R/B; normalize by full PNG dimensions for engine brushes',
        'self_hash_note':'manifest.json excludes itself; all other files below kit/ are enumerated',
        'files':files}
    write_json(KIT/'manifest.json',manifest)
    for rel,rec in files.items():assert sha(ART/rel)==rec['sha256']
    baseline=json.loads((KIT/'stage-a-baseline.json').read_text('utf-8'));marker=b'<!-- STAGE-B-END -->\n\n'
    preserved={}
    for name in ['README.md','prompts.md']:
        p=ART/name;tail=p.read_bytes().split(marker,1)[1]
        preserved[name]=hashlib.sha256(tail).hexdigest()==baseline[str(p.relative_to(ROOT))]
    ctx=json.loads((KIT/'stage-a-record-preservation.json').read_text('utf-8'))
    raw=(ART/'generation-records.json').read_bytes();old=raw[:ctx['prefix_length']]+bytes.fromhex(ctx['tail_hex'])
    preserved['generation-records.json']=hashlib.sha256(old).hexdigest()==ctx['original_sha256']
    assert all(preserved.values())
    # Native review placements cannot clip assets and must cover every export exactly once.
    pages=json.loads((PRE/'review/pages.json').read_text('utf-8'));seen=[]
    for page in pages:
        w,h=Image.open(ROOT/page['file']).size
        for pl in page['placements']:
            for xy in [pl['xy_navy'],pl['xy_light']]:assert xy[0]+pl['size'][0]<=w and xy[1]+pl['size'][1]<=h
            assert pl['xy_navy'][0]+pl['size'][0]<=1100
            seen.append((pl['name'],page['scale']))
    assert len(seen)==len(set(seen))==len(runtime)
    for p in list(ART.rglob('*.json'))+list(ART.rglob('*.md'))+list((ART/'_tools').glob('*.py')):
        assert not p.read_bytes().startswith(b'\xef\xbb\xbf'),str(p)
        p.read_bytes().decode('utf-8')
    report={'status':'pass','kit_indexed_files':len(files),'runtime_pngs':len(runtime),'all_index_hashes_verified':True,'stage_a_bytes_preserved':preserved,
        'native_review_placements':len(seen),'native_review_pages':len(pages),'utf8_no_bom':True,
        'kit_size_bytes':sum(p.stat().st_size for p in KIT.rglob('*') if p.is_file()),
        'source_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in list((DER/'refs').glob('*.png'))+[FONT]+list((ROOT/'art/imagegen/hud-icons-v3/masters').glob('*.png'))}}
    write_json(ART/'stage-b2-package-check.json',report)
    print(json.dumps({k:report[k] for k in ['status','kit_indexed_files','runtime_pngs','native_review_placements','kit_size_bytes','stage_a_bytes_preserved']}))
if __name__=='__main__':main()
