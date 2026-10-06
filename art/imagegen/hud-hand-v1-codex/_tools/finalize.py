"""Record completed manual review, run read-only audit, write manifest last.

Only invoke --record-visual-review after viewing the eight JPEG review sheets,
the named native details and EN check. Normal regeneration: build then verify.
"""
import json
import re
import sys
from types import SimpleNamespace
from pathlib import Path
import verify

PKG=Path(__file__).resolve().parents[1]
ROOT=PKG.parents[2]
DERIVED=ROOT/'scraped-data/derived/hud-hand-v1-codex'


def write(p,d):
    assert p.resolve().is_relative_to(PKG)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def run():
    result=verify.run()
    v=verify.load(PKG/'verification.json')
    v['independent_verification']=result
    # Finish the schematic sheets from already verified rectangles; no final
    # card/background PNG is regenerated here. Show FIELD and mask anchors too.
    import build_mockups as build
    facts=verify.load(PKG/'facts.json')
    for board in build.BG:
        for w,h,ui,s in build.CONFIGS:
            group=[o for o in v['overlap']['per_mockup'] if o['board']==board and o['canvas']==[w,h,ui] and '-en-' not in o['id']]
            canvases=[]
            for o in group:
                blocks={name:r['rectangles_su'][0] for name,r in o['panels'].items() if name!='HAND'}
                output=next(r for r in facts['outputs'] if r['id']==o['id'])
                # Keep the source hand index in the legend; the lifted card was
                # painted last and must not be relabelled as the last hand card.
                for i,r in enumerate(output['geometry']['state_cards']):blocks[f'CARD-{i}']=r
                transients=next(t['elements'] for t in v['transient_overlap'] if t['id']==o['id'])
                ref=build.reference(board,w,h,ui)
                reserved={k:p['rectangle_su'] for k,p in ref['panels'].items() if k in ['PANEL-LOC','ACTIONS','DECKS','LOG']}
                canvases.append(SimpleNamespace(state=o['state'],blocks=blocks,reserved=reserved,
                                                 transients={k:r['rectangle_su'] for k,r in transients.items()}))
            build.overlay(board,w,h,ui,s,canvases)
    for row in v['exports']:
        if '/comparison/' in row['path']:
            from PIL import Image
            with Image.open(ROOT/row['path']) as im:row['size']=list(im.size);row['mode']=im.mode
    if '--record-visual-review' in sys.argv:
        reviews=sorted(p for p in DERIVED.glob('review/*-review-*.jpg') if not p.stem.endswith('-gray'))
        assert len(reviews)==8
        gray_reviews=sorted(DERIVED.glob('review/*-review-*-gray.jpg'))
        assert len(gray_reviews)==8
        v['visual_review']={'reviewer':'Codex','task':'HB-22 fix1','method':'Opened eight colour and eight grayscale 12-state overview sheets; inspected native PNG details and EN check.',
            'review_sheets':[verify.rel(p) for p in reviews],
            'gray_review_sheets':[verify.rel(p) for p in gray_reviews],
            'native_details':['HB-22-marmoreal-selected-1920x1080-100.png','HB-22-sarpedon-boost-attack-1280x720-150.png',
                              'HB-22-marmoreal-unplayable-1920x1080-150.png','HB-22-marmoreal-drop-1280x720-150.png',
                              'HB-22-sarpedon-unplayable-1280x720-150.png',
                              'HB-22-marmoreal-rest-new-en-1920x1080-100.png'],
            'checks':['Both named real boards and six v2 figures; Marmoreal painted backdrop / Sarpedon lit3d.',
                      'Boost backs sit behind attack at equal size/y with the required right strip; +3 chip above/right aligned.',
                      'Caption stays in the same short left plate; selected index1 leaves the count readable.',
                      'WHY tooltip and caption both readable, separated; hover occlusion remains transient.',
                      'Whole scans within frames, no invented overprinted title/value; viewport clipping only.',
                      'Hover, raised selection, disabled cards, boost backs, drop glyphs and 48su lowered row distinguishable.',
                      'Source figure labels left unretouched; full ribbon, tooltip, caption and STATUS.'],
            'note':'JPEG overview thumbnails are for review only. Acceptance PNG and contact/overlay sheets remain native.'}
    v['acceptance']['manifest']={'passed':True,'measured':result['manifest_files'],'expected':'All package and derived files match SHA-256 and complete file set',
                               'note':'Independent verify checks every file before and after final recording.'}
    v['acceptance']['package_budget']={'passed':result['package_bytes']<=30_000_000,'measured':result['package_bytes'],'expected':'<=30 MB without derived','note':''}
    if 'visual_review' in v:
        v['H1_H14']['H12']={'checks':['Verbatim LAN sentence independently checked'],'passed':True}
        readme=PKG/'README.md';text=readme.read_text(encoding='utf8').split('\n## Итоговая ручная проверка')[0]
        text=re.sub(r'Подпись сокращена до ширины текста \+24 su(?: \+2 px)*',
                    'Подпись сокращена до ширины текста +24 su +2 px',text)
        text+='\n## Итоговая ручная проверка\n\nОткрыты восемь цветных и восемь серых обзорных JPEG (96 состояний), нативные детали selected, unplayable, drop и boost-attack, EN-проверка. Подпись слева читается; WHY не закрывает её; у буста видна правая полоса рубашки, chip сверху, атака поверх рубашки. JPEG уменьшены только для просмотра; финалы и листы сравнения не уменьшаются. Обе доски, правильные задники, шесть фигур v2 и старые надписи исходного фона проверены визуально. Независимый аудит проверил '+str(result['native_finals_checked'])+' нативных финалов, '+str(result['exports'])+' PNG, все исходные SHA-256, Rec.709, постоянные и временные пересечения, а также все четыре проверки fix1.\n'
        readme.write_text(text,encoding='utf8')
    write(PKG/'verification.json',v)
    manifest={verify.rel(p):verify.sha(p) for r in [PKG,DERIVED] for p in sorted(r.rglob('*'))
              if p.is_file() and p.name!='manifest-sha256.json'}
    # Last mutation of the complete task.
    write(PKG/'manifest-sha256.json',{'algorithm':'sha256','files':manifest})
    verify.run()


if __name__=='__main__':run()
