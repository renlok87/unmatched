"""Validate current package, baseline PNG preservation, v3 dimensions and links."""
import hashlib
import json
import subprocess
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[2]
def read(name): return json.loads((ROOT/name).read_text(encoding='utf8'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main(revision='v3'):
    baseline='5328354' if revision=='v4' else 'eb4c682'
    m=read('manifest.json'); errors=[]; seen={}
    records=m['assets']+m['correctionDeliverables']+m['derivedDeliverables']+m['auditPreviews']
    for a in m['assets']:
        for key in ['previousVersions','viewHistory','views','exports','flipbooks']: records+=a.get(key,[])
    for r in records:
        if 'sha256' not in r: continue
        p=ROOT/r['path']
        if not p.is_file(): errors.append('Missing '+r['path']); continue
        if digest(p)!=r['sha256']: errors.append('SHA mismatch '+r['path'])
        with Image.open(p) as im:
            if im.size!=(r['width'],r['height']): errors.append('Dimensions '+r['path'])
            if ('A' in im.getbands())!=r['alpha']: errors.append('Alpha metadata '+r['path'])
            im.verify()
        if p.stat().st_size!=r['bytes']: errors.append('Byte count '+r['path'])
        if r.get('promptPath') and not (ROOT/r['promptPath']).is_file(): errors.append('Prompt '+r['path'])
        if r.get('sourceSha256') and digest(ROOT/r['source'])!=r['sourceSha256']: errors.append('Source '+r['path'])
        seen[r['path']]=r
    pngs={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*.png')}
    if pngs!=set(seen): errors.append('PNG inventory difference '+str(sorted(pngs^set(seen))))
    tree=subprocess.check_output(['git','ls-tree','-r',baseline,'--','art/imagegen/mvp-v1'],cwd=REPO,text=True)
    originals=[]
    for line in tree.splitlines():
        header,name=line.split('\t',1)
        if name.endswith('.png'): originals.append((header.split()[2],name))
    hashes=subprocess.check_output(['git','hash-object','--stdin-paths'],input='\n'.join(n for _,n in originals)+'\n',cwd=REPO,text=True).splitlines()
    if len(hashes)!=len(originals): errors.append('Incomplete original audit')
    for (old,name),now in zip(originals,hashes):
        if old!=now: errors.append('Changed original '+name)
    stats=[]
    view_records=read('normalized-'+revision+'.json')['outputs']
    if revision=='v4':
        view_records += [r for r in read('normalized-v3.json')['outputs'] if r['assetId']=='REF-HARPY']
    for r in view_records:
        a=np.asarray(Image.open(ROOT/r['path']).convert('RGB'),dtype=float)
        mask=np.max(np.abs(a-128),axis=2)>15
        ys,xs=np.nonzero(mask); box=[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]
        border=np.concatenate([a[:100].reshape(-1,3),a[-100:].reshape(-1,3),a[:,:100].reshape(-1,3),a[:,-100:].reshape(-1,3)])
        widths=[np.ptp(xx)+1 for y in range(box[3]-39,box[3]+1) if len(xx:=np.flatnonzero(mask[y]))]
        row={'path':r['path'],'assetId':r['assetId'],'role':r['role'],'boundsInclusive':box,
            'heightPx':box[3]-box[1]+1,'minimumMarginPx':min(box[0],box[1],1023-box[2],1023-box[3]),
            'baseline':box[3],'baseWidthPx':int(max(widths)),
            'borderLuminanceStd':float((border@np.array([.2126,.7152,.0722])).std()),
            'previousHeightPx':r.get('measurement',{}).get('previousHeightPx'),'scaleXY':r['parameters']['scaleXY']}
        if 'measurement' in r and row['heightPx']!=r['measurement']['outputHeightPx']: errors.append('Recorded height '+r['path'])
        if row['minimumMarginPx']<102 or row['borderLuminanceStd']>=3: errors.append('Margin/background '+r['path'])
        if a.shape!=(1024,1024,3): errors.append('Output canvas '+r['path'])
        stats.append(row)
    harpy=[r for r in stats if r['assetId']=='REF-HARPY']
    hrange=max(r['heightPx'] for r in harpy)-min(r['heightPx'] for r in harpy)
    brange=max(r['baseline'] for r in harpy)-min(r['baseline'] for r in harpy)
    wrange=max(r['baseWidthPx'] for r in harpy)-min(r['baseWidthPx'] for r in harpy)
    if hrange>2 or brange>1 or wrange>2: errors.append('Harpy alignment')
    seams=[]
    for size in [2048,1024]:
        path=f'materials/export/T_old_wood_D_{size}.png'
        a=np.asarray(Image.open(ROOT/path).convert('RGB'),dtype=float)
        wrap=[np.abs(a[:,0]-a[:,-1]).mean(),np.abs(a[0]-a[-1]).mean()]
        inner=[np.abs(np.diff(a,axis=1)).mean(),np.abs(np.diff(a,axis=0)).mean()]
        seams.append({'path':path,'edgeMeanDifferenceXY':list(map(float,wrap)),
            'interiorNeighborMeanDifferenceXY':list(map(float,inner)),
            'edgeToInteriorRatioXY':[float(w/max(i,.001)) for w,i in zip(wrap,inner)]})
    alpha=[]
    for r in m['assets']:
        if not r['alpha']: continue
        a=np.asarray(Image.open(ROOT/r['path']))[:,:,3]
        edge=int(max(a[0].max(),a[-1].max(),a[:,0].max(),a[:,-1].max()))
        if edge>8 or not (a==0).any(): errors.append('Alpha edge/transparency '+r['path'])
        alpha.append({'path':r['path'],'edgeMaxAlpha':edge})
    inputs=read('generation-inputs.json')
    for b in inputs['characters']:
        for v in b['views']+b['candidateViewsExcluded']:
            if digest(ROOT/v['path'])!=v['sha256']: errors.append('3D selection hash '+v['path'])
        expected='right' if b['assetId']=='REF-MERLIN' else 'left'
        if [v['role'] for v in b['views']]!=['front','back',expected]: errors.append('3D view selection '+b['assetId'])
    links=[]
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ['src','href'] and v:
                    url=urlsplit(v)
                    if not url.scheme and not url.netloc and url.path: links.append(unquote(url.path))
    Links().feed((ROOT/'index.html').read_text(encoding='utf8'))
    for link in links:
        # This invocation creates its own report below; write failures raise normally.
        if link=='correction-'+revision+'-verification.json': continue
        if not (ROOT/link).is_file(): errors.append('Catalog link '+link)
    report={'status':'pass' if not errors else 'fail',
        'scope':'Technical checks only. Visual occlusion reviewed separately; four-view 3D consistency remains open.',
        'revision':revision,'uniquePngMetadataChecked':len(seen),'baselineCommit':baseline,'originalPngsUnchanged':len(originals),
        'normalizedViews':stats,'harpyHeightSpreadPx':hrange,'harpyBaselineSpreadPx':brange,'harpyBaseWidthSpreadPx':wrange,
        'measurementConvention':'max RGB distance from #808080 > 15; inclusive bounds, height=maxY-minY+1',
        'woodSeams':seams,'seamAxes':'X compares left/right border columns; Y compares top/bottom border rows. Ratio is RGB edge mean difference divided by interior neighbor mean difference.',
        'woodSeamAcceptance':'failed; manual repair required, unchanged in v3',
        'selectedAlpha':alpha,'catalogLocalLinksChecked':len(links),'errors':errors}
    if revision=='v4':
        landmarks=[]
        for name,ref,new,rois,kind in [
            ('Arthur','characters/ref-king-arthur-v5-left.png','characters/ref-king-arthur-v7-right.png',[(350,210,425,310),(575,210,650,310)],'blade'),
            ('Merlin','characters/ref-merlin-v3-right.png','characters/ref-merlin-v5-left.png',[(440,100,585,175),(440,100,585,175)],'crystal')]:
            centers=[]
            for path,roi in zip([ref,new],rois):
                x0,y0,x1,y1=roi; a=np.asarray(Image.open(ROOT/path).convert('RGB'),dtype=float)[y0:y1,x0:x1]
                mask=(a.min(axis=2)>150)&(np.ptp(a,axis=2)<40) if kind=='blade' else (a[:,:,2]-a[:,:,0]>12)&(a[:,:,0]<160)
                _,xx=np.nonzero(mask); centers.append(float(np.median(xx+x0)))
            landmarks.append({'character':name,'reference':ref,'candidate':new,'regionXYXY':rois,'landmark':kind,
                'referenceMedianX':centers[0],'mirroredReferenceXAbout512':1024-centers[0],'candidateMedianX':centers[1],
                'residualPx':centers[1]-(1024-centers[0]),
                'method':'Median X in manually selected ROI; blade minRGB>150 and RGB range<40, crystal B-R>12 and R<160.',
                'acceptance':'Diagnostic only; shading and silhouette differ. Does not prove identical 3D placement.'})
        report['profileLandmarks']=landmarks
    (ROOT/('correction-'+revision+'-verification.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ['status','uniquePngMetadataChecked','originalPngsUnchanged','harpyHeightSpreadPx','harpyBaselineSpreadPx','harpyBaseWidthSpreadPx','catalogLocalLinksChecked','errors']}))
    raise SystemExit(bool(errors))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--revision',choices=['v3','v4'],default='v3')
    main(parser.parse_args().revision)
