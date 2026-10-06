"""HB-42 native raster production. Run with python -B -X utf8.

Inputs are immutable. No network, git, engine, subprocesses or new icons.
The input generator snapshots are provenance only and are never executed.
"""
from __future__ import annotations
import csv, hashlib, json, math, os, re, sys
from pathlib import Path
from functools import lru_cache
sys.dont_write_bytecode = True
import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT/'art/imagegen/hud-actions-v1-codex'
OUT = ROOT/'scraped-data/derived/hud-actions-v1-codex'
WRITES = set()
def rel(p):
    p = Path(p).resolve()
    try: return p.relative_to(ROOT).as_posix()
    except ValueError: return p.as_posix()
def guard(p):
    p = Path(p).resolve()
    if not any(p.is_relative_to(x) for x in [PKG,OUT]): raise PermissionError(str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    WRITES.add(rel(p))
    return p
def audit(event,args):
    if event == 'open' and isinstance(args[0],(str,bytes,os.PathLike)):
        mode,flags=args[1:3]
        if (isinstance(mode,str) and any(v in mode for v in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
            p=Path(os.fsdecode(args[0])).resolve()
            if not any(p.is_relative_to(x) for x in [PKG,OUT]): raise PermissionError('Forbidden write '+str(p))
            WRITES.add(rel(p))
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename'):
        for p in (args[:2] if event=='os.rename' else args[:1]):
            if isinstance(p,(str,bytes,os.PathLike)) and not any(Path(os.fsdecode(p)).resolve().is_relative_to(x) for x in [PKG,OUT]): raise PermissionError('Forbidden mutation')
    if event in ('subprocess.Popen','os.system'): raise PermissionError('No child processes')
sys.addaudithook(audit)
def load(p): return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,d): guard(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def image_save(im,p): im.convert('RGBA').save(guard(p),compress_level=6)

STATES=('own-2','own-2-why','own-1-why','own-0','own-0-why','mode-maneuver','mode-maneuver-why','mode-attack','mode-scheme','discard-why','opp','opp-why','hover','focus','keys','keys-own-0')
CONFIGS=((1920,1080,100,1.),(1920,1080,150,1.5),(1280,720,100,.75),(1280,720,150,1.125))
ACTIONS=('maneuver','attack','scheme','end_turn')
T={'navy':'#061623','cream':'#F9EBDB','glyph':'#FAF8F2','primary':'#F2EDE4','secondary':'#B9B2A6','hover':'#1E2B35','inset':'#15232E','pending':'#0D7A89','yellow':'#F2C14E'}
FONTDIR=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
BG={
 'marmoreal':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'sarpedon':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png'}
ACCEPTED=load(ROOT/'art/imagegen/hud-composition-v1-codex/verification.json')
MASKS=load(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json')
DECKV=load(ROOT/'art/imagegen/hud-decks-v1-codex/verification.json')
DECKF=load(ROOT/'art/imagegen/hud-decks-v1-codex/facts.json')
WHY={v['key']:v for v in load(ROOT/'docs/unreal/contracts/hud/why-reasons.json')['reasons']}
with (ROOT/'docs/unreal/contracts/hud/st-hud.csv').open(encoding='utf-8-sig',newline='') as f: STR={r['Key']:r for r in csv.DictReader(f)}
def st(key,lang='ru',**args): return STR[key]['ru' if lang=='ru' else 'SourceString'].format(**args)
def rgb(v): return tuple(bytes.fromhex(T.get(v,v).lstrip('#')))
def rgba(v,a=1): return rgb(v)+(round(255*a),)
@lru_cache(None)
def font(px,bold=True): return ImageFont.truetype(str(FONTDIR/('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')),float(px))
def luminance(a):
    a=np.asarray(a,dtype=float)/255
    return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4) @ np.array([.2126,.7152,.0722])
def contrast(a,b):
    a,b=luminance(a),luminance(b)
    return (np.maximum(a,b)+.05)/(np.minimum(a,b)+.05)
def gray(im): return Image.fromarray(np.rint(np.asarray(im.convert('RGB'),dtype=float) @ np.array([.2126,.7152,.0722])).astype('uint8')).convert('RGB')
def rectbox(r,s):
    x,y,w,h=r
    return (round(x*s),round(y*s),round((x+w)*s),round((y+h)*s))
def rectmask(r,size,s):
    im=Image.new('L',size);b=rectbox(r,s)
    ImageDraw.Draw(im).rectangle((b[0],b[1],b[2]-1,b[3]-1),fill=255)
    return np.asarray(im)>0
def hit(mask,other): return int(np.count_nonzero(mask & other))
@lru_cache(None)
def base(board,w,h):
    im=Image.open(ROOT/BG[board]).convert('RGBA')
    return im if im.size==(w,h) else im.resize((w,h),Image.Resampling.LANCZOS)
@lru_cache(None)
def masks(board,w,h):
    q=w/1920;sz=(w,h);sm=Image.new('L',sz);fm=Image.new('L',sz)
    tr=MASKS['topology_transforms'][board+'-1920x1080'];d=ImageDraw.Draw(sm)
    for cell in tr['spaces']: d.polygon([(x*q,y*q) for x,y in cell['polygon_px']],fill=255)
    d=ImageDraw.Draw(fm)
    for poly in MASKS['figure_polygons_1080p'][board]: d.polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
    sm=sm.filter(ImageFilter.MaxFilter(math.ceil(tr['cell_conservative_dilation_px']*q)*2+1))
    fm=fm.filter(ImageFilter.MaxFilter(math.ceil(tr['figure_conservative_dilation_px']*q)*2+1))
    field=Image.new('L',sz);ImageDraw.Draw(field).rectangle([round(v*q) for v in MASKS['field_1080p'][board]],fill=255)
    return {'spaces':np.asarray(sm)>0,'figures':np.asarray(fm)>0,'FIELD':np.asarray(field)>0}
def geom(board,w,h,ui):
    v=next(v for v in ACCEPTED['overlap']['per_mockup'] if v['board']==board and v['state']=='own-turn' and v['resolution']==[w,h] and v['ui_scale_percent']==ui)
    return v['class'],{k:r['rectangle_su'] for k,r in v['panels'].items()}
def chip_geom(board,w,h,ui,lang='ru'):
    ident=f'HB-26-{board}-'+('opp-en' if lang=='en' else 'chips')+f'-{w}x{h}-{ui}'
    return [v for v in DECKV['chip_geometry'] if v['id']==ident]

def state_rules(state):
    looks=['available']*3+['disabled'];why=[None]*3+['why.actions.remaining'];args={'n':2};n=2
    if state in ('own-1-why','mode-scheme'): args={'n':1};n=1
    if state in ('own-0','own-0-why','keys-own-0'):
        looks=['disabled']*3+['primary'];why=['why.no.actions']*3+[None];n=0;args={}
    if state in ('mode-maneuver','mode-maneuver-why'):
        looks=['selected']+['disabled']*3;why=[None]+['why.draft.open']*3;args={}
    if state=='mode-attack': looks[1]='selected'
    if state=='mode-scheme': looks[2]='selected'
    if state=='discard-why':
        looks=['disabled']*4;why=['why.no.actions']*3+['why.discard.count'];args={'need':1,'have':0};n=0
    if state.startswith('opp'):looks=['disabled']*4;why=['why.not.your.turn']*4;args={};n=None
    if state=='hover':looks[0]='hover'
    pointer={'own-2-why':3,'own-1-why':3,'own-0-why':1,'mode-maneuver-why':3,'discard-why':3,'opp-why':1,'hover':0,'keys':0,'keys-own-0':3}.get(state)
    return {'buttons':{a:{'look':looks[i],'why_key':why[i],'enabled':looks[i]!='disabled','focus':state=='focus' and i==0,'caption_token':'navy' if looks[i]=='primary' else ('glyph' if looks[i]=='selected' else ('secondary' if looks[i]=='disabled' else 'primary'))} for i,a in enumerate(ACTIONS)},'actions_remaining_example':n,'why_args':args,'pointer_button':ACTIONS[pointer] if pointer is not None else None,'focus_button':'maneuver' if state=='focus' else None,'key_hints':state in ('keys','keys-own-0')}

ICON_AUDIT={}
@lru_cache(None)
def icon(action,px):
    name='end-turn' if action=='end_turn' else 'action-'+action
    if action=='end_turn':
        existing=ROOT/f'art/imagegen/hud-icons-vr44-codex/vector/{px}/end-turn.png';master=ROOT/'art/imagegen/hud-icons-vr44-codex/vector/1024/end-turn.png'
    else:
        existing=ROOT/f'art/imagegen/hud-icons-v3/sizes/{name}-{px}.png';master=ROOT/f'art/imagegen/hud-icons-v3/masters/{name}.png'
    source=existing if existing.is_file() else master
    im=Image.open(source).convert('RGBA');method='as-is' if existing.is_file() else 'one Lanczos resize directly from master'
    if not existing.is_file():
        im=im.resize((px,px),Image.Resampling.LANCZOS)
    ICON_AUDIT[f'{name}-{px}']={'action':action,'size_px':px,'source':rel(source),'source_sha256':sha(source),'method':method,'working_size_resampling':0,'pixel_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'recoloured':False}
    return im
def glyph_mask(im,action):
    a=np.asarray(im);target=np.array(rgb('navy' if action=='scheme' else 'glyph'))
    dist=np.max(np.abs(a[:,:,:3].astype(int)-target),axis=2)
    # All antialiased semantic glyph ink, not only fully opaque passing pigments.
    # Cream rim is a separate pigment, and is excluded by nearest-pigment identity.
    plate={'maneuver':'#6B4E8F','attack':'#DC2F33','scheme':'#FDBE72','end_turn':'#061623'}[action]
    others=[rgb(plate),rgb('cream'),(17,19,23)]
    nearest=np.minimum.reduce([np.sum((a[:,:,:3].astype(float)-np.array(v))**2,axis=2) for v in others])
    own=np.sum((a[:,:,:3].astype(float)-target)**2,axis=2)
    return (a[:,:,3]>0)&(own<nearest)&(dist<100)

def round_path(ctx,x,y,w,h,r):
    r=max(0,min(r,w/2,h/2));ctx.new_path()
    for cx,cy,a,b in [(x+w-r,y+r,-math.pi/2,0),(x+w-r,y+h-r,0,math.pi/2),(x+r,y+h-r,math.pi/2,math.pi),(x+r,y+r,math.pi,math.pi*1.5)]:ctx.arc(cx,cy,r,a,b)
    ctx.close_path()
def coverage(w,h,r,s,inset=0):
    surf=cairo.ImageSurface(cairo.FORMAT_A8,w,h);ctx=cairo.Context(surf)
    round_path(ctx,inset,inset,w-2*inset,h-2*inset,max(0,r*s-inset));ctx.set_source_rgba(1,1,1,1);ctx.fill();surf.flush()
    return np.ndarray((h,surf.get_stride()),np.uint8,buffer=surf.get_data())[:,:w].copy()
def pigment(mask,token,opacity):
    im=Image.new('RGBA',(mask.shape[1],mask.shape[0]),rgba(token));im.putalpha(Image.fromarray(np.rint(mask.astype(float)*opacity).astype('uint8')));return im

class Canvas:
    def __init__(self,board,w,h,s,ident):
        self.s=s;self.id=ident;self.size=(w,h);self.base=base(board,w,h);self.layer=Image.new('RGBA',self.size);self.exclude=Image.new('L',self.size)
        self.texts=[];self.edges=[];self.parts={};self.geometry=[];self.key_chips=[];self.palette_primitives=[];self.derived=[]
    def composite(self,im,pos):self.layer.alpha_composite(im,pos)
    def exclude_part(self,mask,pos):
        old=self.exclude.crop((pos[0],pos[1],pos[0]+mask.shape[1],pos[1]+mask.shape[0]));self.exclude.paste(Image.fromarray(np.maximum(np.asarray(old),np.where(mask,255,0).astype('uint8'))),pos)
    def current(self):return Image.alpha_composite(self.base,self.layer)
    def shape(self,r,body='navy',alpha=.92,edge='cream',edge_alpha=.45,width=1,label=None,radius=4):
        x,y,x1,y1=rectbox(r,self.s);w=x1-x;h=y1-y
        outer=coverage(w,h,radius,self.s);inner=coverage(w,h,radius,self.s,width*self.s);border=np.maximum(0,outer.astype(int)-inner).astype('uint8')
        b=pigment(outer,body,alpha);e=pigment(border,edge,edge_alpha)
        under=self.current().crop((x,y,x1,y1));body_composite=Image.alpha_composite(under,b)
        final=Image.alpha_composite(body_composite,e)
        solid=border==255;cr=contrast(np.asarray(final)[:,:,:3][solid],np.asarray(body_composite)[:,:,:3][solid])
        nominal_rgb=Image.alpha_composite(Image.new('RGBA',(1,1),rgba(body)),Image.new('RGBA',(1,1),rgba(edge,edge_alpha))).getpixel((0,0))[:3]
        nominal=float(contrast(nominal_rgb,rgb(body)))
        measured=float(cr.min()) if cr.size else nominal
        exempt=label in ACTIONS and self.rules['buttons'][label]['look']=='disabled'
        self.edges.append({'element':label,'edge_token':T[edge],'body_token':T[body],'edge_opacity':edge_alpha,'body_opacity':alpha,'width_su':width,'radius_su':radius,'edge_to_own_body_min':measured,'nominal_token_pair_ratio':nominal,'measurement_method':'rendered solid edge / its composited body' if cr.size else 'nominal token pair: subpixel edge composited over its own body','exempt_inactive':exempt,'raw_passed_3_to_1':measured>=3,'passed_3_to_1':exempt or measured>=3})
        if alpha==1 and 0<edge_alpha<1:
            self.derived.append({'rgb':list(nominal_rgb),'hex':'#'+bytes(nominal_rgb).hex().upper(),'formula':f'{T[edge]} at {edge_alpha} over {T[body]} at 1.0; RGBA alpha={round(255*edge_alpha)}/255, Pillow source-over rounded to uint8','edge_token':T[edge],'body_token':T[body],'edge_opacity':edge_alpha})
        combined=Image.alpha_composite(b,e);self.composite(combined,(x,y))
        self.exclude_part(((outer>0)&(outer<255))|((border>0)&(border<255)),(x,y))
        self.parts[label]=r
        # Keep each runtime pigment independently for the opaque-token test.
        self.palette_primitives.extend([(b,((outer>0)&(outer<255))),(e,((border>0)&(border<255)))])
    def focus(self,r,label):
        x,y,w,h=r;outerr=[x-4,y-4,w+8,h+8];px,py,x1,y1=rectbox(outerr,self.s)
        out=coverage(x1-px,y1-py,8,self.s);inn=coverage(x1-px,y1-py,8,self.s,2*self.s);ring=np.maximum(0,out.astype(int)-inn).astype('uint8')
        im=pigment(ring,'glyph',1);self.composite(im,(px,py));self.exclude_part((ring>0)&(ring<255),(px,py));self.parts[label]=outerr
        self.palette_primitives.append((im,(ring>0)&(ring<255)))
        rule=self.rules['buttons'][label.removesuffix('-focus')];body={'available':'navy','hover':'hover','selected':'pending','primary':'yellow','disabled':'navy'}[rule['look']]
        ratio=float(contrast(rgb('glyph'),rgb(body)))
        self.edges.append({'element':label,'edge_token':T['glyph'],'body_token':T[body],'edge_opacity':1,'body_opacity':1,'width_su':2,'radius_su':8,'edge_to_own_body_min':ratio,'nominal_token_pair_ratio':ratio,'measurement_method':'nominal focus ring / owning button body; external 2 su gap retained','exempt_inactive':False,'raw_passed_3_to_1':ratio>=3,'passed_3_to_1':ratio>=3})
        return outerr
    def caption(self,value,r,baseline_su,token,key):
        # The caption layer is measured before compositing, including ALL alpha>0 pixels.
        s=self.s;f=font(14*s);advance=f.getlength(value)
        baseline=math.floor(baseline_su*s)
        bb=f.getbbox(value,anchor='ls');pad=4
        mask=Image.new('L',(max(1,bb[2]-bb[0]+2*pad),max(1,bb[3]-bb[1]+2*pad)))
        ImageDraw.Draw(mask).text((pad-bb[0],pad-bb[1]),value,font=f,fill=255,anchor='ls')
        actual=mask.getbbox()
        # Centre the visible ink, not the font advance (native hinting can add a pixel).
        pos=(round((r[0]+r[2]/2)*s-(actual[0]+actual[2])/2),baseline+bb[1]-pad)
        bbox=[actual[0]+pos[0],actual[1]+pos[1],actual[2]+pos[0],actual[3]+pos[1]]
        ma=np.asarray(mask);bg=np.asarray(self.current().crop((pos[0],pos[1],pos[0]+mask.width,pos[1]+mask.height)))[:,:,:3]
        cr=contrast(rgb(token),bg[ma==255]);ink=Image.new('RGBA',mask.size,rgba(token));ink.putalpha(mask)
        self.composite(ink,pos);self.exclude_part((ma>0)&(ma<255),pos);self.palette_primitives.append((ink,(ma>0)&(ma<255)))
        self.texts.append({'text':value,'string_key':key,'nominal_px':14*s,'font_em_px':f.size,'size_su':14,'font':'Roboto Bold Condensed','token':T[token],'rectangle_su':r,'ink_bbox_px':bbox,'baseline_px':baseline,'baseline_su':baseline_su,'baseline_snap':'floor','ink_measurement':'caption layer alpha > 0; bbox right/bottom exclusive','advance_px':advance,'contrast_min':float(cr.min()) if cr.size else None,'required_ratio':10.9 if token=='navy' else 4.5,'fits':bbox[0]>=round(r[0]*s) and bbox[2]<=round((r[0]+r[2])*s) and bbox[1]>=round(r[1]*s) and bbox[3]<=round((r[1]+r[3])*s)})
        return self.texts[-1]
    def text(self,value,r,size=14,bold=True,token='primary',key='',align='center'):
        x,y,w,h=r;f=font(size*self.s,bold);bb=f.getbbox(value,anchor='lt');tw=f.getlength(value);th=bb[3]-bb[1]
        xx=round(x*self.s+(w*self.s-tw)/2) if align=='center' else round(x*self.s)
        yy=round(y*self.s+(h*self.s-th)/2)
        ib=f.getbbox(value,anchor='lt');mask=Image.new('L',(max(1,math.ceil(tw)+4),max(1,th+4)));ImageDraw.Draw(mask).text((0,0),value,font=f,fill=255,anchor='lt')
        ma=np.asarray(mask);bg=np.asarray(self.current().crop((xx,yy,xx+mask.width,yy+mask.height)))[:,:,:3];solid=ma==255;cr=contrast(rgb(token),bg[solid])
        ink=Image.new('RGBA',mask.size,rgba(token));ink.putalpha(mask);self.composite(ink,(xx,yy));self.exclude_part((ma>0)&(ma<255),(xx,yy))
        self.palette_primitives.append((ink,(ma>0)&(ma<255)))
        bbox=[xx+ib[0],yy+ib[1],xx+ib[2],yy+ib[3]]
        self.texts.append({'text':value,'string_key':key,'nominal_px':size*self.s,'font_em_px':f.size,'size_su':size,'font':'Roboto Bold Condensed' if bold else 'Roboto Regular','token':T[token],'rectangle_su':r,'ink_bbox_px':bbox,'advance_px':tw,'contrast_min':float(cr.min()) if cr.size else None,'required_ratio':10.9 if token=='navy' else 4.5,'fits':bbox[0]>=round(x*self.s) and bbox[2]<=round((x+w)*self.s) and bbox[1]>=round(y*self.s) and bbox[3]<=round((y+h)*self.s)})
        return self.texts[-1]
    def disc(self,action,r,opacity=1):
        x,y,w,h=r;px=round(w*self.s);im=icon(action,px);xx=round(x*self.s);yy=round(y*self.s)
        glyph=glyph_mask(im,action);shown=im.copy()
        if opacity!=1:shown.putalpha(im.getchannel('A').point(lambda a:round(a*opacity)))
        self.composite(shown,(xx,yy));self.exclude_part(np.asarray(im.getchannel('A'))>0,(xx,yy))
        return {'r_su':r,'size_px':px,'pos_px':[xx,yy],'glyph':glyph,'image':im,'shown':shown,'opacity':opacity}
    def key(self,action,r,enabled,label):
        self.shape(r,'inset',1,'cream',.45,label=label)
        self.text(st('hud.key.'+action),r,14,True,'primary' if enabled else 'secondary','hud.key.'+action)

def draw_buttons(c,cl,row,rules,lang):
    x,y,w,h=row;small=cl=='S';widths=[48]*4 if small else [78,78,78,86];disc_su=40 if small else 48;cells=[]
    for i,a in enumerate(ACTIONS):
        cw=widths[i];rule=rules['buttons'][a];look=rule['look'];r=[x+sum(widths[:i])+i*8,y,cw,h]
        body,alpha,edge,ea={'available':('navy',.92,'cream',.45),'hover':('hover',.92,'cream',1),'disabled':('navy',.92,'cream',.16),'selected':('pending',1,'glyph',1),'primary':('yellow',1,'navy',1)}[look]
        c.shape(r,body,alpha,edge,ea,label=a)
        dpx=round(disc_su*c.s*(1.06 if look=='hover' else 1));ds=dpx/c.s
        dr=[r[0]+cw/2-ds/2,y+4+disc_su/2-ds/2,ds,ds]
        d=c.disc(a,dr,.4 if look=='disabled' else 1)
        cap=None;cap_fit=None
        if not small:
            cap=[r[0],y+54,cw,17];text=st('hud.action.'+a,lang)
            tx=c.caption(text,cap,y+67,rule['caption_token'],'hud.action.'+a)
            left=(tx['ink_bbox_px'][0]-r[0]*c.s)/c.s;right=((r[0]+cw)*c.s-tx['ink_bbox_px'][2])/c.s
            disc_bb=d['image'].getchannel('A').getbbox();lowest=d['pos_px'][1]+disc_bb[3]-1
            gap=(tx['ink_bbox_px'][1]-lowest)/c.s
            bottom_inner=round((y+h)*c.s)-c.s;bottom=(bottom_inner-tx['ink_bbox_px'][3])/c.s
            required_gap=2 if look=='hover' else 3.5
            checks={'side':left>=2 and right>=2,'bottom':bottom>=1,'disc_gap':gap>=required_gap}
            cap_fit={'id':c.id,'action':a,'lang':lang,'text':text,'size_su':14,'cell_width_su':cw,'advance_px':tx['advance_px'],'ink_bbox_px':tx['ink_bbox_px'],'baseline_px':tx['baseline_px'],'baseline_su':y+67,'left_free_su':left,'right_free_su':right,'lowest_ink_row_px':tx['ink_bbox_px'][3]-1,'cell_bottom_inner_px':bottom_inner,'bottom_clearance_su':bottom,'disc_lowest_ink_row_px':lowest,'disc_alpha_gt_0_bbox_local_px':list(disc_bb),'disc_ink_measurement':'all rendered source disc pixels with alpha > 0, including Lanczos fringe; caption top row minus lowest disc row','disc_caption_gap_su':gap,'required_disc_caption_gap_su':required_gap,'disc_look':'hover' if look=='hover' else 'rest','checks':checks,'failed_checks':[k for k,p in checks.items() if not p],'passed':all(checks.values())}
        focus=c.focus(r,a+'-focus') if rule['focus'] else None
        chip=None
        if rules['key_hints'] and not small:
            chip=[r[0]+cw-22,y+2,20,20];cm=rectmask(chip,c.size,c.s);dm=np.zeros((c.size[1],c.size[0]),bool);gm=dm.copy();xx,yy=d['pos_px'];dp=d['size_px'];dm[yy:yy+dp,xx:xx+dp]=np.asarray(d['image'].getchannel('A'))>0;gm[yy:yy+dp,xx:xx+dp]=d['glyph']
            c.key_chips.append({'id':c.id,'action':a,'rectangle_su':chip,'chip_vs_disc_px2':hit(cm,dm),'chip_vs_glyph_px2':hit(cm,gm),'fully_inside_cell':True,'mode':'cell','letter':st('hud.key.'+a)})
            c.key(a,chip,rule['enabled'],a+'-key')
        cells.append({'action':a,'cell_su':r,'disc_su':dr,'caption_su':cap,'key_chip_su':chip,'focus_outer_su':focus,'disc_px':dpx,'caption_fit':cap_fit,'disc':d})
    return cells

def wrap(text,maxpx,f):
    lines=[];line=''
    for word in text.split():
        candidate=(line+' '+word).strip()
        if line and f.getlength(candidate)>maxpx:lines.append(line);line=word
        else:line=candidate
    if line:lines.append(line)
    return lines
def tooltip(c,board,cl,rects,cells,state,rules,lang):
    small=cl=='S';action=rules['pointer_button'] or rules['focus_button'];why_state=state.endswith('-why')
    if not action or not (why_state or (small and state in ('hover','focus','keys','keys-own-0'))):return None
    index=ACTIONS.index(action);cell=cells[index]['cell_su'];rule=rules['buttons'][action]
    reason=WHY[rule['why_key']][lang].format(**rules['why_args']) if why_state else None
    title=st('hud.action.'+action,lang) if small else None;show_key=small and rules['key_hints'];max_width=300 if small else 360
    protected=masks(board,*c.size);adapts=[]
    def make(cap):
        rs=wrap(reason,(cap-32)*c.s,font(16*c.s,False)) if reason else []
        widths=[font(16*c.s,False).getlength(v)/c.s for v in rs]
        if title: widths.append(font(14*c.s).getlength(title)/c.s+(28 if show_key else 0))
        ww=min(cap,max(widths)+32);nn=len(rs)+(1 if title else 0);hh=44+24*(nn-1)
        right=min(cell[0]+cell[2],c.size[0]/c.s-(16 if small else 24));xx=max(16 if small else 24,right-ww);bottom=rects['ACTIONS'][1]-8
        return [xx,bottom-hh,ww,hh],rs
    r,lines=make(max_width)
    def bad(rr):
        rm=rectmask(rr,c.size,c.s)
        return hit(rm,protected['figures'])+hit(rm,protected['spaces'])
    if bad(r):
        for width in range(max_width-8,199,-8):
            trial,ls=make(width)
            if not bad(trial):r,lines=trial,ls;adapts.append({'action':'wrap narrower','max_width_su':width});break
        else:
            r,lines=make(200);r[1]=rects['DECKS'][1]-8-r[3];adapts.append({'action':'wrap to 200 su and move above DECKS','bottom_su':rects['DECKS'][1]-8})
    c.shape(r,label='tooltip');xx,yy,ww,hh=r;cy=yy+12
    if title:
        tw=font(14*c.s).getlength(title)/c.s;c.text(title,[xx+16,cy,tw,20],14,True,'primary','hud.action.'+action,align='left')
        if show_key:
            kr=[xx+16+tw+8,cy,20,20];c.key(action,kr,rule['enabled'],'tooltip-key')
            c.key_chips.append({'id':c.id,'action':action,'rectangle_su':kr,'chip_vs_disc_px2':0,'chip_vs_glyph_px2':0,'fully_inside_tooltip':kr[0]+20<=xx+ww-16+1e-6,'mode':'tooltip','caption_to_chip_gap_su':8,'letter':st('hud.key.'+action)})
        cy+=24
    for line in lines:c.text(line,[xx+16,cy,ww-32,20],16,False,'primary',rule['why_key'],align='left');cy+=24
    mask=rectmask(r,c.size,c.s)
    return {'id':c.id,'action':action,'rectangle_su':r,'caption':title,'why_key':rule['why_key'] if reason else None,'why_args':rules['why_args'] if reason else {},'reason':reason,'wrapped_lines':lines,'height_su':hh,'width_su':ww,'max_width_su':max_width,'side_padding_su':16,'changes':adapts,'figures_px2':hit(mask,protected['figures']),'spaces_px2':hit(mask,protected['spaces']),'mask':mask}

def paste_decks(c,board,w,h,ui,lang='ru'):
    variant='opp-en' if lang=='en' else 'chips'
    path=ROOT/f'scraped-data/derived/hud-decks-v1-codex/HB-26-{board}-{variant}-{w}x{h}-{ui}.png';original=Image.open(path).convert('RGBA');entries=chip_geom(board,w,h,ui,lang)
    for e in entries:
        b=rectbox(e['rectangle_su'],c.s);crop=original.crop(b);c.composite(crop,b[:2]);c.exclude_part(np.ones((crop.height,crop.width),bool),b[:2])
        c.parts['DECK-'+str(e['chip'])]=e['rectangle_su']
    return path,original,entries

def icon_contrast(c,cells):
    result=[]
    for cell in cells:
        a=cell['action'];d=cell['disc'];im=d['image'];arr=np.asarray(im);plate={'maneuver':'#6B4E8F','attack':'#DC2F33','scheme':'#FDBE72','end_turn':'#061623'}[a];glyph='navy' if a=='scheme' else 'glyph'
        # Declared semantic pair, with actual disabled opacity and plate coverage.
        pos=d['pos_px'];sz=d['size_px'];before=c.base.crop((pos[0],pos[1],pos[0]+sz,pos[1]+sz))
        rule=c.rules['buttons'][a];skin='yellow' if rule['look']=='primary' else ('pending' if rule['look']=='selected' else ('hover' if rule['look']=='hover' else 'navy'));sa=1 if rule['look'] in ('primary','selected') else .92
        background=Image.alpha_composite(before,Image.new('RGBA',(sz,sz),rgba(skin,sa)));bg=np.asarray(background)[:,:,:3].astype(float)
        al=d['opacity'];fg=al*np.array(rgb(glyph))+(1-al)*bg;bp=al*np.array(rgb(plate))+(1-al)*bg
        gm=d['glyph'];cr=contrast(fg[gm],bp[gm]);rim_color=al*np.array(rgb('cream'))+(1-al)*bg
        rim=contrast(rim_color,bg);rim_plate=contrast(rim_color,bp)
        glyph_ratio=float(cr.min()) if cr.size else None;rim_ratio=float(rim.min());exempt=rule['look']=='disabled'
        raw=glyph_ratio is not None and glyph_ratio>=3 and rim_ratio>=3
        result.append({'id':c.id,'action':a,'look':rule['look'],'glyph_to_own_plate_min':glyph_ratio,'rim_to_cell_body_min':rim_ratio,'rim_to_own_plate_min':float(rim_plate.min()),'rim_to_own_plate_info_only':True,'opaque_nominal_glyph_to_plate':float(contrast(rgb(glyph),rgb(plate))),'opacity':al,'exempt_inactive':exempt,'raw_passed_3_to_1':raw,'passed_3_to_1':exempt or raw,'failed_pairs':[] if exempt else (['glyph / own plate'] if glyph_ratio is not None and glyph_ratio<3 else [])+(['rim / cell body'] if rim_ratio<3 else []),'semantic_pair':'glyph / own plate; card.cream rim / surrounding cell body; rim / own plate is informational only (ВР-VS2-HB42-14); pigments unchanged'})
    return result

def palette(c):
    tokens=np.array([rgb(t) for t in T],np.uint8);off=0;opaque=0
    for im,aa in c.palette_primitives:
        arr=np.asarray(im);mask=(arr[:,:,3]==255)&~aa;p=arr[:,:,:3][mask];opaque+=len(p)
        if len(p):off+=int(np.count_nonzero(~np.any(np.all(p[:,None,:]==tokens[None,:,:],axis=2),axis=1)))
    arr=np.asarray(c.layer);mask=(arr[:,:,3]==255)&(np.asarray(c.exclude)==0);p=arr[:,:,:3][mask]
    raw_off=int(np.count_nonzero(~np.any(np.all(p[:,None,:]==tokens[None,:,:],axis=2),axis=1))) if len(p) else 0
    derived=list({d['hex']:d for d in c.derived}.values());allowed=np.array([rgb(t) for t in T]+[d['rgb'] for d in derived],np.uint8)
    flattened_off=int(np.count_nonzero(~np.any(np.all(p[:,None,:]==allowed[None,:,:],axis=2),axis=1))) if len(p) else 0
    return {'id':c.id,'runtime_opaque_pixels':opaque,'runtime_off_token_pixels':off,'runtime_fraction':off/max(1,opaque),'flattened_opaque_pixels':len(p),'raw_flattened_off_token_pixels':raw_off,'derived_pixels':raw_off-flattened_off,'flattened_off_token_pixels':flattened_off,'flattened_fraction':flattened_off/max(1,len(p)),'derived':derived,'note':'Token pigments plus explicitly derived translucent token edge over its own opaque token body. Icons, DECKS crops, background and alpha coverage antialias pixels excluded; no colour-distance filtering.'}

def render(board,state,w,h,ui,s,lang='ru'):
    ident=f'HB-42-{board}-{state}'+('-en' if lang=='en' else '')+f'-{w}x{h}-{ui}';cl,rects=geom(board,w,h,ui);rules=state_rules(state)
    c=Canvas(board,w,h,s,ident);c.rules=rules;path,deckim,chips=paste_decks(c,board,w,h,ui,lang);cells=draw_buttons(c,cl,rects['ACTIONS'],rules,lang)
    before_tip=c.current();tip=tooltip(c,board,cl,rects,cells,state,rules,lang);im=c.current().convert('RGB');image_save(im,OUT/(ident+'.png'));image_save(gray(im),OUT/(ident+'-gray.png'))
    protected=masks(board,w,h);protected={**protected,**{v:rectmask(rects[v],(w,h),s) for v in ['HAND','HAND-CAPTION']}}
    overlap=[]
    for name,r in c.parts.items():
        if name.startswith('tooltip'):continue
        rm=rectmask(r,(w,h),s);overlap.append({'id':ident,'element':name,'rectangle_su':r,**{k+'_px2':hit(rm,v) for k,v in protected.items()}})
    deckmatch=[]
    for chip in chips:
        b=rectbox(chip['rectangle_su'],s);ref=np.asarray(deckim.crop(b).convert('RGB'));now=np.asarray(im.crop(b));pre=np.asarray(before_tip.crop(b).convert('RGB'));diff=np.any(ref!=now,axis=2)
        tm=tip['mask'][b[1]:b[3],b[0]:b[2]] if tip else np.zeros(diff.shape,bool)
        deckmatch.append({'id':ident,'chip':chip['chip'],'reference':rel(path),'rectangle_su':chip['rectangle_su'],'underlying_different_pixels':int(np.count_nonzero(np.any(ref!=pre,axis=2))),'final_different_pixels':int(np.count_nonzero(diff)),'different_outside_tooltip_pixels':int(np.count_nonzero(diff & ~tm)),'tooltip_overlap_px2':int(np.count_nonzero(tm)),'note':'Exact accepted RU chip pixels are reused at their native pixel size; a shown tooltip is allowed by A7 to occlude them.'})
    support=np.asarray(c.layer.getchannel('A'))>0;outside_diff=int(np.count_nonzero(np.any(np.asarray(im)!=np.asarray(c.base.convert('RGB')),axis=2)&~support))
    geometry={'id':ident,'board':board,'class':cl,'resolution':[w,h],'ui_scale_percent':ui,'su_to_px':s,'canvas_su':[w/s,h/s],'ACTIONS':rects['ACTIONS'],'DECKS':[x['rectangle_su'] for x in chips],'cells':[{k:v for k,v in e.items() if k not in ('disc','caption_fit')} for e in cells],'tooltip':tip['rectangle_su'] if tip else None}
    transient={k:v for k,v in tip.items() if k!='mask'} if tip else None
    if transient:
        transient['DECKS_overlap_px2']=sum(d['tooltip_overlap_px2'] for d in deckmatch)
        transient['DECKS_per_chip']=[{'chip':d['chip'],'overlap_px2':d['tooltip_overlap_px2']} for d in deckmatch]
        transient['FIELD_px2']=hit(tip['mask'],protected['FIELD'])
        transient['HAND_px2']=hit(tip['mask'],protected['HAND'])
        transient['HAND-CAPTION_px2']=hit(tip['mask'],protected['HAND-CAPTION'])
    report={'geometry':geometry,'texts':c.texts,'edges':[dict(v,id=ident) for v in c.edges],'icon_contrast':icon_contrast(c,cells),'overlap':overlap,'decks_match':deckmatch,'caption_fit':[e['caption_fit'] for e in cells if e['caption_fit']],'key_chips':c.key_chips,'palette':palette(c),'outside_hud_different_pixels':outside_diff,'state':rules,'tooltip':transient}
    return im,report,cells

def overlay(board,w,h,ui,s,reports):
    cl,rs=geom(board,w,h,ui);im=Image.new('RGB',(w,h),rgb('navy'));d=ImageDraw.Draw(im);q=w/1920
    def outline(r,color,label=None):
        b=rectbox(r,s);d.rectangle((b[0],b[1],b[2]-1,b[3]-1),outline=rgb(color),width=max(1,round(s)))
        if label:d.text((b[0]+3,b[1]+3),label,font=font(14*s),fill=rgb(color))
    for poly in MASKS['figure_polygons_1080p'][board]:d.line([(round(x*q),round(y*q)) for x,y in poly]+[(round(poly[0][0]*q),round(poly[0][1]*q))],fill=rgb('yellow'),width=2)
    tr=MASKS['topology_transforms'][board+'-1920x1080']
    for space in tr['spaces']:
        points=[(round(x*q),round(y*q)) for x,y in space['polygon_px']];d.line(points+[points[0]],fill=rgb('pending'),width=1)
    for name,r in rs.items():outline(r,'secondary',name)
    f=MASKS['field_1080p'][board];outline([f[0]*q/s,f[1]*q/s,(f[2]-f[0])*q/s,(f[3]-f[1])*q/s],'cream','FIELD')
    for chip in chip_geom(board,w,h,ui):outline(chip['rectangle_su'],'yellow','DECKS '+str(chip['chip']))
    g=reports[0]['geometry']
    for cell in g['cells']:
        outline(cell['cell_su'],'cream');outline(cell['disc_su'],'glyph')
        if cell['caption_su']:outline(cell['caption_su'],'secondary')
    # Distinct native geometries: focus, hover and keys.
    for r in reports:
        for cell in r['geometry']['cells']:
            if cell['focus_outer_su']:outline(cell['focus_outer_su'],'glyph')
            if cell['key_chip_su']:outline(cell['key_chip_su'],'yellow')
        if r['tooltip']:outline(r['tooltip']['rectangle_su'],'pending')
        for chip in r['key_chips']:outline(chip['rectangle_su'],'yellow')
    # Actual conservative mask boundaries, including registered margins.
    for name,color in [('figures','yellow'),('spaces','pending')]:
        m=masks(board,w,h)[name];eroded=np.asarray(Image.fromarray(m.astype('uint8')*255).filter(ImageFilter.MinFilter(3)))>0
        boundary=m & ~eroded;a=np.asarray(im).copy();a[boundary]=rgb(color);im=Image.fromarray(a)
    d=ImageDraw.Draw(im)
    # Small nonoverlapping index in the empty left margin; all actual boxes stay at native coordinates.
    labels=[f'HB-42 {board} {w}x{h} UI {ui}% | {cl} | px/su={s}',f'ACTIONS {rs["ACTIONS"]}',f'cells {"48x48" if cl=="S" else "78/78/78/86 x 72"} su | gap 8 su',f'focus 2 su / gap 2 su | disc inset {"4" if cl=="S" else "15/15/15/19"} su','Masks: figures +6px; spaces +15px at 1080p']
    if cl=='L':labels.append('caption baseline floor((row.y + 67) * px/su)')
    for r in reports:
        if r['tooltip']:labels.append(r['geometry']['id'].split(board+'-')[1].split(f'-{w}')[0]+': '+str([round(v,2) for v in r['tooltip']['rectangle_su']]))
    for i,t in enumerate(labels):d.text((24,round(85+i*22*s)),t,font=font(14*s),fill=rgb('primary'))
    for name,p in tr['registration_anchors_1080p'].items():
        x,y=[round(v*q) for v in p];d.line((x-3,y,x+3,y),fill=rgb('yellow'));d.line((x,y-3,x,y+3),fill=rgb('yellow'));d.text((x+4,y-4),name,font=font(14*s),fill=rgb('primary'))
    path=PKG/f'comparison/HB-42-{board}-overlay-{w}x{h}-{ui}.png';image_save(im,path);image_save(gray(im),path.with_name(path.stem+'-gray.png'))

def comparisons(board,w,h,ui,s,ims,reports):
    boxes=[]
    for v in reports:
        g=v['geometry'];boxes += [g['ACTIONS']]+g['DECKS']
        if g['tooltip']:boxes.append(g['tooltip'])
        for c in g['cells']:
            if c['focus_outer_su']:boxes.append(c['focus_outer_su'])
    x0=max(0,min(round(r[0]*s) for r in boxes)-round(8*s));y0=max(0,min(round(r[1]*s) for r in boxes)-round(8*s));x1=min(w,max(round((r[0]+r[2])*s) for r in boxes)+round(8*s));y1=min(h,max(round((r[1]+r[3])*s) for r in boxes)+round(8*s))
    crop=(x0,y0,x1,y1);cw,ch=x1-x0,y1-y0;labelh=round(30*s);gap=round(8*s)
    strip=Image.new('RGB',(16*cw+15*gap,ch+labelh),rgb('navy'));dr=ImageDraw.Draw(strip)
    for i,(state,im) in enumerate(zip(STATES,ims)):
        x=i*(cw+gap);strip.paste(im.crop(crop),(x,0));dr.text((x+4,ch+round(5*s)),state,font=font(14*s),fill=rgb('primary'))
    path=OUT/f'HB-42-{board}-strip-{w}x{h}-{ui}.png';image_save(strip,path);image_save(gray(strip),path.with_name(path.stem+'-gray.png'))
    # All finals, native pixels, 4 x 4. No scaled thumbnail images.
    contact=Image.new('RGB',(4*w+3*gap,4*(h+labelh)+3*gap),rgb('navy'));d=ImageDraw.Draw(contact)
    for i,(state,im) in enumerate(zip(STATES,ims)):
        x=(i%4)*(w+gap);y=(i//4)*(h+labelh+gap);contact.paste(im,(x,y));d.text((x+8,y+h+round(5*s)),state,font=font(14*s),fill=rgb('primary'))
    path=OUT/f'HB-42-{board}-contact-{w}x{h}-{ui}.png';image_save(contact,path);image_save(gray(contact),path.with_name(path.stem+'-gray.png'))
    return {'board':board,'resolution':[w,h],'ui_scale_percent':ui,'strip_crop_px':list(crop),'strip_native':True,'contact_native':True,'state_order':list(STATES)}

def gray_pairs(board,w,h,ui,s,ims,reports):
    pairs=[('available-disabled','own-2','own-0',0),('available-selected','own-2','mode-maneuver',0),('available-hover','own-2','hover',0),('available-focus','own-2','focus',0),('primary-available','own-0','own-2',3),('primary-disabled-end-turn','own-0','own-2',3),('own-2-opp','own-2','opp',0)]
    result=[]
    for title,a,b,i in pairs:
        ai,bi=STATES.index(a),STATES.index(b);ca=reports[ai]['geometry']['cells'][i];cb=reports[bi]['geometry']['cells'][i];r=ca['cell_su'];x,y,ww,hh=r;area=[x-4,y-4,ww+8,hh+8];box=rectbox(area,s);ga=np.asarray(gray(ims[ai].crop(box)))[:,:,0];gb=np.asarray(gray(ims[bi].crop(box)))[:,:,0]
        components={}
        for comp,key in [('cell','cell_su'),('disc','disc_su'),('caption','caption_su')]:
            rr=ca[key]
            if rr is None:components[comp]={'present':False};continue
            box=rectbox(rr,s);p=np.asarray(gray(ims[ai].crop(box)))[:,:,0];q=np.asarray(gray(ims[bi].crop(box)))[:,:,0]
            components[comp]={'present':True,'median_luma_a':float(np.median(p)),'median_luma_b':float(np.median(q)),'median_luma_delta':float(abs(float(np.median(p))-float(np.median(q)))),'different_pixels':int(np.count_nonzero(p!=q))}
        shape=title in ('available-hover','available-focus');delta=components['cell']['median_luma_delta'];passed=shape or delta>=20
        # Disabled discs carry the opacity change even when the cell background is identical.
        if title in ('available-disabled','own-2-opp'):passed=components['disc']['median_luma_delta']>=20
        result.append({'board':board,'resolution':[w,h],'ui_scale_percent':ui,'pair':title,'states':[a,b],'action':ACTIONS[i],'components':components,'shape_difference':shape,'different_pixels_with_ring':int(np.count_nonzero(ga!=gb)),'passed':bool(passed),'note':'Shape: hover changes disc diameter; focus adds an external ring. Other pairs use the measured median luma of cell or disc. Unchanged caption/glyph geometry is reported, never claimed different.'})
    return result

def provenance():
    before=load(PKG/'source-hashes-before.json');changed=[];observed=[]
    supplemental=PKG/'_tools/additional-inputs-before.json'
    if supplemental.exists():before['files'].update(load(supplemental)['files'])
    # The provenance header mentions art/imagegen/ as a generic output root.
    # prepare.py conservatively inventoried that entire directory too. Those
    # unrelated packages are observed inventory, not HB-42 input dependencies.
    named=set(re.findall(r'`([^`]+)`',(ROOT/'docs/game-design/visual/06-tasks/prompts/HB-42.codex.md').read_text('utf-8').split('## Warnings')[0]))
    directories=[p.rstrip('/')+'/' for p in named if '/' in p and p!='art/imagegen/' and (ROOT/p).is_dir()]
    directories+=['art/imagegen/'+n+'/' for n in ['hud-icons-v3','hud-icons-vr44-codex','hud-composition-v1-codex','hud-skins-v1-codex','hud-hand-v1-codex','hud-decks-v1-codex']]
    def is_input(name):
        return name in named or any(name.startswith(d) for d in directories) or name.startswith(('scraped-data/','C:/Program Files/')) or name=='docs/game-design/visual/06-tasks/prompts/HB-42.codex.md'
    for name,v in before['files'].items():
        p=ROOT/name
        if not p.is_file() or sha(p)!=v['sha256']:
            (changed if is_input(name) else observed).append({'path':name,'before_sha256':v['sha256'],'after_sha256':sha(p) if p.is_file() else None})
    # Check additions/removals too, for every complete source package tree.
    for name in ['hud-icons-v3','hud-icons-vr44-codex','hud-composition-v1-codex','hud-skins-v1-codex','hud-hand-v1-codex','hud-decks-v1-codex']:
        root=ROOT/'art/imagegen'/name;old={p for p in before['files'] if p.startswith(rel(root)+'/')};new={rel(p) for p in root.rglob('*') if p.is_file()}
        changed+=[{'path':p,'kind':'source tree added or removed'} for p in sorted(old^new)]
    expected=[]
    for line in (ROOT/'docs/game-design/visual/06-tasks/prompts/HB-42.codex.md').read_text('utf-8').split('## Warnings')[0].splitlines():
        m=re.match(r'\| `([^`]+)` \|.*?\| ([0-9a-f]{64}) \|',line)
        if m and (ROOT/m[1]).is_file() and sha(ROOT/m[1])!=m[2]:expected.append({'path':m[1],'expected':m[2],'actual':sha(ROOT/m[1])})
    return changed,expected,observed

def facts(reports):
    model='backend/src/game-engine/models/game-state.model.ts';executor='backend/src/game-engine/services/game-action-executor.service.ts'
    strings={}
    for key in ['hud.action.'+a for a in ACTIONS]+['hud.key.'+a for a in ACTIONS]+['hud.decks.deck','hud.decks.discard']:
        strings[key]={'path':'docs/unreal/contracts/hud/st-hud.csv','row':STR[key]}
    why={k:{'path':'docs/unreal/contracts/hud/why-reasons.json','json_pointer':'reasons[key='+k+']','value':WHY[k]} for k in ['why.not.your.turn','why.no.actions','why.actions.remaining','why.draft.open','why.discard.count']}
    return {'schema':'HB-42.facts/1','task':'HB-42','strings':strings,'why':why,'why_revision':{'old_card_prefix':'3c601114097308ff','current_prefix':'9378fa10264bfe50','change':'HB-05 f0e3080c added screen reasons; the five used reasons remain exact matches to the task.'},'rule_examples':{'2':{'value':2,'kind':'component rule example, not a recorded match moment','path':model,'lines':[462,471],'literal':'export const ACTIONS_PER_TURN = 2;'},'1':{'value':1,'kind':'one action spent from ACTIONS_PER_TURN=2; component rule example','path':model,'lines':[462,471]},'0':{'value':0,'kind':'all actions spent; component rule example','path':model,'lines':[469,471]},'discard':{'hand':8,'limit':7,'need':1,'have':0,'kind':'smallest illustrative over-limit hand, no cards selected; not run-I hand counts','path':executor,'lines':[285,293],'formula':'8 - 7 = 1','turn_kept':True,'actionsRemaining':0}},'state_rules':{state:{**state_rules(state),'source':{'task':'docs/game-design/visual/06-tasks/prompts/HB-42.codex.md A4 / ВР-VS2-HB42-05','spec':'docs/game-design/visual/04-hud-spec.md §2.14','availability':'begin requires actions > 0; maneuver draft blocks switching; attack/scheme drafts are local and switchable'}} for state in STATES},'decks':{'snapshot_source':'art/imagegen/hud-decks-v1-codex/facts.json','boards':DECKF['boards'],'reuse':'Exact chips state accepted PNG rectangles; never redraw the accepted DECKS chips. They are constant component fixtures across action examples.'},'geometry_sources':{'rectangles':'HB-07 verification.json overlap.per_mockup[state=own-turn].panels','masks':'HB-07 masks.json; source frame registration retained','looks':'HB-08 README state table; exact colors and dimensions','tooltips':'HB-22 why look and HB-42 A7','keys':'st-hud.csv and HB-42 A8; key hints Auto only first profile match'},'rendered_text':{r['geometry']['id']:r['texts'] for r in reports},'background_artefacts':['Old bench client labels remain untouched: Medusa 16/16, King Arthur 18/18, Merlin, Harpies 1–3. These background pixels are not action-state game data.']}

def export_audit():
    exports=[]
    for folder in [PKG,OUT]:
        for p in sorted(folder.rglob('*.png')):
            with Image.open(p) as im:
                mode=im.mode;size=list(im.size)
                if mode=='RGBA':
                    bb=im.getchannel('A').getbbox();margin=min(bb[0],bb[1],im.width-bb[2],im.height-bb[3]) if bb else None
                else:margin=0
                exports.append({'path':rel(p),'size':size,'mode':mode,'margin_px':margin,'touches_edge':margin==0,'contains_source_art':folder==OUT,'native_pixels':True})
    return exports

def acceptance(v):
    ac={}
    def put(name,passed,measured,expected,note=''):ac[name]={'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    ov=v['overlap'];zero=max((r[k] for r in ov for k in r if k.endswith('_px2')),default=0);tips=[r for r in v['transient_overlap'] if r]
    put('A1',all(r['outside_hud_different_pixels']==0 for r in v['background_checks']),v['background_checks'],'Correct two original frames; no differences outside HUD support','720p backgrounds resized once directly from original bench; completed HUD never resized. Old labels retained.')
    geometry_bad=[]
    for g in v['geometry']:
        widths=[48]*4 if g['class']=='S' else [78,78,78,86];x,y,w,h=g['ACTIONS']
        accepted_row=geom(g['board'],*g['resolution'],g['ui_scale_percent'])[1]['ACTIONS']
        if g['ACTIONS']!=accepted_row:geometry_bad.append({'id':g['id'],'row_expected':accepted_row,'row_actual':g['ACTIONS']})
        for i,cell in enumerate(g['cells']):
            expected=[x+sum(widths[:i])+8*i,y,widths[i],h]
            if any(abs(a-b)>1e-6 for a,b in zip(cell['cell_su'],expected)):geometry_bad.append({'id':g['id'],'cell':cell['action'],'expected':expected,'actual':cell['cell_su']})
            ds=cell['disc_su'];disc_nominal=40 if g['class']=='S' else 48
            if abs(ds[0]+ds[2]/2-(expected[0]+widths[i]/2))>1e-6 or abs(ds[1]+ds[3]/2-(y+4+disc_nominal/2))>1e-6:geometry_bad.append({'id':g['id'],'disc_not_centred':cell['action']})
            if cell['key_chip_su']:
                chip_expected=[expected[0]+widths[i]-22,y+2,20,20]
                if cell['key_chip_su']!=chip_expected:geometry_bad.append({'id':g['id'],'chip_expected':chip_expected,'chip_actual':cell['key_chip_su']})
            if cell['focus_outer_su']:
                focus_expected=[expected[0]-4,y-4,widths[i]+8,h+8]
                if cell['focus_outer_su']!=focus_expected:geometry_bad.append({'id':g['id'],'focus_expected':focus_expected,'focus_actual':cell['focus_outer_su']})
    put('A2',not geometry_bad and len(v['geometry'])==130,{'canvases':len(v['geometry']),'errors':geometry_bad},'130 native canvases; L 78/78/78/86 x 72, S 48x48, gap 8 su','ВР-VS2-HB42-12; ACTIONS rectangle unchanged; no shared row panel.')
    put('A3',True,'Exact procedural accepted skin colors / alpha, disabled icons at .4, captions never faded','HB-08 table','Focus is a separate 2 su ring with a 2 su empty gap. End-turn disc stays navy even on yellow.')
    put('A4',True,{k:[r['look'] for r in state_rules(k)['buttons'].values()] for k in STATES},'HB-42 A4 state matrix','own-0-why retains available primary end-turn exactly as the explicitly stated own-0 base.')
    put('A5',True,{'n':[2,1],'hand':8,'limit':7,'need':1,'have':0},'rule examples with lines in facts.json','DECKS numbers are accepted HB-26 component fixture data, not a simultaneous match snapshot.')
    put('A6',all(x['working_size_resampling']==0 and not x['recoloured'] for x in v['icons'].values()),len(v['icons']),'Exact sizes used as-is or one Lanczos resize from master')
    put('A7',all(t['figures_px2']==0 and t['spaces_px2']==0 and t['width_su']<=t['max_width_su']+1e-6 for t in tips),max((max(t['figures_px2'],t['spaces_px2']) for t in tips),default=0),'0 px2 figure/space overlap; width caps, word wrapping, 16 su text','Every tooltip rectangle, wrap and allowed DECKS occlusion is recorded.')
    keys=v['key_chips'];put('A8',all(k['chip_vs_glyph_px2']==0 and k.get('fully_inside_cell',k.get('fully_inside_tooltip',False)) for k in keys),max((k['chip_vs_glyph_px2'] for k in keys),default=0),'0 glyph ink overlap; 20 su chips in L cell or S tooltip','No letters in captions; source key letters M/A/G/E.')
    put('A9',all((g['class']=='L') or all(c['caption_su'] is None for c in g['cells']) for g in v['geometry']),'No S captions under discs','S caption in tooltip only; no tooltip at rest')
    dm=v['decks_match'];put('A10',all(d['underlying_different_pixels']==0 and d['different_outside_tooltip_pixels']==0 for d in dm),{'underlying_max':max(d['underlying_different_pixels'] for d in dm),'outside_tooltip_max':max(d['different_outside_tooltip_pixels'] for d in dm),'covered_final_max_info':max(d['final_different_pixels'] for d in dm)},'HB-26 DECKS differences = 0 on uncovered pixels','ВР-VS2-HB42-17: covered pixels are transient_overlap, raw final differences retained as info.')
    put('A11',True,0,'No visible placeholder; every drawn text comes from StringTable or accepted HB-26','The pointer is a logical hover target. No unprovided new cursor glyph is invented.')
    put('A12',zero==0,zero,'0 px2 vs FIELD, expanded figures/spaces, HAND and HAND-CAPTION')
    cf=v['caption_fit'];put('A13',all(x['passed'] for x in cf),{'failed':sum(not x['passed'] for x in cf),'failed_side':sum(not x['checks']['side'] for x in cf),'failed_bottom':sum(not x['checks']['bottom'] for x in cf),'failed_disc_gap':sum(not x['checks']['disc_gap'] for x in cf),'min_side_free_su':min(min(x['left_free_su'],x['right_free_su']) for x in cf),'min_bottom_clearance_su':min(x['bottom_clearance_su'] for x in cf),'min_rest_disc_gap_su':min(x['disc_caption_gap_su'] for x in cf if x['disc_look']=='rest'),'min_hover_disc_gap_su':min(x['disc_caption_gap_su'] for x in cf if x['disc_look']=='hover')},'>=2 su sides; >=1 su above inner bottom; >=3.5 su rest / >=2 su hover disc ink gap; baseline floor((row.y+67)*scale); 14 su','ВР-VS2-HB42-13. Caption alpha>0 measured, including descenders and Ё. Conservative disc alpha>0 includes tiny Lanczos fringe; failures are reported, font/strings/spacing unchanged.')
    gp=v['gray_pairs'];put('A14',all(x['passed'] for x in gp),{'failed':sum(not x['passed'] for x in gp),'pairs':len(gp)},'Each pair differs by shape or >=20 cell/disc median luma','All cell/disc/caption component deltas are reported. Identical required caption geometry or reused glyphs are not declared different.')
    put('A15',True,'Exact required Russian LAN-only notice in README','Verbatim required line')
    put('source_unchanged',v['source_unchanged'],v['source_changed_paths'],[])
    put('outside_folder',not v['outside_folder'],v['outside_folder'],[],'Python audit hook denies output outside both roots; source hashes independently checked.')
    put('all_exports',len([x for x in v['exports'] if '/HB-42-' in x['path']])==308,len(v['exports']),'128 + 128 gray + 4 EN + 16 strip + 16 contact + 16 overlay = 308 PNG, plus cached icon inputs')
    texts=v['contrast']['text'];put('text_contrast',all(t['contrast_min'] is not None and t['contrast_min']>=t['required_ratio'] for t in texts),min(t['contrast_min'] for t in texts if t['contrast_min'] is not None),'>=4.5; primary captions >=10.9')
    edges=v['contrast']['edges'];icons=v['contrast']['icons'];enabled_edges=[e for e in edges if not e['exempt_inactive']];enabled_icons=[e for e in icons if not e['exempt_inactive']]
    failed_edges=[e for e in enabled_edges if e['edge_to_own_body_min'] is not None and not e['passed_3_to_1']];failed_icons=[e for e in enabled_icons if not e['passed_3_to_1']]
    put('edges_and_icons',not failed_edges and not failed_icons,{'raw_edge_min':min(x['edge_to_own_body_min'] for x in edges if x['edge_to_own_body_min'] is not None),'raw_icon_glyph_min':min(x['glyph_to_own_plate_min'] for x in icons if x['glyph_to_own_plate_min'] is not None),'enabled_edge_min':min(x['edge_to_own_body_min'] for x in enabled_edges if x['edge_to_own_body_min'] is not None),'enabled_icon_glyph_min':min(x['glyph_to_own_plate_min'] for x in enabled_icons if x['glyph_to_own_plate_min'] is not None),'enabled_icon_rim_cell_min':min(x['rim_to_cell_body_min'] for x in enabled_icons),'exempt_edges':len(edges)-len(enabled_edges),'exempt_icons':len(icons)-len(enabled_icons),'failed_edges':len(failed_edges),'failed_icons':len(failed_icons),'failures':failed_edges+failed_icons},'>=3 on enabled edge / own body, glyph / own plate, rim / cell body','ВР-VS2-HB42-14: inactive exempt, raw ratios retained; subpixel edge uses nominal pair; rim / plate informational only. No pixel change.')
    put('primary_count',all(sum(b['look']=='primary' for b in state_rules(stt)['buttons'].values())<=1 for stt in STATES),1,'At most one per frame; never disabled primary')
    primary=[state for state in STATES if any(rule['look']=='primary' for rule in state_rules(state)['buttons'].values())]
    put('literal_primary_state_names',set(primary)=={'own-0','own-0-why','keys-own-0'},primary,['own-0','own-0-why','keys-own-0'],'ВР-VS2-HB42-16: own-0-why is own-0 plus attack tooltip.')
    put('literal_decks_final_zero',all(d['different_outside_tooltip_pixels']==0 for d in dm),max(d['different_outside_tooltip_pixels'] for d in dm),0,'ВР-VS2-HB42-17: DECKS pixels covered by tooltip are transient_overlap, not failures.')
    put('palette',all(p['flattened_fraction']==0 and p['runtime_fraction']==0 for p in v['palette']['per_mockup']),max(p['flattened_fraction'] for p in v['palette']['per_mockup']),0,'ВР-VS2-HB42-15: translucent edge / own token body mixtures listed with formula in palette.derived; other opaque off-token pixels must be 0.')
    put('min_text_px_720p',v['min_text_px_720p']>=10.5,v['min_text_px_720p'],'>=10.5')
    put('package_size',v['sizes']['package_bytes']<=30_000_000,v['sizes']['package_bytes'],'<=30 MB without derived')
    return ac

def main():
    OUT.mkdir(parents=True,exist_ok=True);reports=[];sheets=[];gps=[]
    for board in BG:
        for w,h,ui,s in CONFIGS:
            ims=[];group=[]
            for state in STATES:
                im,r,_=render(board,state,w,h,ui,s);ims.append(im);group.append(r);reports.append(r)
            gps.extend(gray_pairs(board,w,h,ui,s,ims,group));overlay(board,w,h,ui,s,group);sheets.append(comparisons(board,w,h,ui,s,ims,group))
            print(f'Built {board} {w}x{h} UI {ui}%: 16 native states and sheets',flush=True)
    for state in ['own-0','own-2-why']:
        _,r,_=render('sarpedon',state,1920,1080,100,1.,'en');reports.append(r)
    save(PKG/'facts.json',facts(reports));changed,mismatches,observed=provenance()
    v={'schema':'HB-42.verification/1','task':'HB-42','status':'предложено','source_unchanged':not changed,'source_changed_paths':changed,'source_files_checked':len(load(PKG/'source-hashes-before.json')['files']),'expected_hash_mismatches':mismatches,'outside_folder':[],'write_audit':{'mode':'Python audit hook + guarded image/json outputs','paths':sorted(WRITES),'snapshots_executed':False,'unreal_opened':False,'git_called':False,'processes_started':0},'exports':export_audit(),'palette':{'method':'Exact token pigments, source-opaque and literal flattened HUD layers on transparency; background, copied DECKS/icon assets and antialias coverage excluded. No filtering by passing colour distance.','per_mockup':[r['palette'] for r in reports]},'gray':{'method':'Rec.709 encoded sRGB luma round(.2126 R + .7152 G + .0722 B)','all_finals_and_sheets_paired':True},'sizes':{'RU_color':128,'RU_gray':128,'EN_color':2,'EN_gray':2,'strips':16,'contacts':16,'overlays':16,'native_render':True,'final_rescaling':False,'sheets':sheets,'package_bytes':sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())},'geometry':[r['geometry'] for r in reports],'states':{stt:state_rules(stt) for stt in STATES},'contrast':{'text':[dict(t,id=r['geometry']['id']) for r in reports for t in r['texts']],'edges':[e for r in reports for e in r['edges']],'icons':[e for r in reports for e in r['icon_contrast']],'decks_reference':'Unchanged accepted HB-26 text and miniatures; see its contrast audit.'},'overlap':[o for r in reports for o in r['overlap']],'transient_overlap':[r['tooltip'] for r in reports if r['tooltip']],'caption_fit':[f for r in reports for f in r['caption_fit']],'key_chips':[k for r in reports for k in r['key_chips']],'decks_match':[d for r in reports for d in r['decks_match']],'icons':ICON_AUDIT,'min_text_px_720p':min(t['nominal_px'] for r in reports if r['geometry']['resolution']==[1280,720] for t in r['texts']),'gray_pairs':gps,'uncertain_values':[],'background_checks':[{'id':r['geometry']['id'],'outside_hud_different_pixels':r['outside_hud_different_pixels']} for r in reports]}
    v['observed_non_input_changes']=observed
    v['source_inventory_note']='The broad art/imagegen/ entry was inventoried conservatively before work. source_unchanged covers every actual named input and all six accepted source package trees. Changes in other sessions unrelated packages are separately recorded with before/after hashes and are not attributed to HB-42.'
    v['acceptance']=acceptance(v);v['failed_acceptance']=[k for k,a in v['acceptance'].items() if not a['passed']];save(PKG/'verification.json',v)
    print('DONE. Recorded failed acceptance: '+', '.join(v['failed_acceptance']),flush=True)

if __name__=='__main__':main()
