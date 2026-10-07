#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offline fix1 workflow. Mutations are guarded to the five authorised packages.

Run render SC-14 .. SC-18 in dependency order, reviewing/finalising each before
its consumer. Baselines preserve run-1 hashes and documentation. No Git/MCP/UE.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import importlib
import json
import hashlib
import re

ROOT=Path(__file__).resolve().parents[4]
SETS={'SC-14':'sc14-room-hero','SC-15':'sc15-room-board','SC-16':'sc16-room-deck',
      'SC-17':'sc17-room-ready','SC-18':'sc18-room-countdown'}
MODULES={'SC-14':'sc14_room_hero','SC-15':'sc15_room_board','SC-16':'sc16_room_deck',
         'SC-17':'sc17_room_ready','SC-18':'sc18_room_countdown'}
ALLOWED=[ROOT/f'art/imagegen/{s}-codex' for s in SETS.values()]
ALLOWED += [ROOT/f'scraped-data/derived/{s}-codex' for s in SETS.values()]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,value):
    p=p.resolve()
    assert any(p.is_relative_to(r) for r in ALLOWED)
    assert not any(p.is_relative_to(r/'inputs') for r in ALLOWED if 'scraped-data' in str(r))
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def setup(identifier):
    package=ROOT/f'art/imagegen/{SETS[identifier]}-codex'
    sys.path.insert(0,str(package/'_tools'))
    return package,importlib.import_module(MODULES[identifier]),importlib.import_module('sc14_room_hero')

def copy_final(package):
    sources=[('sc14-room-hero','sc14_room_hero.py')]
    if package.name=='sc18-room-countdown-codex':sources.append(('sc17-room-ready','sc17_room_ready.py'))
    for source,name in sources:
        src=ROOT/f'art/imagegen/{source}-codex/_tools/{name}';dst=package/'_tools'/name
        if src!=dst:dst.write_bytes(src.read_bytes())

def refresh_inputs(b,identifier,extra,copies):
    p=b.PACKAGE/'source-hashes-before.json';old=b.load(p);current=b.inputs(identifier,extra)
    allowed_sources={entry['source'] for entry in b.load(b.PACKAGE/'copy-provenance.json')}
    allowed_sources.update(source for source,name in copies)
    allowed_sources.update(f'art/imagegen/{s}-codex/{name}' for s in SETS.values()
                           for name in ('manifest-sha256.json','README.md'))
    revisions=[]
    for path,previous in old['inputs'].items():
        actual=b.sha(b.ROOT/path)
        if actual!=previous:
            assert path in allowed_sources,('Unapproved source change',path)
            revisions.append({'file':path,'sha256_before':previous,'sha256_after':actual,
                              'reason':'Authorised fix1 final renderer/metadata dependency; run-1 snapshot retained in fix1-baseline.json'})
    added=set(current)-set(old['inputs'])
    assert added <= {'docs/game-design/visual/06-tasks/prompts/SC-14-series.fix1.codex.md'},added
    assert not set(old['inputs'])-set(current)
    old['inputs']=current
    old.setdefault('dependency_metadata_revisions',[]).extend(revisions)
    old['fix1']={'run1_snapshot':'fix1-baseline.json:source_snapshot_before','revisions':revisions,
                 'added_inputs':{p:current[p] for p in sorted(added)},'protected_inputs_unchanged':True}
    b.dump(p,old)

def render(identifier):
    package=ROOT/f'art/imagegen/{SETS[identifier]}-codex';copy_final(package)
    package,module,b=setup(identifier)
    original=b.prepare
    def prepare(ident,extra=(),copies=()):
        refresh_inputs(b,ident,extra,copies)
        return original(ident,extra,copies)
    b.prepare=prepare
    v=b.build(identifier,b.sc14_states()) if identifier=='SC-14' else module.build()
    baseline=load(package/'fix1-baseline.json')
    text=baseline['readme_before']
    text=text.replace('SC-01 модаль 640×360','SC-01 модаль шириной 640 su, высота по содержимому')
    text=text.replace('Leave: неизменённый шаблон SC-01','Leave: скины и базовая ширина SC-01, высота по содержимому')
    text=re.sub(r'Минимальный контраст текста [0-9.]+:1',f"Минимальный контраст текста {v['contrast']['text_minimum']:.4f}:1",text)
    # The palette count is measured again below; remove the obsolete run-1 count.
    text=re.sub(r'Палитра измерена на \d+ непрозрачных плоских пикселях UI: вне ΔE76 ≤ 3 — \d+ \([^)]*\)\.',
                'Попиксельный ΔE финала с артом не заменён ложным значением 0; UI цвета и их исходные композиты перечислены.',text)
    detail={
      'SC-14':'Без героя зрителя DeckCount отсутствует; остаётся disabled «ПРОСМОТР КОЛОДЫ» с «Выберите героя». Фразы «ближний бой» / «дальний бой» переносятся только целиком.',
      'SC-15':'Повторно скопирован финальный SC-14. Оверлей показывает обе UUmBoardCard с Thumbnail, NameText, CheckChip и LockedReason.',
      'SC-16':'Повторно скопирован финальный SC-14. Оверлей содержит DeckCount, DeckButton; колода называется UUmScreenInspect (deck mode). Принятые SC-23/SC-21 не изменены.',
      'SC-17':'Повторно скопирован финальный SC-14. Диалог выхода: ширина SC-01 640 su, высота 148 su (24 + 28 + 24 + 48 + 24), по центру; «ОТМЕНА» обычная слева, «ДА» главная справа. Библиотека SC-01 не изменена.',
      'SC-18':'Повторно скопированы финальные SC-14 и SC-17. CountText расположен на непрозрачной CountPlate (kind modal, panel.bg 1, край 1 su, радиус 8 su), отступы 32/24 su по измеренным границам текста, минимум 160 su; остальной экран под второй вуалью 0,8.'}[identifier]
    text+='\n## fix1\n\n'+detail+' Все состояния заново отрисованы в цвете и Rec.709-сером на четырёх холстах. Оверлеи — только контуры и номера Rxx на card.navy; рядом листы `*-legend-*.png` с BindWidget, кадром и x/y/w/h в su. Состояния отсутствия отмечены hidden; при отсутствии героя DeckCount не создаётся. Предыдущие хеши сохранены в fix1-baseline.json, изменения и проверки — в блоке fix1 verification.json. Полная художественная приёмка не подменена технической проверкой: ограничения исходных кромок HB-08 сохранены.\n'
    b.text_file(package/'README.md',text)
    audit=importlib.import_module('audit_palette');audit.run()
    review=importlib.import_module('finalize_review');review.sheets()
    # Legends get their own native-size sheets, all final PNGs remain reviewable.
    from PIL import Image,ImageDraw,ImageFont
    for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]:
        paths=sorted((package/'comparison').glob(f'{identifier}-overlay-{res}-{scale}-legend-*.png'))
        paths=[p for p in paths if not p.stem.endswith('-gray')]
        for start in range(0,len(paths),4):
            for gray in (False,True):
                chunk=[p.with_name(p.stem+'-gray.png') if gray else p for p in paths[start:start+4]]
                W,H=Image.open(chunk[0]).size;sheet=Image.new('RGBA',(W*2,(H+28)*2),b.theme().color('card.navy')+(255,))
                d=ImageDraw.Draw(sheet);font=ImageFont.truetype(str(b.FONT/'Roboto-Regular.ttf'),14)
                for i,p in enumerate(chunk):
                    xy=((i%2)*W,(i//2)*(H+28))
                    with Image.open(p) as im:sheet.alpha_composite(im,(xy[0],xy[1]+28))
                    d.text((xy[0]+12,xy[1]+6),p.name,font=font,fill=b.theme().color('text.primary'))
                dest=b.DERIVED/f'fix1-legends-{res}-{scale}-{start//4+1}{"-gray" if gray else ""}.png'
                sheet.save(b.guard(dest),optimize=True)
    b.refresh_manifest()
    print(identifier,'rendered; inspect comparison and fix1-legends sheets before review',flush=True)

def checks(identifier,b,v):
    for key,f in v['frames'].items():
        comp=f['components']
        assert not f['issues'] and not f['text_pair_overlaps'],key
        for n in f['notes']:
            if 'sidekicks' in n.get('source',''):
                assert all(not line.endswith(('ближний','дальний')) and line!='бой' for line in n['lines'])
        if identifier=='SC-14':
            hero=not key.startswith(('waiting-','taken-'))
            assert ('DeckCount' in comp)==hero
            assert comp['DeckButton']['disabled']==(not hero)
        if identifier=='SC-17' and key.startswith('leave-'):
            x,y,w,h=comp['UUmConfirmDialog']['rect_su'];W,H=f['viewport']['canvas_su']
            assert w==640 and h==148 and abs(x+w/2-W/2)<1e-6 and abs(y+h/2-H/2)<1e-6
            assert all(n in comp for n in ('UUmConfirmDialog.TitleText','UUmConfirmDialog.CancelButton','UUmConfirmDialog.ConfirmButton'))
        if identifier=='SC-16' and key.startswith('deck-open-'):
            assert comp['UUmScreenInspect']['mode']=='deck' and 'UUmConfirmDialog' not in comp
        if identifier=='SC-18':
            plate=comp['CountPlate'];x,y,w,h=plate['rect_su'];tx,ty,tw,th=comp['CountText']['rect_su'];W,H=f['viewport']['canvas_su']
            assert plate['kind']=='modal' and plate['alpha']==1 and plate['radius_su']==8 and plate['edge_su']==1
            assert abs(x+w/2-W/2)<1e-6 and abs(y+h/2-H/2)<1e-6
            assert w>=160 and w+1e-6>=tw+64 and abs(h-th-48)<1e-6
            text=next(t for t in f['text_contrast'] if t['layer']=='modal')
            assert text['background']==list(b.theme().color('panel.bg')) and text['ratio']>=4.5
    for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]:
        legend=load(b.PACKAGE/f'comparison/{identifier}-overlay-{res}-{scale}-legend.json')
        for key,f in v['frames'].items():
            if not key.endswith(f'-{res}-{scale}'):continue
            state=key[:-len(f'-{res}-{scale}')]
            for name,item in f['components'].items():
                assert any(e['name']==name and e['rect_su']==item['rect_su'] and state in e['frames'] for e in legend['entries']),(key,name)
    return {'deck_without_hero':True,'atomic_attack_phrase':True,'count_plate':identifier=='SC-18',
            'content_sized_leave_dialog':identifier=='SC-17','all_overlay_rectangles_keyed':True}

def finish(identifier):
    package,module,b=setup(identifier);v=load(package/'verification.json')
    proof=checks(identifier,b,v)
    review=load(package/'visual-review.json')
    assert review.get('fix1',{}).get('personally_viewed_final_pngs'), 'Record actual visual inspection first'
    # Independent native-size/hash/capture checks, retaining honest acceptance.
    importlib.import_module('finalize_review').finalize()
    v=load(package/'verification.json');baseline=load(package/'fix1-baseline.json')
    old=baseline['files'];changed=[]
    excluded={rel(package/'verification.json'),rel(package/'manifest-sha256.json')}
    for folder in (package,b.DERIVED):
        for p in sorted(folder.rglob('*')):
            if not p.is_file() or rel(p) in excluded:continue
            h=sha(p)
            if old.get(rel(p))!=h:changed.append({'file':rel(p),'sha256_before':old.get(rel(p)),'sha256_after':h})
    # Self-hashes cannot live inside the bytes they hash: manifest covers the
    # verification; manifest itself uses the ordinary self-exclusion contract.
    changed.append({'file':rel(package/'verification.json'),'sha256_before':old[rel(package/'verification.json')],
                    'sha256_after_location':'manifest-sha256.json:files (avoids recursive self-hash)'})
    v['fix1']={'run':'fix1','prompt':'docs/game-design/visual/06-tasks/prompts/SC-14-series.fix1.codex.md',
              'baseline':'fix1-baseline.json','changes':(package/'README.md').read_text(encoding='utf-8').split('## fix1\n',1)[1].strip(),
              'changed_files':changed,'manifest_self_exclusion':{'file':rel(package/'manifest-sha256.json'),
                  'sha256_before':old[rel(package/'manifest-sha256.json')],'reason':'Manifest cannot contain its own digest; independently validated after rebuilding.'},
              'copy_hashes':load(package/'copy-provenance.json'),'checks':proof,
              'protected_inputs_unchanged':all(sha(ROOT/p)==h for p,h in old.items() if '/inputs/' in p),
              'visual_review':'visual-review.json','technical_checks_passed':True,
              'full_acceptance':v['full_acceptance']}
    assert v['fix1']['protected_inputs_unchanged']
    b.dump(package/'verification.json',v)
    manifest=load(package/'manifest-sha256.json');facts=manifest['facts']
    facts['post_render_audit_inputs']=load(package/'source-hashes-before.json').get('audit_inputs',{})
    b.refresh_manifest(facts)
    manifest=load(package/'manifest-sha256.json')
    assert all(sha(ROOT/p)==h for p,h in manifest['files'].items())
    print(identifier,'fix1 final checks passed; full acceptance:',v['full_acceptance'],flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    mode,identifier=sys.argv[1:]
    (render if mode=='render' else finish)(identifier)
