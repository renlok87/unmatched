"""Document B2; append provenance while retaining every byte of the A/B records."""
import sys
sys.dont_write_bytecode=True
from build_kit import *

def main():
    baseline=json.loads((ART/'stage-b2-baseline.json').read_text('utf-8'))
    assets=json.loads((KIT/'assets.json').read_text('utf-8'))
    for name in ['README.md','prompts.md','generation-records.json']:
        ext=Path(name).suffix;archive=ART/(Path(name).stem+'-b1'+ext)
        if not archive.exists():
            raw=(ART/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==baseline['document_baseline'][name]
            archive.write_bytes(raw)
        assert sha(archive)==baseline['document_baseline'][name]
    rows=[]
    for n,d in assets.items():
        body=(d['body_color']+' / '+str(d['body_opacity'])) if d['body_color'] else 'прозрачная вставка / орнамент'
        rows.append('| `'+n+'` | '+'×'.join(map(str,d['size_su']))+' | '+('/'.join(map(str,d['slice_su'])) if d['stretch'] not in ['none','tile_x'] else d['stretch'])+' | '+body+' | '+d['text_color']+' |')
    readme='''# HUD v2 — Этап B2

Дата: 2026-10-15. Комплект A «Мраморный акрополь» усилен: **56 ассетов, 168 RGBA PNG**, ×1 / ×2 / masters 4 px/su. **5 встроенных ImageGen-вызовов из лимита 25**. Неизменённые прозрачные генерации B201…B205 находятся в `kit/source-masters/`, точные запросы — `prompts/B201.json`…`B205.json`. Сохранён полный этап B в `kit-b1/`; его 179 файлов проверены по исходным хешам.

Крупные Panel, Modal, Toast, TurnPlate, StatusBanner и PileFrame получили **видимую полосу материала 7 su при ×1**, вместо прежнего тонкого контура. Panel/Modal имеют фиксированные углы 28 su, Toast 24 su, у TurnPlate — боковые срезы 26 su, у баннера — 48 su. В углах крупный золотой акант; мрамор со спокойными прожилками и золотыми внутренним/наружным скосами. StatusBanner получил массивные торцы с меандром и рельефным золотым краем. Все срезы приведены в таблице ниже и `slice-margins.json`.

Портретные медальоны 80 и 64 su получили широкий мраморный обод и крупные золотые лавры. Прозрачные маски портретов теперь **54 и 42 su**, canvas остался 88 и 72 su. ActionRing получил мраморно-золотую оправу с navy-эмалью; добавлен **`T_Hud_ActionPlate` 80×112 su**, 9-slice 12/12/12/12, позади диска и его подписи. Самостоятельные диски v3 не изменены. `KeyBadge` — золотая эмалевая плитка с отдельной тёмной буквой; `KeyChip` сохраняет обязательное тело #15232E и светлую букву. У кнопок мраморный скос 4 su с более светлым верхом и тёмным низом; Hover усиливает золото, Pressed меняет скос, Primary использует сгенерированную золотую фольгу на кромке. Центр Primary ровный, под текстом нет фактурного шума. FighterPlate остались лёгкими.

**Цветовой контракт live-игры имеет приоритет над всеми рекомендациями этапа B ниже.** Все 29 тел skin keys взяты непосредственно из manifest v1, с исходной opacity. Новые текстовые плашки, HP, статус, ход, колода/сброс, подложка руки, действия и FighterPlate — navy #061623, alpha 235/255 (0,921569). Modal непрозрачен. Цвет и alpha центра не зависят от состояния орнамента. Focus в B2 — **полный скин с обязательным телом**, а не пустой overlay этапа B; не складывать его тело поверх Normal. Текстуры tint=white, иначе игровой tint перекрасит материалы. В комплекте нет букв, цифр, игровых сканов или встроенных v3-иконок.

Проверка `verification.json → stage_b2` измеряет **123 текстовых тела** (41 ассет × 3 масштаба) по реальным RGBA PNG, в области центра ±10% ширины и высоты. Цвет и alpha точные, допустима лишь квантизация alpha до 8 бит. Проверены оба светлых цвета игры и тёмный текст Primary, включая наложение на чёрный, navy, светлый мрамор и белый фон. Все navy-тела проходят 4,5:1; например Panel даёт минимум 12,89:1 с основным и 7,14:1 со вторичным текстом даже поверх белого.

**Полный контрастный gate не пройден: в фиксированной палитре есть несовместимые требования.** #F2EDE4 на обязательном teal #0D7A89 даёт **4,32694:1**, #B9B2A6 — **2,39819:1** (`Btn_Selected`, `ProgressFill`, `Check_On`). Тёмный #061623 на обязательном disabled Primary #4E5457 даёт **2,38032:1**. Без изменения фиксированного цвета игры либо обязательного тела эти пары не достигают 4,5:1. Цвета не подменены и провал не скрыт; `all_requirements_pass=false`. Для ProgressFill/Check_On это консервативная проверка заданной пары, даже если runtime использует только glyph/заливку без букв. SliderThumb не несёт текста; его тёмная пара дана справочно.

**Технические проверки прошли:** 168 PNG, straight RGBA, нулевой RGB у alpha=0, нет green spill; пустые вставки колец/карт сохранены; края для растяжения имеют постоянный поперечный профиль; углы побайтно совпадают в **1107 растяжениях**. Panel/Modal показаны в девяти сочетаниях 144/240/336 × 80/112/160 su на обоих фонах (`kit-preview/stretch/`). `kit/catalog.png` и 23 native-листа в `kit-preview/review/` показывают оба фона в ×1/×2/4 px/su. Метаданные, размеры, срезы и SHA-256 — в `kit/manifest.json`.

Финальные сборки — `kit-preview/own-turn.png`, `combat.png` (1920×1080); `compare-own-turn.png` и `compare-combat.png` — концепт A / B2 при 100%. **`compare-b-vs-b2-own-turn.png`** — сохранённый B / B2, дополнительно есть сравнение боя. PNG старого B сохранены как `*-b1.png`. Реальные сканы остаются только в derived-каталоге. Под полупрозрачными скинами старый HUD скриншотов удалён клонированием чистых областей этих же refs; все такие операции записаны в `*-layers.json`. Это монтаж для проверки ассетов, не живой кадр Unreal.

Слабые места: 9-slice требует ровных продольных полос, поэтому длинные рельсы менее живописны, чем цельный концепт A. Мелкие прожилки при ×1 становятся оттенком материала; крупных листьев и меандра достаточно для чтения формы. Полные рамки ActionPlate делают блок действий плотнее концепта. Фиксированные конфликтные пары текста перечислены выше. Unreal-импорт, фильтрация, DPI, hit boxes и живые переходы состояний в этой задаче не проверялись.

Воспроизведение из корня проекта (Pillow, NumPy и существующий Roboto Bold Condensed):

```text
python -X utf8 art/imagegen/hud-v2-codex/_tools/build_b2.py
python -X utf8 art/imagegen/hud-v2-codex/_tools/compose_b2.py
python -X utf8 art/imagegen/hud-v2-codex/_tools/verify_b2.py
python -X utf8 art/imagegen/hud-v2-codex/_tools/document_b2.py
python -X utf8 art/imagegen/hud-v2-codex/_tools/index_b2.py
```

Исходные команды `*_kit.py` ниже относятся к архивному B и восстановят его оформление; для B2 использовать команды выше. Изменения только в двух разрешённых каталогах. Git, импорт в Unreal и запуск клиента не выполнялись. A/B-документы и 18 старых generation records сохранены побайтно в `*-b1.*`; исходная A-проверка — `stage-a-verification.json`. Ниже исторические этапы B и A без изменений.

`verify_b2.py` возвращает код 2 из-за описанных конфликтов контраста; технические ошибки имели бы код 1. Статус `technical_status=pass` не означает полного прохождения цветового контракта.

| PNG-ключ | Canvas ×1, su | Срез L/T/R/B, su | Тело / alpha | Текст runtime |
|---|---:|---|---|---|
'''+ '\n'.join(rows)+'\n\n'
    marker=b'<!-- STAGE-B2-END -->\n\n'
    (ART/'README.md').write_bytes(readme.encode('utf-8')+marker+(ART/'README-b1.md').read_bytes())
    sources=[json.loads((ART/'prompts'/f'B2{i:02}.json').read_text('utf-8')) for i in range(1,6)]
    prompts='# HUD v2 — Этап B2: prompts\n\n5 built-in ImageGen calls / budget 25. Actual alpha requested; original results retained. No CLI fallback.\n\n'
    prompts+='\n\n'.join('## '+s['id']+'\n\n'+s['prompt'] for s in sources)+'\n\n'
    (ART/'prompts.md').write_bytes(prompts.encode('utf-8')+marker+(ART/'prompts-b1.md').read_bytes())
    old=(ART/'generation-records-b1.json').read_bytes();pos=old.rfind(b']');records=[]
    for i,s in enumerate(sources,1):
        records.append({'call':18+i,'stage':'B2','stage_call':i,'prompt_id':s['id'],'tool':'built-in image_gen',
            'prompt_file':str((ART/'prompts'/(s['id']+'.json')).relative_to(ROOT)).replace('\\','/'),
            'source_path':s['source_path'],'raw_file':s['raw_file'],'output_size':s['output_size'],'sha256':s['sha256'],
            'requested_alpha':True,'kept':True,'reviewed_at_native_size':True,
            'selection':'Generated marble, gold and laurel ornament retained; deterministic crop/9-slice/body and alpha enforcement in build_b2.py.',
            'derived_assets':[n for n,d in assets.items() if s['id'] in d['source_masters']]})
    addition=(',\n'+',\n'.join(json.dumps(x,ensure_ascii=False,indent=2) for x in records)+'\n').encode('utf-8')
    (ART/'generation-records.json').write_bytes(old[:pos]+addition+old[pos:])
    assert len(json.loads((ART/'generation-records.json').read_text('utf-8')))==23
    base_sources=json.loads((ART/'kit-b1/source-masters/generation.json').read_text('utf-8'))
    write_json(KIT/'source-masters/generation.json',base_sources+sources)
    contract=json.loads((ART/'kit-b1/runtime-contract.json').read_text('utf-8'))
    contract.update({'stage':'B2','body_contract':'Exact v1 RGB and opacity; fixed live text colours; contrast exceptions are in verification.json.stage_b2',
        'focus':{'overlay_only':False,'full_body_skin':True,'canvas_outset_su':5,'reason':'B2 hard body-colour contract overrides B transparent focus choice'},
        'widgets':{n:{'size_su':d['size_su'],'slice_su':d['slice_su'],'body_color':d['body_color'],'body_opacity':d['body_opacity'],'text_color':d['text_color'],
                       'insert_diameter_su':d.get('insert_diameter_su'),'stretch':d['stretch']} for n,d in assets.items()},'runtime_import_verified':False})
    write_json(KIT/'runtime-contract.json',contract)
    write_json(ART/'stage-b2-record-preservation.json',{'readme_b1_suffix_unchanged':(ART/'README.md').read_bytes().split(marker,1)[1]==(ART/'README-b1.md').read_bytes(),
        'prompts_b1_suffix_unchanged':(ART/'prompts.md').read_bytes().split(marker,1)[1]==(ART/'prompts-b1.md').read_bytes(),
        'generation_b1_prefix_unchanged':(ART/'generation-records.json').read_bytes()[:pos]==old[:pos],
        'b1_record_count':18,'b2_record_count':5,'built_in_imagegen_calls_b2':5,'budget_b2':25})
    print('B2 docs written; 5 generation records appended; original 18-record prefix and A/B docs preserved.')

if __name__=='__main__':main()
