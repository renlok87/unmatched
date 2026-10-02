"""Validate spec.json against rig contract and material library.

Run: python tools/scratch-model/check_spec.py art/imagegen/scratch-v1/merlin/spec.json
Input: scratch spec, repository rig-contract.json, material-library/README.md.
Output: spec-check.json beside spec; exit 0 only if all numeric checks pass.
"""
import argparse
import re
from pathlib import Path
import numpy as np
from common import read, report, check, rgb, lab, BACKGROUND, GRID

def validate(s, root):
    c={}
    required='schema asset_id key ue_key kind status height_cm height_tolerance_rel base heads landmarks_z_cm widths_cm joints_cm joint_parents joint_tails_cm weapon pose silhouette_features palette triangle_target texture_px'.split()
    missing=sorted(set(required)-set(s))
    c['schema_fields']=check(not missing and s.get('schema')=='unmatched.scratch-spec/1',missing,required)
    if missing: return c
    z=s['landmarks_z_cm']
    names='base_top sole ankle knee crotch waist chest shoulder chin eye head_top'.split()
    values=[z.get(n,-1) for n in names]
    # The contract's own example has sole == base_top; they are one physical plane.
    ordered=values[0]==values[1] and all(a<b for a,b in zip(values[1:],values[2:]))
    c['landmarks_order']=check(ordered,dict(zip(names,values)),'base_top == sole; all subsequent mandatory landmarks strictly increase','Coincident sole/base_top follows §2 example; no other equal levels allowed.')
    c['height']=check(z['head_top']==s['height_cm'],z['head_top'],s['height_cm'])
    c['base_top']=check(z['base_top']==s['base']['height_cm'],z['base_top'],s['base']['height_cm'])
    ratio=(s['height_cm']-z['base_top'])/(s['heads']['count']*s['heads']['head_height_cm'])
    c['head_proportion']=check(abs(ratio-1)<=.05,ratio,'1 ± 0.05')
    rig=read(root/'docs/art-pipeline/rig/rig-contract.json')['skeletons']['UM_HUMANOID_17_v2']
    bones={b['name']:b['parent'] for b in rig['bones'] if not b.get('optional') or b['name']==s['weapon']['bone']}
    c['rig_names_parents']=check(set(bones)==set(s['joints_cm']) and bones==s['joint_parents'],s['joint_parents'],bones)
    c['joint_coordinates']=check(all(len(p)==3 and all(isinstance(v,(float,int)) and np.isfinite(v) for v in p) for p in s['joints_cm'].values()),s['joints_cm'],'finite xyz centimetres')
    side_bad=[n for n,p in s['joints_cm'].items() if (n.endswith('.L') and p[0]<=0) or (n.endswith('.R') and p[0]>=0)]
    c['joint_sides']=check(not side_bad,side_bad,'.L > 0; .R < 0')
    out=[]
    for name,p in s['joints_cm'].items():
        if name=='root' or name.startswith('weapon.'): continue
        for axis,idx in [('front',0),('side',1)]:
            widths=s['widths_cm'][axis]; levels=sorted((z[k],v) for k,v in widths.items())
            width=float(np.interp(p[2],[v[0] for v in levels],[v[1] for v in levels]))
            if abs(p[idx])>width/2: out.append(dict(bone=name,axis=axis,coordinate=p[idx],half_width=width/2))
    c['joints_inside_body']=check(not out,out,'each nonweapon joint inside both interpolated body widths')
    leaves=set(bones)-set(bones.values())
    c['leaf_tails']=check(leaves<=set(s['joint_tails_cm']),sorted(s['joint_tails_cm']),sorted(leaves))
    weapon=s['weapon']; side=rig['characters'][s['key']]['weapon_bone']
    c['weapon_grip']=check(weapon['bone']==side and s['joints_cm'][side]==weapon['grip_cm'] and s['joints_cm']['hand.'+side[-1]]==weapon['grip_cm'],weapon['grip_cm'],dict(bone=side,grip=s['joints_cm'][side]))
    total=sum(float(np.linalg.norm(np.array(a)-b)) for a,b in zip(weapon['centerline_cm'],weapon['centerline_cm'][1:]))
    c['weapon_length']=check(abs(total-weapon['length_cm'])<=.01,total,weapon['length_cm'])
    text=(root/'docs/art-pipeline/material-library/README.md').read_text(encoding='utf-8')
    classes=set(re.findall(r'^\| \d+\*? \| `([^`]+)`',text,re.M))|{'legacy_bake'}
    dye={'leather_smooth','leather_worn','wool_coarse','linen','silk','feathers'}
    errors=[]; distances={}
    for p in s['palette']:
        if p['class'] not in classes or (p['team_accent'] and p['class'] not in dye): errors.append(p['zone'])
        if p['class']=='legacy_bake' and (not all(k in p and 0<=p[k]<=1 for k in ('roughness','metallic'))): errors.append(p['zone'])
        l=lab(rgb(p['hex']))
        distances[p['zone']]=[float(np.linalg.norm(l-lab(rgb(col)))) for col in (BACKGROUND,GRID)]
    c['palette_classes_team']=check(not errors,errors,'library classes; team dye allowed; explicit legacy roughness/metallic')
    c['palette_background_distance']=check(all(min(d)>=20 for d in distances.values()),distances,'ΔE76 >=20 from background AND grid')
    c['asset_budget']=check(s['kind']=='sidekick' and s['height_cm']==45 and s['base']['diameter_cm']==24 and 5<=s['base']['height_cm']<=6 and 5<=s['heads']['count']<=5.5,s['height_cm'],'Merlin pilot: 45 cm, Ø24 cm, base 5–6 cm, 5–5.5 heads')
    return c

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('spec',type=Path); p.add_argument('--output',type=Path)
    a=p.parse_args(); root=Path(__file__).resolve().parents[2]
    r=report(a.output or a.spec.with_name('spec-check.json'),validate(read(a.spec),root))
    print('checks_passed:',r['checks_passed']); raise SystemExit(0 if r['checks_passed'] else 1)

if __name__=='__main__': main()
