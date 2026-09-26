"""Select revised Arthur/Merlin profile candidates, retaining prior versions."""
import copy
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
def read(name): return json.loads((ROOT/name).read_text(encoding='utf8'))
def write(name,value): (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def put(rows,record):
    i=next((i for i,r in enumerate(rows) if r['path']==record['path']),None)
    if i is None: rows.append(record)
    else: rows[i]=record

def main():
    m=read('manifest.json'); inputs=read('generation-inputs.json')
    notes={
        'REF-KING-ARTHUR':'Right v7: меч снова впереди груди, как в left v5. Дальняя верхняя часть руки скрыта корпусом; кисть видна за передним контуром груди. Ближняя рука пустая. Точное совпадение геометрии и четырёхвидовая приёмка остаются открытыми.',
        'REF-MERLIN':'Left v5: посох уходит за капюшон/плечо; дальняя кисть и средняя часть стержня закрыты одеждой. Ближняя рука у пояса пустая. Новый профиль просмотрен рядом с right v3; точное совпадение геометрии и четырёхвидовая приёмка остаются открытыми.'}
    for raw in read('normalized-v4.json')['outputs']:
        r=copy.deepcopy(raw); source=next(s for s in m['correctionDeliverables'] if s['path']==r['source'])
        r.update(promptPath=source['promptPath'],status='generated-reviewed',approval='proposal',
            generationTool='imagegen source; scripted technical derivation',useFor3D='candidate-requires-review',
            review={'result':'revised occlusion and anterior/posterior placement reviewed; human acceptance pending','notes':notes[r['assetId']]})
        put(m['derivedDeliverables'],r)
        a=next(a for a in m['assets'] if a['id']==r['assetId'])
        prior=next(v for v in a['views'] if v['role']==r['role'])
        if prior['path']!=r['path']:
            put(a.setdefault('viewHistory',[]),{**copy.deepcopy(prior),'supersededBy':r['path'],'revision':'correction-v4','acceptance':'rejected by user: weapon placement inconsistent/ambiguous'})
        a['views']=[r if v['role']==r['role'] else v for v in a['views']]
        a['review']={'result':'revised profile candidate; see three-view input set','notes':notes[a['id']]}
        bundle=next(b for b in inputs['characters'] if b['assetId']==a['id'])
        bundle['candidateViewsExcluded']=[{k:r[k] for k in ['role','path','sha256']}]
        bundle['notes']=notes[a['id']]
    p=ROOT/'side-profiles-v4-preview.png'; im=Image.open(p)
    put(m['auditPreviews'],{'path':p.name,'width':im.width,'height':im.height,'alpha':False,'bytes':p.stat().st_size,
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'kind':'technical-review-preview'})
    m['correction'].update(status='delivered-with-open-acceptance-gates',generatedFiles=len(m['correctionDeliverables']),
        previewFiles=len(m['auditPreviews']),acceptanceReport='PRODUCTION-NOTES.md#коррекция-v4')
    m['correctionV4']={'status':'revised-candidates-delivered; human acceptance pending','rawSideEdits':2,'normalizedFiles':2,
        'originalPngsPreservedFrom':'5328354','normalization':'normalized-v4.json','verification':'correction-v4-verification.json',
        'preview':'side-profiles-v4-preview.png','generationInputs':'generation-inputs.json','acceptanceReport':'PRODUCTION-NOTES.md#коррекция-v4',
        'scope':'Arthur/right v7 and Merlin/left v5; Harpy v5 and all other images unchanged',
        'fourView3DAcceptance':'not granted; previous three-view selections remain recommended'}
    inputs['revision']='correction-v4'; inputs['selectionBasis']='Three-view selections retained. Two revised profile candidates viewed against opposite side; await human acceptance.'
    write('manifest.json',m); write('generation-inputs.json',inputs)
    print(json.dumps({'raw':len(m['correctionDeliverables']),'derived':len(m['derivedDeliverables']),'previews':len(m['auditPreviews'])}))

if __name__=='__main__': main()
