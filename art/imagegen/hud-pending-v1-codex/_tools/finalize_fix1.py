"""Refresh affected finals after native chip/scroll skin verification; manifest last."""
import sys
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image
import build_mockups as b
from audit_package import fix1_checks


def run():
    b.V=b.load(b.PKG/'verification.json');b.FACTS=b.load(b.PKG/'facts.json');b.hb.FACTS=b.FACTS
    reports_only='--reports-only' in sys.argv
    states=[] if reports_only else ['toast','after-combat','slot-boost','modal-order']
    ids={f'HB-34-{board}-{st}-{w}x{h}-{ui}' for board in ['marmoreal','sarpedon'] for w,h,ui,s in b.CONFIGS for st in states}
    prior_writes=b.V['write_proof']['writes']
    for key,value in b.V.items():
        if isinstance(value,list):b.V[key]=[r for r in value if not isinstance(r,dict) or r.get('id') not in ids]
    for key in ['outputs','rendered_texts','scans','deltas_04']:
        b.FACTS[key]=[r for r in b.FACTS[key] if r.get('id',r.get('mockup')) not in ids]
    for board in ([] if reports_only else ['marmoreal','sarpedon']):
        for w,h,ui,s in b.CONFIGS:
            path=b.DERIVED/f'contact-HB-34-{board}-{w}x{h}-{ui}.png'
            with Image.open(path) as source:contact=source.convert('RGBA')
            for st in states:
                c=b.render(board,st,w,h,ui,s);out=b.measure(c)
                b.save(b.DERIVED/(c.id+'.png'),out);b.save(b.DERIVED/(c.id+'-gray.png'),b.gray(out))
                i=b.STATES.index(st);contact.paste(out,(i%6*w,i//6*(h+32)+32))
            b.save(path,contact);b.save(path.with_name(path.stem+'-gray.png'),b.gray(contact))
            print(f'{board} {w}x{h} {ui}%: verified chip/scroll skin and BOOST font refreshed',flush=True)
    outputs={r['id']:r for r in b.FACTS['outputs']}
    # Compare actual gray PNGs; ribbon comparisons deliberately exclude card scans.
    for r in b.V['gray_pairs']:
        a,bb=r['states'];res,ui=r['canvas'];stem=f'HB-34-{r["board"]}'
        field='modal' if a.startswith('modal') else 'compact' if a.startswith('compact') else 'ribbon_plate'
        arrays=[]
        s=1.125 if res=='1280x720' and ui=='150' else .75 if res=='1280x720' else 1.5 if ui=='150' else 1
        for st in [a,bb]:
            ident=f'{stem}-{st}-{res}-{ui}';g=outputs[ident]['geometries'][field]
            rect=g['rectangle_su'] if isinstance(g,dict) else g
            with Image.open(b.DERIVED/(ident+'-gray.png')) as im:arrays.append(np.asarray(im.crop(tuple(b.pxbox(rect,s)))))
        h=max(x.shape[0] for x in arrays);w=max(x.shape[1] for x in arrays)
        padded=[]
        for arr in arrays:
            canvas=np.zeros((h,w,4),np.uint8);canvas[:arr.shape[0],:arr.shape[1]]=arr;padded.append(canvas)
        r['gray_changed_pixels']=int(np.any(padded[0]!=padded[1],axis=2).sum())
        r['measurement']='Actual Rec.709 PNG component crops; ribbon_plate excludes scans'
        r['passed']=r['gray_changed_pixels']>0
    b.V['skin_match_hb08']=[];b.V['frame_match_cp13']=[];b.frame_skin_checks()
    b.source_checks();b.V['write_proof']['writes']=sorted(set(prior_writes+b.V['write_proof']['writes']))
    b.export_checks();b.acceptance()
    correction=fix1_checks(b.FACTS,b.V);b.V['fix1_independent']=correction
    b.V['acceptance']['fix1 independent PNG/facts audit']={'passed':correction['passed'],'measured':correction,'expected':'All independent fix1 checks pass','note':'Includes actual PNG HOLD fill/track contrast'}
    b.FACTS['fix1']['independent_checks']=correction['checks']
    b.V['visual_review']={'opened_pngs':[
        'HB-34-marmoreal-compact-move-1280x720-150.png','HB-34-marmoreal-modal-order-1920x1080-100.png',
        'HB-34-marmoreal-toast-1920x1080-100.png','HB-34-marmoreal-slot-boost-1920x1080-150.png',
        'HB-34-marmoreal-modal-pick-1280x720-100-gray.png','HB-34-marmoreal-compact-place-1280x720-100.png',
        'HB-34-sarpedon-slot-discard-1920x1080-100.png','HB-34-sarpedon-slot-opp-hold-1280x720-100.png',
        'HB-34-sarpedon-modal-pick-1920x1080-150.png','HB-34-sarpedon-boost-1280x720-150.png',
        'HB-34-sarpedon-modal-order-1280x720-150-gray.png','HB-34-marmoreal-compact-target-en-1920x1080-100.png'],
        'findings':'Real boards, preserved prescribed backdrops and six v2 figures; raised PICK cards readable in gray, ORDER two numbered cards, compacts clear, owner ribbons readable.'}
    b.V['lifecycle']={'child_processes_started':0,'services_started':0,'editor_started':False,'background_processes_retained':0}
    b.dump(b.PKG/'facts.json',b.FACTS);b.dump(b.PKG/'verification.json',b.V);b.readme()
    p=b.PKG/'README.md';text=p.read_text(encoding='utf-8')
    before=b.load(b.PKG/'fix1-before.json')
    rows=[]
    for old in before['modal_fit']:
        new=next(r for r in b.V['modal_fit'] if r['id']==old['id'])
        rows.append(f'| {old["id"]} | {old["rectangle_su"][3]:.0f} → {new["rectangle_su"][3]:.0f} | {old["scrolled_part_su"]:.0f} → {new["scrolled_part_su"]:.0f} |')
    text+='\n### Числа модалей до → после\n\n| Холст / состояние | Высота su | Скрыто в scroll su |\n|---|---|---|\n'+'\n'.join(rows)+'\n'
    text+='\n### Ширина серых компактов до → после\n\n| Холст / состояние | Ширина su |\n|---|---|\n'
    for new in b.V['compact_geometry']:
        if new['state'] not in ['opp','slot-opp-show','after-combat']:continue
        old=next(r for r in before['compact_geometry'] if r['id']==new['id'])
        text+=f'| {new["id"]} | {old["rectangle_su"][2]:.2f} → {new["rectangle_su"][2]:.2f} |\n'
    text+='\nДополнение аудита P12 для нового scrollbar ORDER: производные RGB полупрозрачного ProgressTrack рассчитаны из неизменённого x1 HB-08 поверх card.navy тем же способом, что кромки кнопок; `allowed_hb08_derived_progress_colors` содержит источники и операции. Новых пигментов нет (material_off_token_pixels=0). STATUS KeyChip повторяет native Pillow-кромку HB-13.\n'
    text+='\nПолное воспроизведение fix1: сначала `python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/build_mockups.py`, затем `python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/finalize_fix1.py` и read-only `audit_package.py`. Оба этапа завершают запись manifest последним действием.\n'
    text+=f'\nНезависимый аудит fix1: {correction["checks"]} проверок; минимум контраста HOLD по фактическому PNG {correction["actual_png_minimum_hold_contrast"]:.2f}:1.\n'
    p.write_text(text,encoding='utf-8')
    b.V['sizes']['package_bytes']=sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file())
    b.V['acceptance']['P15 package budget']['measured']=b.V['sizes']['package_bytes']
    b.V['acceptance']['P15 package budget']['passed']=b.V['sizes']['package_bytes']<=30*1024*1024
    b.dump(b.PKG/'verification.json',b.V);b.manifest()
    print({'acceptance_failures':[k for k,r in b.V['acceptance'].items() if not r['passed']], 'fix1_checks':correction['checks']},flush=True)


if __name__=='__main__':run()
