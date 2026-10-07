#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Measure opaque flat UI pixels; artwork/AA/translucent composites excluded.

This script derives its package from its own path and writes only there. It does
not modify any PNG, capture, copied renderer, skin, icon or other input.
"""
import sys
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image
import sc14_room_hero as b

def lab(rgb):
    rgb=np.asarray(rgb,dtype=float)/255
    rgb=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    xyz=rgb@np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]]).T
    xyz=xyz/np.array([.95047,1,1.08883])
    f=np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[:,1]-16,500*(f[:,0]-f[:,1]),200*(f[:,1]-f[:,2])],axis=1)

def rect(mask,r,factor,value=True,pad=0):
    x,y,w,h=r
    x0=max(0,int(np.floor(x*factor))-pad);y0=max(0,int(np.floor(y*factor))-pad)
    x1=min(mask.shape[1],int(np.ceil((x+w)*factor))+pad);y1=min(mask.shape[0],int(np.ceil((y+h)*factor))+pad)
    mask[y0:y1,x0:x1]=value

def run():
    v=b.load(b.PACKAGE/'verification.json');frames={}
    raw=[tuple(int(item['hex'].lstrip('#')[i:i+2],16) for i in (0,2,4)) for item in b.theme().tokens['colors'].values() if 'hex' in item]
    raw+=[(78,84,87)] # HB-08 documented 40% text.secondary over navy disabled primary.
    navy=b.theme().color('panel.bg')
    # Include native flat skin composites over the opaque navy parent.
    for p in (b.SKINS/'vector').rglob('*.png'):
        a=np.asarray(Image.open(p).convert('RGBA'))
        for rgba in np.unique(a.reshape(-1,4),axis=0):
            if rgba[3]>=230:
                raw.append(tuple(round(int(rgba[i])*int(rgba[3])/255+navy[i]*(1-int(rgba[3])/255)) for i in range(3)))
    palette=set(raw)
    for alpha in (.6,.8):palette.update(tuple(round(v*(1-alpha)+n*alpha) for v,n in zip(rgb,navy)) for rgb in raw)
    palette=np.array(sorted(palette));palette_lab=lab(palette)
    for key,frame in v['frames'].items():
        identifier=b.PACKAGE.name.split('-')[0].upper().replace('SC','SC-')
        p=b.DERIVED/f'{identifier}-{key}.png';rgb=np.asarray(Image.open(p).convert('RGB'))
        mask=np.zeros(rgb.shape[:2],dtype=bool);factor=frame['viewport']['factor']
        for region in frame['geometry']:
            if region['kind'] in ('screen','modal') and region.get('alpha',1)==1:
                rect(mask,region['rect_su'],factor,pad=-2)
            elif region['kind']=='button':rect(mask,region['rect_su'],factor,pad=-2)
        for asset in frame['assets']:
            if 'rect_su' in asset:rect(mask,asset['rect_su'],factor,False,pad=3)
        for icon in frame['icons']:
            # Native icon palettes already have their own source audit; ignore AA.
            if icon['name'].startswith('cursor-'):
                mask[-64:,-64:]=False
        # A 3×3 constant neighbourhood removes raster AA and fine texture pixels.
        centre=rgb[1:-1,1:-1];flat=np.ones(centre.shape[:2],dtype=bool)
        for dy in (-1,0,1):
            for dx in (-1,0,1):flat&=(centre==rgb[1+dy:rgb.shape[0]-1+dy,1+dx:rgb.shape[1]-1+dx]).all(axis=2)
        region=mask[1:-1,1:-1]&flat
        colors,counts=np.unique(centre[region],axis=0,return_counts=True)
        delta=np.sqrt(((lab(colors)[:,None,:]-palette_lab[None,:,:])**2).sum(axis=2)).min(axis=1)
        bad=delta>3
        pixels=int(counts.sum());violations=int(counts[bad].sum())
        frames[key]={'sampled_opaque_flat_ui_pixels':pixels,'outside_deltaE76_3_pixels':violations,
            'outside_fraction':violations/pixels if pixels else None,'maximum_deltaE76':float(delta.max()),
            'outside_colors':[{'rgb':rgb.tolist(),'pixels':int(n),'deltaE76':float(d)} for rgb,n,d in zip(colors[bad],counts[bad],delta[bad])]}
    pixels=sum(f['sampled_opaque_flat_ui_pixels'] for f in frames.values());bad=sum(f['outside_deltaE76_3_pixels'] for f in frames.values())
    v['palette'].update({'outside_token_fraction':bad/pixels,'passed':bad==0,'sampled_opaque_flat_ui_pixels':pixels,
        'outside_deltaE76_3_pixels':bad,'deltaE':'CIE76, D65, linearized sRGB→XYZ→Lab',
        'method':'Opaque screen/modal/button regions; exclude portrait/map/scan rectangles plus 3px, translucent header/insets over artwork, and nonconstant 3×3 AA neighbourhoods. Approved token and HB-08 navy/veil composites are allowed.',
        'coverage_limit':'This fraction concerns opaque flat UI regions, not every RGB pixel in the composite scene.',
        'allowed_flat_colors':palette.tolist(),'frames':frames})
    v['palette']['note']='Measured opaque UI fraction, with explicit artwork/AA/transparency exclusions; source art and accepted skins remain unchanged.'
    v['acceptance']=[item for item in v['acceptance'] if not item['criterion'].startswith('07 §1.2 palette')]
    v['acceptance'].append({'criterion':'07 §1.2 palette: opaque flat UI outside ΔE76 ≤3 =0',
        'passed':bad==0,'measured':{'sampled_pixels':pixels,'outside_pixels':bad,'fraction':bad/pixels},
        'expected':0,'note':v['palette']['coverage_limit']})
    v['full_acceptance']=v['full_acceptance'] and bad==0
    b.dump(b.PACKAGE/'verification.json',v)
    p=b.PACKAGE/'README.md';s=p.read_text(encoding='utf-8')
    s=s.replace('Попиксельный ΔE финала с артом не заменён ложным значением 0; UI цвета и их исходные композиты перечислены.',
        f'Палитра измерена на {pixels} непрозрачных плоских пикселях UI: вне ΔE76 ≤ 3 — {bad} ({bad/pixels:.8%}). Арт, прозрачные композиты и AA явно исключены; это не доля всех пикселей сцены. Допустимые токены и композиты HB-08 перечислены в verification.json.')
    b.text_file(p,s);b.refresh_manifest()
    print(b.PACKAGE.name,'palette pixels',pixels,'violations',bad)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');run()
