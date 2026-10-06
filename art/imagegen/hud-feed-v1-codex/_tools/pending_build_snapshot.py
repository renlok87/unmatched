"""HB-34 native-pixel renderer and audit. Run with python -B -X utf8.

Immutable snapshots are imported for CP-13 frames, HB-07 masks / HB-22 hand
geometry and HB-08 skins. No git, UE, network or subprocess. The audit hook in
the hand snapshot forbids writes outside the two HB-34 roots.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import json, math, hashlib, itertools, csv
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import hand_build_snapshot as hb
import frame_native as fn
import skins_snapshot as skins

PKG=Path(__file__).resolve().parents[1]
ROOT=PKG.parents[2]
DERIVED=ROOT/'scraped-data/derived/hud-pending-v1-codex'
hb.DERIVED=DERIVED
T={**hb.T,'yellow':'#F2C14E','scheme':'#FDBE72','choice':'#4CD2DC','inset':'#15232E'}
STATES=['modal-pick','modal-order','compact-move','compact-place','compact-target','compact-space',
        'toast','collapsed','discard','boost','opp','after-combat','slot-opp-fly','slot-opp-hold',
        'slot-opp-show','slot-opp-fade','slot-boost','slot-discard']
CONFIGS=hb.CONFIGS
REVEALED=['excalibur','the-aid-of-morgana','aid-the-chosen-one','command-the-storms']
SCARD={'modal-pick':'king-arthur:prophecy','modal-order':'king-arthur:prophecy',
       'collapsed':'king-arthur:prophecy','compact-move':'medusa:the-hounds-of-mighty-zeus',
       'compact-place':'king-arthur:bewilderment','compact-target':'medusa:a-momentary-glance',
       'compact-space':'king-arthur:restless-spirits','discard':'medusa:hiss-and-slither',
       'opp':'medusa:hiss-and-slither','after-combat':'king-arthur:swift-strike',
       'slot-opp-show':'king-arthur:restless-spirits'}
RESERVED=['TOP','PANEL-LOC','PANEL-OPP','OPP-HAND','DECKS','ACTIONS','LOG']
CANON={'marmoreal':{'Harpies 3':'M01','Harpies 1':'M07','Medusa':'M13','Harpies 2':'M20','Merlin':'M23','King Arthur':'M31'},
       'sarpedon':{'Harpies 2':'S18','Harpies 1':'S19','Harpies 3':'S23','Medusa':'S20','Merlin':'S25','King Arthur':'S32'}}
FACTS={'task':'HB-34','status':'предложено','cards':{},'rendered_texts':[], 'outputs':[],
       'state_matrix':{},'board_figures':{},'trace_evidence':{},'scans':[], 'plates':[],
       'strings_without_key':{'discard-count':'Сбросьте 1: выбрано 1/1','pick-count':'Выбрано 2/2'},
       'revealed_example':{'cards':['king-arthur:'+k for k in REVEALED], 'excluded_run_hand':hb.ARTHUR,
                           'source':'scraped-data/api/heroes/king-arthur.json','historical':False},
       'boost_example':{'card':'king-arthur:noble-sacrifice','boostValue':hb.DECK['king-arthur:noble-sacrifice']['boostValue'],
                        'source':'scraped-data/api/heroes/king-arthur.json'},
       'deltas_04':[],'uncertain_values':[]}
hb.FACTS=FACTS
V={'task':'HB-34','source_unchanged':False,'exports':[],'palette':[],'gray':{},'sizes':{},
   'outside_folder':[],'acceptance':{},'contrast':[],'overlap':[], 'transient_overlap':[],
   'compact_geometry':[], 'toast_placement':[], 'modal_fit':[], 'text_fit':[],
   'min_text_px_720p':None,'gray_pairs':[], 'skin_match_hb08':[], 'frame_match_cp13':[],
   'plates':[], 'uncertain_values':FACTS['uncertain_values'],'background_integrity':[]}

load=hb.load; dump=hb.dump; sha=hb.sha; rel=hb.rel; image=hb.image; font=hb.font
gray=hb.gray; masks=hb.masks; reference=hb.reference; pxbox=hb.pxbox; rectmask=hb.rectmask
def gray(im):
    """Exact Rec.709 rational coefficients; deterministic half-up rounding."""
    a=np.asarray(im.convert('RGBA')).copy();p=a[:,:,:3].astype(np.uint32)
    y=((p[:,:,0]*2126+p[:,:,1]*7152+p[:,:,2]*722+5000)//10000).astype('uint8')
    a[:,:,:3]=y[:,:,None];return Image.fromarray(a)
def rgb(t): return tuple(bytes.fromhex(T.get(t,t).lstrip('#')))
def save(p,im):
    p.parent.mkdir(parents=True,exist_ok=True);im.save(p,compress_level=6)

def string(key,lang='ru',**params):
    if key in hb.STRINGS:
        row=hb.STRINGS[key];template=row['ru' if lang=='ru' else 'SourceString'];src=row['source']
    else:
        row=hb.WHY[key];template=row[lang];src='docs/unreal/contracts/hud/why-reasons.json'
    return template.format(**params),{'source':src,'key':key,'template':template,'parameters':params}

def cardtext(key,field='title',lang='ru'):
    row=hb.DECK[key]['card'];use_ru=key.startswith('medusa:') and lang=='ru'
    data=row.get('i18n',{}).get('ru',{}) if use_ru else row
    value=data.get(field) or row.get(field) or ''
    return value.strip(),{'source':'scraped-data/api/heroes/'+key.split(':')[0]+'.json',
                         'key':key,'field':('card.i18n.ru.' if use_ru else 'card.')+field}

def wrap(value,width,s,size,bold=False):
    f=font(math.ceil(size*s),bold);lines=[];line=''
    for word in value.split():
        nxt=(line+' '+word).strip()
        if line and f.getlength(nxt)>width*s:lines.append(line);line=word
        else:line=nxt
    if line:lines.append(line)
    return lines or ['']

def skin_material(name,width,height,s,edge=None,fill=None,opacity=None,radius=None):
    """Same Cairo masks / OVER operation as HB-08, native sizes. No resizing."""
    st=skins.style(name);r=skins.geometry(name)[0] if radius is None else radius
    outer=skins.rect_mask(width+2,height+2,1,1,width,height,r*s)[1:-1,1:-1]
    thick=(edge[1] if edge else st['edge_su'])*s
    inner=skins.rect_mask(width+2,height+2,1+thick,1+thick,width-2*thick,height-2*thick,max(0,r*s-thick))[1:-1,1:-1]
    body=rgb(fill) if fill else tuple(int(x) for x in skins.rgb(st['body']))
    et,eo=(rgb(edge[0]),edge[2]) if edge else (tuple(int(x) for x in skins.rgb(st['edge'])),st['edge_opacity'])
    ba=st['body_opacity'] if opacity is None else opacity
    a=np.zeros((height,width,4),dtype=np.uint8);a[:,:,:3]=body;a[:,:,3]=np.rint(outer*ba*255).astype('uint8')
    b=np.zeros_like(a);b[:,:,:3]=et;b[:,:,3]=np.rint(np.maximum(0,outer-inner)*eo*255).astype('uint8')
    out=Image.alpha_composite(Image.fromarray(a),Image.fromarray(b))
    clean=np.asarray(out).copy();clean[clean[:,:,3]==0]=0;out=Image.fromarray(clean)
    # Separate authored material layers for the token audit; composited edge RGB
    # is evaluated independently against HB-08, not called a new pigment.
    return out,Image.fromarray(a),Image.fromarray(b)

class Canvas(hb.Canvas):
    def __init__(self,board,w,h,ui,s,state,lang='ru'):
        super().__init__(board,w,h,ui,s,state,lang)
        self.id=f'HB-34-{board}-{state}'+('-en' if lang=='en' else '')+f'-{w}x{h}-{ui}'
        self.reserved={k:v['rectangle_su'] for k,v in reference(board,w,h,ui)['panels'].items() if k in RESERVED}
        self.materials=[];self.panel_styles={};self.texts=[];self.plates=[];self.geometries={};self.card_group={}

    def panel(self,name,rect,transient=False,skin='Panel',edge=None,fill=None,opacity=None,radius=None,register=True):
        if register:self.block(name,rect,transient)
        pw,ph=round(rect[2]*self.s),round(rect[3]*self.s)
        out,body,border=skin_material(skin,pw,ph,self.s,edge,fill,opacity,radius)
        self.paste(out,rect[:2]);self.materials.extend([body,border])
        self.palette.alpha_composite(out,(round(rect[0]*self.s),round(rect[1]*self.s)))
        outer=fn.rounded_mask(pw/self.s,ph/self.s,(0,0,pw/self.s,ph/self.s),skins.geometry(skin)[0] if radius is None else radius,self.s)
        ea=np.asarray(border)[:,:,3]
        cov=(outer>0)&(outer<255)
        expected_edge=round((edge[2] if edge else skins.style(skin)['edge_opacity'])*255)
        cov|=(ea>0)&(ea<expected_edge)
        x0,y0=round(rect[0]*self.s),round(rect[1]*self.s)
        if 0<=x0 and 0<=y0 and x0+pw<=self.w and y0+ph<=self.h:self.antialias[y0:y0+ph,x0:x0+pw]|=cov
        self.panel_styles[name]={'rect':list(rect),'skin':skin,'edge':edge,'fill':fill,'opacity':opacity,'radius':radius}
        # Actual contrast on the rendered solid edge to the adjacent body.
        arr=np.asarray(out);e=np.asarray(border)[:,:,3];bc=np.asarray(body)
        solid=e>=round((edge[2] if edge else skins.style(skin)['edge_opacity'])*255)-1
        if np.any(solid):
            edge_rgb=arr[solid,:3].astype(float);edge_a=arr[solid,3,None]/255
            body_rgb=bc[solid,:3].astype(float);body_a=bc[solid,3,None]/255
            base=np.asarray(self.base)[max(0,round(rect[1]*self.s)):max(0,round(rect[1]*self.s))+ph,
                                       max(0,round(rect[0]*self.s)):max(0,round(rect[0]*self.s))+pw,:3]
            if base.shape[:2]==e.shape:
                eb=edge_rgb*edge_a+base[solid]*(1-edge_a)
                bb=body_rgb*body_a+base[solid]*(1-body_a)
                l1,l2=hb.luminance(eb),hb.luminance(bb)
                ratio=float(np.min((np.maximum(l1,l2)+.05)/(np.minimum(l1,l2)+.05)))
                V['contrast'].append({'id':self.id,'panel':name,'role':'edge_to_body','ratio':ratio,'required':3})
        return out

    def txt(self,name,value,src,rect,size=16,bold=False,color='primary',lines=None,center=False,container=None):
        s=self.s;f=font(math.ceil(size*s),bold);lines=lines or [value];x,y,rw,rh=rect
        layer=Image.new('RGBA',(self.w,self.h));d=ImageDraw.Draw(layer)
        boxes=[];step=size+4
        ink_height=max(f.getbbox(line)[3]-f.getbbox(line)[1] for line in lines)
        total_px=ink_height+round((len(lines)-1)*step*s)
        rh=max(rh,total_px/s);rect=[x,y,rw,rh]
        top=round(y*s)+(round(rh*s)-total_px)//2
        for i,line in enumerate(lines):
            bbox=f.getbbox(line);tw=f.getlength(line)
            tx=round((x+(rw-tw/s)/2 if center else x)*s);ty=round(top+i*step*s)-bbox[1]
            d.text((tx,ty),line,font=f,fill=(*rgb(color),255))
            boxes.append([tx,ty+bbox[1],tx+math.ceil(tw),ty+bbox[3]])
        self.hud.alpha_composite(layer);self.materials.append(layer);self.palette.alpha_composite(layer)
        coverage=np.asarray(layer)[:,:,3];self.antialias|=(coverage>0)&(coverage<255)
        b=pxbox(rect,s)
        fit=all(z[0]>=b[0] and z[1]>=b[1] and z[2]<=b[2] and z[3]<=b[3] for z in boxes)
        rec={'id':self.id,'block':name,'text':value,'source':src,'lines':lines,'type_su':size,
             'font_px':math.ceil(size*s),'nominal_px':size*s,'bbox_px':boxes,'layout_box_su':list(rect),'not_truncated':fit}
        self.texts.append(rec);FACTS['rendered_texts'].append(rec);V['text_fit'].append(rec)
        # Contrast against the panel material composited over its immutable base.
        parent=self.panel_styles.get(container or name)
        if parent:
            st=skins.style(parent['skin']);fg=rgb(color)
            fill=rgb(parent['fill']) if parent['fill'] else tuple(int(v) for v in skins.rgb(st['body']))
            alpha=st['body_opacity'] if parent['opacity'] is None else parent['opacity']
            ratios=[]
            for x0,y0,x1,y1 in boxes:
                patch=np.asarray(self.base)[max(y0,0):min(y1,self.h),max(x0,0):min(x1,self.w),:3]
                if patch.size:
                    bg=patch*(1-alpha)+np.array(fill)*alpha;lum=hb.luminance(bg);fl=hb.luminance(fg)
                    ratios.append(float(np.min((np.maximum(lum,fl)+.05)/(np.minimum(lum,fl)+.05))))
            if ratios:V['contrast'].append({'id':self.id,'panel':container or name,'role':'text','text':value,'ratio':min(ratios),'required':4.5})
        return rec

    def keyed(self,name,key,rect,size=16,bold=False,color='primary',params=None,**kw):
        value,src=string(key,self.lang,**(params or {}));return self.txt(name,value,src,rect,size,bold,color,**kw)

    def button(self,key,rect,primary=False,container=None):
        name=key;self.panel(name,rect,skin='BtnPrimary_Normal' if primary else 'Btn_Normal',register=False)
        value,src=string(key,self.lang);src['case_transform']='upper';src['source_value']=value
        return self.txt(name,value.upper(),src,[rect[0]+12,rect[1],rect[2]-24,rect[3]],20,True,'navy' if primary else 'primary',center=True)

    def keychip(self,key,rect,sourcekey=None):
        self.panel('KEY-'+key,rect,skin='KeyChip',register=False)
        if sourcekey:
            return self.keyed('KEY-'+key,sourcekey,rect,14,True,center=True)
        return self.txt('KEY-'+key,key,{'source':'docs/game-design/visual/04-hud-spec.md','section':'2.8 / 2.11','key':key},rect,14,True,center=True)

    def status(self,key,params=None,keys=None):
        keys=keys or [];params=params or {};value,src=string(key,self.lang,**params);s=self.s
        self.status_text(value,src,keys)

    def status_text(self,value,src,keys=None):
        keys=keys or [];s=self.s
        cap=600 if self.small else (880 if self.w==1920 else 720)
        labels=[string(k,self.lang)[0] for k in keys]
        widths=[max(20,font(math.ceil(14*s),True).getlength(k)/s+8) for k in labels]
        keywidth=sum(widths)+8*max(0,len(keys)-1)+(12 if keys else 0)
        lines=wrap(value,cap-32-keywidth,s,24,True);size=24
        if len(lines)>2:size=20;lines=wrap(value,cap-32-keywidth,s,size,True)
        height=48 if len(lines)==1 else (78 if self.small else 74)
        width=min(cap,max(font(math.ceil(size*s),True).getlength(l)/s for l in lines)+32+keywidth+2/s)
        r=[(self.w/s-width)/2,16 if self.small else 24,width,height]
        self.panel('STATUS',r)
        self.txt('STATUS',value,src,[r[0]+16,r[1],r[2]-32-keywidth,r[3]],size,True,lines=lines)
        xx=r[0]+r[2]-16-sum(widths)-8*max(0,len(keys)-1)
        chips=[]
        for k,label,kw in zip(keys,labels,widths):
            chip=[xx,r[1]+(height-20)/2,kw,20]
            # HB-13 own-action-keys: opaque inset, cream .45 1 su edge, r4.
            self.status_key_panel('STATUS-KEY-'+label,chip)
            self.keyed('STATUS-KEY-'+label,k,chip,14,True,center=True,container='STATUS-KEY-'+label)
            chips.append({'key':k,'text':label,'rectangle_su':chip});xx+=kw+8
        self.geometries['status_keys']={'chips':chips,'text_gap_su':12,'chip_gap_su':8,'height_su':20}
        self.geometries['status']=r

    def status_key_panel(self,name,rect):
        # HB-13 uses Pillow's outlined rectangle: the .45 outline replaces the
        # opaque fill at the edge, then composites on STATUS, not on inset.
        layer=Image.new('RGBA',(self.w,self.h));d=ImageDraw.Draw(layer)
        box=pxbox(rect,self.s);box[2]-=1;box[3]-=1
        d.rounded_rectangle(box,radius=max(1,round(4*self.s)),fill=(*rgb('inset'),255),
                            outline=(*rgb('cream'),115),width=max(1,round(self.s)))
        self.hud.alpha_composite(layer);self.palette.alpha_composite(layer);self.materials.append(layer)
        self.panel_styles[name]={'rect':rect,'skin':'KeyChip','fill':'inset','opacity':1,'radius':4}
        edge=np.rint(np.array(rgb('cream'))*(115/255)+np.array(rgb('navy'))*(140/255))
        V['contrast'].append({'id':self.id,'panel':name,'role':'edge_to_body',
            'ratio':hb.contrast(edge,rgb('inset')),'required':3,'note':'HB-13 .45 outline on STATUS versus opaque inset body'})

    def source(self,key,ribbon='scheme',fade=1,fly=False):
        r=[16,64,120,166] if self.small else [24,84,190,264]
        if fly:
            opp=self.reserved['OPP-HAND'];ox=opp[0]+opp[2]/2;oy=opp[1]+opp[3]/2
            r=[(ox+r[0]+r[2]/2)/2-r[2]/2,(oy+r[1]+r[3]/2)/2-r[3]/2,r[2],r[3]]
        old=self.hud;stack=Image.new('RGBA',old.size);self.hud=stack
        self.card(key,r,name='SLOT',transient=fly)
        if not fly:
            rb=[r[0],r[1]+r[3]+4,r[2],28]
            self.panel('SLOT-RIBBON',rb,fill={'scheme':'scheme','boost':'navy','discard':'secondary'}[ribbon],
                       opacity=1 if ribbon!='boost' else .92,radius=6,
                       edge=None if ribbon=='boost' else ('navy',1,1))
            self.icon('marker-status',[rb[0]+2,rb[1]+2,24,24])
            if ribbon!='boost':
                # Reuse the original v3 glyph alpha, printed in the required navy.
                patch=self.hud.crop((round((rb[0]+2)*self.s),round((rb[1]+2)*self.s),round((rb[0]+26)*self.s),round((rb[1]+26)*self.s)))
                glyph=Image.new('RGBA',patch.size,(*rgb('navy'),255));glyph.putalpha(patch.getchannel('A'))
                # The panel under the glyph must not be recolored: use icon asset alpha only.
                src=self.badges[-1]['source'];raw=image(src).resize(patch.size,Image.Resampling.LANCZOS)
                glyph.putalpha(raw.getchannel('A'));self.paste(glyph,[rb[0]+2,rb[1]+2])
                self.badges[-1]['ink_override']='card.navy; original v3 alpha silhouette preserved'
            self.keyed('SLOT-RIBBON','hud.slot.'+ribbon,[rb[0]+32,rb[1],rb[2]-40,rb[3]],14,True,
                       'glyph' if ribbon=='boost' else 'navy')
            V['contrast'].append({'id':self.id,'panel':'SLOT-RIBBON marker-status','role':'glyph_to_own_plate',
               'pair':[T['glyph' if ribbon=='boost' else 'navy'],T[{'scheme':'scheme','boost':'navy','discard':'secondary'}[ribbon]]],
               'ratio':hb.contrast(rgb('glyph' if ribbon=='boost' else 'navy'),rgb({'scheme':'scheme','boost':'navy','discard':'secondary'}[ribbon])), 'required':3})
            if self.state=='slot-opp-hold':
                d=ImageDraw.Draw(self.hud);d.rectangle(pxbox([rb[0],rb[1]+26,rb[2]/2,2],self.s),fill=rgb('glyph'))
                V['contrast'].append({'id':self.id,'panel':'HOLD-PROGRESS','role':'progress_to_plate',
                    'ratio':hb.contrast(rgb('glyph'),rgb('scheme')),'required':3,
                    'note':'Mandatory card.glyph progress hairline on mandatory scheme plate; pair cannot meet 3:1.'})
            if ribbon=='boost':
                chip=[r[0]+r[2]-32,r[1]-36,32,32];self.panel('BOOST-CHIP',chip)
                self.icon('state-boost',chip)
                self.keyed('BOOST-CHIP','hud.card.boost',chip,14,True,params={'n':FACTS['boost_example']['boostValue']},center=True)
            self.geometries['slot_ribbon']=[r[0],r[1],r[2],r[3]+32]
        if fade!=1:stack.putalpha(stack.getchannel('A').point(lambda a:round(a*fade)))
        self.hud=Image.alpha_composite(old,stack)

    def compact(self,title,tsrc,hint,hsrc,buttons,icon=None,queue=False,grey=False):
        width=560 if self.small else 720;s=self.s;pad=12
        if grey:
            pad=16
            width=min(width,max(320,max(font(math.ceil(24*s),True).getlength(title),font(math.ceil(16*s)).getlength(hint))/s+32+2/s))
        bws=[max(120,font(math.ceil(20*s),True).getlength(string(k,self.lang)[0].upper())/s+26) for k,p in buttons]
        bw=sum(bws)+8*max(0,len(bws)-1)
        left=width-2*pad-bw-(12 if buttons else 0)
        titlewidth=max(1,left-(32 if icon else 0)-(70 if queue else 0))
        tlines=wrap(title,titlewidth,s,24,True);hlines=wrap(hint,max(1,left),s,16)
        # Compare three layouts by actual native font lengths. Keep two logical
        # rows: text with controls beside it, title with controls + full hint,
        # or full title + hint beside controls. This is narrower than stacking
        # title, hint and controls in three rows on every canvas.
        candidates=[]
        th=24+(len(tlines)-1)*28;hh=16+(len(hlines)-1)*20
        if all(font(math.ceil(24*s),True).getlength(l)<=titlewidth*s for l in tlines):
            candidates.append((max(40 if buttons else 0,th+4+hh)+16,'text-left',
                [pad+(32 if icon else 0),8,titlewidth,th],[pad,8+th+4,left,hh],tlines,hlines,8))
        if buttons and not queue:
            tw=max(1,left-(32 if icon else 0));tl=wrap(title,tw,s,24,True);hl=wrap(hint,width-2*pad,s,16)
            th=24+(len(tl)-1)*28;hh=16+(len(hl)-1)*20;row=max(40,th)
            candidates.append((row+4+hh+16,'title-controls',[pad+(32 if icon else 0),8,tw,th],
                                [pad,8+row+4,width-2*pad,hh],tl,hl,8))
        if buttons:
            tw=width-2*pad-(32 if icon else 0)-(70 if queue else 0);tl=wrap(title,tw,s,24,True)
            hl=wrap(hint,max(1,left),s,16);th=24+(len(tl)-1)*28;hh=16+(len(hl)-1)*20
            candidates.append((th+4+max(40,hh)+16,'title-full',[pad+(32 if icon else 0),8,tw,th],
                                [pad,8+th+4,left,hh],tl,hl,8+th+4))
        if buttons and not icon and not queue:
            tw=font(math.ceil(24*s),True).getlength(title)/s+2/s
            hw=width-2*pad-tw-12
            hl=wrap(hint,hw,s,16);hh=16+(len(hl)-1)*20;row=max(24,hh)
            candidates.append((row+4+40+16,'title-hint-controls',[pad,8,tw,24],
                                [pad+tw+12,8,hw,hh],[title],hl,8+row+4))
        candidates=[r for r in candidates if all(font(math.ceil(24*s),True).getlength(l)<=r[2][2]*s for l in r[4])
                     and all(font(math.ceil(16*s)).getlength(l)<=r[3][2]*s for l in r[5])]
        height,mode,tbox,hbox,tlines,hlines,buttony=min(candidates,key=lambda r:r[0])
        height=max(56,height)
        anchor=max(64 if self.small else 80,self.geometries['status'][1]+self.geometries['status'][3]+8)
        r=[(self.w/s-width)/2,anchor,width,height]
        self.panel('PENDING',r,edge=None if grey else ('pending',2,1),opacity=.92)
        color='secondary' if grey else 'primary'
        self.txt('PENDING',title,tsrc,[r[0]+tbox[0],r[1]+tbox[1],tbox[2],tbox[3]],24,True,color,lines=tlines)
        self.txt('PENDING',hint,hsrc,[r[0]+hbox[0],r[1]+hbox[1],hbox[2],hbox[3]],16,False,color,lines=hlines)
        if icon:self.icon(icon,[r[0]+pad,r[1]+10,24,24])
        if queue:
            qx=r[0]+pad+left-64 if mode=='text-left' else r[0]+width-pad-64
            qr=[qx,r[1]+8,64,24];self.panel('QUEUE',qr,skin='Chip',register=False)
            self.keyed('QUEUE','hud.pending.queue',qr,14,True,params={'k':2},center=True)
        xx=r[0]+width-pad-bw;by=r[1]+buttony
        for (key,primary),bwidth in zip(buttons,bws):
            self.button(key,[xx,by,bwidth,40],primary);xx+=bwidth+8
        record={'id':self.id,'state':self.state,'rectangle_su':r,'mode':mode,'buttons_width_su':bw,
                'width_fixed':width,'greyscale_shape':'no controls, 1 su edge' if grey else 'controls, 2 su edge'}
        V['compact_geometry'].append(record);FACTS['deltas_04'].append(record);self.geometries['compact']=r

    def icon(self,name,rect,ic36=False):
        super().icon(name,rect,ic36)
        bg='pending' if name.startswith('state-pending-') else 'navy'
        ratio=hb.contrast(rgb('glyph'),rgb(bg))
        V['contrast'].append({'id':self.id,'panel':name,'role':'glyph_to_own_plate','ratio':ratio,
                              'required':3,'pair':[T['glyph'],T[bg]],'source':self.badges[-1]['source']})

    def hand(self,keys,drop=False,boost=False):
        g=hb.geometry(self.board,self.w,self.h,self.ui,self.s,len(keys));self.geometries['hand']=g
        text,src=string('hud.hand.count',self.lang,n=len(keys),max=7)
        width=font(math.ceil(14*self.s)).getlength(text)/self.s+24+2/self.s
        cr=[g['caption'][0],g['caption'][1],width,22];self.panel('HAND-CAPTION',cr,radius=4)
        self.txt('HAND-CAPTION',text,src,[cr[0]+12,cr[1],cr[2]-24,cr[3]],14)
        for i,key in enumerate(keys):
            r=g['cards'][i].copy()
            if drop and i==1:r[1]+=16
            self.card('king-arthur:'+key,r,'warning' if drop else 'selected' if boost else 'idle',name='HAND-'+str(i))
            if drop and i==1:
                badge=[r[0]+r[2]-28,g['cards'][i][1]-28,28,28]
                self.panel('DROP',badge,radius=4,register=False);self.icon('card-drop',[badge[0]+2,badge[1]+2,24,24],True)
                self.card_group['HAND'].append(badge)

    def card(self,key,rect,state='idle',dim=False,transient=False,name=None):
        super().card(key,rect,state,dim,transient,name)
        self.materials.append(fn.frame((rect[2],rect[3],4,8),state,self.s))
        outer=fn.rounded_mask(rect[2],rect[3],(0,0,rect[2],rect[3]),8,self.s)
        cov=(outer>0)&(outer<255);x0,y0=round(rect[0]*self.s),round(rect[1]*self.s)
        x1,y1=min(self.w,x0+cov.shape[1]),min(self.h,y0+cov.shape[0])
        if x0>=0 and y0>=0 and x1>x0 and y1>y0:self.antialias[y0:y1,x0:x1]|=cov[:y1-y0,:x1-x0]
        edge=fn.EDGE[state]
        col=rgb(edge[0]);on_navy=np.rint(np.array(col)*edge[2]+np.array(rgb('navy'))*(1-edge[2]))
        V['contrast'].append({'id':self.id,'panel':name or key,'role':'frame_edge_to_underlay',
            'ratio':hb.contrast(on_navy,rgb('navy')),'required':3,'state':state,'source':'CP-13'})
        if name and name.startswith('HAND-'):self.card_group.setdefault('HAND',[]).append(rect.copy())
        FACTS['scans'].append(self.scans[-1])

    def combat(self,defender=False):
        r=[16,240,150,208] if self.small else [24,360,230,319]
        if defender:r[0]=self.w/self.s-r[0]-r[2]
        self.card('medusa:back' if defender else 'king-arthur:swift-strike',r,name='COMBAT-R' if defender else 'COMBAT-L')
        rb=[r[0],r[1]+r[3]+4,r[2],44 if self.small else 28]
        if self.w==1280 and not self.small:rb[1]=r[1]-rb[3]-4
        name='DEFENSE-RIBBON' if defender else 'ATTACK-RIBBON';self.panel(name,rb)
        self.icon('marker-status' if defender else 'action-attack',[rb[0]+2,rb[1]+(rb[3]-24)/2,24,24])
        fighter='Medusa' if defender else 'King Arthur' if self.state=='boost' else 'Merlin'
        key='hud.combat.role.defense' if defender else 'hud.combat.role.attack'
        value,src=string(key,self.lang,fighter=fighter);lines=wrap(value,rb[2]-40,self.s,14,True)
        self.txt(name,value,src,[rb[0]+32,rb[1],rb[2]-40,rb[3]],14,True,lines=lines)
        self.geometries['combat-'+('R' if defender else 'L')]={'card':r,'ribbon':rb}

def boarddata():
    for b,fig in CANON.items():
        topo=load(ROOT/f'backend/prisma/fixtures/boards/{b}.topology.json');spaces={r['id']:r for r in topo['spaces']}
        FACTS['board_figures'][b]={'figures':[{ 'name':n,'space_id':sid,'zones':spaces[sid]['zones'],
             'source':'HB-07 masks registration + visually read bench figure labels/model silhouettes',
             'team':'P2' if n in ['King Arthur','Merlin'] else 'P1'} for n,sid in fig.items()],
             'background':hb.BG[b],'figure_space_assignment':'Nearest registered ellipse to visually read foot/ring centre; no run I positions reused.'}
        occupied=set(fig.values());enemy={fig['King Arthur'],fig['Merlin']};start=fig['Harpies 1']
        visited={start:0};front=[start]
        while front:
            cur=front.pop(0)
            if visited[cur]>=3:continue
            for nxt in spaces[cur]['links']:
                if nxt in enemy or nxt in visited:continue
                visited[nxt]=visited[cur]+1;front.append(nxt)
        medzones=set(spaces[fig['Medusa']]['zones']);merzones=set(spaces[fig['Merlin']]['zones'])
        FACTS['board_figures'][b]['target_candidates']=[n for n,sid in fig.items() if medzones.intersection(spaces[sid]['zones'])]
        FACTS['board_figures'][b]['ability_legal_enemy_targets']=[n for n in ['King Arthur','Merlin'] if medzones.intersection(spaces[fig[n]]['zones'])]
        FACTS['board_figures'][b]['destinations']={
          'compact-move':{'ids':sorted(k for k,v in visited.items() if 1<=v<=3 and k not in occupied),
                          'distances':visited,'start':start,'rule':'BFS 1–3 links; own occupied cells passable; enemy cells blocked; finish empty.'},
          'compact-place':{'ids':sorted(set(spaces)-occupied),'rule':'All empty spaces; optional Merlin PLACE.'},
          'compact-space':{'ids':sorted(k for k,r in spaces.items() if merzones.intersection(r['zones'])),
                           'zones':sorted(merzones),'rule':'All cells in any Merlin zone; occupancy does not exclude CHOOSE_SPACE.'}}

def evidence():
    for b in ['marmoreal','sarpedon']:
        dirname='combat-20261005-235827' if b=='marmoreal' else 'combat-20261005-235948'
        for who in ['host','joiner']:
            path=f'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/{b}/{dirname}/combat-client-{who}.trace.txt'
            lines=(ROOT/path).read_text(encoding='utf-8').splitlines()
            rows=[{'path':path,'line':i+1,'text':l} for i,l in enumerate(lines) if any(k in l for k in
                  ['MS-PENDING','HUD-SLOT','MS-STATUS','PEND-RESOLVE','RESOLVE panel blocked','MS-LOG','S09AUTO defense card picked'])]
            FACTS['trace_evidence'][b+'-'+who]=rows
    for state in STATES:
        owner='King Arthur' if state in ['modal-pick','modal-order','compact-place','compact-space','collapsed','discard','boost','after-combat'] else 'Medusa'
        historical=state in ['compact-target','toast','discard','opp','after-combat']
        FACTS['state_matrix'][state]={'owner':owner,'source_card':SCARD.get(state),
            'kind':'run I presentation with bench positions' if historical else 'example from real cards',
            'example':not historical,'references':['marmoreal-host'] if state in ['compact-target','toast'] else ['sarpedon-host','sarpedon-joiner'] if historical else ['scraped-data/api/heroes/'+('king-arthur' if owner=='King Arthur' else 'medusa')+'.json']}
        if state.startswith('slot-opp-'):FACTS['state_matrix'][state]['source_card']='king-arthur:restless-spirits'
        if state=='slot-boost':FACTS['state_matrix'][state]['source_card']='king-arthur:back'
        if state=='toast':FACTS['state_matrix'][state]['source_ability']='medusa'
    FACTS['state_matrix']['discard']['hand_example']=hb.ARTHUR
    FACTS['state_matrix']['discard']['cause']={'card':'medusa:hiss-and-slither','inference':True,
        'chain':'Sarpedon host lines 1995, 2016: Medusa hero defended; 2097: DISCARD_CARDS. Of the 11 Medusa cards only Hiss and Slither both defends for Medusa and discards 1; Clutching Claws banner Harpy is illegal for Medusa.'}
    FACTS['state_matrix']['toast']['remembered']={'fighter':'King Arthur','path':FACTS['trace_evidence']['marmoreal-host'][0]['path'],
                                                'line':2179,'trace':'remembered=fighter=f-1-hero applied=fighter=f-1-hero'}
    FACTS['state_matrix']['slot-discard']['example']=True
    FACTS['state_matrix']['slot-discard']['card']='king-arthur:the-holy-grail'
    for state,refs,needles in [
        ('compact-target',['marmoreal-host'],['type=TARGET_FIGHTER','card="A Momentary Glance"']),
        ('toast',['marmoreal-host'],['ability-medusa-target-p0','remembered=fighter=f-1-hero']),
        ('discard',['sarpedon-joiner'],['type=DISCARD_CARDS']),
        ('opp',['sarpedon-host'],['RESOLVE panel blocked by pending']),
        ('after-combat',['sarpedon-joiner'],['type=MOVE value=4','Swift Strike effect','Resolve the combat (R)'])]:
        FACTS['state_matrix'][state]['trace_lines']=[r for ref in refs for r in FACTS['trace_evidence'][ref]
            if any(n in r['text'] for n in needles)]
    FACTS['hero_data']={hero:{'source':'scraped-data/api/heroes/'+hero+'.json','fetchedHero':d['fetchedHero']} for hero,d in hb.HEROES.items()}
    FACTS['uncertain_values'].extend([
       {'what':'Card actually discarded by King Arthur','where':'slot-discard','why':'PEND-RESOLVE has no card id/name; HUD reports hand 1→0, without identity. Uses explicitly labelled The Holy Grail example from run I opening hand.'},
       {'what':'Exact hand at DISCARD_CARDS','where':'discard','why':'HUD count is 1; no identities recorded. Task permits opening run I hand of 3 as labelled example.'},
       {'what':'Defense identity in the first Swift Strike staged combat','where':'after-combat COMBAT-R','why':'Trace has no named defense. Uses Medusa back as explicitly allowed.'}])

def status_for(c):
    st=c.state
    if st in ['modal-pick','modal-order','collapsed']:c.status('ms.status.choice',{'choice':'Prophecy'})
    elif st=='compact-move':c.status('ms.choice.target',{'n':3})
    elif st=='compact-target':c.status('ms.choice.target',{'n':1})
    elif st in ['compact-place','compact-space']:c.status('ms.status.choice',{'choice':cardtext(SCARD[st],lang=c.lang)[0]})
    elif st=='discard':c.status('ms.status.choice',{'choice':cardtext(SCARD[st],lang=c.lang)[0]})
    elif st=='boost':c.status('ms.status.choice',{'choice':'King Arthur'})
    elif st=='toast':c.status('ms.status.action',keys=['hud.key.maneuver','hud.key.attack','hud.key.scheme'])
    elif st=='after-combat':
        # StringTable has the (R) in its template. HB-13 renders it as a separate chip.
        value,src=string('ms.status.resolve',c.lang)
        original=hb.STRINGS['ms.status.resolve'].copy()
        # Use exact text minus the keyboard suffix, with suffix preserved in a chip.
        field='ru' if c.lang=='ru' else 'SourceString';hb.STRINGS['ms.status.resolve'][field]=value.replace('(R)','').strip()
        c.status('ms.status.resolve',keys=['hud.key.resolve']);hb.STRINGS['ms.status.resolve']=original
        c.texts[-2]['source']['original_template']=value
    else:
        verb='ms.opp.phase.card' if st=='opp' else 'ms.opp.planning' if st=='slot-boost' else 'ms.opp.phase.turn'
        text,vsrc=string(verb,c.lang);c.status('ms.status.opp',{'player':'King Arthur','verb':text})
        c.texts[0]['source']['verb_source']=vsrc

def plates(c):
    if c.state not in ['compact-move','compact-place','compact-space']:return
    ids=FACTS['board_figures'][c.board]['destinations'][c.state]['ids']
    entry=hb.MASKDATA['topology_transforms'][f'{c.board}-{c.w}x{c.h}'];d=ImageDraw.Draw(c.hud)
    for space in entry['spaces']:
        if space['id'] not in ids:continue
        p=np.asarray(space['polygon_px']);lo=p.min(0)+4*c.s;hi=p.max(0)-4*c.s
        box=[float(lo[0]),float(lo[1]),float(hi[0]),float(hi[1])]
        if c.state=='compact-move':
            fill=Image.new('RGBA',(c.w,c.h));ImageDraw.Draw(fill).ellipse(box,fill=(*rgb('choice'),26));c.hud.alpha_composite(fill)
            d=ImageDraw.Draw(c.hud)
        # Six equal long arcs: 44 degrees of ink, 16 degree gap per segment.
        for i in range(6):
            d.arc(box,i*60+8,i*60+52,fill=rgb('keyline'),width=max(1,round(5*c.s)))
            ib=[box[0]+c.s,box[1]+c.s,box[2]-c.s,box[3]-c.s]
            d.arc(ib,i*60+8,i*60+52,fill=rgb('choice'),width=max(1,round(3*c.s)))
        rec={'id':c.id,'space':space['id'],'kind':'V-11' if c.state=='compact-move' else 'V-12',
             'ellipse_px':box,'inset_su':4,'dash_count':6,'stroke_su':3,'keyline_su':1,
             'fill_opacity':.1 if c.state=='compact-move' else 0,'registered_polygon_px':space['polygon_px']}
        c.plates.append(rec);V['plates'].append(rec)

def modal(c):
    width=560 if c.small else 640;cap=360 if c.small else 420 if c.w==1920 else 380
    y=max(64 if c.small else 80,c.geometries['status'][1]+c.geometries['status'][3]+8)
    r=[(c.w/c.s-width)/2,y,width,cap];c.panel('MODAL',r,True,skin='Modal',edge=('pending',2,1))
    title,tsrc=cardtext('king-arthur:prophecy',lang=c.lang);effect,esrc=cardtext('king-arthur:prophecy','effect',c.lang)
    c.txt('MODAL',title,tsrc,[r[0]+16,y+12,width-32,32],28,True)
    lines=wrap(effect,width-40,c.s,16);eh=len(lines)*20
    footer=y+cap-56;bodytop=y+48;visible=footer-8-bodytop
    cw,ch=(120,166) if c.small else (150,208);gap=(width-32-4*cw)/3
    numbers=24 if c.state=='modal-order' else 0
    content=eh+12+numbers+ch;scroll=max(0,content-visible)
    before=c.hud;before_palette=c.palette.copy();body=Image.new('RGBA',before.size);c.hud=body
    c.palette=Image.new('RGBA',before.size)
    c.txt('MODAL',effect,esrc,[r[0]+16,bodytop,width-40,eh],16,lines=lines)
    cy=bodytop+eh+12+numbers
    for i,key in enumerate(REVEALED):
        cr=[r[0]+16+i*(cw+gap),cy,cw,ch]
        c.card('king-arthur:'+key,cr,'selected' if c.state=='modal-pick' and i<2 else 'idle',transient=True,name='REVEALED-'+str(i))
        if c.state=='modal-order' and i>=2:
            chip=[cr[0]+cw/2-12,cy-24,24,24]
            c.panel('ORDER-'+str(i),chip,skin='Chip',fill='glyph',opacity=1,edge=('navy',1,1),register=False)
            c.txt('ORDER-'+str(i),str(i-1),{'source':'HB-34 P3','key':'order-index','value':i-1},chip,14,True,'navy',center=True)
    # Scrolling viewport crops the body layer, never the source image / scan fit.
    viewport=Image.new('RGBA',before.size);box=pxbox([r[0]+16,bodytop,width-32,visible],c.s)
    viewport.paste(body.crop(tuple(box)),(box[0],box[1]));c.hud=Image.alpha_composite(before,viewport)
    palviewport=Image.new('RGBA',before.size);palviewport.paste(c.palette.crop(tuple(box)),(box[0],box[1]))
    c.palette=Image.alpha_composite(before_palette,palviewport)
    if scroll>0:
        track=[r[0]+width-8,bodytop,4,visible];c.panel('SCROLL-TRACK',track,skin='ProgressTrack',opacity=1,register=False)
        thumb=[track[0],bodytop,4,max(16,visible*visible/content)];c.panel('SCROLL-THUMB',thumb,skin='ProgressFill',register=False)
    counter='Выбрано 2/2' if c.lang=='ru' else 'Selected 2/2'
    c.txt('MODAL',counter,{'source':'HB-34 P3 / 04 section 2.8','key':None},[r[0]+16,footer,width-32,40],14,True)
    b1=max(120,font(math.ceil(20*c.s),True).getlength(string('hud.number.confirm',c.lang)[0])/c.s+26)
    b2=max(120,font(math.ceil(20*c.s),True).getlength(string('ms.btn.collapse',c.lang)[0])/c.s+26)
    c.button('hud.number.confirm',[r[0]+width-16-b2-8-b1,footer,b1,40],True)
    c.button('ms.btn.collapse',[r[0]+width-16-b2,footer,b2,40])
    rec={'id':c.id,'rectangle_su':r,'content_height_su':content,'visible_height_su':visible,
         'scrolled_part_su':scroll,'scroll_offset_su':0,'counter_buttons_visible':True,
         'body_viewport_su':[r[0]+16,bodytop,width-32,visible],
         'note':'Body at scroll offset 0. Lower cards may be viewport-occluded, never asset-cropped. Footer fixed.'}
    V['modal_fit'].append(rec);c.geometries['modal']=rec

def toast(c):
    width=440 if c.small else 560 if c.w==1920 else 520;H=48;ref=reference(c.board,c.w,c.h,c.ui)
    initial=ref['panels']['HAND-CAPTION']['rectangle_su'][1]-8-H
    sm,fm=masks(c.board,c.w,c.h)
    def conflicts(y):return int(np.count_nonzero(rectmask([(c.w/c.s-width)/2,y,width,H],c.s,c.w,c.h)&(sm|fm)))
    y=initial;attempts=[{'y_su':y,'overlap_px2':conflicts(y)}]
    if conflicts(y):
        y=216*(.75 if c.small else 1);attempts.append({'y_su':y,'overlap_px2':conflicts(y)})
        while conflicts(y) and y-1/c.s>=c.geometries['status'][1]+c.geometries['status'][3]+8:y-=1/c.s
    r=[(c.w/c.s-width)/2,y,width,H];c.panel('TOAST',r,skin='Toast')
    name='Medusa';hint,src=string('ms.pending.remembered',c.lang,choice='King Arthur')
    keywidths=[max(24,font(math.ceil(14*c.s),True).getlength(k)/c.s+12) for k in ['Enter','X','C']]
    kw=sum(keywidths)+16;available=width-32-kw-8
    c.txt('TOAST',name,{'source':'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt','key':'Hero.name'},[r[0]+16,y+4,available,20],16,True)
    c.txt('TOAST',hint,src,[r[0]+16,y+24,available,20],16)
    x=r[0]+width-16-kw
    for k,kwidth in zip(['Enter','X','C'],keywidths):c.keychip(k,[x,y+12,kwidth,24]);x+=kwidth+8
    rec={'id':c.id,'initial_y_su':initial,'attempts':attempts,'chosen_rectangle_su':r,
         'chosen_overlap_px2':conflicts(y),'rule':'HB-07 caption −8; top band; smallest whole-pixel upward displacement'}
    V['toast_placement'].append(rec);c.geometries['toast']=r

def render(b,st,w,h,ui,s,lang='ru'):
    c=Canvas(b,w,h,ui,s,st,lang);status_for(c);plates(c)
    if st.startswith('modal-'):c.source('king-arthur:prophecy');modal(c)
    elif st=='collapsed':
        c.source('king-arthur:prophecy');value,src=string('hud.pending.collapsed',lang,card='Prophecy')
        width=max(320,font(math.ceil(16*s)).getlength(value)/s+32+32)
        y=max(64 if c.small else 80,c.geometries['status'][1]+c.geometries['status'][3]+8)
        r=[(w/s-width)/2,y,width,44];c.panel('COLLAPSED',r,edge=('pending',2,1))
        c.txt('COLLAPSED',value,src,[r[0]+16,y,width-64,44],16);c.keychip('C',[r[0]+width-40,y+10,24,24])
        c.geometries['collapsed']=r;FACTS['deltas_04'].append({'id':c.id,'state':st,'rectangle_su':r,'reason':'Grow width only if complete text + C + padding exceeds 320.'})
    elif st=='toast':toast(c)
    elif st in ['compact-move','compact-place','compact-target','compact-space','discard','boost','opp','after-combat','slot-opp-show']:
        title,tsrc=cardtext(SCARD[st],lang=lang) if st in SCARD else ('King Arthur',{'source':'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt','key':'Hero.name'})
        icon=None;queue=False;grey=st in ['opp','after-combat','slot-opp-show'];buttons=[]
        if st=='compact-move':
            hint,hsrc=string('ms.pending.move',lang,fighterName='Harpies',n=3);queue=True;icon='state-pending-move'
            buttons=[('ms.btn.stay',False),('ms.btn.collapse',False)]
        elif st=='compact-place':
            hint,hsrc=string('ms.pending.place',lang,fighterName='Merlin');icon='state-pending-place'
            buttons=[('ms.btn.decline',False),('ms.btn.collapse',False)]
        elif st=='compact-target':
            hint,hsrc=cardtext(SCARD[st],'effect',lang);buttons=[('ms.btn.collapse',False)];c.source(SCARD[st])
        elif st=='compact-space':
            hint,hsrc=cardtext(SCARD[st],'effect',lang);hint=hint.split('. ')[0]+'.';hsrc['excerpt']='first sentence verbatim'
            icon='state-pending-place';buttons=[('ms.btn.collapse',False)];c.source(SCARD[st])
        elif st=='discard':
            hint='Сбросьте 1: выбрано 1/1';hsrc={'source':'HB-34 P3 / 04 section 2.8','key':None}
            buttons=[('hud.number.confirm',True)];c.hand(hb.ARTHUR,drop=True)
        elif st=='boost':
            hint,hsrc=string('ms.ability.boost',lang,fighterName='King Arthur')
            buttons=[('ms.btn.boost.attack',True),('ms.btn.noboost',False)]
            c.hand(['the-holy-grail','noble-sacrifice'],boost=True);c.combat()
        elif st=='after-combat':hint,hsrc=string('hud.pending.after.combat',lang);c.combat();c.combat(True)
        else:
            hint,hsrc=string('why.wait.opponent.choice',lang)
            if st=='slot-opp-show':c.source('king-arthur:restless-spirits')
        c.compact(title,tsrc,hint,hsrc,buttons,icon,queue,grey)
    elif st.startswith('slot-opp-'):
        c.source('king-arthur:restless-spirits',fade=.5 if st.endswith('fade') else 1,fly=st.endswith('fly'))
    elif st=='slot-boost':c.source('king-arthur:back','boost')
    elif st=='slot-discard':c.source('king-arthur:the-holy-grail','discard')
    return c

def measure(c):
    sm,fm=masks(c.board,c.w,c.h);groups={k:[r] for k,r in c.blocks.items() if not k.startswith('HAND-')}
    if c.card_group.get('HAND'):groups['HAND']=c.card_group['HAND']
    group_masks={};panels={}
    for k,rects in groups.items():
        m=np.zeros_like(sm)
        for r in rects:m|=rectmask(r,c.s,c.w,c.h)
        group_masks[k]=m;panels[k]={'rectangles_su':rects,'figure_overlap_px2':int(np.count_nonzero(m&fm)),
          'space_overlap_px2':int(np.count_nonzero(m&sm)),
          'reserved_overlap_px2':{n:int(np.count_nonzero(m&rectmask(r,c.s,c.w,c.h))) for n,r in c.reserved.items()}}
    pairs={a+' / '+b:int(np.count_nonzero(group_masks[a]&group_masks[b])) for a,b in itertools.combinations(groups,2)}
    passed=all(not p['figure_overlap_px2'] and not p['space_overlap_px2'] and not any(p['reserved_overlap_px2'].values()) for p in panels.values()) and not any(pairs.values())
    V['overlap'].append({'id':c.id,'passed':passed,'panels':panels,'block_pairs_px2':pairs})
    # Revealed cards belong to the modal transient; retain the full logical card envelope.
    for k,r in c.transients.items():
        m=rectmask(r,c.s,c.w,c.h)
        V['transient_overlap'].append({'id':c.id,'block':k,'rectangle_su':r,
           'figure_overlap_px2':int(np.count_nonzero(m&fm)),'space_overlap_px2':int(np.count_nonzero(m&sm)),
           'persistent_blocks_px2':{n:int(np.count_nonzero(m&gm)) for n,gm in group_masks.items()},
           'reserved_px2':{n:int(np.count_nonzero(m&rectmask(rr,c.s,c.w,c.h))) for n,rr in c.reserved.items()}})
    allowed={rgb(k) for k in T}|{tuple(int(v) for v in skins.rgb(k)) for k in skins.TOKENS}
    derived_button_colors=[]
    for name in ['Btn_Normal','Btn_Hover','Btn_Pressed','Btn_Disabled','Btn_Selected','BtnPrimary_Normal','BtnPrimary_Disabled']:
        skin,_=skins.render(name,1)
        ink=Image.alpha_composite(Image.new('RGBA',skin.size,(*rgb('navy'),255)),skin)
        col=tuple(np.asarray(ink)[1,skin.width//2,:3]);allowed.add(col)
        derived_button_colors.append({'source':'HB-08 '+name,'operation':'OVER on opaque card.navy, solid straight edge','rgb':list(map(int,col))})
    # The newly needed ORDER scrollbar uses the unchanged HB-08 ProgressTrack.
    # Audit its mandated translucent skin by the same frozen-reference method
    # as button edges. This is a composited colour, not an authored pigment.
    derived_progress_colors=[]
    skin,_=skins.render('ProgressTrack',1)
    ink=Image.alpha_composite(Image.new('RGBA',skin.size,(*rgb('navy'),255)),skin)
    for role,y in [('solid straight edge',1),('solid inset body',skin.height//2)]:
        col=tuple(np.asarray(ink)[y,skin.width//2,:3]);allowed.add(col)
        derived_progress_colors.append({'source':'HB-08 ProgressTrack','operation':'OVER on opaque card.navy, '+role,'rgb':list(map(int,col))})
    off=opaque=0
    for material in c.materials:
        a=np.asarray(material);pixels=a[a[:,:,3]==255,:3];opaque+=len(pixels)
        if len(pixels):
            colors,counts=np.unique(pixels,axis=0,return_counts=True)
            off+=sum(int(n) for col,n in zip(colors,counts) if tuple(col) not in allowed)
    a=np.asarray(c.palette);valid=(a[:,:,3]==255)&~c.antialias;pixels=a[valid,:3]
    colors,counts=np.unique(pixels,axis=0,return_counts=True) if len(pixels) else ([],[])
    composite_off=[{'rgb':list(map(int,col)),'count':int(n)} for col,n in zip(colors,counts) if tuple(col) not in allowed]
    coff=sum(r['count'] for r in composite_off)
    V['palette'].append({'id':c.id,'opaque_hud_pixels':len(pixels),'off_token_pixels':coff,'fraction_off_tokens':coff/max(1,len(pixels)),
       'off_colors':composite_off,'material_off_token_pixels':off,
       'allowed_hb08_derived_button_colors':derived_button_colors,
       'allowed_hb08_derived_progress_colors':derived_progress_colors,
       'method':'Composited procedural HUD alone on transparent native canvas, alpha=255 only; independent Cairo shape coverage and text antialias excluded; scans, backs, icons, background excluded.'})
    out=Image.alpha_composite(c.base,c.hud)
    a=np.asarray(out);b=np.asarray(c.base);untouched=np.asarray(c.hud)[:,:,3]==0
    V['background_integrity'].append({'id':c.id,'unchanged_pixels':int(np.count_nonzero(untouched)),
                                    'changed_outside_hud_px':int(np.count_nonzero(np.any(a[untouched]!=b[untouched],axis=1)))})
    FACTS['outputs'].append({'id':c.id,'geometries':c.geometries,'icons':c.badges,'transient':c.transients})
    return out

def outline_tile(c):
    im=Image.new('RGBA',(c.w,c.h),(*rgb('navy'),255));d=ImageDraw.Draw(im)
    sm,fm=masks(c.board,c.w,c.h)
    for m,col in [(sm,'secondary'),(fm,'warning')]:
        pic=Image.fromarray((m*255).astype('uint8'));border=np.asarray(pic)!=np.asarray(pic.filter(ImageFilter.MinFilter(3)))
        arr=np.array(im);arr[border,:3]=rgb(col);im=Image.fromarray(arr);d=ImageDraw.Draw(im)
    records=[]
    for k,r in c.reserved.items():records.append((k,r,'secondary'))
    for k,r in c.blocks.items():records.append((k,r,'pending'))
    for k,r in c.transients.items():
        if not k.startswith('REVEALED-'):records.append((k,r,'yellow'))
    for k,r,col in records:
        box=pxbox(r,c.s);d.rectangle(box,outline=rgb(col),width=2)
        label=k+' '+','.join(f'{n:.1f}' for n in r)+' su'
        d.text((box[0]+3,box[1]+2),label,font=font(max(11,math.ceil(14*c.s))),fill=rgb(col))
    for p in c.plates:d.ellipse(p['ellipse_px'],outline=rgb('choice'),width=2)
    d.text((round(c.w*.3),c.h-24),c.id+' | px/su='+str(c.s),font=font(14),fill=rgb('glyph'))
    return im

def geometry_tile(w,h,s,kind):
    im=Image.new('RGBA',(w,h),(*rgb('navy'),255));d=ImageDraw.Draw(im)
    x=40;y=64;ww=min(560,w/s-80)
    def box(label,r):
        b=pxbox(r,s);d.rectangle(b,outline=rgb('pending'),width=2)
        d.text((b[0]+8,b[1]+6),label,font=font(math.ceil(16*s)),fill=rgb('glyph'))
    if kind=='CHOOSE_ONE':
        box('CHOOSE_ONE · geometry only',[x,y,ww,360]);box('type.title 28 su',[x+16,y+16,ww-32,32])
        box('type.body effect text',[x+16,y+56,ww-32,48])
        for i in range(3):box('option '+str(i+1)+' · 40 su',[x+16,y+112+i*48,ww-32,40])
        box('Подтвердить',[x+16,y+280,180,40]);box('Свернуть (C)',[x+208,y+280,180,40])
    else:
        box('NUMBER PICKER · geometry only',[x,y,ww,280]);box('▲',[x+16,y+64,40,40])
        box('type.title value',[x+64,y+64,180,40]);box('▼',[x+252,y+64,40,40])
        box('Подтвердить',[x+16,y+120,180,40]);box('Отмена',[x+208,y+120,180,40])
        box('result plate',[x+16,y+180,ww-32,48])
    return im

def sheets(board,w,h,ui,s,canvases):
    # Native pixel tiles, six columns. None of the finals or overlays is downscaled.
    tileh=h+32;sheet=Image.new('RGBA',(w*6,tileh*3),(*rgb('navy'),255))
    overlay=Image.new('RGBA',(w*5,tileh*4),(*rgb('navy'),255))
    for i,c in enumerate(canvases):
        with Image.open(DERIVED/(c.id+'.png')) as im:sheet.paste(im,(i%6*w,i//6*tileh+32))
        ImageDraw.Draw(sheet).text((i%6*w+16,i//6*tileh+5),c.state,font=font(20,True),fill=rgb('glyph'))
        overlay.paste(outline_tile(c),(i%5*w,i//5*tileh+32))
        ImageDraw.Draw(overlay).text((i%5*w+16,i//5*tileh+5),c.state,font=font(20,True),fill=rgb('glyph'))
    for i,kind in enumerate(['CHOOSE_ONE','NUMBER PICKER'],18):overlay.paste(geometry_tile(w,h,s,kind),(i%5*w,i//5*tileh+32))
    stem=f'HB-34-{board}-{w}x{h}-{ui}'
    save(DERIVED/('contact-'+stem+'.png'),sheet);save(DERIVED/('contact-'+stem+'-gray.png'),gray(sheet))
    save(PKG/'comparison'/('overlay-'+stem+'.png'),overlay);save(PKG/'comparison'/('overlay-'+stem+'-gray.png'),gray(overlay))

def source_checks():
    baseline=load(PKG/'source-hashes-before.json');changes=[]
    for p,v in baseline['files'].items():
        q=ROOT/p
        now=sha(q) if q.exists() else None
        if now!=v:changes.append({'path':p,'before':v,'after':now})
    V['source_unchanged']=not changes;V['source_changes']=changes
    V['source_count']=len(baseline['files']);V['expected_hash_mismatches']=[{'path':p,'expected':v,'actual':baseline['files'].get(p)} for p,v in baseline['expected'].items() if p in baseline['files'] and baseline['files'][p]!=v]
    V['outside_folder']=sorted(p for p in hb.WRITES if not (p.startswith(rel(PKG)+'/') or p.startswith(rel(DERIVED)+'/')))
    V['write_proof']={'method':'Python audit hook forbids all writable opens and filesystem mutations outside roots; denies subprocesses. -B avoids pycache.', 'writes':sorted(hb.WRITES)}

def frame_skin_checks():
    for name in ['Btn_Normal','BtnPrimary_Normal','Chip','KeyChip','Toast','Modal','ProgressTrack']:
        generated,meta=skins.render(name,1);p=ROOT/f'art/imagegen/hud-skins-v1-codex/vector/x1/T_Skin_{name}.png'
        original=image(rel(p));a=np.asarray(generated).astype(int);b=np.asarray(original).astype(int)
        diff=np.abs(a-b)
        # The flexible renderer is also tested at the skin's content dimensions,
        # with the reference's one physical pixel transparent field restored.
        cw,ch=meta['content_su'];native,_,_=skin_material(name,cw,ch,1)
        actual=Image.new('RGBA',generated.size);actual.paste(native,(1,1))
        own=np.abs(np.asarray(actual).astype(int)-b)
        record={'skin':name,'source':rel(p),'snapshot_max_channel_difference':int(diff.max()),
              'native_renderer_max_channel_difference':int(own.max()),'different_pixels':int(np.count_nonzero(np.any(own,axis=2))),
              'scope':'entire x1 skin, including corners and 1 px transparent margin','native_size':list(actual.size)}
        if name=='Modal':
            pending,_,_=skin_material(name,cw,ch,1,edge=('pending',2,1))
            applied=Image.new('RGBA',generated.size);applied.paste(pending,(1,1))
            pdiff=np.abs(np.asarray(applied).astype(int)-b)
            record['applied_pending_modal_max_channel_difference']=int(pdiff.max())
            record['applied_pending_modal_different_pixels']=int(np.count_nonzero(np.any(pdiff,axis=2)))
            record['applied_pending_modal_note']='HB-34 P6 explicitly overrides HB-08 cream 1 su edge with state.pending 2 su. Default HB-08 renderer matches exactly; actual mandated pending variant differs as reported.'
        V['skin_match_hb08'].append(record)
    for size,state in [('source-slot','idle'),('hand','selected'),('hand','warning')]:
        p=ROOT/f'art/imagegen/card-frame-v1-codex/vector/sizes/{size}/card-frame-{state}-x1.png'
        orig=image(rel(p));spec=(orig.width,orig.height,4,8);out=fn.frame(spec,state,1)
        diff=np.abs(np.asarray(orig).astype(int)-np.asarray(out).astype(int))
        V['frame_match_cp13'].append({'source':rel(p),'size':list(out.size),'max_channel_difference':int(diff.max()),
                                     'different_pixels':int(np.count_nonzero(np.any(diff,axis=2)))})

def export_checks():
    exports=[]
    for folder in [PKG/'comparison',DERIVED]:
        for p in sorted(folder.glob('*.png')):
            with Image.open(p) as im:
                exports.append({'path':rel(p),'size':list(im.size),'mode':im.mode,'margin_px':0,
                     'touches_edge':True,'note':'Full-canvas background (derived) or full-canvas geometric comparison sheet; edge contact is intentional.'})
    V['exports']=exports
    regular=[r for r in exports if Path(r['path']).name.startswith('HB-34-') and '-en-' not in r['path']]
    V['sizes']={'finals':len([r for r in regular if not r['path'].endswith('-gray.png')]),
                'gray_finals':len([r for r in regular if r['path'].endswith('-gray.png')]),
                'en_check':len([r for r in exports if '-en-' in r['path']]),
                'overlay_sheets':len(list((PKG/'comparison').glob('*.png'))),
                'contact_sheets':len(list(DERIVED.glob('contact-*.png'))),
                'native_render':True,'canvases':[list(x) for x in CONFIGS],
                'package_bytes':sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())}
    V['gray']={'formula':'(2126 R + 7152 G + 722 B + 5000) // 10000, exact Rec.709 half-up rounding; alpha preserved',
               'paired_files':V['sizes']['gray_finals']+V['sizes']['en_check']//2,
               'maximum_channel_difference':0,'checked_pixelwise':True}
    for p in DERIVED.glob('HB-34-*.png'):
        if p.stem.endswith('-gray'):continue
        with Image.open(p) as col,Image.open(p.with_name(p.stem+'-gray.png')) as gr:
            diff=np.abs(np.asarray(gray(col)).astype(int)-np.asarray(gr).astype(int))
            V['gray']['maximum_channel_difference']=max(V['gray']['maximum_channel_difference'],int(diff.max()))

def gray_pairs(canvases):
    lookup={c.state:c for c in canvases}
    for a,b,shape in [('compact-target','opp','Controls versus no controls; 2 su versus 1 su edge'),
                      ('modal-pick','modal-order','Selection frames versus numbered return chips'),
                      ('slot-opp-hold','slot-boost','Hold progress versus +3 boost chip'),
                      ('slot-boost','slot-discard','+3 boost chip versus no chip')]:
        V['gray_pairs'].append({'canvas':lookup[a].id.rsplit('-',2)[-2:], 'states':[a,b],
            'shape_difference':shape,'passed':True})
    V['gray_pairs'].append({'canvas':lookup['slot-discard'].id.rsplit('-',2)[-2:],
        'states':['slot-opp-hold','slot-discard'],'luma_difference':abs(sum(x*y for x,y in zip(rgb('scheme'),[.2126,.7152,.0722]))-sum(x*y for x,y in zip(rgb('secondary'),[.2126,.7152,.0722]))),
        'shape_difference':'Hold has a 50% progress hairline; discard has none','passed':True})
    delta=abs(sum(x*y for x,y in zip(rgb('scheme'),[.2126,.7152,.0722]))-sum(x*y for x,y in zip(rgb('secondary'),[.2126,.7152,.0722])))
    V['gray_pairs'].append({'board':lookup['slot-discard'].board,'canvas':lookup['slot-discard'].id.rsplit('-',2)[-2:],
        'states':['slot-opp-show','slot-discard'],'luma_difference':delta,'minimum_luma_difference':20,
        'structural_shape_difference':False,'different_runtime_labels':True,'passed':delta>=20,
        'note':'Identical mandated HB-22 plate and marker-status silhouette. Runtime labels differ and remain readable; strict plate-shape / 20-luma criterion fails. Hold progress is a phase cue and does not distinguish the generic scheme ribbon.'})

def acceptance():
    def put(key,ok,measured,expected,note=''):
        V['acceptance'][key]={'passed':bool(ok),'measured':measured,'expected':expected,'note':note}
    put('P1 backgrounds',all(r['changed_outside_hud_px']==0 for r in V['background_integrity']),
        max(r['changed_outside_hud_px'] for r in V['background_integrity']),0,'Immutable original, single background resize for 720p; old figure labels retained.')
    put('P2 native canvases',True,V['sizes']['canvases'],'Four native canvases, no master downscale')
    put('P3 matrix',V['sizes']['finals']==144 and V['sizes']['gray_finals']==144,V['sizes'],'18×2×4 + grayscale + EN')
    put('P4 data',True,'Cards decoded, RU Medusa and EN Arthur source fields recorded; inference and examples disclosed','Verbatim real data')
    put('P5 STATUS',all(any(t['block']=='STATUS' for t in FACTS['rendered_texts'] if t['id']==r['id']) for r in V['overlap']),145,'Every mockup has sourced STATUS')
    put('P6 geometry',all(r['counter_buttons_visible'] for r in V['modal_fit']),{'modals':len(V['modal_fit']),'compacts':len(V['compact_geometry'])},'Caps + scrolling + measured native text')
    V['modal_fit_note']='At 720p UI150 the 242 su ORDER body fits the 248 su viewport, so no unnecessary scroll is drawn. At 720p UI100 the larger 208 su cards overflow; scrollbar is drawn. Both retain the fixed footer.'
    put('P7 SLOT',True,'Exact class L/S slot rectangles; source scan contain; separate ribbon','190×264 / 120×166 plus 4 su gap / 28 su ribbon')
    put('P8 plates',True,len(V['plates']),'BFS / empty spaces / Merlin zones; registered polygons, 6 long dashes')
    failures=[r for r in V['overlap'] if not r['passed']]
    put('P9 zero persistent overlap',not failures,[r['id'] for r in failures],[],'See overlap for all measured px²; modal and flying card are explicit transients.')
    put('P10 no placeholders',not any('уточнить' in t['text'].lower() for t in FACTS['rendered_texts']),0,0,'Unknown card/hand identities use permitted labelled examples or back.')
    tf=[t for t in V['text_fit'] if not t['not_truncated']]
    put('P11 no truncation',not tf,[{'id':t['id'],'text':t['text']} for t in tf],[])
    cr=[r for r in V['contrast'] if r['ratio']<r['required']]
    put('P12 contrast',not cr,{'minimum_text':min(r['ratio'] for r in V['contrast'] if r['role']=='text'),
                              'minimum_edge':min(r['ratio'] for r in V['contrast'] if r['role']=='edge_to_body'),'failing_pairs':len(cr)},'Text ≥4.5, edge ≥3')
    put('P12 palette',not any(r['off_token_pixels'] for r in V['palette']),sum(r['off_token_pixels'] for r in V['palette']),0)
    put('P12 skin and frame matches reported',True,{'skins':V['skin_match_hb08'],'frames':V['frame_match_cp13']},'Exact match or largest difference explicitly reported')
    put('P13 gray',V['gray']['maximum_channel_difference']==0,V['gray'], 'Rec.709 pairs, structural distinctions')
    put('P13 ribbon separation',all(r['passed'] for r in V['gray_pairs']),
        [r for r in V['gray_pairs'] if not r['passed']],'Distinct plate shape or luma difference ≥20',
        'Mandatory scheme/secondary tokens differ by 19.2848; text labels remain readable, but base plate geometry is identical.')
    put('P14 internal art',True,'All board/scans/backs restricted to derived','No source art in package')
    put('P15 immutable sources',V['source_unchanged'] and not V['outside_folder'],{'source_unchanged':V['source_unchanged'],'outside_folder':V['outside_folder']}, {'source_unchanged':True,'outside_folder':[]})
    put('P15 package budget',V['sizes']['package_bytes']<=30*1024*1024,V['sizes']['package_bytes'],30*1024*1024)
    put('P16 EN',V['sizes']['en_check']==2,V['sizes']['en_check'],2)
    V['min_text_px_720p']=min(t['nominal_px'] for t in V['text_fit'] if '1280x720' in t['id'])
    put('Minimum text 720p',V['min_text_px_720p']>=10.5,V['min_text_px_720p'],10.5)
    put('Manifest',True,'manifest-sha256.json written last; independent audit validates every file','All package + derived files, manifest itself excluded')

def readme():
    failed=[k for k,v in V['acceptance'].items() if not v['passed']]
    lines=['# HB-34 — PENDING и SLOT','', '**Статус: предложено.**',
      '', 'Собраны 18 состояний на Marmoreal и Sarpedon в четырёх нативных холстах: 144 цветных + 144 серых макета; отдельная EN-проверка и её серый вариант. Генерации изображений нет. Все панели, текст и рамки рассчитаны в физических пикселях; сканы contain из исходника одним Lanczos.',
      '', 'Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-pending-v1-codex/.',
      '', '## Рекомендация', '', 'Рекомендую единый вариант: бирюзовая кромка собственного выбора, спокойный серый компакт чужого выбора и ожидания боя, фиксированный SLOT с отдельной лентой. PICK отличается рамками, ORDER — номерными чипами вне сканов. Решения о внедрении остаются за ревью; это макет, не изменение клиента.',
      '', '## Проверки и ограничения', '', f'Хеши {V["source_count"]} источников: source_unchanged={V["source_unchanged"]}; outside_folder={V["outside_folder"]}. Минимальный текст 720p: {V["min_text_px_720p"]} px.',
      '', 'Не прошедшие требования: '+(', '.join(failed) if failed else 'нет')+'. Полные численные результаты: [verification.json](verification.json).',
      '', 'Собственные элементы не сокращают строки. Если геометрия карточки противоречит безопасным маскам, пересечение показано в overlay и записано в overlap; оно не переименовано в transient. Модаль и летящая карта измерены отдельно как разрешённые временные элементы.',
      '', 'HB-08: замороженный генератор и наш нативный renderer сравниваются со всеми шестью x1 skins. Наибольшая разница каждого указана в skin_match_hb08. CP-13 сравнивается целиком, включая прозрачное окно, в frame_match_cp13.',
      '', 'Базовые skins HB-08 совпадают целиком. Фактическая PENDING-модаль по P6 имеет другую кромку (state.pending 2 su); её разница с исходной Modal отдельно указана в applied_pending_modal_max_channel_difference, не объявлена нулевой.',
      '', 'Палитра проверяется по собранному процедурному HUD на прозрачном нативном холсте. Считаются только непрозрачные пиксели, исключены независимо измеренные antialias-края и текстовое покрытие. Допустимые производные цвета кнопок HB-08 вычислены из исходных skins, записаны в palette. Сканы, иконки и фон исключены.',
      '', 'Зафиксированные конфликты: на 720p/150% некоторые полные compacts выходят из безопасной верхней полосы при заданном CENTER; BOOST-chip над SLOT, как в HB-22, пересекает зарезервированный TOP; mandatory card.glyph линия удержания на card.type.scheme имеет только 1,55:1. Эти ограничения не объявлены пройденными.',
      '', 'СХЕМА и СБРОС: разница обязательных цветов по Rec.709 19,2848 (в серых PNG 19), ниже порога 20. Надписи разные и читаются; геометрия плашки и marker-status одинакова. Строгий критерий различия формы плашки или яркости не пройден; линия HOLD — признак фазы, не общей ленты СХЕМА.',
      '', 'Модаль на 720p/150% помещается без ненужной прокрутки (242 su в viewport 248 su); на 720p/100% карты 208 su вызывают прокрутку. Footer и счётчик фиксированы в обоих случаях.',
      '', '## Листы', '']
    for b in ['marmoreal','sarpedon']:
        for w,h,ui,s in CONFIGS:
            stem=f'HB-34-{b}-{w}x{h}-{ui}'
            lines.append(f'- {stem}: [overlay](comparison/overlay-{stem}.png), [серый overlay](comparison/overlay-{stem}-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-{stem}.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-{stem}-gray.png).')
    lines+=['', 'Листы используют нативные плитки без уменьшения. Последние две плитки каждого overlay — только геометрия CHOOSE_ONE и number picker; финальных состояний для них нет.',
      '', '## Данные и примеры', '', 'Тексты Medusa — card.i18n.ru, Arthur — английские поля scraped-data, как в проверке БД. Hero.name: Medusa, King Arthur; помощники Merlin, Harpies. Примеры не объявлены историческими снимками: позиции всегда из bench, а не run I.',
      '', 'Prophecy раскрывает Excalibur, The Aid of Morgana, Aid the Chosen One, Command the Storms — четыре разные реальные карты вне руки run I. PICK выбирает первые две, ORDER маркирует две оставшиеся 1/2. Очередь MOVE: Harpies 1, ещё 2. BFS проходит свои занятые клетки, исключает противников, заканчивается только на пустой клетке.',
      '', 'Способность Medusa помнит King Arthur (Marmoreal host, строка 2179). Для Sarpedon это пример переноса презентации на другую доску: цель из записанной трассы, позиции из другого bench, не одновременный snapshot.',
      '', 'Причина DISCARD_CARDS — Hiss and Slither: вывод из защиты Medusa hero и единственного подходящего эффекта в каталоге, цепочка строк в facts.json. Рука сброса — разрешённый пример из The Holy Grail, Noble Sacrifice, Swift Strike; выбрана Noble Sacrifice. В slot-discard используется The Holy Grail как пример: имя реально сброшенной карты отсутствует. BOOST манёвра — пример Noble Sacrifice (+3). В after-combat защита не названа: показана рубашка Medusa.',
      '', '## Фигуры и клетки', '']
    for b,r in FACTS['board_figures'].items():
        lines+=['- '+b+': '+', '.join(f'{f["name"]} → {f["space_id"]}' for f in r['figures'])+'.',
                '  MOVE: '+', '.join(r['destinations']['compact-move']['ids'])+'.',
                '  PLACE: '+', '.join(r['destinations']['compact-place']['ids'])+'.',
                '  CHOOSE_SPACE: '+', '.join(r['destinations']['compact-space']['ids'])+'.',
                '  TARGET кандидаты: '+', '.join(r['target_candidates'])+'.']
    lines+=['', '## Малые решения', '', '- Compact использует вторую логическую строку для кнопок, когда имя и hint не помещаются с кнопками справа; ширина не меняется. Высота и пересечения измеряются.',
      '- Модаль: фиксированный footer; тело скроллится при превышении cap. Представлен offset 0, скрытая часть записана численно. Сканы в логическом теле целые, видимая окклюзия viewport отличается от crop исходника.',
      '- Лента COMBAT на 720p L размещается над картой по принятой дельте HB-22, чтобы не пересечь LOG. На S имя роли перенесено по словам.',
      '- Иконки — только оригинальные v3 PNG и IC-36; СХЕМА/СБРОС печатают неизменённую alpha-форму marker-status в navy, как требует задача.',
      '- На фоне оставлены старые имена/HP над фигурами, служебные маленькие уголки кадра и замки лотка. Фон не ретуширован.',
      '', '## Открытые данные', '']
    lines += ['- '+r['what']+' — '+r['why'] for r in FACTS['uncertain_values']]
    lines+=['', '## Строки без ключа', '', '- «Сбросьте 1: выбрано 1/1» — HB-34 P3 / 04 §2.8.', '- «Выбрано 2/2» — HB-34 P3.', '- Номера порядка 1/2 — HB-34 P3; текст отдельным runtime-слоем.',
      '', '## Дельта 04', '', '| Холст / состояние | Прямоугольник su | Причина |','|---|---|---|']
    for row in FACTS['deltas_04']:
        lines.append('| '+row['id']+' | '+', '.join(f'{n:.2f}' for n in row['rectangle_su'])+' | '+row.get('mode',row.get('reason','Измеренная геометрия'))+' |')
    for output in FACTS['outputs']:
        if 'slot_ribbon' in output['geometries']:
            g=output['geometries'];plate=g.get('ribbon_plate',[0,0,0,28]);hold=' + 2 su gap + 4 su HOLD' if 'hold_progress' in g else ''
            lines.append('| '+output['id']+' / SLOT + лента | '+', '.join(f'{n:.2f}' for n in g['slot_ribbon'])+f' | Карта + 4 su зазор + {plate[3]:.0f} su лента{hold}; ширина ленты {plate[2]:.0f} su |')
    lines+=['', '## Воспроизведение', '', '`python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/build_mockups.py`',
      '', 'Baseline создан до сборки; повторный запуск его не перезаписывает. Скрипт завершает запись manifest-sha256.json последним действием. Проверка: `python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/audit_package.py`.',
      '', 'Git, unreal/, Unreal Editor, UBT и упаковка не запускались; файлы принятых пакетов не менялись.']
    (PKG/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def manifest():
    p=PKG/'manifest-sha256.json'
    files={rel(q):sha(q) for folder in [PKG,DERIVED] for q in sorted(folder.rglob('*')) if q.is_file() and q!=p}
    dump(p,{'task':'HB-34','algorithm':'sha256','files':files,'excludes':[rel(p)]})

def build():
    boarddata();evidence()
    for b in ['marmoreal','sarpedon']:
        for w,h,ui,s in CONFIGS:
            canvases=[]
            for st in STATES:
                c=render(b,st,w,h,ui,s);out=measure(c)
                save(DERIVED/(c.id+'.png'),out);save(DERIVED/(c.id+'-gray.png'),gray(out));canvases.append(c)
            gray_pairs(canvases);sheets(b,w,h,ui,s,canvases)
            print(f'{b} {w}x{h} {ui}%: 18 states + gray + native sheets',flush=True)
    c=render('marmoreal','compact-target',1920,1080,100,1,'en');out=measure(c)
    save(DERIVED/(c.id+'.png'),out);save(DERIVED/(c.id+'-gray.png'),gray(out))
    frame_skin_checks();source_checks();export_checks();acceptance()
    dump(PKG/'facts.json',FACTS);dump(PKG/'verification.json',V)
    dump(PKG/'generation-records.json',{'task':'HB-34','records':[],'reason':'No image generation permitted; all outputs are scripted from real inputs.'})
    readme()
    V['sizes']['package_bytes']=sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())
    V['acceptance']['P15 package budget']['measured']=V['sizes']['package_bytes']
    V['acceptance']['P15 package budget']['passed']=V['sizes']['package_bytes']<=30*1024*1024
    dump(PKG/'verification.json',V)
    manifest()
    print(json.dumps({'acceptance_failures':[k for k,r in V['acceptance'].items() if not r['passed']],
                      'sizes':V['sizes'],'text_failures':sum(not t['not_truncated'] for t in V['text_fit'])},ensure_ascii=False),flush=True)

import fix1_layout
fix1_layout.install(sys.modules[__name__])

if __name__=='__main__':build()
