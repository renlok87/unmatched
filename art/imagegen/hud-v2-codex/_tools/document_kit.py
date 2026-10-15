"""Preserve stage A bytes; append B generation metadata and prepend B documentation."""
import sys
sys.dont_write_bytecode=True
from build_kit import *
TARGETS={
'PortraitFrame':'Портрет своего героя: кольцо 80 su, вставка 60 su, поле 4 su. Портрет под кольцом в круглой маске.',
'PortraitFrame_Active':'То же кольцо 80 su во время своего хода; статичный тёплый glow.',
'PortraitFrame_64':'Портрет соперника: кольцо 64 su, вставка 48 su, поле 4 su.',
'PortraitFrame_Active_64':'Активный ход соперника, вариант 64 su.',
'SidekickRing':'Мини-портрет помощника: номинал 32 su, вставка 25 su, поле 2 su.',
'HpPlate':'HP героя: сердце v3 в слот [8,8,24,24], число справа. Левый торец 40 su фиксирует слот.',
'StatusBanner':'Верхний центральный статус; текст поверх navy. M/A/G — отдельные KeyBadge.',
'TurnPlate':'Верхняя левая плашка «Ход N»; menu/connection v3 отдельно, тёмный текст.',
'KeyBadge':'Буква M/A/G/E поверх navy; отдельный слой на углу action ring.',
'HandTray':'Низкая подложка руки, штатная высота 56 su; растягивать по ширине.',
'CardGlow_Hover':'Тёплая внешняя рамка карты 150×208; карта с отступом [12,12] на canvas 174×232.',
'CardGlow_Selected':'Та же геометрия, более сильный teal-ореол выбора; вся вставка карты прозрачна.',
'CardBackSlot':'Одна рубашка соперника 24×34; canvas 28×38, вставка [2,2,24,34]; рубашка отдельно.',
'PileFrame':'Чип колоды/сброса: отдельно значок v3 и счётчик поверх navy.',
'CombatRibbon_Attack':'Над атакующей картой: красная эмаль, светлый заголовок «АТАКА · …».',
'CombatRibbon_Defense':'Над защищающейся картой: синяя эмаль, светлый заголовок «ЗАЩИТА · …».',
'CombatFrame':'Вокруг карты 230×322 su: canvas 250×342, вставка [10,10,230,322]. Карта под рамкой.',
'VersusBadge':'Центральный счёт/результат «3 : 1», текст отдельно.',
'FighterPlate':'Плашка своей фигуры при hover/selection: digit slot [7,7,18,18], HP-track [31,24,82,2]. Цифра, HP fill и значение отдельно.',
'FighterPlate_Enemy':'Та же плашка противника: синий слот и холодная кромка, отдельный team marker v3.',
'Divider':'Повторять меандр по X, не растягивать рисунок.'}
for st in ['Normal','Hover','Pressed','Disabled','Active']:
    TARGETS['ActionRing_'+st]='Обод действий M/A/G/E, состояние '+st+': номинал 64 su, вставка 50 su, поле 4 su. Неизменённый диск v3 50 su под кольцом по центру.'

def main():
    assets=json.loads((KIT/'assets.json').read_text('utf-8'))
    sources=json.loads((KIT/'source-masters/generation.json').read_text('utf-8'))
    baseline=json.loads((KIT/'stage-a-baseline.json').read_text('utf-8'))
    table=['| PNG-ключ | Canvas ×1 | Срез L/T/R/B, su | Код / виджет |','|---|---:|---|---|']
    for n,d in assets.items():
        info=('Подменить существующий skin key `'+d['ue_skin_key']+'`.' if d['ue_skin_key'] else TARGETS[n.removeprefix('T_Hud_')])
        if d.get('focus_overlay'):info+=' Только outer ring поверх Normal: canvas offset 5 su, видимый вынос 4 su, кольцо 2 su, зазор 2 su; тело прозрачное.'
        if n=='T_Skin_Check_On':info+=' Галочку `ui-check` добавляет код.'
        if n=='T_Skin_Input_Error':info+=' Красная внутренняя кромка, error icon v3 отдельно.'
        table.append('| `'+n+'` | '+'×'.join(map(str,d['size_su']))+' | '+('/'.join(map(str,d['slice_su'])) if d['stretch'] not in ['none','tile_x'] else d['stretch'])+' | '+info+' |')
    section=(ART/'_tools/stage-b-readme.md').read_text('utf-8').replace('{{TABLE}}','\n'.join(table))
    prompts='# HUD v2 — Этап B: prompts\n\n6 built-in ImageGen calls / budget 35. RGB masters on pure #00FF00; Pillow creates alpha. B01/B02 use A-styleguide as style reference only.\n\n'
    prompts+='\n\n'.join('## '+s['id']+'\n\n'+s['prompt'] for s in sources)+'\n\n'
    marker=b'<!-- STAGE-B-END -->\n\n'
    for name,prefix in [('README.md',section),('prompts.md',prompts)]:
        path=ART/name;raw=path.read_bytes();original=raw.split(marker,1)[1] if marker in raw else raw
        assert hashlib.sha256(original).hexdigest()==baseline[str(path.relative_to(ROOT))],name
        path.write_bytes(prefix.encode('utf-8')+marker+original)
    path=ART/'generation-records.json';current=path.read_bytes();ctxpath=KIT/'stage-a-record-preservation.json'
    if not ctxpath.exists():
        pos=current.rfind(b']')
        write_json(ctxpath,{'prefix_length':pos,'tail_hex':current[pos:].hex(),'original_sha256':hashlib.sha256(current).hexdigest()})
    ctx=json.loads(ctxpath.read_text('utf-8'));pos=ctx['prefix_length']
    original=current[:pos]+bytes.fromhex(ctx['tail_hex']);assert hashlib.sha256(original).hexdigest()==ctx['original_sha256']
    new=[]
    for i,s in enumerate(sources,1):
        raw=ART/s['raw_file'];q=Image.open(raw)
        prompt={'id':s['id'],'stage':'B','prompt':s['prompt'],'transparent_background':False,'style_references':['art/imagegen/hud-v2-codex/styleguides/A-styleguide.png'] if i<=2 else []}
        write_json(ART/'prompts'/(s['id']+'.json'),prompt)
        new.append({'call':12+i,'stage':'B','stage_call':i,'prompt_id':s['id'],'prompt_file':'art/imagegen/hud-v2-codex/prompts/'+s['id']+'.json',
            'source_path':s['source_path'],'raw_file':str(raw.relative_to(ROOT)).replace('\\','/'),'output_size':list(q.size),'sha256':sha(raw),
            'requested_alpha':False,'key_background':'#00FF00','kept':True,'reviewed_at_native_size':True,
            'selection':'Орнамент принят; Pillow вырезал фон с decontamination и выровнял stretch-кромки. Текст, иконки и сканы в kit отсутствуют.',
            'derived_assets':[n for n,d in assets.items() if s['id'] in d['source_masters']]})
    addition=(',\n'+',\n'.join(json.dumps(v,ensure_ascii=False,indent=2) for v in new)+'\n').encode('utf-8')
    path.write_bytes(original[:pos]+addition+original[pos:]);assert len(json.loads(path.read_text('utf-8')))==18
    write_json(KIT/'runtime-contract.json',{'direction':'A Marble Acropolis','font':'Roboto Bold Condensed','icons':'hud-icons-v3',
        'alpha':'straight RGBA, zero RGB at zero alpha','tint':'white','margin_normalization':'L/R divided by full PNG width, T/B by full PNG height',
        'focus':{'overlay_only':True,'canvas_outset_su':5,'visual_outset_su':4,'gap_su':2,'ring_width_su':2},
        'checkbox':{'nominal_su':24,'canvas_su':26,'separate_glyph':'ui-check'},'widgets':TARGETS,'runtime_import_verified':False})
    write_json(ART/'stage-b-record-preservation.json',{'readme_stage_a_suffix_unchanged':True,'prompts_stage_a_suffix_unchanged':True,'generation_stage_a_prefix_unchanged':True,'stage_a_records':12,'stage_b_records':6})
    print('Stage B docs prepended and 6 records appended; original bytes verified.')
if __name__=='__main__':main()
