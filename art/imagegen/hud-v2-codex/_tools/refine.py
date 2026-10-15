from pathlib import Path
import sys, importlib.util, json, shutil
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('hud_compose',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
from PIL import Image,ImageDraw,ImageFilter,ImageChops
c.CROPS['P09']['status']=(489,25,1258,95)
c.hover_card=c.attack_scan.copy()
def material(x,size,dark=False):
    if dark or x=='A':return Image.new('RGBA',size,c.NAVY)
    return c.GUIDES[x].crop(c.GTEXTURE[x]).resize(size,Image.Resampling.LANCZOS)
def patchtext(p,x,box,shade=None):
    xx,yy,w,h=box
    q=material(x,(w,h))
    if shade:q=Image.new('RGBA',(w,h),shade)
    m=Image.new('L',(w,h),255)
    if min(w,h)>24:
        m=Image.new('L',(w,h));ImageDraw.Draw(m).rectangle((1,1,w-2,h-2),fill=255);m=m.filter(ImageFilter.GaussianBlur(1))
    q.putalpha(m)
    c.paste(p,q,(xx,yy))
def rawpanel(pid,key,size):
    p=c.RAW[pid].crop(c.CROPS[pid][key]).resize(size,Image.Resampling.LANCZOS)
    m=Image.new('L',size);ImageDraw.Draw(m).rounded_rectangle((0,0,size[0]-1,size[1]-1),radius=4,fill=255)
    p.putalpha(m.filter(ImageFilter.GaussianBlur(.4)))
    return p
def frame(x,state):
    pid=f'P{dict(A=0,B=4,C=8)[x]+state:02}'
    ownid={'A':'P01','B':'P05','C':'P09'}[x]
    base_name={1:'01-maneuver-own-turn.png',2:'03-combat-attack.png',3:'05-choice-banner.png'}[state]
    original=c.REFS[base_name];im=original.copy();patches=[]
    def repair(box,ref):
        im.paste(ref.crop(box),box[:2]);patches.append(box)
    clean5=c.REFS['05-choice-banner.png'].copy()
    clean5.paste(c.REFS['02-action-choice.png'].crop((787,809,1135,858)),(787,809))
    clean5.paste(c.REFS['02-action-choice.png'].crop((883,864,947,889)),(883,864))
    if state==1:
        repair((0,76,681,145),c.REFS['02-action-choice.png'])
        repair((727,210,1194,255),c.REFS['02-action-choice.png'])
        repair((994,277,1027,378),c.REFS['02-action-choice.png'])
        repair((24,710,324,914),c.REFS['03-combat-attack.png'])
        repair((488,864,570,889),clean5)
    if state==2:
        repair((680,76,1242,200),c.REFS['02-action-choice.png'])
        repair((1003,744,1230,891),clean5)
        repair((567,864,650,889),clean5)
    if state==3:
        repair((787,809,1135,858),c.REFS['02-action-choice.png'])
        repair((600,78,1321,161),c.REFS['02-action-choice.png'])
        repair((883,864,947,889),c.REFS['02-action-choice.png'])
    hud=Image.new('RGBA',(1920,1080))
    # Preserve the complete generated HUD component art, not only its outer stroke.
    # Text repairs are small local inserts; card and icon artwork comes from accepted sources.
    p=rawpanel(ownid,'turn',(286,70))
    turnshade='#F4EFE4' if x=='A' else None
    patchtext(p,x,(119,16,145,40),turnshade)
    c.text(p,(135,20),'Ход 1',28,c.NAVY if x in 'AB' else c.CREAM)
    c.paste(hud,p,(24,24))
    p=rawpanel(ownid,'status',(830,96))
    status={1:'Выберите действие: манёвр, атака или схема',2:'Выберите карту защиты',3:'Сделайте выбор…'}[state]
    if x=='A':
        patchtext(p,x,(99,10,635,36))
        c.fittext(p,(103,9,626,37),status,24,c.CREAM)
    elif x=='B':
        patchtext(p,x,(82,24,566,45))
        c.fittext(p,(82,21,566,49),status,23,c.NAVY)
    else:
        patchtext(p,x,(41,22,516,51))
        c.fittext(p,(41,20,516,53),status,22,c.CREAM)
    if state==3:p=p.resize((830,74),Image.Resampling.LANCZOS)
    c.paste(hud,p,(550,24))
    # Opponent rail retains generated filigree, wax seal/glass and five original, unbranded backs.
    p=rawpanel(ownid,'opp',(341,290))
    # Caption is deterministic and exactly matches the requested inventory.
    if x=='A':
        patchtext(p,x,(27,257,289,25),'#F4EFE4')
        c.fittext(p,(27,257,289,25),'Рука 5 · колода 25 · сброс 0',18,c.NAVY)
    else:
        patchtext(p,x,(22,244 if x=='B' else 257,300,41 if x=='B' else 28))
        c.fittext(p,(22,257,300,28),'Рука 5 · колода 25 · сброс 0',18,c.NAVY if x=='B' else c.CREAM)
    c.paste(hud,p,(1555,24))
    # Own player: restore the authentic source portrait while preserving the generated medallion.
    p=rawpanel(ownid,'own',(370,184))
    pos={'A':(28,44,72),'B':(38,36,70),'C':(37,33,70)}[x]
    xx,yy,ss=pos
    por=c.portrait_medusa.resize((ss,ss),Image.Resampling.LANCZOS)
    m=Image.new('L',(ss,ss));ImageDraw.Draw(m).ellipse((0,0,ss-1,ss-1),fill=255);por.putalpha(m);c.paste(p,por,(xx,yy))
    patchtext(p,x,(128,10,229,96))
    fg=c.NAVY if x=='B' else c.CREAM
    c.text(p,(137,12),'Медуза',28,fg);c.text(p,(137,45),'ВАШ ХОД',18,fg)
    c.paste(p,c.icon('resource-hp-full',27),(136,72));c.text(p,(172,69),'16/16',30,fg)
    for j in range(2):c.paste(p,c.icon('resource-action-full',25),(304+j*27,72))
    patchtext(p,x,(107,106,250,69))
    for j in range(3):
        h=c.REFS['01-maneuver-own-turn.png'].crop((155,1005,181,1031)).resize((29,29),Image.Resampling.LANCZOS)
        hm=Image.new('L',(29,29));ImageDraw.Draw(hm).ellipse((0,0,28,28),fill=255);h.putalpha(hm)
        c.paste(p,h,(129+j*78,110))
    for j in range(3):
        xx=143+j*78
        c.text(p,(xx,149),f'Гарпия {j+1}',16,fg,'mm')
        c.text(p,(xx,169),'1/1',18,fg,'mm')
    c.paste(hud,p,(24,884))
    # The log keeps its generated title plaque and material; only copy is repaired.
    jb=(24,710,299,166) if state==1 else ((24,268,299,80) if state==2 else (24,735,299,141))
    p=rawpanel(pid,'journal',(jb[2],jb[3]))
    patchtext(p,x,(17,8,jb[2]-34,jb[3]-16))
    c.text(p,(23,9),'Журнал',22,fg)
    patchtext(p,x,(20,44,jb[2]-40,min(55,jb[3]-52)))
    c.fittext(p,(22,44,jb[2]-44,27),'Х1 Медуза: манёвр: без движения',16,fg,False)
    c.paste(hud,p,jb[:2])
    # Real card scans fill the generated hand surround; no generated card face survives.
    p=rawpanel(ownid,'hand',(966,196))
    c.paste(p,Image.new('RGBA',(932,180),c.NAVY),(17,15))
    c.paste(hud,p,(480,884))
    for j,card in enumerate(c.own_cards):c.paste(hud,card,(497+j*155,899))
    glow=Image.new('RGBA',(166,228))
    ImageDraw.Draw(glow).rounded_rectangle((4,4,161,223),radius=5,outline='#C7ECFF' if x=='C' else '#F9DE9A',width=3)
    c.paste(hud,glow,(797,864))
    c.paste(hud,c.hover_card.resize((150,212),Image.Resampling.LANCZOS),(805,872))
    cap=c.panel(x,(112,31),dark=True);c.text(cap,(56,15),'Рука 6/7',18,c.CREAM,'mm');c.paste(hud,cap,(486,862))
    # Accepted flat v3 discs sit in the original generated marble/leather/glass surround.
    p=rawpanel(ownid,'actions',(346,152))
    patchtext(p,x,(25,13,299,35),c.NAVY if x!='B' else '#EBD9AF')
    acol=c.CREAM if x!='B' else c.NAVY
    c.paste(p,c.icon('resource-card',25),(28,18));c.text(p,(61,19),'Колода 24',20,acol)
    c.paste(p,c.icon('marker-slot-discard',25),(194,17));c.text(p,(227,19),'Сброс 0',20,acol)
    # Preserve the leather texture instead of painting a flat rectangle over it.
    if x=='B':
        tex=c.GUIDES[x].crop((478,450,501,475)).resize((306,91))
        c.paste(p,tex,(20,56))
    else:patchtext(p,x,(20,56,306,91))
    patchtext(p,x,(12,111,322,40),'#34241E' if x=='B' else None)
    ImageDraw.Draw(p).line((14,149,332,149),fill={'A':'#C6A15A','B':'#A9804E','C':'#8DABB9'}[x],width=1)
    for j in range(4):
        xx=20+j*78
        c.paste(p,c.icon(c.ACTION_IDS[j],54),(xx,56))
        c.chip(p,xx+49,58,c.HOTKEYS[j],x,18)
        if j==3:
            c.text(p,(xx+28,120),'КОНЕЦ',16,c.CREAM,'mm');c.text(p,(xx+28,136),'ХОДА',16,c.CREAM,'mm')
        else:c.text(p,(xx+28,129),c.ACTION_NAMES[j],16,c.CREAM,'mm')
    c.paste(hud,p,(1550,916))
    # Small floating plates stay optically quiet; material ornament is confined to large panels.
    plates=[((494,214,635,253),'1/1','③',False),((350,349,492,388),'1/1','①',False)]
    plates+=([((563,433,697,471),'16/16','',False),((560,554,703,593),'1/1','②',False),((1240,535,1361,574),'7/7','',True),((1051,681,1188,720),'18/18','',True)] if state==1 else
    [((751,575,886,614),'16/16','',False),((452,512,594,551),'1/1','②',False),((1240,535,1361,574),'7/7','',True),((1039,574,1173,613),'18/18','',True)])
    for box,value,digit,enemy in plates:
        bx,by,ex,ey=box;w,h=ex-bx,ey-by;p=Image.new('RGBA',(w,h))
        d=ImageDraw.Draw(p);d.rounded_rectangle((0,0,w-1,h-1),radius=5,fill=c.NAVY,outline={'A':'#C6A15A','B':'#A9804E','C':'#8DABB9'}[x],width=1)
        c.paste(p,c.icon('team-chip-p2' if enemy else 'team-chip-p1',21),(9,8))
        if digit:c.text(p,(37,8),digit,20,c.CREAM)
        c.text(p,(w-11,h/2),value,18,c.CREAM,'rm')
        d.line((62 if digit else 40,h-7,w-49,h-7),fill='#5AC481',width=3)
        c.paste(hud,p,(bx,by))
    if state>=2:
        for side,bx,scan,label,value in [('L',24,c.attack_scan,'АТАКА · Медуза','3'),('R',1650,c.defense_scan if state==2 else c.choice_defense,'ЗАЩИТА · Король Артур','1')]:
            p=c.panel(x,(246,376),dark=x=='B')
            f=c.CREAM
            c.fittext(p,(13,13,220,27),label,19,f)
            c.paste(p,scan.resize((214,299),Image.Resampling.LANCZOS),(16,45))
            c.paste(p,c.icon('action-attack' if side=='L' else 'action-defense',25),(82,346))
            c.text(p,(122,345),value,26,f)
            c.paste(hud,p,(bx,355))
        if state==2:
            c.smallbutton(hud,x,(25,748,245,47),'ЗАЩИТИТЬСЯ',True,21)
            c.smallbutton(hud,x,(25,805,245,47),'БЕЗ ЗАЩИТЫ',False,21)
            p=c.panel(x,(112,40),dark=True);c.text(p,(56,20),'27 с',25,c.CREAM,'mm');p=p.resize((112,30),Image.Resampling.LANCZOS);c.paste(hud,p,(91,850))
            p=c.panel(x,(590,52),dark=True);c.fittext(p,(12,4,566,44),'3 : 1 · Медуза побеждает',29,c.CREAM);c.paste(hud,p,(665,157))
        else:
            p=rawpanel(pid,'choice',(850,116))
            patchtext(p,x,(13,11,824,94))
            c.text(p,(151,16),'Второй выстрел',25,fg)
            c.text(p,(151,52),'ВО ВРЕМЯ БОЯ: Можете',19,fg)
            c.text(p,(151,77),'УСИЛИТЬ эту атаку.',19,fg)
            # Replace the miniature with real source artwork, preserving the generated card frame.
            c.paste(p,c.attack_scan.crop((0,0,223,220)).resize((109,89),Image.Resampling.LANCZOS),(14,12))
            c.smallbutton(p,x,(460,35,175,49),'ПОДТВЕРДИТЬ',True,19)
            c.smallbutton(p,x,(644,35,190,49),'СВЕРНУТЬ (C)',False,19)
            p=p.resize((850,104),Image.Resampling.LANCZOS)
            c.paste(hud,p,(530,104))
    im=Image.alpha_composite(im,hud)
    name=f'{x}-{state}-'+{1:'own-turn',2:'combat',3:'choice'}[state]+'.png'
    im.convert('RGB').save(c.OUT/name)
    mask=hud.getchannel('A').point(lambda a:255 if a else 0);md=ImageDraw.Draw(mask)
    for box in patches:md.rectangle(box,fill=255)
    mask.save(c.OUT/'proof'/f'{x}-{state}-hud-mask.png')
    diff=ImageChops.multiply(ImageChops.difference(im.convert('RGB'),original.convert('RGB')).convert('L'),ImageOps_invert(mask))
    assert diff.getbbox() is None
    return {'file':name,'base':base_name,'size':[1920,1080],'raw_call':pid,'repairs':patches,'outside_hud_max_difference':0}
def ImageOps_invert(p):
    from PIL import ImageOps
    return ImageOps.invert(p)

def ImageEnhance_Brightness(p,n):
    from PIL import ImageEnhance
    return ImageEnhance.Brightness(p).enhance(n)
def guide(x):
    p=c.GUIDES[x].copy();d=ImageDraw.Draw(p)
    if x=='A':
        d.rectangle((40,99,815,134),fill=c.NAVY)
        c.text(p,(54,108),'',18,c.CREAM)
    if x=='B':d.rectangle((52,100,689,135),fill=c.NAVY)
    if x=='C':
        d.rectangle((277,709,490,757),fill=c.NAVY)
        c.text(p,(383,731),'Наведение',18,c.CREAM,'mm')
        c.text(p,(383,752),'',18,c.CREAM,'mm')
    start=876 if x=='A' else 731
    d.rectangle((start-14,0,1668,136),fill=c.NAVY)
    c.text(p,(start,8),'Палитра',18,c.CREAM)
    pals=c.PALETTES[x];step=(1644-start)/len(pals)
    for i,color in enumerate(pals):
        xx=round(start+i*step);ww=round(step-12)
        d.rounded_rectangle((xx,40,xx+ww,87),radius=2,fill=color,outline=c.CREAM,width=1)
        c.text(p,(xx+ww/2,107),color,16,c.CREAM,'mm')
    # The original generated sheet layout and materials are retained. Replace only glyph discs
    # with the accepted masters, at the measured centres of its 4 x 4 matrix.
    cols={'A':[850,1076,1307,1534],'B':[981,1167,1351,1542],'C':[846,1061,1280,1497]}[x]
    rows={'A':[283,411,538,667],'B':[261,405,550,697],'C':[262,386,512,637]}[x]
    for i,yy in enumerate(rows):
        for j,xx in enumerate(cols):
            n=90 if x=='B' else 86
            # Erase the generated disc first, keeping the surrounding button frame intact.
            clear=98
            tile={'A':(62,672,113,728),'B':(478,450,501,475),'C':(100,205,160,265)}[x]
            tex=c.GUIDES[x].crop(tile).resize((clear,clear),Image.Resampling.LANCZOS)
            cm=Image.new('L',(clear,clear));ImageDraw.Draw(cm).ellipse((0,0,clear-1,clear-1),fill=255);tex.putalpha(cm)
            c.paste(p,tex,(xx-clear//2,yy-clear//2))
            c.paste(p,c.disc_state(i,n,j),(xx-n//2,yy-n//2+(2 if j==2 else 0)))
    if x=='A':
        for box,sample,shade,size in [((630,817,113,62),'Ход 1','#F4EFE4',33),((779,817,112,62),'16/16','#F4EFE4',36),((944,818,213,61),'ВАШ ХОД',c.NAVY,31)]:
            xx,yy,w,h=box
            d.rectangle((xx,yy,xx+w,yy+h),fill=shade)
            c.fittext(p,box,sample,size,c.NAVY if shade!=c.NAVY else c.CREAM)
    # Disabled labels remain full-contrast while the frame and icon carry the disabled state.
    # All generated words are Russian; the only Latin symbols are required hotkeys and hex.
    if x=='B':
        for j,xx in enumerate(cols):
            for i,yy in enumerate(rows):
                tex=c.GUIDES[x].crop((478,450,501,475)).resize((130,25))
                c.paste(p,tex,(xx-65,yy+45))
                c.fittext(p,(xx-65,yy+45,130,25),c.ACTION_NAMES[i],18,c.CREAM)
    if x=='C':
        for j,xx in enumerate(cols):
            for i,yy in enumerate(rows):
                # Repaint the typography zone to remove generated glyph defects.
                d.rectangle((xx+51,yy-19,xx+140,yy+27),fill='#0A2232')
                if i==3:
                    c.text(p,(xx+95,yy-7),'КОНЕЦ',18,c.CREAM,'mm');c.text(p,(xx+95,yy+16),'ХОДА',18,c.CREAM,'mm')
                else:c.fittext(p,(xx+48,yy-17,96,39),c.ACTION_NAMES[i],18,c.CREAM)
    if x=='C':
        # Rebuild the action matrix from the clean generated glass panel to remove all old glyphs.
        for i,yy in enumerate([210,334,460,586]):
            for j,xx in enumerate([798,1013,1230,1443]):
                d.rectangle((xx-2,yy-2,xx+204,yy+108),fill='#082233')
                button=c.panel('C',(202,106))
                if j==1:
                    ImageDraw.Draw(button).rounded_rectangle((2,2,199,103),radius=6,outline='#BDEBFF',width=3)
                if j==2:button=ImageEnhance_Brightness(button,.76)
                c.paste(button,c.disc_state(i,70,j),(11+(2 if j==2 else 0),17+(2 if j==2 else 0)))
                if i==3:
                    c.text(button,(139,42),'КОНЕЦ',18,c.CREAM,'mm');c.text(button,(139,65),'ХОДА',18,c.CREAM,'mm')
                else:c.fittext(button,(88,22,105,62),c.ACTION_NAMES[i],18,c.CREAM)
                c.paste(p,button,(xx,yy))
    p=p.resize((1920,1080),Image.Resampling.LANCZOS)
    target=c.OUT/f'{x}-4-styleguide.png';p.convert('RGB').save(target)
    shutil.copy2(target,c.ART/'styleguides'/f'{x}-styleguide.png')
    return {'file':target.name,'size':[1920,1080],'raw_size':[1672,941],'contains_game_scans':False,'source_call':{'A':'P04','B':'P08','C':'P12'}[x]}
c.build_frame=frame;c.styleguide=guide
if __name__=='__main__':c.main()
