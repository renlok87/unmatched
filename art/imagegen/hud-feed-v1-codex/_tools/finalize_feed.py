"""Verify HB-08 edges on ACTUAL 1080p/100 PNGs, refresh reports, manifest LAST."""
import sys
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image
import build_feed as b
def main():
    b.V=b.load(b.PKG/'verification.json');b.F=b.load(b.PKG/'facts.json')
    b.hb.BASELINE=b.load(b.PKG/'source-hashes-before.json')
    ledger=b.V['write_scope']['paths_written']
    b.source_checks()
    b.V['write_scope']['paths_written']=sorted(set(ledger+b.V['write_scope']['paths_written']))
    b.V['acceptance']['source_unchanged'].update(passed=b.V['source_unchanged'],measured=b.V['source_changed_paths'])
    b.V['skin_match_hb08']=[r for r in b.V['skin_match_hb08'] if not r.get('actual_final')]
    margins=b.load(b.ROOT/'art/imagegen/hud-skins-v1-codex/slice-margins.json')['files']
    checks=[]
    for output in b.F['outputs']:
        if not output['id'].endswith('1920x1080-100'):continue
        board=output['id'].split('-')[2]
        base=b.hb.image(b.hb.BG[board])
        with Image.open(b.ROOT/output['path']) as source:final=source.convert('RGBA')
        for name,r in output['blocks'].items():
            if not (name.startswith('TOAST-') or name=='SUB'):continue
            skin='Capsule' if name=='SUB' else 'ToastWarning' if '-toast-warning-' in output['id'] else 'Toast'
            path=b.ROOT/f'art/imagegen/hud-skins-v1-codex/vector/x1/T_Skin_{skin}.png'
            with Image.open(path) as im:reference=im.convert('RGBA')
            x,y=round(r[0]),round(r[1]);w,h=round(r[2]),round(r[3])
            expected=b.skins.nine_slice(reference,margins[f'vector/x1/T_Skin_{skin}.png'],(w+2,h+2)).crop((1,1,w+1,h+1))
            _,body,border=b.p.skin_material(skin,w,h,1)
            edge=np.asarray(border)[:,:,3]>0
            patch=base.crop((x,y,x+w,y+h));composed=Image.alpha_composite(patch,expected)
            actual=final.crop((x,y,x+w,y+h))
            delta=np.abs(np.asarray(actual).astype(int)-np.asarray(composed).astype(int))
            checks.append({'skin':skin,'actual_final':output['path'],'block':name,'rectangle_su':r,
              'reference':b.rel(path),'scale':1,'max_channel_difference':int(delta[edge].max()) if np.any(edge) else None,
              'different_edge_pixels':int(np.count_nonzero(np.any(delta[edge]>0,axis=1))),
              'pixel_identical':bool(not np.any(delta[edge])),
              'edge_pixels_checked':int(np.count_nonzero(edge)),
              'method':'Actual FINAL PNG edge pixels versus HB-08 x1 nine-slice over the unchanged actual background; text/signs inside excluded from edge mask.'})
    b.V['skin_match_hb08'].extend(checks)
    bad=[r for r in checks if not r['pixel_identical']]
    maximum=max(r['max_channel_difference'] for r in b.V['skin_match_hb08'])
    b.V['acceptance']['skin_match_hb08'].update(passed=maximum==0,measured=maximum,
        note='Also verified every actual 1080p/100 final toast/capsule edge against x1 HB-08 composited on its unchanged background.')
    b.V['visual_review']={'method':'Agent opened both source backgrounds and the eight review sheets plus selected native finals, grayscale and overlays; reviewed all state thumbnails. Review thumbnails are not acceptance exports.',
        'boards':['Marmoreal original painted backdrop','Sarpedon original lit3d'],
        'six_v2_figures_visible':True,'old_background_labels_retained':True,
        'native_caption_and_warning_reviewed':True}
    # Independent read-only auditor verifies these claims against the bytes.
    b.V['failures']=[k for k,r in b.V['acceptance'].items() if not r['passed']]
    b.dump(b.PKG/'verification.json',b.V);b.readme()
    package=sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file() and p.name!='manifest-sha256.json')
    b.V['package_bytes_without_manifest']=package
    b.V['acceptance']['package_30MB'].update(measured=package,passed=package<=30_000_000)
    b.dump(b.PKG/'verification.json',b.V)
    print('Actual final HB-08 edge checks:',len(checks),'failures:',bad)
    print('Acceptance failures:',b.V['failures'],'package bytes:',package)
    b.manifest()
if __name__=='__main__':main()
