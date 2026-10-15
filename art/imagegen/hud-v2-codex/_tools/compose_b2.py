"""Assembly proof: ONLY kit sprites + existing v3 icons + real scans + Pillow text.
Scene clean-up copies pixels from other supplied references, never stage-A generated HUD.
"""
import sys
sys.dont_write_bytecode=True
from build_kit import *
ASSETS.update(json.loads((KIT/'assets.json').read_text('utf-8')))
REF=DER/'refs'
REFS={f.name:Image.open(f).convert('RGBA') for f in REF.glob('*.png')}
clean5=REFS['05-choice-banner.png'].copy()
for box in [(787,809,1135,858),(883,864,947,889)]:clean5.paste(REFS['02-action-choice.png'].crop(box),box[:2])
ICON=ROOT/'art/imagegen/hud-icons-v3/masters'
PROVENANCE=[]

def ico(im,name,xy,n=24):
    p=Image.open(ICON/(name+'.png')).convert('RGBA').resize((n,n),Image.Resampling.LANCZOS)
    im.alpha_composite(p,xy)
    PROVENANCE.append({'type':'v3 icon','file':str((ICON/(name+'.png')).relative_to(ROOT)).replace('\\','/'),'xy':xy,'size':n})

def put(im,name,xy,size=None):
    q=render(name,size);im.alpha_composite(q,xy)
    PROVENANCE.append({'type':'kit PNG','name':name,'xy':xy,'size':q.size})

def scan(im,ref,box,xy,size,circle=False):
    q=REFS[ref].crop(box).resize(size,Image.Resampling.LANCZOS)
    if circle:
        mask=Image.new('L',size);ImageDraw.Draw(mask).ellipse((0,0,size[0]-1,size[1]-1),fill=255);q.putalpha(mask)
    im.alpha_composite(q,xy)
    PROVENANCE.append({'type':'real scan crop','ref':ref,'crop':box,'xy':xy,'size':size})

def label(im,xy,s,n=20,col=LIGHT,anchor=None):
    text(im,xy,s,n,col,anchor)
    PROVENANCE.append({'type':'Pillow text','text':s,'size':n,'xy':xy,'color':col})

def key(im,xy,s):
    put(im,'T_Hud_KeyBadge',xy)
    label(im,(xy[0]+13,xy[1]+13),s,18,NAVY,'mm')

def frame(state):
    PROVENANCE.clear()
    ref='01-maneuver-own-turn.png' if state==1 else '03-combat-attack.png'
    im=REFS[ref].copy();patches=[]
    def repair(box,name):
        im.paste((clean5 if name=='05-choice-banner.png' else REFS[name]).crop(box),box[:2]);patches.append({'crop':box,'source':name})
    if state==1:
        for box in [(0,76,681,145),(727,210,1194,255),(994,277,1027,378)]:repair(box,'02-action-choice.png')
        repair((24,710,324,914),'03-combat-attack.png')
        repair((488,864,570,889),'05-choice-banner.png')
    else:
        repair((680,76,1242,200),'02-action-choice.png')
        repair((1003,744,1230,891),'05-choice-banner.png')
        repair((567,864,650,889),'05-choice-banner.png')
        for box in [(0,347,290,738),(1640,346,1919,738)]:repair(box,'02-action-choice.png')
    # A few old labels sit just outside the replacement silhouettes: copy clean garden.
    repair((24,24,310,96),'02-action-choice.png')
    def erase_old_ui(box,source_box):
        # The source screenshots already contain UI. Restore scene pixels before
        # applying the genuinely translucent B2 skins, so old letters cannot ghost.
        x,y,w,h=box
        q=REFS['02-action-choice.png'].crop(source_box).resize((w,h),Image.Resampling.LANCZOS)
        im.paste(q,(x,y));patches.append({'target_xywh':box,'source':'02-action-choice.png','source_crop':source_box,'method':'scene clone under replacement UI'})
    for box,src in [((24,24,286,70),(320,24,520,94)),((550,24,830,80),(560,115,1260,190)),
                    ((1555,24,341,290),(1380,24,1530,314)),((24,884,370,184),(400,884,475,1068)),
                    ((480,884,966,196),(1450,884,1540,1080)),((1550,900,346,178),(1450,900,1540,1078)),
                    ((486,858,112,32),(400,850,475,882))]:erase_old_ui(box,src)
    erase_old_ui((24,710,299,176) if state==1 else (24,268,299,78),(325,720,390,884))
    # Turn/menu uses the dark live-game body and separate v3 icons/text.
    put(im,'T_Hud_TurnPlate',(24,24),(286,70))
    put(im,'T_Hud_KeyBadge',(48,45));put(im,'T_Hud_KeyBadge',(93,45))
    ico(im,'ui-menu',(49,46),24);ico(im,'resource-connection-online',(94,46),24)
    label(im,(158,40),'Ход 1',29,LIGHT)
    put(im,'T_Hud_StatusBanner',(550,24),(830,80))
    status='Выберите действие: манёвр, атака или схема' if state==1 else 'Выберите карту защиты'
    label(im,(965,49),status,24,LIGHT,'mm')
    for j,s in enumerate(['M','A','G']):key(im,(916+j*34,69),s)
    # Opponent rail: no newly generated portrait or card art.
    put(im,'T_Skin_Panel',(1555,24),(341,290))
    label(im,(1580,43),'Король Артур',26)
    label(im,(1580,75),'ЖДЁТ',18,'#F2C14E')
    scan(im,'01-maneuver-own-turn.png',(1805,52,1877,124),(1812,59),(42,42),True)
    put(im,'T_Hud_PortraitFrame_64',(1797,44))
    put(im,'T_Hud_HpPlate',(1576,101),(174,40))
    ico(im,'resource-hp-full-enemy',(1584,109),24)
    label(im,(1676,122),'18/18',25,LIGHT,'mm')
    scan(im,'01-maneuver-own-turn.png',(1680,108,1708,136),(1582,152),(25,25),True)
    put(im,'T_Hud_SidekickRing',(1577,147))
    label(im,(1621,151),'Мерлин 7/7',19)
    # Five real card backs cropped from ref 01, each with a kit surround.
    for j in range(5):
        scan(im,'01-maneuver-own-turn.png',(1610,175,1638,231),(1586+j*56,198),(36,52))
        put(im,'T_Hud_CardBackSlot',(1583+j*56,195),(42,58))
    label(im,(1725,283),'Рука 5 · колода 25 · сброс 0',18,LIGHT,'mm')
    # Own HUD.
    put(im,'T_Skin_Panel',(24,884),(370,184))
    scan(im,'01-maneuver-own-turn.png',(43,951,113,1021),(50,931),(54,54),True)
    put(im,'T_Hud_PortraitFrame_Active',(33,914))
    label(im,(128,902),'Медуза',28)
    label(im,(128,936),'ВАШ ХОД',18,'#F2C14E')
    put(im,'T_Hud_HpPlate',(126,954),(150,40))
    ico(im,'resource-hp-full',(134,962),24)
    label(im,(220,974),'16/16',26,LIGHT,'mm')
    for j in range(2):ico(im,'resource-action-full',(301+j*30,961),24)
    for j in range(3):
        xx=139+j*80
        scan(im,'01-maneuver-own-turn.png',(155,1005,181,1031),(xx,997),(25,25),True)
        put(im,'T_Hud_SidekickRing',(xx-5,992))
        label(im,(xx+12,1033),f'Гарпия {j+1}',16,LIGHT,'mm')
        label(im,(xx+12,1050),'1/1',17,LIGHT,'mm')
    # Log outside the board.
    jb=(24,710,299,176) if state==1 else (24,268,299,78)
    put(im,'T_Skin_Panel',jb[:2],jb[2:])
    label(im,(46,jb[1]+12),'Журнал',22)
    label(im,(46,jb[1]+43),'Х1 Медуза: манёвр: без движения',16)
    # Hand background and low tray. The six visible faces are source scans.
    put(im,'T_Skin_PanelInset',(480,884),(966,196))
    put(im,'T_Hud_HandTray',(480,1024),(966,56))
    for j in range(6):
        scan(im,'01-maneuver-own-turn.png',(498+158*j,899,628+158*j,1080),(493+155*j,900),(146,204))
    put(im,'T_Hud_CardGlow_Hover',(793,858))
    scan(im,'05-choice-banner.png',(28,364,251,676),(805,870),(150,208))
    put(im,'T_Skin_Tag',(486,858),(112,32))
    label(im,(542,874),'Рука 6/7',18,LIGHT,'mm')
    # Action rack and separate coloured v3 discs, no icon embedded in bezel.
    put(im,'T_Skin_Panel',(1550,900),(346,178))
    for j,(s,iconname) in enumerate([('Колода 24','resource-card'),('Сброс 0','marker-slot-discard')]):
        xx=1564+j*166
        put(im,'T_Hud_PileFrame',(xx,908),(154,48))
        ico(im,iconname,(xx+10,920),24);label(im,(xx+40,921),s,20)
    for j,(id,s,k) in enumerate(zip(['action-maneuver','action-attack','action-scheme','action-end-turn'],['МАНЁВР','АТАКА','СХЕМА','КОНЕЦ ХОДА'],['M','A','G','E'])):
        xx=1560+j*80
        put(im,'T_Hud_ActionPlate',(xx-2,959),(78,112))
        ico(im,id,(xx+11,968),50)
        put(im,'T_Hud_ActionRing_Hover' if j==0 else 'T_Hud_ActionRing_Normal',(xx,957))
        key(im,(xx+49,956),k)
        if j==3:
            label(im,(xx+36,1040),'КОНЕЦ',16,LIGHT,'mm');label(im,(xx+36,1056),'ХОДА',16,LIGHT,'mm')
        else:label(im,(xx+36,1047),s,16,LIGHT,'mm')
    # Fighter plates occupy the same locations as in the supplied real frame.
    plates=[((494,214,635,253),'1/1','3',False),((350,349,492,388),'1/1','1',False)]
    plates+=([((563,433,697,471),'16/16','',False),((560,554,703,593),'1/1','2',False),((1240,535,1361,574),'7/7','',True),((1051,681,1188,720),'18/18','',True)] if state==1 else
             [((751,575,886,614),'16/16','',False),((452,512,594,551),'1/1','2',False),((1240,535,1361,574),'7/7','',True),((1039,574,1173,613),'18/18','',True)])
    for box,value,digit,enemy in plates:
        x,y,ex,ey=box;w,h=ex-x,ey-y
        erase_old_ui((x,y,w,h),(x,y+h,ex,y+2*h))
        put(im,'T_Hud_FighterPlate_Enemy' if enemy else 'T_Hud_FighterPlate',(x,y),(w,h))
        if digit:label(im,(x+16,y+19),digit,18,LIGHT,'mm')
        else:ico(im,'team-chip-p2' if enemy else 'team-chip-p1',(x+6,y+8),21)
        put(im,'T_Skin_ProgressFill',(x+34,y+h-10),(42,6))
        label(im,(ex-13,y+18),value,19,LIGHT,'rm')
    if state==2:
        for x,side,ref,box,s,value in [
            (24,'Attack','05-choice-banner.png',(28,364,251,676),'АТАКА · Медуза','3'),
            (1646,'Defense','03-combat-attack.png',(1671,364,1893,676),'ЗАЩИТА · Король Артур','1')]:
            put(im,'T_Hud_CombatRibbon_'+side,(x,355),(250,40))
            label(im,(x+125,375),s,19,LIGHT,'mm')
            scan(im,ref,box,(x+10,405),(230,322))
            put(im,'T_Hud_CombatFrame',(x,395))
            put(im,'T_Skin_Capsule',(x+67,724),(116,32))
            ico(im,'action-attack' if side=='Attack' else 'action-defense',(x+78,728),24)
            label(im,(x+128,740),value,25,LIGHT,'mm')
        put(im,'T_Skin_BtnPrimary_Normal',(25,767),(249,42));label(im,(149,788),'ЗАЩИТИТЬСЯ',21,NAVY,'mm')
        put(im,'T_Skin_Btn_Normal',(25,816),(249,42));label(im,(149,837),'БЕЗ ЗАЩИТЫ',21,LIGHT,'mm')
        put(im,'T_Skin_Capsule',(91,862),(112,30));label(im,(147,877),'27 с',23,LIGHT,'mm')
        put(im,'T_Hud_VersusBadge',(676,157),(568,52))
        label(im,(960,183),'3 : 1 · Медуза побеждает',28,LIGHT,'mm')
    name='own-turn' if state==1 else 'combat'
    save(im.convert('RGB'),PRE/(name+'.png'))
    write_json(PRE/(name+'-layers.json'),{'reference':ref,'repairs':patches,'layers':PROVENANCE.copy(),'rules':'All replacement HUD drawn using kit PNGs, real scan crops, v3 icons and Pillow text; no stage-A generated HUD pixels.'})
    concept=Image.open(DER/'concepts'/('A-1-own-turn.png' if state==1 else 'A-2-combat.png')).convert('RGB')
    comparison=Image.new('RGB',(3840,1124),NAVY)
    comparison.paste(concept,(0,44));comparison.paste(im,(1920,44))
    text(comparison,(20,9),'Этап A · концепт',26);text(comparison,(1940,9),'Этап B2 · мрамор и золото, тёмные тела v1',26)
    save(comparison,PRE/('compare-'+name+'.png'))

def main():
    frame(1);frame(2)
    for name in ['own-turn','combat']:
        comparison=Image.new('RGB',(3840,1124),NAVY)
        comparison.paste(Image.open(PRE/(name+'-b1.png')),(0,44))
        comparison.paste(Image.open(PRE/(name+'.png')),(1920,44))
        text(comparison,(20,9),'Этап B · сохранённая сборка',26)
        text(comparison,(1940,9),'Этап B2 · мрамор и золото, тела v1',26)
        save(comparison,PRE/('compare-b-vs-b2-'+name+'.png'))
    print('Two 1920x1080 assembly proofs and native side-by-side comparisons written.')
if __name__=='__main__':main()
