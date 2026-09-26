"""Read-only validation of delivered PNGs, provenance and correction measurements."""
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import subprocess
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[2]
def read(name): return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
manifest=read('manifest.json')
records=list(manifest['assets'])+manifest.get('correctionDeliverables',[])+manifest.get('derivedDeliverables',[])+manifest.get('auditPreviews',[])
for asset in manifest['assets']: records+=asset.get('previousVersions',[])
seen={}
errors=[]
for r in records:
    if 'sha256' not in r or 'path' not in r: continue
    p=ROOT/r['path']
    if not p.exists(): errors.append('Missing '+r['path']); continue
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    if sha!=r['sha256']: errors.append('SHA mismatch '+r['path'])
    im=Image.open(p)
    if im.size!=(r['width'],r['height']): errors.append('Size mismatch '+r['path'])
    if r.get('promptPath') and not (ROOT/r['promptPath']).exists(): errors.append('Missing prompt '+r['path'])
    seen[r['path']]=r

# Original raw PNGs at correction handoff commit, checked independently of manifest.
tree=subprocess.check_output(['git','ls-tree','-r','571ea46','--','art/imagegen/mvp-v1'],cwd=REPO,text=True)
originals=[]
for line in tree.splitlines():
    header,name=line.split('\t',1)
    if name.endswith('.png'): originals.append((header.split()[2],name))
hashes=subprocess.check_output(['git','hash-object','--stdin-paths'],input='\n'.join(name for _,name in originals)+'\n',cwd=REPO,text=True).splitlines()
for (old,name),now in zip(originals,hashes):
    if old!=now: errors.append('Original PNG changed '+name)
if len(hashes)!=len(originals): errors.append('Incomplete original audit')

views=read('normalized-views.json')['outputs']
env=read('normalized-environment.json')['outputs']
stats=[]
baselines=defaultdict(list)
for r in views+env:
    a=np.asarray(Image.open(ROOT/r['path']).convert('RGB')).astype(float)
    border=np.concatenate([a[:100].reshape(-1,3),a[-100:].reshape(-1,3),a[:,:100].reshape(-1,3),a[:,-100:].reshape(-1,3)])
    mask=np.max(np.abs(a-128),axis=2)>15
    ys,xs=np.nonzero(mask)
    box=[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]
    row={'path':r['path'],'bounds':box,'borderMeanRgb':border.mean(axis=0).tolist(),'borderLuminanceStd':float((border@np.array([.2126,.7152,.0722])).std()),'minimumMarginPx':min(box[0],box[1],1023-box[2],1023-box[3]),'baseline':box[3]}
    stats.append(row)
    if r in views:
        baselines[r['assetId']].append(box[3])
        if row['minimumMarginPx']<102: errors.append('Character margin '+r['path'])
    if row['borderLuminanceStd']>=3: errors.append('Background std '+r['path'])
baseline_ranges={k:max(v)-min(v) for k,v in baselines.items()}
if max(baseline_ranges.values())>10: errors.append('Baseline variance')

# Manually reviewed grid boundary coordinates in v3, propagated through actual resize.
b=next(r for r in env if r['assetId']=='REF-BOARD-COBBLE' and r['role']=='top')
p=b['parameters']; box=p['sourceBounds']; outw,outh=p['pasteSize']; px,py=p['pasteXY']
sx=outw/(box[2]-box[0]); sy=outh/(box[3]-box[1])
xs=[148,315,486,658,829,995]; ys=[139,314,501,680,861,1040,1210]
a=np.asarray(Image.open(ROOT/b['path']).convert('RGB'),dtype=float)
means=[]
for y in range(6):
    for x in range(5):
        x0=round(px+(xs[x]+15-box[0])*sx); x1=round(px+(xs[x+1]-15-box[0])*sx)
        y0=round(py+(ys[y]+15-box[1])*sy); y1=round(py+(ys[y+1]-15-box[1])*sy)
        means.append(a[y0:y1,x0:x1].mean(axis=(0,1)))
means=np.array(means); luma=means@np.array([.2126,.7152,.0722])
ratio=(995-148)*sx/((1210-139)*sy)
board={'path':b['path'],'grid':[5,6],'gridCountingMethod':'visual count; manually reviewed source boundary coordinates','playableAspectRatio':ratio,'relativeErrorFromFiveSix':abs(ratio/(5/6)-1),'cellLuminanceMeans':luma.tolist(),'cellLuminanceRange':float(np.ptp(luma)),'maxCellChannelBias':float(np.ptp(means,axis=1).max())}
if board['relativeErrorFromFiveSix']>.02 or board['cellLuminanceRange']>=8: errors.append('Board acceptance measurement')

flipchecks=[]
for r in read('flipbook-exports.json')['outputs']:
    a=np.asarray(Image.open(ROOT/r['path']).convert('RGBA'))
    if a.shape!=(2048,2048,4): errors.append('Flipbook size '+r['path'])
    edges=[]
    for y in range(4):
        for x in range(4):
            f=a[y*512:(y+1)*512,x*512:(x+1)*512,3]
            edges.append(int(max(f[0].max(),f[-1].max(),f[:,0].max(),f[:,-1].max())))
    if max(edges)>8: errors.append('Flipbook edge alpha '+r['path'])
    flipchecks.append({'path':r['path'],'frameCount':16,'frameEdgeMaxAlpha':edges,'hasTransparency':bool((a[:,:,3]==0).any()),'rawCropEdgesPass':r['rawCropEdgesPass']})

materialchecks=[]
for r in read('material-exports.json')['outputs']:
    a=np.asarray(Image.open(ROOT/r['path']),dtype=float)
    if r['kind']=='N':
        err=float(np.abs(np.linalg.norm(a/255*2-1,axis=2)-1).max())
        if err>=.015: errors.append('Normal vector length '+r['path'])
        materialchecks.append({'path':r['path'],'normalMaxLengthError':err})
    elif r['kind']=='ORM':
        if not np.all(a[:,:,2]==255*r['parameters']['metallic']): errors.append('Metallic '+r['path'])

alphachecks=[]
for r in manifest['assets']:
    if not r.get('alpha'): continue
    a=np.asarray(Image.open(ROOT/r['path']).convert('RGBA'))[:,:,3]
    edge=int(max(a[0].max(),a[-1].max(),a[:,0].max(),a[:,-1].max()))
    if edge>8: errors.append('Selected outer edge alpha '+r['path'])
    alphachecks.append({'path':r['path'],'outerMaxAlpha':edge})
report={'status':'pass' if not errors else 'fail','scope':'Technical file/provenance/dimension/alpha validation. Artistic acceptance and 3D consistency are separate.','uniquePngMetadataChecked':len(seen),'originalPngsUnchanged':len(originals),'normalizedViews':stats,'characterBaselineRangePx':baseline_ranges,'board':board,'flipbooks':flipchecks,'normalMaps':materialchecks,'selectedAlpha':alphachecks,'errors':errors}
(ROOT/'correction-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['status','uniquePngMetadataChecked','originalPngsUnchanged','characterBaselineRangePx','board','errors']}))
raise SystemExit(bool(errors))
