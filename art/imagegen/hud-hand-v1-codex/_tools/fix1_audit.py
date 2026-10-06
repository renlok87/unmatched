"""Read-only corrective-rule checks, independent of the layout search/drawing code."""
import math
from pathlib import Path
from PIL import ImageFont


def box(rect, scale):
    x,y,w,h=rect
    x0,y0=round(x*scale),round(y*scale)
    return [x0,y0,max(round((x+w)*scale),x0+round(w*scale)),
            max(round((y+h)*scale),y0+round(h*scale))]


def intersection(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))


def close(a,b):
    return len(a)==len(b) and all(abs(x-y)<1e-8 for x,y in zip(a,b))


def check(facts,verification,before):
    originals={r['id']:r for r in before['outputs']}
    overlaps={r['id']:r for r in verification['overlap']['per_mockup']}
    transients={r['id']:r['elements'] for r in verification['transient_overlap']}
    fonts=Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
    boost=[];caption=[];tooltip=[];reserve=[]
    for output in facts['outputs']:
        name=output['id'];state=output['state'];g=output['geometry'];old=originals[name]
        w,h,ui=overlaps[name]['canvas'];scale=(1 if w==1920 else .75)*ui/100
        panels=overlaps[name]['panels']
        if state=='lowered':
            reserve.append({'id':name,'passed':'HAND-CAPTION' not in panels and 'caption_plate' not in g})
        else:
            text=next(t for t in facts['rendered_texts'] if t['mockup']==name and t['block']=='HAND-CAPTION')
            width=ImageFont.truetype(str(fonts/'Roboto-Regular.ttf'),math.ceil(14*scale)).getlength(text['text'])/scale+24+2/scale
            expected=[g['cards'][0][0],g['caption'][1],width,22]
            plate=panels['HAND-CAPTION']['drawn_plate_rectangle_su']
            row={'id':name,'state':state,'before_rectangle_su':old['caption_drawn_rectangle_su'],
                 'after_rectangle_su':plate,'expected_rectangle_su':expected,
                 'before_selected_index':old['selected_card_index'],'after_selected_index':g.get('selected_card_index'),
                 'before_selected_lift_su':old['selected_lift_su'],'after_selected_lift_su':g.get('selected_lift_su'),
                 'passed':close(plate,expected) and text['not_truncated']}
            if state=='selected':
                selected=next(r for r in output['scans'] if r['state']=='selected')
                row['selected_caption_overlap_px2']=intersection(box(selected['rectangle_su'],scale),box(plate,scale))
                row['passed'] &= g['selected_card_index']==1 and selected['key']=='medusa:gaze-of-stone' and row['selected_caption_overlap_px2']==0
            caption.append(row)
            r=panels['HAND-CAPTION']['reserved_row']
            reserve.append({'id':name,'rectangle_su':r['rectangle_su'],
                'passed':close(r['rectangle_su'],old['caption_reserved_rectangle_su']) and
                    r['figure_overlap_px2']==r['space_overlap_px2']==0 and not any(r['reserved_overlap_px2'].values())})
        if state=='boost-attack':
            small=g['class']=='S';attack=[16,240,150,208] if small else [24,360,230,319]
            expected=[attack[0]+(32 if small else 40),attack[1],attack[2],attack[3]]
            chip=[expected[0]+expected[2]-32,expected[1]-36,32,32]
            back=next(r for r in output['scans'] if r['key']=='king-arthur:back')
            ribbon=panels['ATTACK-RIBBON']['rectangles_su'][0]
            expected_ribbon=[attack[0],attack[1]+attack[3]+4,attack[2],44 if small else 28]
            if not small and w==1280:expected_ribbon[1]=328
            b=box(expected,scale)
            intentional=overlaps[name]['intentional_occlusion_px2']
            row={'id':name,'before_rectangle_su':old['boost_card_rectangle_su'],
                'after_rectangle_su':g['attack_boost'],'before_chip_su':old['boost_chip_rectangle_su'],
                'after_chip_su':g['boost_chip'],'visible_strip_su':32 if small else 40,
                'chip_ribbon_overlap_px2':intersection(box(chip,scale),box(ribbon,scale)),
                'intentional_occlusion_px2':intentional,'protected_and_other_blocks_zero':overlaps[name]['persistent_zero']}
            row['passed']=close(g['attack_boost'],expected) and close(g['combat'],attack) and close(g['boost_chip'],chip) and close(ribbon,expected_ribbon) and \
                close(back['rectangle_su'],expected) and back['scan_crop_px']==0 and back['resizes_from_source']==1 and back['state']=='idle' and \
                g['attack_z_order']==['ATTACK-BOOST','COMBAT-L','ATTACK-RIBBON','BOOST-CHIP'] and \
                0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h and row['chip_ribbon_overlap_px2']==0 and \
                len(intentional)==1 and next(iter(intentional.values()))==intersection(box(attack,scale),b) and row['protected_and_other_blocks_zero']
            boost.append(row)
        if state=='unplayable':
            tip=g['tooltip_rectangle_su'];plate=g['caption_plate']
            tipbox=box(tip,scale)
            captiontext=next(t for t in facts['rendered_texts'] if t['mockup']==name and t['block']=='HAND-CAPTION')
            hit=intersection(tipbox,box(plate,scale))
            texthit=sum(intersection(tipbox,b) for b in captiontext['bbox_px'])
            left_clear=tip[0]>=plate[0]+plate[2]+8-1e-8
            above_clear=tip[1]+tip[3]<=plate[1]
            unchanged=close(tip,old['tooltip_rectangle_su'])
            row={'id':name,'before_rectangle_su':old['tooltip_rectangle_su'],'after_rectangle_su':tip,
                'before_caption_overlap_px2':intersection(box(old['tooltip_rectangle_su'],scale),box(old['caption_drawn_rectangle_su'],scale)),
                'caption_overlap_px2':hit,'caption_text_overlap_px2':texthit,
                'right_gap_su':tip[0]-plate[0]-plate[2],
                'transient_recorded':transients[name]['WHY']['persistent_blocks_overlap_px2']['HAND-CAPTION']==hit,
                'passed':hit==texthit==0 and (unchanged or left_clear or above_clear)}
            row['passed'] &= row['transient_recorded']
            tooltip.append(row)
    checks={}
    for key,rows,total,expected in [
        ('fix1_boost_rule',boost,8,'8 exact COMBAT-sized backs behind attack; shift40/32 su, chip gap4 su/right edge; 0 protected/ribbon collisions'),
        ('fix1_caption_rule',caption,89,'89 drawn captions (including EN), text width+24su+2px, height22su, first-card x/rest-row y; selected index1/readable'),
        ('fix1_tooltip_clear',tooltip,8,'8 WHY panels: 0 px² with caption plate and text, all transient intersections reported'),
        ('fix1_caption_reserve',reserve,97,'97 original full caption reservations unchanged/clear; lowered hides the plate')]:
        checks[key]={'passed':len(rows)==total and all(r['passed'] for r in rows),
            'measured':{'checked':len(rows),'failures':[r for r in rows if not r['passed']]},'expected':expected}
    return {'task':'HB-22 fix1','before_file':'art/imagegen/hud-hand-v1-codex/fix1-before.json',
            'boost':boost,'caption':caption,'tooltip':tooltip,'caption_reserve':reserve,'checks':checks}
