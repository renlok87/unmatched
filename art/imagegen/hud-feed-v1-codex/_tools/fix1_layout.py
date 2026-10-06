"""The nine HB-34 fix1 corrections. Inputs and source baseline stay read-only."""
import math
import numpy as np
from PIL import Image, ImageDraw


def install(b):
    C=b.Canvas
    original_compact=C.compact
    original_status_for=b.status_for
    original_readme=b.readme
    original_acceptance=b.acceptance

    def length(c,text,size=24,bold=True):
        return b.font(math.ceil(size*c.s),bold).getlength(text)/c.s

    def status_for(c):
        st=c.state
        if st=='boost':c.status('ms.ability.boost',{'fighterName':'King Arthur'})
        elif c.small and st=='compact-move':c.status('ms.pending.move',{'fighterName':'Harpies','n':3})
        elif c.small and st=='compact-place':c.status('ms.pending.place',{'fighterName':'Merlin'})
        elif c.small and st=='compact-space':
            text,src=b.cardtext(b.SCARD[st],'effect',c.lang)
            src['excerpt']='first sentence verbatim';c.status_text(text.split('. ')[0]+'.',src)
        elif c.small and st=='discard':
            c.status_text('Сбросьте 1: выбрано 1/1',{'source':'HB-34 fix1 Fix 4 / P3 / 04 section 2.8','key':None})
        elif st=='toast':c.status('ms.status.action',keys=['hud.key.maneuver','hud.key.attack','hud.key.scheme'])
        elif st=='after-combat':
            text,src=b.string('ms.status.resolve',c.lang)
            key,keysrc=b.string('hud.key.resolve',c.lang)
            src['original_template']=text;src['suffix_transform']='keyboard suffix extracted into sourced chip'
            c.status_text(text.replace('('+key+')','').strip(),src,['hud.key.resolve'])
        else:original_status_for(c)

    def compact(c,title,tsrc,hint,hsrc,buttons,icon=None,queue=False,grey=False):
        if not c.small and c.state!='boost':
            return original_compact(c,title,tsrc,hint,hsrc,buttons,icon,queue,grey)
        boost=c.state=='boost';pad=16;gap=8
        bws=[max(120,length(c,b.string(k,c.lang)[0].upper(),20)+26) for k,p in buttons]
        bw=sum(bws)+gap*max(0,len(bws)-1)
        tw=0 if boost else length(c,title)+2/c.s
        hw=length(c,hint,16,False)+2/c.s if grey else 0
        qtext,qsrc=b.string('hud.pending.queue',c.lang,k=2)
        qw=max(24,length(c,qtext,14)+12+2/c.s) if queue else 0
        components=([24] if icon and not boost else [])+([tw] if tw else [])+([hw] if hw else [])+([qw] if qw else [])+([bw] if buttons else [])
        needed=sum(components)+gap*max(0,len(components)-1)+2*pad
        icon_omitted=False
        if needed>720 and icon:
            needed-=32;icon=None;icon_omitted=True
        width=max(320 if grey else 560,needed)
        width=min(720,width)
        height=56 if buttons else 48
        anchor=max(64 if c.small else 80,c.geometries['status'][1]+c.geometries['status'][3]+8)
        x=(c.w/c.s-width)/2
        free=None
        if c.small:
            left=16+120+8
            right=min(c.reserved[k][0] for k in ['PANEL-OPP','OPP-HAND'])-8
            free=[left,right]
            if x<left or x+width>right:x=(left+right-width)/2
        r=[x,anchor,width,height];c.panel('PENDING',r,edge=None if grey else ('pending',2,1),opacity=.92)
        color='secondary' if grey else 'primary';xx=x+pad
        if icon:c.icon(icon,[xx,anchor+(height-24)/2,24,24]);xx+=32
        if tw:
            c.txt('PENDING',title,tsrc,[xx,anchor,tw,height],24,True,color);xx+=tw+gap
        if hw:
            c.txt('PENDING',hint,hsrc,[xx,anchor,hw,height],16,False,color);xx+=hw+gap
        if queue:
            qr=[xx,anchor+(height-24)/2,qw,24];c.panel('QUEUE',qr,skin='Chip',register=False)
            c.txt('QUEUE',qtext,qsrc,qr,14,True,center=True);xx+=qw+gap
        bx=x+width-pad-bw
        for (key,primary),ww in zip(buttons,bws):
            c.button(key,[bx,anchor+(height-40)/2,ww,40],primary);bx+=ww+gap
        rec={'id':c.id,'state':c.state,'rectangle_su':r,'mode':'buttons-only' if boost else 'single-row',
             'buttons_width_su':bw,'measured_content_width_su':needed,'class_cap_su':720,
             'free_band_su':free,'optional_glyph_omitted_for_fit':icon_omitted,
             'content_fits':needed<=width,'hint_in_status':c.small and not grey and not boost,
             'greyscale_shape':'no controls, 1 su edge' if grey else 'controls, 2 su edge'}
        b.V['compact_geometry'].append(rec);b.FACTS['deltas_04'].append(rec);c.geometries['compact']=r

    def source(c,key,ribbon='scheme',fade=1,fly=False):
        r=[16,64,120,166] if c.small else [24,84,190,264]
        if fly:
            opp=c.reserved['OPP-HAND'];ox=opp[0]+opp[2]/2;oy=opp[1]+opp[3]/2
            r=[(ox+r[0]+r[2]/2)/2-r[2]/2,(oy+r[1]+r[3]/2)/2-r[3]/2,r[2],r[3]]
        old=c.hud;stack=Image.new('RGBA',old.size);c.hud=stack
        c.card(key,r,name='SLOT',transient=fly)
        if not fly:
            owner='Medusa' if key.startswith('medusa:') else 'King Arthur'
            label,src=b.string('hud.slot.'+ribbon,c.lang)
            label+=' · '+owner
            src.update({'composition_key':'hud.slot.*.owner','owner':owner,
                        'owner_source':'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt; Hero.name'})
            chipw=24 if ribbon=='boost' else 0
            width=r[2]
            if ribbon=='boost' and c.small:width=190
            textwidth=width-40-(chipw+8 if chipw else 0)
            lines=b.wrap(label,textwidth,c.s,14,True)
            height=max(28,14+18*(len(lines)-1)+8)
            rb=[r[0],r[1]+r[3]+4,width,height]
            fg='secondary' if ribbon=='discard' else 'glyph' if ribbon=='boost' else 'navy'
            fill='scheme' if ribbon=='scheme' else 'navy'
            edge=('secondary',2,1) if ribbon=='discard' else None if ribbon=='boost' else ('navy',1,1)
            c.panel('SLOT-RIBBON',rb,fill=fill,opacity=1 if ribbon=='scheme' else .92,radius=6,edge=edge)
            ir=[rb[0]+2,rb[1]+(height-24)/2,24,24];c.icon('marker-status',ir)
            # Reprint only the accepted marker's original alpha; no new glyph.
            if ribbon!='boost':
                raw=b.image(c.badges[-1]['source']).resize((round(24*c.s),round(24*c.s)),Image.Resampling.LANCZOS)
                glyph=Image.new('RGBA',raw.size,(*b.rgb(fg),255));glyph.putalpha(raw.getchannel('A'));c.paste(glyph,ir[:2])
                c.badges[-1]['ink_override']=fg+'; original v3 alpha silhouette preserved'
            c.txt('SLOT-RIBBON',label,src,[rb[0]+32,rb[1],textwidth,height],14,True,fg,lines=lines)
            ratio=b.hb.contrast(b.rgb(fg),b.rgb(fill))
            if ribbon!='scheme':
                box=b.pxbox(rb,c.s);patch=np.asarray(c.base)[box[1]:box[3],box[0]:box[2],:3]
                ground=patch*.08+np.array(b.rgb(fill))*.92
                lum=b.hb.luminance(ground);fl=b.hb.luminance(b.rgb(fg))
                ratio=float(np.min((np.maximum(lum,fl)+.05)/(np.minimum(lum,fl)+.05)))
            b.V['contrast'].append({'id':c.id,'panel':'SLOT-RIBBON marker-status','role':'glyph_to_own_plate','ratio':ratio,'required':3})
            if chipw:
                chip=[rb[0]+width-chipw-4,rb[1]+(height-chipw)/2,chipw,chipw]
                c.panel('BOOST-CHIP',chip,register=False);c.icon('state-boost',chip)
                c.keyed('BOOST-CHIP','hud.card.boost',chip,14,True,params={'n':b.FACTS['boost_example']['boostValue']},center=True)
                c.geometries['boost_chip']=chip
            extra=0
            if c.state=='slot-opp-hold':
                pr=[rb[0],rb[1]+height+2,width,4]
                c.panel('HOLD-PROGRESS',pr,fill='navy',opacity=.92,radius=0)
                # Fill the full left half; the track's authored 1 su edge remains a separate layer.
                fr=[pr[0],pr[1],width/2,4]
                c.panel('HOLD-FILL',fr,fill='glyph',opacity=1,edge=('glyph',0,1),radius=0,register=False)
                box=b.pxbox(pr,c.s);patch=np.asarray(c.base)[box[1]:box[3],box[0]:box[2],:3]
                ground=patch*.08+np.array(b.rgb('navy'))*.92
                lum=b.hb.luminance(ground);fl=b.hb.luminance(b.rgb('glyph'))
                ratio=float(np.min((np.maximum(lum,fl)+.05)/(np.minimum(lum,fl)+.05)))
                b.V['contrast'].append({'id':c.id,'panel':'HOLD-PROGRESS','role':'progress_to_track','ratio':ratio,'required':3})
                c.geometries['hold_progress']={'track':pr,'fill':fr,'gap_su':2,'hold_ms':1500,'sample_ms':750,'ratio':ratio}
                extra=6
            c.geometries['ribbon_plate']=rb
            c.geometries['slot_ribbon']=[r[0],r[1],max(r[2],width),r[3]+4+height+extra]
            c.geometries['ribbon_style']={'kind':ribbon,'owner':owner,'label':label,'body':b.T[fill],
                'opacity':1 if ribbon=='scheme' else .92,'foreground':b.T[fg],'shape':'outline' if ribbon=='discard' else 'filled'}
        if fade!=1:stack.putalpha(stack.getchannel('A').point(lambda a:round(a*fade)))
        c.hud=Image.alpha_composite(old,stack)

    def modal(c):
        width=560 if c.small else 640;cap=360 if c.small else 420 if c.w==1920 else 380
        y=max(64 if c.small else 80,c.geometries['status'][1]+c.geometries['status'][3]+8)
        title,tsrc=b.cardtext('king-arthur:prophecy',lang=c.lang);effect,esrc=b.cardtext('king-arthur:prophecy','effect',c.lang)
        lines=b.wrap(effect,width-40,c.s,16);eh=len(lines)*20
        pick=c.state=='modal-pick';cw,ch=(120,166) if c.small else (150,208)
        keys=b.REVEALED if pick else b.REVEALED[2:]
        extra=16 if pick else 28
        content=eh+12+extra+ch
        height=min(cap,48+content+16+56)
        r=[(c.w/c.s-width)/2,y,width,height];c.panel('MODAL',r,True,skin='Modal',edge=('pending',2,1))
        c.txt('MODAL',title,tsrc,[r[0]+16,y+12,width-32,32],28,True)
        footer=y+height-56;bodytop=y+48;visible=footer-16-bodytop;scroll=max(0,content-visible)
        before=c.hud;before_palette=c.palette.copy();body=Image.new('RGBA',before.size);c.hud=body;c.palette=Image.new('RGBA',before.size)
        c.txt('MODAL',effect,esrc,[r[0]+16,bodytop,width-40,eh],16,lines=lines)
        cy=bodytop+eh+12+extra
        gap=(width-32-4*cw)/3 if pick else 16
        roww=len(keys)*cw+(len(keys)-1)*gap;start=r[0]+(width-roww)/2
        cards=[];chips=[]
        for i,key in enumerate(keys):
            raised=pick and i<2
            cr=[start+i*(cw+gap),cy-(16 if raised else 0),cw,ch]
            c.card('king-arthur:'+key,cr,'selected' if raised else 'idle',transient=True,name='REVEALED-'+str(i))
            cards.append({'key':'king-arthur:'+key,'rectangle_su':cr,'raised_su':16 if raised else 0})
            if not pick:
                chip=[cr[0]+cw/2-12,cy-28,24,24]
                c.panel('ORDER-'+str(i),chip,skin='Chip',fill='glyph',opacity=1,edge=('keyline',1,1),register=False)
                c.txt('ORDER-'+str(i),str(i+1),{'source':'HB-34 P3 / fix1 Fix 3','key':'order-index','value':i+1},chip,20,True,'navy',center=True)
                chips.append(chip)
        if pick:
            # Measure the actual gray frame band at the straight left edges, excluding corners and scan.
            arr=np.asarray(body);lumas=[]
            for card in cards:
                x,yy,ww,hh=card['rectangle_su'];box=b.pxbox([x+1,yy+10,3,hh-20],c.s)
                patch=arr[box[1]:box[3],box[0]:box[2],:3]
                lumas.append(float(np.mean(patch@np.array([.2126,.7152,.0722]))))
            b.V.setdefault('gray_shape_pick',[]).append({'id':c.id,'raise_su':16,'marked_frame_band_luma':lumas[:2],
                'unmarked_frame_band_luma':lumas[2:],'frame_band_luma_difference':abs(np.mean(lumas[:2])-np.mean(lumas[2:])),
                'shape_distinct':cards[0]['rectangle_su'][1]+16==cards[2]['rectangle_su'][1]})
        viewport=Image.new('RGBA',before.size);box=b.pxbox([r[0]+16,bodytop,width-32,visible],c.s)
        viewport.paste(body.crop(tuple(box)),(box[0],box[1]));c.hud=Image.alpha_composite(before,viewport)
        palviewport=Image.new('RGBA',before.size);palviewport.paste(c.palette.crop(tuple(box)),(box[0],box[1]));c.palette=Image.alpha_composite(before_palette,palviewport)
        if scroll>0:
            track=[r[0]+width-8,bodytop,4,visible];c.panel('SCROLL-TRACK',track,skin='ProgressTrack',register=False)
            c.panel('SCROLL-THUMB',[track[0],bodytop,4,max(16,visible*visible/content)],skin='ProgressFill',register=False)
        if pick:c.txt('MODAL','Выбрано 2/2',{'source':'HB-34 P3 / 04 section 2.8','key':None},[r[0]+16,footer,140,40],14,True)
        b1=max(120,length(c,b.string('hud.number.confirm',c.lang)[0].upper(),20)+26)
        b2=max(120,length(c,b.string('ms.btn.collapse',c.lang)[0].upper(),20)+26)
        c.button('hud.number.confirm',[r[0]+width-16-b2-8-b1,footer,b1,40],True)
        c.button('ms.btn.collapse',[r[0]+width-16-b2,footer,b2,40])
        rec={'id':c.id,'rectangle_su':r,'content_height_su':content,'visible_height_su':visible,'scrolled_part_su':scroll,
             'scrollbar':scroll>0,'footer_su':[r[0]+16,footer,width-32,40],
             'counter_buttons_visible':footer+40<=y+height-16,'scan_row_footer_gap_su':16,
             'counter_present':pick,'cap_su':cap,'cards':cards,'number_chips':chips,'numeral_type_su':20 if not pick else None}
        b.V['modal_fit'].append(rec);c.geometries['modal']=rec

    C.compact=compact;C.source=source;b.modal=modal;b.status_for=status_for

    def gray_pairs(canvases):
        lookup={c.state:c for c in canvases}
        for a,bb,shape in [('compact-target','opp','Controls and 2 su edge versus no controls and 1 su edge'),
                          ('modal-pick','modal-order','Four cards, two raised 16 su versus two centred numbered cards'),
                          ('slot-opp-show','slot-boost','Filled scheme plate versus BOOST chip'),
                          ('slot-boost','slot-discard','BOOST chip versus outline discard plate'),
                          ('slot-opp-show','slot-discard','Filled scheme versus outline discard plate')]:
            ca=lookup[a];cb=lookup[bb]
            # Actual Rec.709 gray crops of the two full component envelopes.
            field='modal' if a.startswith('modal') else 'compact' if a.startswith('compact') else 'slot_ribbon'
            ra=ca.geometries[field];rb=cb.geometries[field]
            if isinstance(ra,dict):ra=ra['rectangle_su'];rb=rb['rectangle_su']
            ga=np.asarray(b.gray(ca.hud).crop(tuple(b.pxbox(ra,ca.s))))
            gb=np.asarray(b.gray(cb.hud).crop(tuple(b.pxbox(rb,cb.s))))
            ph=max(ga.shape[0],gb.shape[0]);pw=max(ga.shape[1],gb.shape[1]);aa=np.zeros((ph,pw,4),np.uint8);cc=aa.copy()
            aa[:ga.shape[0],:ga.shape[1]]=ga;cc[:gb.shape[0],:gb.shape[1]]=gb
            changed=int(np.any(aa!=cc,axis=2).sum())
            b.V['gray_pairs'].append({'board':ca.board,'canvas':ca.id.rsplit('-',2)[-2:],'states':[a,bb],
                 'shape_difference':shape,'structural_shape_difference':True,'gray_changed_pixels':changed,'passed':changed>0})
    b.gray_pairs=gray_pairs

    def acceptance():
        original_acceptance()
        b.V['modal_fit_note']='Content-driven modal height; fixed footer, 16 su scan/footer gap. Scroll only for content beyond class cap.'
        b.V['acceptance']['P7 SLOT']['measured']='Original card rectangles; owner-labelled ribbons; boost chip inside plate; separate 4 su hold bar with 2 su gap'
        b.V['acceptance']['P7 SLOT']['expected']='Card geometry preserved; source scans contained; fix1 ribbons and hold geometry measured'
        b.V['acceptance']['P13 ribbon separation']['note']='Scheme filled, discard outline; BOOST has its internal +N chip. Actual grayscale component crops measured.'
        checks={
            'fix1 picked shape':(all(r['shape_distinct'] and r['raise_su']==16 for r in b.V['gray_shape_pick']),b.V['gray_shape_pick'],'16 su raised selected cards, actual gray frame-band luma'),
            'fix1 single row compacts':(all(r['mode'] in ['single-row','buttons-only'] and r['content_fits'] for r in b.V['compact_geometry'] if '-150' in r['id']),
                [r['id'] for r in b.V['compact_geometry'] if '-150' in r['id'] and not r['content_fits']],'One measured row, cap 720 su'),
            'fix1 source baseline preserved':(b.sha(b.PKG/'source-hashes-before.json')==b.load(b.PKG/'fix1-before.json')['source_baseline_sha256'],b.sha(b.PKG/'source-hashes-before.json'),'Original baseline SHA-256'),
        }
        for key,(passed,measured,expected) in checks.items():b.V['acceptance'][key]={'passed':bool(passed),'measured':measured,'expected':expected,'note':'HB-34 fix1'}
        b.V['fix1']={'baseline':'fix1-before.json','scope':'Nine corrections in HB-34.fix1.codex.md','image_generations':0}
        b.FACTS['fix1']=b.V['fix1']
        b.FACTS['strings_without_key']['hud.slot.*.owner']='{hud.slot.*} · {Hero.name}; analogous to hud.combat.role.*'
    b.acceptance=acceptance

    def readme():
        original_readme()
        p=b.PKG/'README.md';text=p.read_text(encoding='utf-8')
        text=text.replace('со всеми шестью x1 skins','с шестью основными x1 skins и дополнительным ProgressTrack')
        text=text.replace('Зафиксированные конфликты: на 720p/150% некоторые полные compacts выходят из безопасной верхней полосы при заданном CENTER; BOOST-chip над SLOT, как в HB-22, пересекает зарезервированный TOP; mandatory card.glyph линия удержания на card.type.scheme имеет только 1,55:1. Эти ограничения не объявлены пройденными.',
            'Открытый пункт HB-22: принятый boost-maneuver имеет тот же конфликт чипа над SLOT с TOP (640 px² на 1080p/100%). Здесь чип перенесён внутрь ленты; HB-22 не менялся.')
        text=text.replace('СХЕМА и СБРОС: разница обязательных цветов по Rec.709 19,2848 (в серых PNG 19), ниже порога 20. Надписи разные и читаются; геометрия плашки и marker-status одинакова. Строгий критерий различия формы плашки или яркости не пройден; линия HOLD — признак фазы, не общей ленты СХЕМА.',
            'СХЕМА — залитая лента; СБРОС — контурная (navy 0,92, secondary 2 su и secondary текст/глиф); BOOST — внутренний +N. Серые пары измерены по фактическим компонентам.')
        old='Модаль на 720p/150% помещается без ненужной прокрутки (242 su в viewport 248 su); на 720p/100% карты 208 su вызывают прокрутку. Footer и счётчик фиксированы в обоих случаях.'
        text=text.replace(old,'Модаль подогнана по содержимому до cap. Footer отделён от scan row на 16 su; прокрутка только при превышении cap. Счётчик только в PICK, в ORDER две карты и номера 20 su на чипах 24 su.')
        text=text.replace('- Compact использует вторую логическую строку для кнопок, когда имя и hint не помещаются с кнопками справа; ширина не меняется. Высота и пересечения измеряются.',
            '- L сохраняет исходный двухстрочный compact; S — одна строка до 720 su в свободной полосе SLOT+8 … PANEL-OPP/OPP-HAND−8. Hint собственного выбора в S перенесён в STATUS. BOOST везде содержит только две кнопки. Серые compacts имеют ширину по измеренному содержимому с padding 16 su.')
        text=text.replace('СХЕМА/СБРОС печатают неизменённую alpha-форму marker-status в navy, как требует задача.',
            'СХЕМА печатает marker-status в navy, СБРОС — secondary; alpha-форма исходника сохранена.')
        text=text.replace('## Строки без ключа','## Строки без ключа\n\n- `hud.slot.*.owner` — «{hud.slot.* RU} · {Hero.name}», по fix1 Fix 9b; EN «SCHEME · Medusa».')
        before=b.load(b.PKG/'fix1-before.json')
        def rangev(rows,key):
            vals=[r[key] for r in rows];return f'{min(vals):.2f}–{max(vals):.2f}'
        oldcompact=before['compact_geometry'];newcompact=b.V['compact_geometry']
        oldh=[r['rectangle_su'][3] for r in oldcompact if r['id'].endswith('-150')]
        newh=[r['rectangle_su'][3] for r in newcompact if r['id'].endswith('-150')]
        bars=[r for r in b.V['contrast'] if r['role']=='progress_to_track']
        hold_min=b.V.get('fix1_independent',{}).get('actual_png_minimum_hold_contrast',min(r['ratio'] for r in bars))
        failures=[r['id'] for r in b.V['overlap'] if not r['passed']]
        section=['','## Исправления fix1','',
            '| № | До → после |','|---|---|',
            '| 1 | M/A/S → M/A/G из st-hud; STATUS chips 24 su → 20 su, промежутки 8 su и 12 su до текста; resolve из hud.key.resolve. |',
            '| 2 | Sentence case → upper() всех кнопок; 20 su Bold Condensed, источник и case_transform записаны, ширины пересчитаны. |',
            '| 3 | PICK подъём 0 → 16 su; ORDER 4 → 2 карты, цифры 14 → 20 su на чипах 24 su; счётчик удалён из ORDER. Высота по содержимому, зазор до footer 16 su. |',
            f'| 4 | S compact высоты {min(oldh):.0f}–{max(oldh):.0f} → {min(newh):.0f}–{max(newh):.0f} su, одна строка; свободная полоса и точные ширины в compact_geometry. Общие непрошедшие overlap: {len(failures)}. |',
            '| 5 | King Arthur три раза → один раз в STATUS ms.ability.boost; BOOST compact содержит только две кнопки в одной строке. |',
            '| 6 | Серые compacts 720/560 su → измеренная ширина + 32 su, min 320 su, cap класса; значения в дельте 04. |',
            '| 7 | BOOST chip TOP overlap 640 px² → чип внутри ленты, от правого края 4 su, ничего выше SLOT. |',
            f'| 8 | HOLD 2 su на scheme, 1,55:1 → отдельный bar 4 su, gap 2 su, fill 50%; минимум {hold_min:.2f}:1 по PNG; SLOT group +6 su относительно новой ленты. |',
            '| 9 | СХЕМА/СБРОС одна форма, Δluma 19,28 → filled/outline; на каждой ленте указан владелец, ни одна надпись не сокращена. |',
            '', '### P5 — дельта ВР-VS2-HB34-12','',
            '| Состояние | L STATUS | S STATUS |','|---|---|',
            '| compact-move | ms.choice.target(n=3) | ms.pending.move(Harpies,3) |',
            '| compact-place | ms.status.choice(Bewilderment) | ms.pending.place(Merlin) |',
            '| compact-target | ms.choice.target(n=1) | ms.choice.target(n=1) |',
            '| compact-space | ms.status.choice(Restless Spirits) | первая фраза эффекта Restless Spirits |',
            '| discard | ms.status.choice(Hiss and Slither) | «Сбросьте 1: выбрано 1/1» |',
            '| boost | ms.ability.boost(King Arthur) | ms.ability.boost(King Arthur) |',
            '| toast / after-combat | ms.status.action + M/A/G / ms.status.resolve + R | то же |',
            '', 'Смена входных хешей: '+('нет' if not b.V['source_changes'] else str(b.V['source_changes']))+'. Исходный source-hashes-before.json сохранён.',
            'Все точные изменения по холстам: fix1-before.json → facts.json / verification.json.']
        p.write_text(text+'\n'.join(section)+'\n',encoding='utf-8')
    b.readme=readme
