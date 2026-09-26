"""Register v3 derivatives and explicit 3D input selections; preserve history."""
import copy
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
def read(name): return json.loads((ROOT/name).read_text(encoding='utf8'))
def write(name, value): (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def put(rows, record):
    index=next((i for i,r in enumerate(rows) if r['path']==record['path']),None)
    if index is None: rows.append(record)
    else: rows[index]=record

def main():
    m=read('manifest.json')
    rows=read('normalized-v3.json')['outputs']
    sources={r['path']:r for r in m['correctionDeliverables']+m['derivedDeliverables']}
    notes={
        'REF-KING-ARTHUR':'Дальняя кисть с мечом скрыта, ближняя рука пустая. Меч сместился за голову: новый right исключён из набора для 3D до согласования положения оружия.',
        'REF-MERLIN':'Дальняя кисть и середина посоха скрыты одеждой. Кристалл сместился над капюшоном: новый left исключён из набора для 3D до согласования положения посоха.',
        'REF-MEDUSA':'Дальняя кисть и середина лука перекрыты телом, ближняя рука пустая, видно 7 голов змей. Новый right остаётся кандидатом: плоскость лука согласовать на модели.',
        'REF-HARPY':'На right ближняя правая нога без браслета; дальний левый браслет скрыт. Высота четырёх видов 479–480 px после независимого масштаба Y; позы крыльев ещё требуют согласования в Blender.'}
    for raw in rows:
        r=copy.deepcopy(raw)
        r.update(promptPath=sources[r['source']]['promptPath'],status='generated-reviewed',approval='proposal',
            generationTool='imagegen source; scripted technical derivation',
            review={'result':'occlusion/2D normalization reviewed; four-view 3D acceptance open','notes':notes[r['assetId']]})
        r['useFor3D']='candidate-requires-review' if r['assetId']!='REF-HARPY' or r['role']=='right' else 'recommended-with-Blender-wing-alignment'
        put(m['derivedDeliverables'],r)
        a=next(a for a in m['assets'] if a['id']==r['assetId'])
        prior=next(v for v in a['views'] if v['role']==r['role'])
        if prior['path']!=r['path']:
            put(a.setdefault('viewHistory',[]),{**copy.deepcopy(prior),'supersededBy':r['path'],'revision':'correction-v3'})
        a['views']=[r if v['role']==r['role'] else v for v in a['views']]
        a['review']={'result':'proposal; three-view selection in generation-inputs.json','notes':notes[a['id']]}
        a['generationInputs']='generation-inputs.json'
        if a['id']=='REF-HARPY' and r['role']=='front':
            if a['path']!=r['path']:
                prior_primary={k:copy.deepcopy(v) for k,v in a.items() if k not in ['views','viewHistory','previousVersions','exports','flipbooks','generationInputs']}
                put(a.setdefault('previousVersions',[]),prior_primary)
            for key in ['path','width','height','alpha','bytes','sha256','promptPath']: a[key]=r[key]
            a['sourcePath']=str(ROOT/r['source'])
            a['derivation']={'script':'_tools/normalize-v3.py','source':r['source'],'sourceSha256':r['sourceSha256']}
    p=ROOT/'normalized-views-v3-preview.png'; im=Image.open(p)
    put(m['auditPreviews'],{'path':p.name,'width':im.width,'height':im.height,'alpha':False,'bytes':p.stat().st_size,
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'kind':'technical-review-preview'})
    m['correction'].update(status='delivered-with-open-acceptance-gates',generatedFiles=len(m['correctionDeliverables']),
        previewFiles=len(m['auditPreviews']),normalizationAuthorization='User approved scripted normalization, preserving originals.',
        acceptanceReport='PRODUCTION-NOTES.md#коррекция-v3',
        openGates=['Four-view weapon placement and 3D anatomy consistency; Harpy wing alignment',
            'Old-wood seams: D2048 wrap X 2.515, wrap Y 3.832; manual offset/clone',
            'Manual board/top/frame by S04 and miniature bases by 04',
            'VFX frames are particle textures; animation must be authored in Niagara',
            'Blender/UE production and GD-058'])
    m['correctionV3']={'status':'delivered-with-open-acceptance-gates','rawSideEdits':4,'normalizedFiles':7,
        'harpyTargetHeightPx':480,'harpyMeasuredHeightRangePx':[479,480],
        'originalPngsPreservedFrom':'eb4c682','normalization':'normalized-v3.json',
        'verification':'correction-v3-verification.json','preview':'normalized-views-v3-preview.png',
        'generationInputs':'generation-inputs.json','acceptanceReport':'PRODUCTION-NOTES.md#коррекция-v3',
        'fourView3DAcceptance':'open; use explicit three-view selections until corrected profiles are accepted'}
    bundles=[]
    for id,side in [('REF-KING-ARTHUR','left'),('REF-MERLIN','right'),('REF-MEDUSA','left'),('REF-HARPY','left')]:
        a=next(a for a in m['assets'] if a['id']==id)
        selected=[next(v for v in a['views'] if v['role']==role) for role in ['front','back',side]]
        excluded=[v for v in a['views'] if v['role'] not in ['front','back',side]]
        bundles.append({'assetId':id,'status':'recommended-reference-set; mesh generation not run',
            'views':[{k:v[k] for k in ['role','path','sha256','width','height']} for v in selected],
            'candidateViewsExcluded':[{k:v[k] for k in ['role','path','sha256']} for v in excluded],
            'notes':notes[id]})
    props=[]
    for id in ['REF-BARREL','REF-LANTERN','REF-TABLE-BASE']:
        a=next(a for a in m['assets'] if a['id']==id)
        props.append({'assetId':id,'referenceViews':[{k:v[k] for k in ['role','path','sha256']} for v in a['views']],
            'scope':'Rock underside only; top and frame modeled manually from S04.' if id=='REF-TABLE-BASE' else 'Usable visual references; reconcile fittings in Blender.'})
    write('generation-inputs.json',{'revision':'correction-v3','pathBase':'art/imagegen/mvp-v1',
        'status':'Reference selection only; no Rodin/Hunyuan/Blender mesh generated or accepted.',
        'selectionBasis':'User review: front/back plus non-contradictory side. New side candidates remain excluded pending placement review.',
        'characters':bundles,'props':props,
        'manualModeling':{'boardAndTableTopFrame':'docs/game-design/evidence/S04/board-contract.json: 5x6 grid, cell 100 uu',
            'bases':'docs/game-design/04-blender-production.md: Base_Hero diameter 30 x height 6 uu; Base_Sidekick diameter 22 x height 5 uu. Do not infer thickness from PNG.'},
        'materials':'Old-wood requires manual offset + clone in Blender/Substance; no regeneration in v3.',
        'vfx':'Flipbooks not accepted as animation. Use frames as particle textures; animate in Niagara.'})
    write('manifest.json',m)
    print(json.dumps({'assets':len(m['assets']),'raw':len(m['correctionDeliverables']),'derived':len(m['derivedDeliverables']),'previews':len(m['auditPreviews'])}))

if __name__=='__main__': main()
