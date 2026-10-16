"""Rebuild the eight SEL references. Reads repository inputs; writes only this task folder."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OUT = ROOT / 'refs'
OUT.mkdir(exist_ok=True)
W, H = 1920, 1080
CREAM = '#ECE3CF'
BRONZE = '#8C6B3F'
GOLD = '#C9A45C'
P1 = '#E8C06A'
P2 = '#5A7F9F'
MUTED = '#B5B6B3'
FONT_DIR = REPO / 'art/imagegen/anim-move-sheet-codex/_tools/fonts'
FONTS = {
    'sans': FONT_DIR / 'Roboto-Regular.ttf',
    'cond': FONT_DIR / 'Roboto-BoldCondensed.ttf',
    'serif': Path('C:/Windows/Fonts/georgia.ttf'),
}
if not FONTS['serif'].exists():
    FONTS['serif'] = FONTS['sans']

DATA = {
    'arthur': {
        'name': 'Король Артур', 'stats': 'HP 18 · ход 2 · ближний бой',
        'helper': '+ Мерлин · HP 7 · дальний бой',
        'ability': 'Когда Король Артур атакует, вы можете УСИЛИТЬ эту атаку: сыграйте карту УСИЛЕНИЯ…',
    },
    'medusa': {
        'name': 'Медуза', 'stats': 'HP 16 · ход 3 · дальний бой',
        'helper': '+ Гарпии ×3 · HP 1 · ближний бой',
        'ability': 'В начале своего хода вы можете нанести 1 урон бойцу противника в зоне Медузы.',
    },
}
BOARD_NAMES = {'marmoreal': 'Marmoreal · оригинальная карта', 'sarpedon': 'Sarpedon · оригинальная карта'}
ALLOWED = {
    *[v for hero in DATA.values() for v in hero.values()], *BOARD_NAMES.values(),
    'Колода · 30', 'Veteran', 'ProGamer', 'SNYMNZ', 'P1', 'P2', '?',
    'ВЫБОР ГЕРОЯ', 'шаг 1 из 2', 'ВЫБОР ПОЛЯ', 'шаг 2 из 2', 'VS',
    'Случайный', 'Случайное', 'Выйти', 'Готов', 'Начать партию', '‹ Герой',
    'Выбирает…', 'Выбран', 'Соперник выбирает…', 'Поле выбирает хост', 'Подготовка поля…',
}
MARBLE = Image.open(REPO / 'art/imagegen/hud-table-materials-codex/M3/hero-card-plate.png').convert('RGB')
MARBLE = MARBLE.crop((14, 14, MARBLE.width-14, MARBLE.height-14))
RECORDS = {}
BOUNDS = []
CURRENT = None


def font(size, kind='sans'):
    return ImageFont.truetype(str(FONTS[kind]), size)


def mix(im, colour, strength):
    return Image.blend(im.convert('RGB'), Image.new('RGB', im.size, colour), strength)


def fit(im, size):
    return ImageOps.fit(im, size, Image.Resampling.LANCZOS)


def text(im, value, pos, size=24, kind='sans', colour=CREAM, anchor='lt', maxwidth=None):
    assert value in ALLOWED, f'Unapproved visible string: {value}'
    f = font(size, kind)
    d = ImageDraw.Draw(im)
    if maxwidth:
        assert d.textlength(value, font=f) <= maxwidth, (CURRENT, value, maxwidth)
    box = d.textbbox(pos, value, font=f, anchor=anchor)
    assert 0 <= box[0] and 0 <= box[1] and box[2] <= W and box[3] <= H, (CURRENT, value, box)
    # Shadows are subtle and intentional; the actual glyphs are all real font rendering.
    if colour != '#111820':
        d.text((pos[0]+1, pos[1]+2), value, font=f, anchor=anchor, fill='#080C11', stroke_width=1)
    d.text(pos, value, font=f, anchor=anchor, fill=colour)
    RECORDS[CURRENT].append(value)
    BOUNDS.append({'image': CURRENT, 'text': value, 'bbox': box, 'font': kind, 'size': size})


def paragraph(im, value, xy, width, size=23, leading=29, colour=CREAM):
    assert value in ALLOWED
    f = font(size)
    words, lines, line = value.split(), [], ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if f.getlength(candidate) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    d = ImageDraw.Draw(im)
    for n, line in enumerate(lines):
        pos = (xy[0], xy[1]+n*leading)
        box = d.textbbox(pos, line, font=f, anchor='lt')
        assert box[2] <= xy[0]+width and box[3] <= H
        d.text((pos[0]+1, pos[1]+2), line, font=f, anchor='lt', fill='#080C11', stroke_width=1)
        d.text(pos, line, font=f, anchor='lt', fill=colour)
        BOUNDS.append({'image': CURRENT, 'text': line, 'logical_text': value, 'bbox': box, 'font': 'sans', 'size': size})
    RECORDS[CURRENT].append(value)
    return len(lines)*leading


def corners(im, box, colour=GOLD, n=17):
    x0,y0,x1,y1 = box
    d = ImageDraw.Draw(im)
    for x,y,sx,sy in [(x0,y0,1,1),(x1,y0,-1,1),(x0,y1,1,-1),(x1,y1,-1,-1)]:
        points=[(x,y+sy*n),(x,y),(x+sx*n,y),(x+sx*n,y+sy*n),(x+sx*7,y+sy*n),
                (x+sx*7,y+sy*7),(x+sx*12,y+sy*7)]
        d.line(points, fill=colour, width=2)


def frame(im, box, colour=BRONZE, width=2, ornament=True):
    d = ImageDraw.Draw(im)
    d.rectangle(box, outline='#080C11', width=6)
    d.rectangle(box, outline=colour, width=width)
    x0,y0,x1,y1 = box
    d.rectangle((x0+4,y0+4,x1-4,y1-4), outline='#625844', width=1)
    if ornament:
        corners(im, (x0+8,y0+8,x1-8,y1-8), colour=GOLD)


def panel(im, box, variant='A', colour=BRONZE, material=True, opacity=.76):
    x0,y0,x1,y1 = box
    size = (x1-x0,y1-y0)
    if material:
        plate = fit(MARBLE, size)
        plate = mix(plate, '#141B24', opacity if variant=='A' else opacity-.16)
    else:
        plate = Image.new('RGB', size, '#141C29')
    im.paste(plate, (x0,y0))
    frame(im, box, colour)


def button(im, box, value, variant, primary=False, disabled=False):
    panel(im, box, variant, colour=BRONZE if disabled else (P1 if primary else BRONZE), opacity=.73)
    if primary and not disabled:
        x0,y0,x1,y1 = box
        ImageDraw.Draw(im).line((x0+12,y1-6,x1-12,y1-6), fill=P1, width=2)
    x0,y0,x1,y1 = box
    text(im, value, ((x0+x1)//2, (y0+y1)//2), size=24, kind='cond',
         colour='#70747A' if disabled else (P1 if primary else CREAM), anchor='mm', maxwidth=x1-x0-36)


def clean_boards():
    # Only source debug name/HP pixels are retouched. The painted map, nodes, edges,
    # figures, original lighting and scenery remain from the real colour K1 crop.
    regions = {
        'marmoreal': [(256,122,301,133),(232,168,281,179),(232,211,280,227),(232,271,281,283)],
        'sarpedon': [(187,236,233,247),(313,224,356,240),(249,256,289,267),
                     (185,289,226,301),(568,266,603,278),(544,310,582,325)],
    }
    boards = {}
    for board, boxes in regions.items():
        im = Image.open(ROOT / '_tools' / f'{board}-K1-colour.png').convert('RGB')
        for box in boxes:
            x0,y0,x1,y1 = box
            x0,y0,x1,y1=x0-2,y0-2,x1+2,y1+2
            # Blur inside the exact text band, without extending the operation
            # onto the map's adjacent figures or movement nodes.
            patch=im.crop((x0,y0,x1,y1)).filter(ImageFilter.GaussianBlur(5))
            im.paste(patch,(x0,y0))
        im.save(ROOT / '_tools' / f'{board}-K1-clean.png')
        boards[board]=im
    return boards, regions


BOARDS, LABEL_REGIONS = clean_boards()


def background(variant):
    y,x = np.mgrid[0:H,0:W]
    if variant=='B':
        base = fit(BOARDS['marmoreal'], (W,H)).filter(ImageFilter.GaussianBlur(16))
        return mix(ImageEnhance.Color(base).enhance(.66),'#101824',.70)
    a = np.zeros((H,W,3),dtype=float)
    a[:] = (9,13,20)
    glow = np.exp(-((x-960)/800)**2-((y-420)/600)**2)
    a += glow[:,:,None]*np.array([9,13,21])
    for cx, colour in [(328,(25,20,10)),(1592,(11,18,26))]:
        cone = np.exp(-((x-cx)/(65+y*.19))**2)*np.exp(-y/850)
        a += cone[:,:,None]*np.array(colour)
    # A quiet reflective marble floor; generated pedestals supply the actual reflections below.
    floor = np.maximum((y-760)/320,0)
    a += floor[:,:,None]*np.array([5,6,8])
    return Image.fromarray(np.uint8(np.clip(a,0,255)))


def header(im, variant, board=False):
    panel(im, (32,20,1888,96),variant,opacity=.84)
    text(im,'ВЫБОР ПОЛЯ' if board else 'ВЫБОР ГЕРОЯ',(960,32),size=36,kind='serif',anchor='mt')
    text(im,'шаг 2 из 2' if board else 'шаг 1 из 2',(960,75),size=19,kind='cond',colour=GOLD,anchor='mt')
    text(im,'Выйти',(66,48),size=25,kind='cond')
    d=ImageDraw.Draw(im)
    d.line((1544,43,1544,74),fill=BRONZE,width=1)
    text(im,'SNYMNZ',(1686,57),size=25,kind='cond',colour=MUTED,anchor='mm')
    for yy in (46,55,64):
        d.line((1824,yy,1848,yy),fill=CREAM,width=2)


# Native 1672x941 crop coordinates. Content is contained with its aspect ratio intact.
# These remove empty generated nameplates/UI; consistent exact layout is applied below.
ART_CROPS = {
    'R1-hero-hover-A': [(144,96,520,710),(1157,98,1525,710)],
    'R1-hero-hover-B': [(49,68,492,714),(1184,102,1621,714)],
    'R2-hero-locked-A': [(78,0,516,717),(1154,45,1617,717)],
    'R2-hero-locked-B': [(49,26,510,778),(1166,38,1625,778)],
    'R3-board-select-A': [(37,101,341,687),(1335,108,1637,687)],
    'R3-board-select-B': [(40,57,364,705),(1315,87,1639,705)],
}


def showcase(im, raw, crop, box, side, variant, empty=False):
    x0,y0,x1,y1 = box
    nameheight=100 if x1-x0==560 else 90
    imagebottom=y1-nameheight
    panel(im,box,variant,colour=P1 if side==0 else P2,opacity=.83 if variant=='A' else .50)
    cut = raw.crop(crop).convert('RGB')
    # No silhouette stretching; the whole crown, sword, body and pedestal stay in frame.
    cut = ImageOps.contain(cut,(x1-x0-26,imagebottom-y0-20),Image.Resampling.LANCZOS)
    xx=x0+(x1-x0-cut.width)//2
    yy=imagebottom-8-cut.height
    mask=Image.new('L',cut.size,255)
    # Blend only outer image edges into the matching marble niche; preserve the hero itself.
    arr=np.ones((cut.height,cut.width),dtype=float)
    ramp=np.minimum(np.arange(cut.width)/10,np.arange(cut.width)[::-1]/10)
    arr*=np.minimum(ramp,1)[None,:]
    mask=Image.fromarray(np.uint8(np.clip(arr*255,0,255)))
    im.paste(cut,(xx,yy),mask)
    # Floor glint belongs to the studio treatment, not the text panel.
    if variant=='A':
        glint=cut.crop((0,max(0,cut.height-38),cut.width,cut.height)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        glint=ImageEnhance.Brightness(glint).enhance(.23).filter(ImageFilter.GaussianBlur(3))
        # Reflection appears within the picture portion and is never drawn across the label.
        im.paste(glint,(xx,min(imagebottom-12,yy+cut.height-8)))
    frame(im,box,colour=P1 if side==0 else P2,ornament=True)
    if empty:
        text(im,'?',((x0+x1)//2,y0+245),size=120,kind='serif',colour=P2,anchor='mm')
        text(im,'Соперник выбирает…',((x0+x1)//2,y0+365),size=24,kind='cond',colour=MUTED,anchor='mm',maxwidth=x1-x0-48)


def nameplate(im, box, side, variant, state, empty=False):
    x0,y0,x1,y1=box
    panel(im,box,variant,colour=P1 if side==0 else P2,opacity=.57)
    col=P1 if side==0 else P2
    size=34 if x1-x0==560 else 29
    text(im,'?' if empty else DATA['arthur' if side==0 else 'medusa']['name'],(x0+26,y0+15),size=size,kind='serif')
    text(im,'Veteran' if side==0 else 'ProGamer',(x0+28,y1-32),size=20,colour=MUTED)
    if side==0:
        # Host is indicated with a tiny crown icon; no invented UI word is printed.
        d=ImageDraw.Draw(im)
        cx=x0+141
        d.polygon([(cx,y1-19),(cx-8,y1-29),(cx,y1-25),(cx+4,y1-34),(cx+8,y1-25),(cx+16,y1-29),(cx+10,y1-19)],fill=P1)
    chipw=130 if state=='Выбирает…' else 105
    cx=x1-chipw-20
    ImageDraw.Draw(im).rounded_rectangle((cx,y1-39,x1-20,y1-12),radius=3,fill='#141B24',outline=col,width=1)
    text(im,state,((cx+x1-20)//2,y1-25),size=18,kind='cond',colour=col,anchor='mm',maxwidth=chipw-12)
    text(im,'P1' if side==0 else 'P2',(x1-36,y0+19),size=18,kind='cond',colour=col,anchor='rt')


def hero_card(im,variant,hero):
    panel(im,(640,500,1280,788),variant,opacity=.79)
    data=DATA[hero]
    text(im,data['name'],(668,519),size=34,kind='serif')
    text(im,data['stats'],(668,567),size=25,kind='cond',colour=P1 if hero=='arthur' else '#A4BECE',maxwidth=582)
    text(im,data['helper'],(668,603),size=22,maxwidth=582)
    ImageDraw.Draw(im).line((668,638,1252,638),fill=BRONZE,width=1)
    paragraph(im,data['ability'],(668,654),width=578,size=22,leading=27)
    if hero=='arthur':
        button(im,(1051,742,1252,778),'Колода · 30',variant)


def roster(im,variant,locked):
    paths={
        'arthur':REPO/'art/imagegen/hero-quality-v1/king-arthur/king-arthur-front.png',
        'medusa':REPO/'art/imagegen/hero-quality-v1/medusa/medusa-front.png',
    }
    facecrops={'arthur':(350,110,850,610),'medusa':(180,10,810,640)}
    for n,x0 in enumerate((752,896,1040)):
        box=(x0,800,x0+128,968)
        panel(im,box,variant,colour=P1 if n==0 else (P2 if n==1 and locked else BRONZE),opacity=.62)
        if n<2:
            hero='arthur' if n==0 else 'medusa'
            portrait=fit(Image.open(paths[hero]).crop(facecrops[hero]),(118,128))
            if locked and n==1:
                portrait=ImageEnhance.Brightness(portrait).enhance(.50)
            im.paste(portrait,(x0+5,805))
            title=DATA[hero]['name']
        else:
            text(im,'?',(x0+64,865),size=66,kind='serif',colour=GOLD,anchor='mm')
            title='Случайный'
        ImageDraw.Draw(im).rectangle((x0+5,932,x0+123,963),fill='#121923')
        text(im,title,(x0+64,947),size=18,kind='cond',anchor='mm',maxwidth=120)
        frame(im,box,colour=P1 if n==0 else (P2 if n==1 and locked else BRONZE),width=3 if n==0 else 2,ornament=False)
        if locked and n<2:
            col=P1 if n==0 else P2
            ImageDraw.Draw(im).rectangle((x0+91,804,x0+123,830),fill=col)
            text(im,'P1' if n==0 else 'P2',(x0+107,818),size=16,kind='cond',colour='#111820',anchor='mm')


MEDAL_CROPS={
    'R2-hero-locked-A':(725,87,951,313),
    'R2-hero-locked-B':(754,151,918,315),
    'R4-vs-A':(689,249,983,537),
    'R4-vs-B':(687,246,985,542),
}


def medallion(im,raw,key,diameter):
    medal=raw.crop(MEDAL_CROPS[key]).resize((diameter,diameter),Image.Resampling.LANCZOS)
    mask=Image.new('L',medal.size,0)
    ImageDraw.Draw(mask).ellipse((1,1,diameter-2,diameter-2),fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(.5))
    im.paste(medal,(960-diameter//2,420-diameter//2),mask)
    text(im,'VS',(960,420),size=52 if diameter==140 else 80,kind='serif',colour=CREAM,anchor='mm')


def bottom(im,variant,screen):
    panel(im,(32,980,1888,1060),variant,opacity=.84)
    button(im,(52,994,244,1046),'‹ Герой' if screen==3 else 'Выйти',variant)
    if screen==1:
        text(im,'Соперник выбирает…',(936,1020),size=23,kind='cond',colour=MUTED,anchor='mm')
    elif screen==3:
        text(im,'Поле выбирает хост',(936,1020),size=23,kind='cond',colour=MUTED,anchor='mm')
    button(im,(1390,994,1550,1046),'Готов',variant,primary=screen==2,disabled=screen==1)
    button(im,(1570,994,1866,1046),'Начать партию',variant,primary=screen==3,disabled=screen!=3)


def compose_hero(key,variant,locked):
    raw=Image.open(ROOT/'raw'/f'{key}.png').convert('RGB')
    if key=='R2-hero-locked-B':
        # ImageGen placed an empty header across the two crop boundaries. Remove
        # only its two fragments from this working copy, retaining sword and snakes.
        neutral=raw.crop((544,86,636,146))
        for box in ((410,26,513,89),(1163,38,1261,89)):
            raw.paste(neutral.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS),box[:2])
    im=background(variant)
    for side,x0 in enumerate((48,1312)):
        showcase(im,raw,ART_CROPS[key][side],(x0,120,x0+560,920),side,variant,empty=not locked and side==1)
        nameplate(im,(x0,820,x0+560,920),side,variant,
                  ('Выбран' if side==0 else 'Готов') if locked else 'Выбирает…',empty=not locked and side==1)
        if variant=='A':
            # Reflect pedestal material only; reflected UI lettering would violate
            # the clean-text constraint. Feather into the floor without a hard box.
            source=raw.crop(ART_CROPS[key][side])
            reflection=source.crop((0,source.height-28,source.width,source.height))
            reflection=reflection.resize((440,32),Image.Resampling.LANCZOS).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            reflection=ImageEnhance.Brightness(reflection).enhance(.35).filter(ImageFilter.GaussianBlur(4))
            ry,rx=np.mgrid[0:32,0:440]
            alpha=np.maximum(0,1-ry/31)*np.minimum(1,np.minimum(rx,439-rx)/32)*90
            im.paste(reflection,(x0+60,922),Image.fromarray(np.uint8(alpha)))
    header(im,variant)
    hero_card(im,variant,'medusa' if locked else 'arthur')
    roster(im,variant,locked)
    if locked:
        medallion(im,raw,key,140)
        d=ImageDraw.Draw(im)
        d.line((670,420,852,420),fill=BRONZE,width=1)
        d.line((1068,420,1250,420),fill=BRONZE,width=1)
    bottom(im,variant,2 if locked else 1)
    return im


def compose_board(key,variant):
    raw=Image.open(ROOT/'raw'/f'{key}.png').convert('RGB')
    im=background(variant)
    for side,x0 in enumerate((48,1472)):
        showcase(im,raw,ART_CROPS[key][side],(x0,160,x0+400,760),side,variant)
        nameplate(im,(x0,670,x0+400,760),side,variant,'Готов')
    header(im,variant,board=True)
    # Exactly 960x540 of the real colour K1, not an ImageGen map.
    panel(im,(474,124,1446,676),variant,opacity=.65)
    im.paste(BOARDS['marmoreal'],(480,130))
    frame(im,(474,124,1446,676),colour=GOLD,width=2)
    panel(im,(480,692,1440,758),variant,opacity=.60)
    text(im,BOARD_NAMES['marmoreal'],(960,725),size=30,kind='serif',anchor='mm',maxwidth=900)
    for n,x0 in enumerate((644,860,1076)):
        box=(x0,788,x0+200,908)
        panel(im,box,variant,colour=P1 if n==0 else BRONZE,opacity=.64)
        if n<2:
            board='marmoreal' if n==0 else 'sarpedon'
            im.paste(fit(BOARDS[board],(192,108)),(x0+4,794))
            paragraph(im,BOARD_NAMES[board],(x0,917),width=202,size=17,leading=21,colour=CREAM if n==0 else MUTED)
        else:
            text(im,'?',(x0+100,846),size=65,kind='serif',colour=GOLD,anchor='mm')
            text(im,'Случайное',(x0+100,932),size=21,kind='cond',anchor='mm')
        frame(im,box,colour=P1 if n==0 else BRONZE,width=3 if n==0 else 2,ornament=False)
    bottom(im,variant,3)
    return im


def compose_vs(key,variant):
    raw=Image.open(ROOT/'raw'/f'{key}.png').convert('RGB')
    im=raw.resize((W,H),Image.Resampling.LANCZOS)
    # Preserve generated diagonal plaques and fighter silhouettes. Replace the empty
    # centre with a true K1 frame; replace the original oversized blank medal as well.
    points=[(574,0),(1101,0),(940,780),(731,780)] if variant=='A' else [(535,0),(1134,0),(940,820),(729,820)]
    points=[(round(x*W/raw.width),round(y*H/raw.height)) for x,y in points]
    mask=Image.new('L',(W,H),0)
    ImageDraw.Draw(mask).polygon(points,fill=255)
    backdrop=fit(BOARDS['marmoreal'],(W,H)).filter(ImageFilter.GaussianBlur(5 if variant=='A' else 16))
    backdrop=mix(backdrop,'#101824',.56 if variant=='A' else .66)
    im.paste(backdrop,(0,0),mask)
    if variant=='B':
        # The whole outside of the diagonal plaques is the same real blurred board.
        outer=Image.new('L',(W,H),0)
        ImageDraw.Draw(outer).rectangle((0,1000,W,H),fill=255)
        im.paste(backdrop,(0,0),outer)
    medallion(im,raw,key,220)
    for side,(x0,x1) in enumerate(((70,710),(1210,1850))):
        panel(im,(x0,895,x1,994),variant,colour=P1 if side==0 else P2,opacity=.68)
        text(im,DATA['arthur' if side==0 else 'medusa']['name'],((x0+x1)//2,910),size=38,kind='serif',anchor='mt')
        text(im,'Veteran' if side==0 else 'ProGamer',((x0+x1)//2,966),size=23,colour=P1 if side==0 else '#A4BECE',anchor='mm')
        text(im,'P1' if side==0 else 'P2',(x0+24,914),size=20,kind='cond',colour=P1 if side==0 else P2)
    # Cover all former blank bottom plaques so there are no duplicate or clipped strips.
    panel(im,(32,1006,1888,1076),variant,opacity=.84)
    text(im,BOARD_NAMES['marmoreal'],(960,1016),size=27,kind='serif',anchor='mt')
    text(im,'Подготовка поля…',(981,1054),size=20,kind='cond',colour=MUTED,anchor='mm')
    d=ImageDraw.Draw(im)
    d.arc((849,1045,866,1062),start=35,end=303,fill=GOLD,width=2)
    d.line((520,1071,1400,1071),fill='#46505C',width=1)
    d.line((520,1071,1036,1071),fill=GOLD,width=2)
    return im


def build():
    global CURRENT
    files=[]
    for screen in ('R1-hero-hover','R2-hero-locked','R3-board-select','R4-vs'):
        for variant in ('A','B'):
            key=f'{screen}-{variant}'
            CURRENT=key
            RECORDS[key]=[]
            if screen.startswith('R1') or screen.startswith('R2'):
                im=compose_hero(key,variant,screen.startswith('R2'))
            elif screen.startswith('R3'):
                im=compose_board(key,variant)
            else:
                im=compose_vs(key,variant)
            assert im.size==(1920,1080)
            im.save(OUT/f'{key}.png',optimize=True)
            files.append(key)
    contact=Image.new('RGB',(960,1080),'#101824')
    for n,key in enumerate(files):
        contact.paste(Image.open(OUT/f'{key}.png').resize((480,270),Image.Resampling.LANCZOS),((n%2)*480,(n//2)*270))
    contact.save(OUT/'contact-sheet.png',optimize=True)
    metadata={
        'output_size':[1920,1080], 'contact_sheet_size':[960,1080], 'contact_grid':'2 columns x 4 rows; A left, B right',
        'fonts':{k:str(v) for k,v in FONTS.items()},
        'visible_text':{k:list(dict.fromkeys(v)) for k,v in RECORDS.items()},
        'rendered_text_bounds':BOUNDS, 'source_label_retouch_regions':LABEL_REGIONS,
        'raw_sizes':{k:list(Image.open(ROOT/'raw'/f'{k}.png').size) for k in files},
        'file_hashes':{f'{k}.png':hashlib.sha256((OUT/f'{k}.png').read_bytes()).hexdigest() for k in files},
        'spec_sections':{k:'§3' if k.startswith(('R1','R2')) else ('§4' if k.startswith('R3') else '§5') for k in files},
        'visual_review':'pending', 'moderation_blocked':[],
    }
    (ROOT/'_tools/composition.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'generated':files,'all_1920x1080':True,'allowed_strings_only':True,'contact_sheet':[960,1080]},ensure_ascii=False))


if __name__=='__main__':
    build()
