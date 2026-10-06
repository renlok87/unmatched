"""Corrective provenance and before/after reports, inside HB-38 only."""
from pathlib import Path
import math
import fix1_font as composite

def game_rows(rows):
    # Original combat() changed its id AFTER persistent(); those eight records
    # were mislabeled toast-stack duplicates, not additional GAME mockups.
    unique={}
    for row in rows:
        if '-en-' not in row['id'] and '-combat-overlay-' not in row['id']:
            unique.setdefault(row['id'],row)
    return [unique[k] for k in sorted(unique)]

def summarize(pkg, derived, facts, verification, before, sha):
    v=verification;f=facts
    records=[]
    for index,row in enumerate(f['rendered_texts']):
        original=row.get('record',row)
        text=row['text'];size=original.get('font_px',max(1,math.ceil(row.get('nominal_px',16))))
        bold=original.get('bold_condensed',str(row.get('block','')).startswith('TOP/STATUS'))
        face=composite.font(size,bold)
        fallback=[{'index':i,'character':ch,'codepoint':f'U+{ord(ch):04X}','face':composite.FALLBACK.name}
                  for i,ch in enumerate(text) if ord(ch) not in face.primary_cmap]
        missing=sum(ord(z['character']) not in face.fallback_cmap for z in fallback)
        coverage={'record_index':index,'id':row.get('id',row.get('mockup')),'block':row.get('block'),
                  'text':text,'primary_face':Path(face.path).name,'font_px':size,
                  'fallback_characters':fallback,'missing_glyphs':missing}
        records.append(coverage)
    v['glyph_coverage']={'rendered_texts':records,'draw_calls':composite.RECORDS,
                         'missing_glyphs':sum(r['missing_glyphs'] for r in records)+sum(r['missing_glyphs'] for r in composite.RECORDS),
                         'fallback_face':composite.FALLBACK.as_posix(),
                         'method':'Best cmap per primary face; identical font size; shared primary baseline; same run metrics for bbox/advance/wrap/ellipsis. Raw draw calls cover native sheets and reused source layers.'}
    prior={(r['id'],r['seq']):r for r in before['log_rows']}
    changes=[]
    for row in v['log_ellipsis']:
        old=prior[(row['id'],row['seq'])]
        assert old['full_text']==row['full_text'], 'Full log text must not change'
        if old['displayed']!=row['displayed']:
            changes.append({'id':row['id'],'seq':row['seq'],'before':old['displayed'],'after':row['displayed']})
    placement_changes=[]
    for key in ('toast_placement','sub_placement','persistent_blocks','hand_geometry'):
        old=game_rows(before['game_placements'][key])
        new=game_rows(v[key])
        if old!=new:placement_changes.append(key)
    en='HB-38-marmoreal-toast-stack-en-1920x1080-100'
    ru='HB-38-marmoreal-toast-stack-1920x1080-100'
    output={r['id']:r for r in f['outputs']}
    en_diffs=[k for k,r in output[ru]['blocks'].items() if not k.startswith(('LOG','TOAST','SUB','REFUSE')) and output[en]['blocks'].get(k)!=r]
    pngs=[]
    for name,digest in before['game_png_sha256'].items():
        if '-en-' in name:continue
        path=Path(name)
        if sha(path)==digest:continue
        cid=path.stem.removesuffix('-gray')
        pngs.append({'id':cid,'path':name,'before':digest,'after':sha(path),'reason':'Fix 1 LOG glyph fallback / measured ellipsis'})
    v['fix1']={'before_file':'fix1-before.json','baseline_preserved':sha(pkg/'source-hashes-before.json')==before['source_baseline_sha256'],
               'displayed_log_changes':changes,'game_placements_unchanged':not placement_changes,
               'game_placement_changes':placement_changes,'comparison_note':'Unique GAME ids, first occurrence: original combat persistent records had duplicate GAME toast-stack ids before combat id assignment. Full original records remain in fix1-before.json.','en_base_rectangles_unchanged':not en_diffs,
               'en_base_rectangle_changes':en_diffs,'changed_ru_pngs':pngs}
    f['fix1']={'displayed_log_changes':changes,'combat_decision':'ВР-VS2-HB38-18','en_fit':v['en_fit'],'en_without_value':v['en_without_value']}

def markdown(v,before):
    lines=['## Исправления fix1','',
           '1. Весь рисуемый текст и его измерение используют Roboto с посимвольным DroidSansFallback на том же baseline и кегле. До: U+2192 отсутствовал в обоих Roboto, стрелка не рисовалась; после: `→` выводится fallback. Полные строки LOG сохранены; изменённые сокращения перечислены ниже.',
           '2. Overlay: вместо всех отклонённых прямоугольников показаны первые попытки фаз и последний отклонённый шаг каждого поиска вверх, контур state.warning 1 px без заливки. Пунктир text.secondary показывает STATUS.bottom + 8 su; легенда хранит число отклонений. Все попытки остаются в verification.',
           '3. COMBAT: клетки исключены из препятствий согласно ВР-VS2-HB38-18; figures и все HUD-блоки остаются препятствиями, HAND-CAPTION защищён зазором 8 su. Ниже приведены результаты до → после.',
           '4. EN check: ключевые подписи базового HUD взяты из SourceString (EN) st-hud/st-ms вместо RU; STATUS и подпись руки также переведены. Прямоугольники базового HUD совпадают с RU-парой. Имена и данные сохранены.','',
           '### Строки LOG с изменившимся отображением','',
           '| Макет / seq | До | После |','|---|---|---|']
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    for row in v['fix1']['displayed_log_changes']:
        lines.append(f"| {row['id']} / {row['seq']} | {cell(row['before'])} | {cell(row['after'])} |")
    if not v['fix1']['displayed_log_changes']:lines.append('| Все строки | без изменений текста | стрелки выводятся fallback |')
    lines += ['', '### Бой: до → после по доске и холсту','',
              '| Доска / холст | До: совместная группа | После: фаза | Тосты / капсула, su | figures_px2 | hud_px2 | spaces_px2 (информационно) | Тостов |',
              '|---|---|---|---|---|---|---|---|']
    for r in v['toast_placement_combat']:
        old=next(a for a in before['combat']['toast_placement_combat'] if a['id']==r['id'])
        oldphase=next((a['phase'] for a in old['attempts'] if a['zero']),'FAIL')
        chosen=next((a for a in reversed(r['attempts']) if a['zero']),None)
        sums={k:sum(z[k] for z in chosen['overlap']) if chosen else None for k in ['figures_px2','hud_px2','spaces_px2']}
        geometry=str((r['chosen_rectangles_su'],r['chosen_subtitle_rectangle_su']))
        lines.append(f"| {r['id'].replace('HB-38-','').replace('-combat-overlay-',' · ')} | {oldphase} | {r['chosen_phase'] or 'FAIL'} | {geometry} | {sums['figures_px2']} | {sums['hud_px2']} | {sums['spaces_px2']} | {r['toasts_shown']} |")
    lines += ['', '### EN fit','', '| Блок | До → после | Помещается |', '|---|---|---|']
    oldtexts=[r['text'] for r in before['en_strings'] if r.get('block') not in ['LOG','LOG.row','LOG.turn','TOAST-0','TOAST-1']]
    for i,r in enumerate(v['en_fit']):
        old=oldtexts[i] if i<len(oldtexts) else 'RU строка / StringTable'
        lines.append(f"| {r['block']} | {cell(old)} → {cell(r['text'])} | {'да' if r['passed'] else 'FAIL, без усечения'} |")
    lines+=['','Нет усечения: строки, не помещающиеся в принятый блок, сохраняются полностью и отмечены FAIL.' if any(not r['passed'] for r in v['en_fit']) else 'Все переведённые строки помещаются в принятые блоки, усечения нет.',
            'Базовые строки без EN: '+(str(v['en_without_value']) if v['en_without_value'] else 'нет; имена и числовые данные остаются из источников.'),'']
    return '\n'.join(lines)
