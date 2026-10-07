"""Asset-free, state-specific diagrams. No rendering of source illustrations."""
import re
from PIL import Image, ImageDraw, ImageFont


def make(base, vp, task, states, measurements):
    g = base.layout(vp)
    pages = []
    all_entries = {}
    audits = []
    scale = 2
    ink = base.theme().color('text.primary')
    edge = base.theme().color('text.secondary')
    bg = base.theme().color('card.navy')
    font = ImageFont.truetype(str(base.FONT/'Roboto-Regular.ttf'), 14)
    heading = ImageFont.truetype(str(base.FONT/'Roboto-BoldCondensed.ttf'), 24)
    for state, config in states.items():
        entries = []
        def add(name, rect, note='', drawn=True, dashed=False):
            entries.append({'bind_widget': name, 'rect_su': list(rect) if rect else None,
                            'note': note, 'box_drawn': drawn and rect is not None,
                            'dashed': dashed})
        for name in ('Header', 'NicknameText', 'MenuButton', 'LangChipRu', 'LangChipEn',
                     'GameList', 'ListTitle', 'CreateColumn', 'CreateTitle', 'ModeLabel',
                     'BoardLabel', 'CreateButton', 'CodeColumn', 'CodeTitle', 'OverviewCaption'):
            note = ''
            if name == 'CreateButton':
                note = 'busy; why.syncing = Синхронизация… (только подсказка)' if config.get('busy') else 'обычная' if len(config.get('code','')) == 6 else 'primary'
            add(name, g[name], note)
        add('RefreshButton', g['RefreshButton'], 'скрыта при ошибке' if config.get('list')=='error' else '', config.get('list')!='error')
        add('CreateNote', g['CreateNote'], 'Соперник — ИИ: AI Bot' if config.get('ai') else 'резерв, не рисуется в макете', dashed=not config.get('ai'))
        for name, selected in [('ModeChip1v1',not config.get('ai')), ('ModeChipAi',bool(config.get('ai')))]:
            add(name, g[name], 'выбран' if selected else 'обычный')
        for i in range(2):
            add(f'BoardChips[{i}]',g[f'BoardChips[{i}]'],'выбран' if i==config.get('board',0) else 'обычный')
        code=config.get('code','')
        for i in range(6):
            note='заполнена: '+code[i] if i<len(code) else 'пустая; подчёркивание 24×2 su'
            if config.get('keyboard') and len(code)<6 and i==len(code): note+='; Input_Focus'
            add(f'CodeCells[{i}]',g[f'CodeCells[{i}]'],note)
        add('JoinButton (code)',g['JoinButtonCode'], 'disabled; why.code.length' if len(code)<6 else 'primary; BtnPrimary_Focus, кольцо 2 su' if config.get('keyboard') else 'primary; normal')
        add('CodeError',g['CodeError'],'скрыт' if len(code)==6 and not config.get('error') else base.REASONS['why.code.length'] if len(code)<6 else base.STRINGS['screens.lobby.code.error.'+config['error']], dashed=len(code)==6 and not config.get('error'))
        if config.get('error'):
            x,y,w,h=g['CodeError']
            add('CodeError.BadgeRefuse',(x,y,24,24),'badge-refuse, 24 su')
            add('CodeError.Text',(x+32,y,w-32,h),base.STRINGS['screens.lobby.code.error.'+config['error']])
        add('RecoverButton',g['RecoverButton'],'скрыт: myGames = []; условный слот внутри CodeColumn' if g['RecoverButton'] else 'слот не рисуется: внутри CodeColumn нет места', dashed=True)
        if config.get('busy'):
            x,y,w,h=g['CreateButton'];label=base.STRINGS['screens.lobby.create.busy'].upper();tw=base.width(label,'type.button');left=x+(w-44-tw)/2
            add('CreateButton.Spinner',(left,y+8,32,32),'loader-spinner, 32 su')
            add('CreateButton.Label',(left+44,y+8,tw,32),label)
            cursor=next(i for i in measurements[state]['icons'] if i['name']=='cursor-busy')
            cursor_x,cursor_y=[q/vp.factor for q in cursor['position_px']]
            add('BusyCursor',(cursor_x,cursor_y,32,32),'cursor-busy, 32 su; hotspot = центр (16,16)')
            add('BusyCursor.Hotspot',(cursor_x+16,cursor_y+16,0,0),'точка курсора')
        list_state=config.get('list','list')
        if list_state in ('empty','error'):
            for item in measurements[state]['geometry']:
                if item.get('component') in ('EmptyState','HintGlyph','EmptyText','ErrorState','ConnectionIcon','ErrorText','RetryButton'):
                    add(item['component'],item['rect_su'])
        elif list_state=='loading':
            for n in range(3):
                row=g[f'UUmLobbyGameRow[{n}]'];add(f'UmSkeletonRows[{n}]',row,'900 ms; opacity 1.0')
                for name in ('Code','Board','JoinButton'):
                    x,y,w,h=g[f'UUmLobbyGameRow[{n}].{name}'];add(f'UmSkeletonRows[{n}].{name}Bar',(x,y+12,w,12))
        else:
            for n,row in enumerate(base.ROWS):
                prefix=f'UUmLobbyGameRow[{n}]';add(prefix,g[prefix],row['code'])
                for name in ('Code','Mode','Board','Seats','HeroDiscs','JoinButton'):
                    why={'4XM89G':'why.room.full','ZJ4LXZ':'why.room.started'}.get(row['code'])
                    if name=='Seats' and why: continue
                    if name=='HeroDiscs' and not any(p['heroId'] for p in row['players']): continue
                    suffix='WhyText' if name=='JoinButton' and why else name
                    add(prefix+'.'+suffix,g[prefix+'.'+name],base.REASONS[why]+'; tooltip = '+why if suffix=='WhyText' else '')
        all_entries[state]=entries
        legend_height=74+len(entries)*42
        diagram_w=round(vp.canvas[0]*scale)
        diagram_h=round(vp.canvas[1]*scale)
        page=Image.new('RGBA',(diagram_w+1080,max(diagram_h+64,legend_height)),bg+(255,))
        d=ImageDraw.Draw(page);labels=[]
        d.text((20,10),f'{task} / {state} / {vp.width}×{vp.height} / {vp.ui*100:.0f}% · схема 2 px/su',font=heading,fill=ink)
        # Draw all outlines before labels. Each full name is in the local box;
        # row children inherit their explicitly named parent, expanded in legend.
        for e in entries:
            if not e['box_drawn']: continue
            x,y,w,h=e['rect_su'];box=(round(x*scale),round(y*scale)+48,round((x+w)*scale),round((y+h)*scale)+48)
            if w==0 or h==0:
                d.line((box[0]-4,box[1],box[0]+4,box[1]),fill=edge)
                d.line((box[0],box[1]-4,box[0],box[1]+4),fill=edge);continue
            if e['dashed']:
                for xx in range(box[0],box[2],16):
                    d.line((xx,box[1],min(xx+8,box[2]),box[1]),fill=edge);d.line((xx,box[3],min(xx+8,box[2]),box[3]),fill=edge)
                for yy in range(box[1],box[3],16):
                    d.line((box[0],yy,box[0],min(yy+8,box[3])),fill=edge);d.line((box[2],yy,box[2],min(yy+8,box[3])),fill=edge)
            elif e['bind_widget'].endswith('HeroDiscs'):d.ellipse(box,outline=edge,width=2)
            else:d.rectangle(box,outline=edge,width=2)
        for e in entries:
            if not e['box_drawn']:continue
            x,y,w,h=e['rect_su'];name=e['bind_widget']
            if w==0 or h==0: continue
            local=name.rsplit('.',1)[-1]
            # Label parent groups in their upper border band, children inside.
            group=name in ('Header','GameList','CreateColumn','CodeColumn','EmptyState','ErrorState','CodeError','CreateButton') or name.startswith(('UUmLobbyGameRow[','UmSkeletonRows[')) and '.' not in name
            max_w=max(8,w*scale-8)
            words=re.findall(r'[A-Z][a-z]*|[A-Z]+(?=[A-Z]|$)|[a-z]+|[0-9]+|[^A-Za-z0-9]+',local)
            lines=[];line=''
            for word in words:
                if line and d.textlength(line+word,font=font)>max_w: lines.append(line);line=word
                else:line+=word
            if line:lines.append(line)
            px=round(x*scale)+4;py=round(y*scale)+48+(0 if group else 4)
            if name=='CreateNote':py+=0
            for line in lines:
                bb=d.textbbox((px,py),line,font=font,anchor='lt')
                d.rectangle((bb[0]-1,bb[1]-1,bb[2]+1,bb[3]+1),fill=bg)
                d.text((px,py),line,font=font,fill=ink,anchor='lt')
                labels.append({'element':name,'text':line,'bbox_px':list(bb)})
                py+=16
        xx=diagram_w+24
        d.text((xx,14),'BindWidget / состояние / x, y, w, h (su)',font=heading,fill=ink)
        for n,e in enumerate(entries):
            yy=58+n*42
            d.text((xx,yy),e['bind_widget']+(' · '+e['note'] if e['note'] else ''),font=font,fill=ink)
            r=e['rect_su'];coords='нет прямоугольника на этом холсте' if r is None else 'x %.2f · y %.2f · w %.2f · h %.2f'%tuple(r)
            d.text((xx,yy+18),coords,font=font,fill=edge)
        overlaps=[]
        for n,a in enumerate(labels):
            for b in labels[:n]:
                if base.intersection(a['bbox_px'],b['bbox_px'])>0:overlaps.append([a['element'],b['element']])
        audits.append({'state':state,'labels':labels,'overlapping_label_pairs':overlaps})
        pages.append(page)
    sheet=Image.new('RGBA',(max(p.width for p in pages),sum(p.height for p in pages)+24*(len(pages)-1)),bg+(255,))
    yy=0
    for p in pages:sheet.alpha_composite(p,(0,yy));yy+=p.height+24
    return sheet,all_entries,audits
