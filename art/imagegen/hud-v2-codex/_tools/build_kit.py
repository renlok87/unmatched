"""Stage B. Deterministic chroma-key / assembly. Run from any working directory.
Only writes inside the two HUD-v2 directories. No image-generation/network/git calls.
"""
from pathlib import Path
import json, hashlib, math, sys
import numpy as np
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops, ImageEnhance
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
ART = ROOT/'art/imagegen/hud-v2-codex'
KIT = ART/'kit'
DER = ROOT/'scraped-data/derived/hud-v2-codex'
PRE = DER/'kit-preview'
FONT = ROOT/'art/imagegen/anim-move-sheet-codex/_tools/fonts/Roboto-BoldCondensed.ttf'
NAVY='#061623'; LIGHT='#F2EDE4'; IVORY='#EEE7D8'; GOLD='#C6A15A'
S=4
ASSETS={}

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def rgb(c): return tuple(bytes.fromhex(c.lstrip('#')))
def font(n): return ImageFont.truetype(str(FONT),n)
def text(im,xy,s,n=20,color=LIGHT,anchor=None): ImageDraw.Draw(im).text(xy,s,font=font(n),fill=color,anchor=anchor)
def save(im,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    # All alpha-zero texels have zero RGB: no hidden key color in engine filtering.
    if im.mode=='RGBA':
        a=np.array(im)
        fringe=(a[:,:,3]<=32)&(a[:,:,1].astype(int)>np.maximum(a[:,:,0],a[:,:,2]).astype(int)+16)
        a[:,:,1][fringe]=np.maximum(a[:,:,0],a[:,:,2])[fringe]
        a[a[:,:,3]==0,:3]=0;im=Image.fromarray(a)
    im.save(path,optimize=True)

def key_green(path):
    a=np.asarray(Image.open(path).convert('RGB'),dtype=np.float32)
    m=np.maximum(a[:,:,0],a[:,:,2])
    alpha=np.clip(1-(a[:,:,1]-m)/np.maximum(255-m,1),0,1)
    bg=(a[:,:,1]>235)&(a[:,:,0]<40)&(a[:,:,2]<40)
    alpha[bg]=0
    clean=(a-(1-alpha[:,:,None])*np.array([0,255,0]))/np.maximum(alpha[:,:,None],.001)
    clean[:,:,1]=np.where(alpha<.999,np.minimum(clean[:,:,1],np.maximum(clean[:,:,0],clean[:,:,2])),clean[:,:,1])
    out=np.dstack((np.clip(clean,0,255),alpha*255)).round().astype('uint8')
    out[out[:,:,3]<3]=0
    return Image.fromarray(out)

@lru_cache(maxsize=None)
def source(id):
    return key_green(next((KIT/'source-masters').glob(id+'-*.png')))

def tint(im, kind):
    if kind=='normal': return im.copy()
    a=im.getchannel('A'); q=im.convert('RGB')
    if kind=='hover': q=ImageEnhance.Brightness(q).enhance(1.19)
    elif kind=='pressed': q=ImageEnhance.Brightness(q).enhance(.68)
    elif kind=='disabled':
        q=ImageEnhance.Color(q).enhance(.06);q=ImageEnhance.Brightness(q).enhance(.82)
    elif kind=='enemy': q=Image.blend(q,Image.new('RGB',q.size,'#6BA7C4'),.22)
    elif kind=='active': q=ImageEnhance.Brightness(q).enhance(1.13)
    q.putalpha(a); return q

def stabilize(im,margins,body=None,horizontal=False):
    a=np.array(im);h,w=a.shape[:2];l,t,r,b=margins
    # Constant transverse profiles. Two-pixel guards make slice joins exact as well.
    if w>l+r:
        for y0,y1 in [(0,t),(h-b,h)]:
            col=a[y0:y1,w//2:w//2+1].copy()
            a[y0:y1,l:w-r]=col
            for i in range(2):
                if l>i:a[y0:y1,l-1-i]=col[:,0]
                if r>i:a[y0:y1,w-r+i]=col[:,0]
    if not horizontal and h>t+b:
        for x0,x1 in [(0,l),(w-r,w)]:
            row=a[h//2:h//2+1,x0:x1].copy()
            a[t:h-b,x0:x1]=row
            for i in range(2):
                if t>i:a[t-1-i,x0:x1]=row[0]
                if b>i:a[h-b+i,x0:x1]=row[0]
    if body is not None and w>l+r and h>t+b:
        a[t:h-b,l:w-r]=(*rgb(body),255)
    a[a[:,:,3]==0,:3]=0
    return Image.fromarray(a)

def plain_frame(size,margin,body=NAVY,rich=False,state='normal',hole=False):
    w,h=[round(v*S) for v in size];c=round(margin*S)
    src=source('B04') if rich else source('B01')
    # Measured native source coordinates. Source masters are immutable.
    if rich:
        q=src.crop((54,56,438,440)).resize((c,c),Image.Resampling.LANCZOS)
        top=src.crop((750,56,751,440)).resize((1,c),Image.Resampling.LANCZOS)
        left=src.crop((54,750,438,751)).resize((c,1),Image.Resampling.LANCZOS)
    else:
        # Remove external laurels for quiet controls. Rich panels use B04 instead.
        q=src.crop((80,104,260,284)).resize((c,c),Image.Resampling.LANCZOS)
        top=src.crop((740,104,741,284)).resize((1,c),Image.Resampling.LANCZOS)
        left=src.crop((80,470,260,471)).resize((c,1),Image.Resampling.LANCZOS)
    # Fade each end of corner into exactly the chosen straight profile.
    ar=np.array(q,dtype=np.float32);tp=np.array(top,dtype=np.float32)[:,0];lp=np.array(left,dtype=np.float32)[0]
    blend=max(8,c//5)
    for k in range(blend):
        f=(k+1)/blend
        ar[:,c-blend+k]=ar[:,c-blend+k]*(1-f)+tp*f
        ar[c-blend+k,:]=ar[c-blend+k,:]*(1-f)+lp*f
    q=Image.fromarray(ar.round().astype('uint8'))
    out=Image.new('RGBA',(w,h));out.paste(q,(0,0));out.paste(ImageOps.mirror(q),(w-c,0))
    out.paste(ImageOps.flip(q),(0,h-c));out.paste(ImageOps.flip(ImageOps.mirror(q)),(w-c,h-c))
    out.paste(top.resize((w-2*c,c)),(c,0));out.paste(ImageOps.flip(top).resize((w-2*c,c)),(c,h-c))
    out.paste(left.resize((c,h-2*c)),(0,c));out.paste(ImageOps.mirror(left).resize((c,h-2*c)),(w-c,c))
    out=tint(out,state)
    if not hole:
        boundary=out.getchannel('A').point(lambda x:255 if x>=48 else 0)
        filled=boundary.copy();ImageDraw.floodfill(filled,(w//2,h//2),255)
        interior=ImageChops.subtract(filled,boundary)
        bg=Image.new('RGBA',out.size,body);bg.putalpha(interior)
        out=Image.alpha_composite(bg,out)
    return stabilize(out,(c,c,c,c),None if hole else body)

def focus(size,margin):
    w,h=[v*S for v in size];q=Image.new('RGBA',(w,h));d=ImageDraw.Draw(q)
    d.rounded_rectangle((S,S,w-S-1,h-S-1),radius=5*S,outline='#FAF8F2',width=2*S)
    return stabilize(q,(margin*S,)*4)

def emit(name,im,margin=0,stretch='nine_slice',body=None,text_color=LIGHT,role='',widget='',sources=None,**extra):
    if isinstance(margin,(int,float)): margin=[margin]*4
    size=[im.width//S,im.height//S]
    d={'name':name,'size_su':size,'slice_su':list(margin),'stretch':stretch,'body_color':body,'text_color':text_color,
       'role':role,'ue_skin_key':name.removeprefix('T_Skin_') if name.startswith('T_Skin_') else None,
       'widget':widget,'text_safe_insets_su':list(margin) if body else None,'source_masters':sources or ['B01'],'files':{},**extra}
    for scale,folder in [(1,'x1'),(2,'x2'),(4,'masters')]:
        p=im if scale==4 else im.resize((size[0]*scale,size[1]*scale),Image.Resampling.LANCZOS)
        mm=[round(x*scale) for x in margin]
        if stretch in ['nine_slice','horizontal']:p=stabilize(p,mm,body,horizontal=stretch=='horizontal')
        if 'glow_color' in extra:
            ar=np.array(p);ar[:,:,:3]=rgb(extra['glow_color']);p=Image.fromarray(ar)
        if 'insert_diameter_su' in extra:
            ar=np.array(p);yy,xx=np.ogrid[:p.height,:p.width];rr=extra['insert_diameter_su']*scale/2
            dist=np.sqrt((xx-p.width/2)**2+(yy-p.height/2)**2)
            ar[:,:,3]=np.minimum(ar[:,:,3],np.clip((dist-rr)*255,0,255).astype('uint8'));p=Image.fromarray(ar)
        if stretch=='tile_x':
            ar=np.array(p);ends=((ar[:,0].astype(int)+ar[:,-1].astype(int))/2).round().astype('uint8');ar[:,0]=ends;ar[:,-1]=ends;p=Image.fromarray(ar)
        if 'insert_rect_su' in extra:
            ix,iy,iw,ih=[round(v*scale) for v in extra['insert_rect_su']]
            alpha=p.getchannel('A');ImageDraw.Draw(alpha).rectangle((ix,iy,ix+iw-1,iy+ih-1),fill=0);p.putalpha(alpha)
        path=KIT/folder/(name+'.png');save(p,path)
        d['files'][folder]={'path':str(path.relative_to(ART)).replace('\\','/'),'size_px':list(p.size),'scale':scale,'slice_px':dict(zip(['left','top','right','bottom'],mm)),'sha256':sha(path)}
    ASSETS[name]=d

def b1():
    old=json.loads((ROOT/'art/imagegen/hud-skins-v1-codex/manifest.json').read_text('utf-8'))
    for n in old['names']:
        v=old['skins']['vector/x1/T_Skin_'+n+'.png'];content=v['content_su'];state='normal';rich=False
        body=NAVY;tc=LIGHT;b=8
        if n in ['Panel','PanelInset','Modal']:
            b={'Panel':18,'PanelInset':12,'Modal':24}[n];rich=n!='PanelInset';body='#040E17' if n=='PanelInset' else NAVY
        elif n.startswith('Btn'):
            state=n.split('_')[-1].lower()
            primary=n.startswith('BtnPrimary')
            body=({'normal':'#F2C14E','hover':'#F3C55B','pressed':'#D5AA45','disabled':'#4E5457','focus':'#F2C14E'} if primary else
                  {'normal':IVORY,'hover':'#FFF6DE','pressed':'#C9B995','disabled':'#C3C0B8','selected':'#0D7A89','focus':IVORY})[state]
            tc=LIGHT if (primary and state=='disabled') or state=='selected' else NAVY
        elif n in ['Toast','ToastWarning']:
            b=14 if n=='Toast' else 16;rich=True
        elif n in ['Capsule','Tag','Chip','KeyChip']:
            b=4 if n=='KeyChip' else 6;body=IVORY if n in ['Capsule','KeyChip'] else NAVY;tc=NAVY if body==IVORY else LIGHT
        elif n in ['ProgressTrack','SliderTrack','ProgressFill']:
            b=2;body='#0D7A89' if n=='ProgressFill' else '#040E17'
        elif n=='SliderThumb':b=4;body=IVORY;tc=NAVY
        elif n.startswith('Check_'):
            b=1;body='#0D7A89' if n=='Check_On' else IVORY;tc=LIGHT if n=='Check_On' else NAVY
        elif n.startswith('Input_'):
            b=7;body=IVORY;tc=NAVY
        if n in ['Btn_Selected','Check_On','ProgressFill']:tc='#FAF8F2'
        w,h=content[0]+2*b,content[1]+2*b
        overlay=n.endswith('_Focus')
        if overlay:
            b+=5;w+=10;h+=10;im=focus((w,h),b);body_out=None
        else:
            im=plain_frame((w,h),b,body,rich,state if state in ['hover','pressed','disabled'] else 'normal')
            body_out=body
            if state=='pressed':
                dd=ImageDraw.Draw(im);o=2*S
                dd.line((o,o,w*S-o-1,o),fill='#75664B',width=S)
                dd.line((o,h*S-o-1,w*S-o-1,h*S-o-1),fill='#F9EBDB',width=S)
                im=stabilize(im,(b*S,)*4,body)
            if n in ['ToastWarning','Input_Error']:
                col='#E8812C' if n=='ToastWarning' else '#D9483F'
                d=ImageDraw.Draw(im);off=round(b*.32*S)
                d.rounded_rectangle((off,off,w*S-off-1,h*S-off-1),radius=3*S,outline=col,width=S)
                im=stabilize(im,(b*S,)*4,body)
        emit('T_Skin_'+n,im,b,'none' if n.startswith('Check_') else 'nine_slice',body_out,tc,
             role='v1 replacement; '+('focus overlay only' if overlay else 'ornament rim with flat text body'),
             widget='existing skin registry: '+n,sources=['B04'] if rich else ['B01'],
             content_su=content,focus_overlay=overlay,focus_outset_su=5 if overlay else 0,focus_visual_outset_su=4 if overlay else 0,focus_gap_su=2 if overlay else None,
             glyph_in_png=False,checkbox_runtime_glyph='hud-icons-v3/ui-check' if n=='Check_On' else None,
             recommended_min_su=old['working_sizes_su'][n][0])

def ring(which,nominal,pad=4,state='normal',portrait=False):
    src=source(which)
    if portrait:
        cx,cy,r=627,612,558
    else:cx,cy,r=627,622,555
    # Square crop retains true circle instead of fitting a non-square laurel bounding box.
    ext=round((nominal/2+pad)/(nominal/2)*r)
    crop=src.crop((cx-ext,cy-ext,cx+ext,cy+ext))
    out=crop.resize(((nominal+2*pad)*S,)*2,Image.Resampling.LANCZOS)
    out=tint(out,state)
    if state in ['active','hover']:
        alpha=out.getchannel('A');g=alpha.filter(ImageFilter.GaussianBlur((1.5 if state=='hover' else 2.5)*S))
        glow=Image.new('RGBA',out.size,'#FFC85D');glow.putalpha(g.point(lambda x:round(x*.65)))
        out=Image.alpha_composite(glow,out)
        # Clear the insert explicitly, including the blur: no tint over v3 icon or portrait.
        rr=(nominal*.375 if portrait else nominal*.39)*S
        mask=Image.new('L',out.size);ImageDraw.Draw(mask).ellipse((out.width/2-rr,out.height/2-rr,out.width/2+rr,out.height/2+rr),fill=255)
        a=ImageChops.subtract(out.getchannel('A'),mask);out.putalpha(a)
    return out

def cartouche(size,margins,body=NAVY,state='normal'):
    src=source('B05');bbox=src.getbbox();src=src.crop(bbox)
    # This source is used for end pieces only; central rails are straightened.
    w,h=[v*S for v in size];l,t,r,b=[v*S for v in margins]
    sh=src.height;end=min(src.width//3,round(sh*.85))
    out=Image.new('RGBA',(w,h))
    out.paste(src.crop((0,0,end,sh)).resize((l,h),Image.Resampling.LANCZOS),(0,0))
    out.paste(src.crop((src.width-end,0,src.width,sh)).resize((r,h),Image.Resampling.LANCZOS),(w-r,0))
    prof=src.crop((src.width//2,0,src.width//2+1,sh)).resize((1,h),Image.Resampling.LANCZOS)
    out.paste(prof.resize((w-l-r,h)),(l,0))
    boundary=out.getchannel('A').point(lambda x:255 if x>=48 else 0)
    fill=boundary.copy();ImageDraw.floodfill(fill,(w//2,h//2),255)
    interior=ImageChops.subtract(fill,boundary)
    bg=Image.new('RGBA',out.size,body);bg.putalpha(interior)
    out=Image.alpha_composite(bg,tint(out,state))
    return stabilize(out,(l,t,r,b),body,horizontal=True)

def glow_card(color,strength=1):
    size=(174*S,232*S);mask=Image.new('L',size);d=ImageDraw.Draw(mask)
    d.rounded_rectangle((10*S,10*S,164*S-1,222*S-1),radius=5*S,outline=255,width=2*S)
    soft=mask.filter(ImageFilter.GaussianBlur(3*S)).point(lambda x:min(255,round(x*strength*2)))
    q=Image.new('RGBA',size,color);q.putalpha(soft);solid=Image.new('RGBA',size,color);solid.putalpha(mask)
    q=Image.alpha_composite(q,solid)
    # Entire exact 150x208 insert is clear; card art never gets washed out.
    a=q.getchannel('A');ImageDraw.Draw(a).rectangle((12*S,12*S,162*S-1,220*S-1),fill=0);q.putalpha(a)
    return q

def b2():
    for nominal,suffix in [(80,''),(64,'_64')]:
        for state,ss in [('normal',''),('active','_Active')]:
            emit('T_Hud_PortraitFrame'+ss+suffix,ring('B02',nominal,4,state,True),0,'none',role='transparent portrait medallion',widget='own hero portrait' if nominal==80 else 'opponent hero portrait',sources=['B02'],nominal_diameter_su=nominal,insert_diameter_su=nominal*.75,canvas_outset_su=4)
    emit('T_Hud_SidekickRing',ring('B03',32,2),0,'none',role='transparent small portrait ring',widget='sidekick portrait',sources=['B03'],nominal_diameter_su=32,insert_diameter_su=25,canvas_outset_su=2)
    for state in ['Normal','Hover','Pressed','Disabled','Active']:
        emit('T_Hud_ActionRing_'+state,ring('B03',64,4,state.lower()),0,'none',role='transparent bezel outside v3 action disc',widget='action discs M/A/G/E',sources=['B03'],nominal_diameter_su=64,insert_diameter_su=50,canvas_outset_su=4)
    q=plain_frame((128,40),10,IVORY);d=ImageDraw.Draw(q)
    d.rounded_rectangle((8*S,8*S,32*S,32*S),radius=4*S,fill=NAVY,outline=GOLD,width=S)
    emit('T_Hud_HpPlate',q,[40,10,12,10],'horizontal',IVORY,NAVY,'HP body with empty heart slot','own/opponent HP value',heart_slot_su=[8,8,24,24])
    emit('T_Hud_StatusBanner',cartouche((256,56),[40,16,40,16]),[40,16,40,16],'horizontal',NAVY,LIGHT,'slim status cartouche with fixed meander ends','top centre status',sources=['B05'])
    emit('T_Hud_TurnPlate',plain_frame((128,44),12,IVORY,True),12,'nine_slice',IVORY,NAVY,'turn/menu plate','top-left turn and connectivity',sources=['B04'])
    emit('T_Hud_KeyBadge',plain_frame((26,26),4,NAVY),4,'nine_slice',NAVY,LIGHT,'hotkey insert, no letter','action hotkey M/A/G/E')
    q=plain_frame((256,56),20,NAVY,True)
    emit('T_Hud_HandTray',q,[24,20,24,20],'horizontal',NAVY,LIGHT,'low hand tray','resting hand background',sources=['B04'])
    for state,col,s in [('Hover','#FFD37C',1),('Selected','#72E4D7',1.8)]:
        emit('T_Hud_CardGlow_'+state,glow_card(col,s),0,'none',role='outer card halo, 150x208 exact clear insert',widget='hand card '+state.lower(),sources=['procedural Pillow outer halo'],insert_rect_su=[12,12,150,208],glow_color=col)
    emit('T_Hud_CardBackSlot',plain_frame((28,38),4,hole=True),4,'nine_slice',role='empty 24x34 opponent card-back surround',widget='each opponent hand card back',insert_rect_su=[2,2,24,34])
    emit('T_Hud_PileFrame',plain_frame((96,36),10,NAVY),10,'nine_slice',NAVY,LIGHT,'deck/discard chip surround','deck and discard counters')
    for side,col in [('Attack','#7F242C'),('Defense','#173F68')]:
        emit('T_Hud_CombatRibbon_'+side,cartouche((230,40),[28,12,28,12],col),[28,12,28,12],'horizontal',col,LIGHT,'red/blue combat cartouche','combat '+side.lower()+' header',sources=['B05'])
    emit('T_Hud_CombatFrame',plain_frame((250,342),16,rich=True,hole=True),16,'nine_slice',role='empty frame around a 230x322 card',widget='combat card display',sources=['B04'],insert_rect_su=[10,10,230,322])
    emit('T_Hud_VersusBadge',cartouche((160,48),[28,14,28,14]),[28,14,28,14],'horizontal',NAVY,LIGHT,'versus/result inset','combat score 3 : 1',sources=['B05'])
    for suffix,state in [('', 'normal'),('_Enemy','enemy')]:
        q=plain_frame((128,32),8,NAVY,state=state);d=ImageDraw.Draw(q)
        d.rounded_rectangle((7*S,7*S,25*S,25*S),radius=3*S,fill='#173F68' if suffix else '#463B20',outline='#6BA7C4' if suffix else GOLD,width=S//2)
        d.rectangle((31*S,24*S,113*S,26*S),fill='#172E36')
        emit('T_Hud_FighterPlate'+suffix,q,[29,12,14,8],'horizontal',NAVY,LIGHT,'empty digit slot and HP track; fill/text drawn at runtime','figure hover/selection plate',digit_slot_su=[7,7,18,18],hp_slot_su=[31,24,82,2])
    # Generated Greek-key strip. One native period, mirrored to a continuous periodic cell.
    src=source('B06');src=src.crop(src.getbbox())
    period=min(range(155,185),key=lambda k:float(np.mean(np.abs(np.array(src.crop((400,0,800,src.height)),dtype=float)-np.array(src.crop((400+k,0,800+k,src.height)),dtype=float)))))
    tile=src.crop((400,0,400+period,src.height)).resize((8*S,8*S),Image.Resampling.LANCZOS)
    a=np.array(tile);blend=S
    # Match the boundary with a smooth periodic blend, preserving the engraved middle.
    for k in range(blend):
        f=(blend-k)/blend/2
        x=a[:,k].astype(float);y=a[:,-1-k].astype(float)
        z=x*(1-f)+y*f;zz=y*(1-f)+x*f
        a[:,k]=z.round().astype('uint8');a[:,-1-k]=zz.round().astype('uint8')
    one=Image.fromarray(a);tile=Image.new('RGBA',(128*S,8*S))
    for x in range(0,128*S,8*S):tile.paste(one,(x,0))
    emit('T_Hud_Divider',tile,0,'tile_x',role='periodic Greek meander divider',widget='horizontal section divider',sources=['B06'])

def nine(im,size,m):
    w,h=size;sw,sh=im.size;l,t,r,b=m
    assert w>=l+r and h>=t+b,(size,m)
    out=Image.new('RGBA',size)
    xs=[0,l,sw-r,sw];ys=[0,t,sh-b,sh];xx=[0,l,w-r,w];yy=[0,t,h-b,h]
    for j in range(3):
        for i in range(3):
            tw,th=xx[i+1]-xx[i],yy[j+1]-yy[j]
            if tw and th:
                q=im.crop((xs[i],ys[j],xs[i+1],ys[j+1])).resize((tw,th),Image.Resampling.NEAREST)
                out.paste(q,(xx[i],yy[j]))
    return out

def load(name,scale=1):return Image.open(KIT/({1:'x1',2:'x2',4:'masters'}[scale])/(name+'.png')).convert('RGBA')
def render(name,size=None,scale=1):
    d=ASSETS[name];im=load(name,scale)
    if size is None:return im
    if d['stretch'] in ['nine_slice','horizontal']:return nine(im,size,[round(x*scale) for x in d['slice_su']])
    if d['stretch']=='tile_x':
        out=Image.new('RGBA',size)
        for x in range(0,size[0],im.width):out.alpha_composite(im,(x,0))
        return out
    return im.resize(size,Image.Resampling.LANCZOS)

def catalog():
    names=list(ASSETS);cellw,cellh=310,245;cols=4;rows=math.ceil(len(names)/cols)
    im=Image.new('RGB',(cols*cellw,rows*cellh),'#102332');d=ImageDraw.Draw(im)
    for i,n in enumerate(names):
        x=(i%cols)*cellw;y=(i//cols)*cellh
        d.rectangle((x,y,x+cellw-1,y+cellh-1),outline='#465765')
        short=n.replace('T_Skin_','Skin / ').replace('T_Hud_','HUD / ')
        text(im,(x+9,y+7),short,16)
        q=load(n);q.thumbnail((cellw//2-12,cellh-50),Image.Resampling.LANCZOS)
        for j,bg in enumerate([NAVY,'#E2DACD']):
            xx=x+j*cellw//2;d.rectangle((xx,y+32,xx+cellw//2-1,y+cellh-1),fill=bg)
            im.paste(q,(xx+(cellw//2-q.width)//2,y+42+(cellh-54-q.height)//2),q)
        text(im,(x+8,y+cellh-20),'x1 native or fitted / navy + marble',12,'#C6A15A')
    save(im,KIT/'catalog.png')

def review_pages():
    pages=[]
    # Each export is shown at EXACTLY 100%, twice, no thumbnailing.
    for scale in [1,2,4]:
        names=list(ASSETS);page=Image.new('RGB',(2200,1600),NAVY);y=42;page_n=1;placements=[]
        def flush():
            path=PRE/'review'/f'x{scale}-{page_n:02}.png';save(page,path)
            pages.append({'file':str(path.relative_to(ROOT)).replace('\\','/'),'scale':scale,'placements':placements.copy()})
        for n in names:
            q=load(n,scale);rh=q.height+36
            if y+rh>1600:
                flush();page_n+=1;page=Image.new('RGB',(2200,1600),NAVY);y=42;placements=[]
            d=ImageDraw.Draw(page)
            for j,bg in enumerate([NAVY,'#E2DACD']):
                x=j*1100;d.rectangle((x,y,x+1099,y+rh-1),fill=bg)
                text(page,(x+8,y+3),n+f' / x{scale} / 100%',18,LIGHT if j==0 else NAVY)
                page.paste(q,(x+20,y+29),q)
            placements.append({'name':n,'xy_navy':[20,y+29],'xy_light':[1120,y+29],'size':list(q.size)})
            y+=rh
        flush()
    write_json(PRE/'review/pages.json',pages)
    return pages

def build():
    b1();b2();assert len([n for n in ASSETS if n.startswith('T_Skin_')])==29
    write_json(KIT/'assets.json',ASSETS)
    slices={v['path']:{**v['slice_px'],'stretch':d['stretch']} for d in ASSETS.values() for v in d['files'].values()}
    write_json(ART/'slice-margins.json',{'unit':'physical px','order':['left','top','right','bottom'],'files':slices})
    write_json(KIT/'slice-margins.json',{'unit':'physical px','order':['left','top','right','bottom'],'files':slices})
    catalog();pages=review_pages()
    print(json.dumps({'assets':len(ASSETS),'exports':len(ASSETS)*3,'review_pages':len(pages)}))

if __name__=='__main__':build()
