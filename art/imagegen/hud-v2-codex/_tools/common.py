from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance
import json, hashlib, math, shutil
ROOT=Path(__file__).resolve().parents[4]
ART=ROOT/'art/imagegen/hud-v2-codex'
OUT=ROOT/'scraped-data/derived/hud-v2-codex/concepts'
REF=ROOT/'scraped-data/derived/hud-v2-codex/refs'
ICON=ROOT/'art/imagegen/hud-icons-v3/masters'
FONT=ROOT/'art/imagegen/anim-move-sheet-codex/_tools/fonts/Roboto-BoldCondensed.ttf'
REG=ROOT/'art/imagegen/anim-move-sheet-codex/_tools/fonts/Roboto-Regular.ttf'
NAVY='#061623'; CREAM='#F9EBDB'
NAMES={'A':'Мраморный акрополь','B':'Бронза и пергамент','C':'Цифровое издание'}
PALETTES={'A':['#061623','#F9EBDB','#F4EFE4','#C6A15A','#6B4E8F','#DC2F33','#FDBE72','#656B70'],
'B':['#061623','#F9EBDB','#34241E','#A9804E','#EBD9AF','#6B4E8F','#DC2F33','#FDBE72','#656B70'],
'C':['#061623','#F9EBDB','#122C42','#8DABB9','#6B4E8F','#DC2F33','#FDBE72','#656B70']}
RAW={f'P{i:02}':Image.open(OUT/f'generated/P{i:02}.png').convert('RGBA') for i in range(1,13)}
GUIDES={'A':RAW['P04'],'B':RAW['P08'],'C':RAW['P12']}
GFRAME={'A':(43,187,545,301),'B':(32,177,510,366),'C':(33,171,379,289)}
GTEXTURE={'A':(120,220,180,260),'B':(120,245,200,300),'C':(120,200,180,250)}
GPORTRAIT={'A':(36,433,285,635),'B':(23,436,225,636),'C':(32,372,234,574)}
ACTION_NAMES=['МАНЁВР','АТАКА','СХЕМА','КОНЕЦ ХОДА']
ACTION_IDS=['action-maneuver','action-attack','action-scheme','action-end-turn']
HOTKEYS=['M','A','G','E']
# Per-call HUD region crops, measured on reviewed 1672 x 941 raw outputs.
CROPS={
'P01':{'turn':(17,21,305,88),'status':(480,19,1190,134),'own':(11,751,376,930),'opp':(1332,19,1659,286),'journal':(17,590,290,744),'actions':(1298,751,1661,932),'hand':(422,754,1250,940)},
'P02':{'turn':(20,21,307,94),'status':(499,21,1172,94),'own':(16,747,375,929),'opp':(1347,21,1657,280),'journal':(18,168,318,255),'actions':(1298,748,1661,932),'hand':(420,749,1275,940),'combatL':(20,273,299,736),'combatR':(1375,289,1655,672)},
'P03':{'turn':(16,20,307,86),'status':(476,19,1193,69),'own':(14,746,389,931),'opp':(1347,18,1658,271),'journal':(15,633,292,733),'actions':(1288,747,1661,931),'hand':(420,747,1275,940),'choice':(460,64,1209,188),'combatL':(17,310,226,621),'combatR':(1448,312,1657,622)},
'P05':{'turn':(12,15,275,92),'status':(455,13,1220,108),'own':(11,759,372,930),'opp':(1347,15,1661,330),'journal':(13,580,286,758),'actions':(1298,751,1662,933),'hand':(393,749,1275,940)},
'P06':{'turn':(19,20,277,97),'status':(477,20,1198,99),'own':(15,750,373,929),'opp':(1326,21,1656,324),'journal':(20,163,320,263),'actions':(1298,750,1661,931),'hand':(383,748,1274,940),'combatL':(18,273,319,731),'combatR':(1377,324,1653,691)},
'P07':{'turn':(14,22,282,103),'status':(478,14,1201,97),'own':(14,751,374,930),'opp':(1349,23,1662,329),'journal':(13,630,289,748),'actions':(1298,749,1661,932),'hand':(392,749,1275,940),'choice':(455,93,1219,216),'combatL':(16,308,225,625),'combatR':(1448,323,1657,628)},
'P09':{'turn':(21,27,318,94),'status':(489,27,1223,94),'own':(18,743,396,923),'opp':(1347,27,1653,301),'journal':(18,586,311,733),'actions':(1317,745,1655,923),'hand':(437,742,1263,940)},
'P10':{'turn':(21,25,307,84),'status':(509,25,1208,86),'own':(20,744,392,922),'opp':(1354,24,1653,273),'journal':(21,117,322,201),'actions':(1316,745,1657,925),'hand':(438,742,1265,940),'combatL':(20,218,270,673),'combatR':(1404,284,1655,640)},
'P11':{'turn':(16,22,310,85),'status':(499,20,1247,85),'own':(17,747,393,925),'opp':(1357,21,1659,283),'journal':(16,631,315,732),'actions':(1316,745,1658,925),'hand':(437,743,1264,940),'choice':(490,86,1184,178),'combatL':(17,293,240,623),'combatR':(1435,293,1656,624)}
}
def font(n,regular=False): return ImageFont.truetype(str(REG if regular else FONT),n)
def text(im,xy,s,size=20,fill=CREAM,anchor=None,regular=False):
    d=ImageDraw.Draw(im)
    d.text(xy,s,font=ImageFont.truetype('C:/Windows/Fonts/seguisym.ttf',size) if s in ['①','②','③'] else font(size,regular),fill=fill,anchor=anchor,spacing=3)
def fittext(im,box,s,size=22,fill=CREAM,center=True):
    x,y,w,h=box; f=font(size)
    while f.getlength(s)>w-12 and size>16: size-=1; f=font(size)
    assert f.getlength(s)<=w-6,(s,w,size)
    d=ImageDraw.Draw(im); d.text((x+w/2,y+h/2),s,font=f,fill=fill,anchor='mm') if center else d.text((x,y),s,font=f,fill=fill)
def nine(src,size,b=22):
    w,h=size; sw,sh=src.size; b=min(b,sw//3,sh//3,w//3,h//3)
    dest=Image.new('RGBA',size)
    xs=[0,b,sw-b,sw]; ys=[0,b,sh-b,sh]; xd=[0,b,w-b,w]; yd=[0,b,h-b,h]
    for yy in range(3):
        for xx in range(3):
            box=(xs[xx],ys[yy],xs[xx+1],ys[yy+1]); tw=xd[xx+1]-xd[xx]; th=yd[yy+1]-yd[yy]
            dest.paste(src.crop(box).resize((tw,th),Image.Resampling.LANCZOS),(xd[xx],yd[yy]))
    return dest
def panel(x,size,source=None,box=None,dark=False):
    src=(source.crop(box) if source is not None else GUIDES[x].crop(GFRAME[x]))
    p=nine(src,size,22 if x!='B' else 28)
    pad=14 if min(size)>80 else 8
    tex=GUIDES[x].crop(GTEXTURE[x]).resize((size[0]-2*pad,size[1]-2*pad))
    p.paste(tex,(pad,pad))
    d=ImageDraw.Draw(p)
    if x=='A' or dark:
        d.rounded_rectangle((pad,pad,size[0]-pad-1,size[1]-pad-1),radius=4,fill=NAVY,outline='#C6A15A' if x=='A' else '#A9804E',width=1)
    return p
def paste(im,p,xy): im.alpha_composite(p,tuple(map(int,xy)))
def icon(name,n=32):
    p=Image.open(ICON/(name+'.png')).convert('RGBA').resize((n,n),Image.Resampling.LANCZOS)
    if name=='action-end-turn':
        px=p.load()
        for y in range(n):
            for x in range(n):
                r,g,b,a=px[x,y]
                if a and b>r and r<40 and g<60: px[x,y]=(101,107,112,a)
    return p
def disc_state(i,n,state=0):
    p=icon(ACTION_IDS[i],n)
    if state==3:
        alpha=p.getchannel('A')
        p=ImageEnhance.Color(p).enhance(0.12); p=ImageEnhance.Brightness(p).enhance(0.8); p.putalpha(alpha)
    return p
def chip(im,x,y,label,style='A',n=25):
    d=ImageDraw.Draw(im); d.rounded_rectangle((x,y,x+n,y+n),radius=4,fill=NAVY,outline=CREAM,width=1)
    text(im,(x+n/2,y+n/2),label,18,CREAM,'mm')
def medallion(x,portrait,size=92):
    p=GUIDES[x].crop(GPORTRAIT[x]).resize((size,size),Image.Resampling.LANCZOS)
    m=Image.new('L',(size,size)); ImageDraw.Draw(m).ellipse((1,1,size-2,size-2),fill=255)
    p.putalpha(m)
    if portrait is not None:
        s=round(size*0.70); inner=portrait.resize((s,s),Image.Resampling.LANCZOS)
        mi=Image.new('L',(s,s));ImageDraw.Draw(mi).ellipse((0,0,s-1,s-1),fill=255);inner.putalpha(mi)
        paste(p,inner,((size-s)//2,(size-s)//2))
    return p
REFS={f.name:Image.open(f).convert('RGBA') for f in REF.glob('*.png')}
portrait_medusa=REFS['01-maneuver-own-turn.png'].crop((43,951,113,1021))
portrait_arthur=REFS['01-maneuver-own-turn.png'].crop((1805,52,1877,124))
own_cards=[REFS['01-maneuver-own-turn.png'].crop((490+158*i,891,634+158*i,1080)) for i in range(6)]
hover_card=REFS['04-combat-defense.png'].crop((1248,751,1460,1051))
attack_scan=REFS['05-choice-banner.png'].crop((28,364,251,676))
defense_scan=REFS['03-combat-attack.png'].crop((1671,364,1893,676))
choice_defense=REFS['05-choice-banner.png'].crop((1671,364,1893,676))
def cardback(size=(48,66)):
    w,h=size;p=Image.new('RGBA',size,NAVY);d=ImageDraw.Draw(p)
    d.rounded_rectangle((1,1,w-2,h-2),radius=3,outline=CREAM,width=1)
    d.rectangle((5,5,w-6,h-6),outline='#DB8065',width=1)
    cx=w//2;cy=h//2
    d.polygon([(cx,10),(w-10,cy),(cx,h-10),(10,cy)],outline='#DB8065',width=2)
    d.ellipse((cx-3,cy-3,cx+3,cy+3),fill=CREAM)
    return p
def action_button(x,i,size=(78,88),state=0):
    w,h=size;p=panel(x,size,dark=True)
    if state==1:
        d=ImageDraw.Draw(p);d.rounded_rectangle((2,2,w-3,h-3),radius=5,outline='#F9DE9A' if x!='C' else '#BDEBFF',width=2)
    if state==2:
        p=ImageEnhance.Brightness(p).enhance(.76)
    n=min(54,h-32,w-14); off=2 if state==2 else 0
    paste(p,disc_state(i,n,state),((w-n)//2+off,5+off))
    label=ACTION_NAMES[i]
    if i==3:
        text(p,(w/2,h-26),'КОНЕЦ',16,CREAM,'mm');text(p,(w/2,h-10),'ХОДА',16,CREAM,'mm')
    else: text(p,(w/2,h-17),label,16,CREAM,'mm')
    return p
def smallbutton(im,x,box,label,primary=False,size=20):
    bx,by,bw,bh=box;p=panel(x,(bw,bh),dark=not primary)
    if primary and x=='C':
        ImageDraw.Draw(p).rounded_rectangle((4,4,bw-5,bh-5),radius=5,fill=CREAM)
    fill=NAVY if (primary and x in ['B','C']) else CREAM
    fittext(p,(8,5,bw-16,bh-10),label,size,fill)
    paste(im,p,(bx,by))
def contact():
    im=Image.new('RGB',(2560,1080),NAVY)
    for r,x in enumerate('ABC'):
        for c,state in enumerate(['own-turn','combat','choice','styleguide']):
            name=f'{x}-{c+1}-{state}.png'
            p=Image.open(OUT/name).resize((640,360),Image.Resampling.LANCZOS)
            im.paste(p,(c*640,r*360))
            d=ImageDraw.Draw(im);d.rounded_rectangle((c*640+6,r*360+5,c*640+162,r*360+32),radius=3,fill=NAVY)
            text(im,(c*640+15,r*360+8),f'{x}-{c+1} · '+['Свой ход','Бой','Выбор','Стиль'][c],18,CREAM)
    im.save(OUT/'contact.png')
def main():
    (OUT/'proof').mkdir(parents=True,exist_ok=True);(ART/'styleguides').mkdir(parents=True,exist_ok=True)
    audit={'concepts':[],'styleguides':[],'input_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in list(REF.glob('*.png'))+list(ICON.glob('*.png'))}}
    for x in 'ABC':
        for s in [1,2,3]:audit['concepts'].append(build_frame(x,s))
        audit['styleguides'].append(styleguide(x))
    contact()
    (ART/'verification.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'concepts':len(audit['concepts']),'styleguides':len(audit['styleguides']),'contact':[2560,1080]},ensure_ascii=False))

